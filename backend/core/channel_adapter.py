"""
channel_adapter.py — Multi-Channel Request Normalization & Execution Gateway.
Implements FR-8, FR-9, FR-10 from prd-general-agent.md & Bab 4/12 from rancangan-general-agent.md.

Normalizes requests from Telegram, CLI, WhatsApp, Web, and Scheduler into a uniform
internal request format, routing through Unified Plan Detector and Permission Gate.
"""
import asyncio
import contextvars
from datetime import datetime
import json
import logging
import os
import re
import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from pydantic import BaseModel, Field

from memory import memory_engine, file_memory
from core.context_compactor import ContextCompactor
# NOTE: classify_approval_intent is imported lazily at line ~636 when needed
# needs_plan and is_explicit_plan_approval were removed (dead imports — never called in this file)
from core.prompt_assembler import PromptAssembler
from core.skill_library import skill_library
from core.security import check_prompt_injection
from core.session_manager import session_state_manager, PendingAction
from providers import call_universal_chat_model, get_active_model_id
from integrations.dedup import MessageDeduplicator

logger = logging.getLogger(__name__)

_channel_message_dedup = MessageDeduplicator(max_size=500, ttl_seconds=4.0)

# Active channel execution context (channel, channel_id, user_id, sender_name)
_ACTIVE_CHANNEL_CONTEXT: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "_ACTIVE_CHANNEL_CONTEXT", default=None
)

def get_active_channel_context() -> Optional[Dict[str, Any]]:
    return _ACTIVE_CHANNEL_CONTEXT.get()

# Active pending plans memory store: plan_id -> plan_metadata
_PENDING_PLANS: Dict[str, Dict[str, Any]] = {}


def _format_tool_progress_message(evt: Dict[str, Any]) -> str:
    """Formats an informative, user-friendly live status message for tool execution via dynamic introspection."""
    t_name = evt.get("tool_name", "")
    status = evt.get("status", "running")
    detail = evt.get("detail", "")
    summary = evt.get("summary", "")
    step = evt.get("step")

    step_str = f" [Step {step}]" if step else ""

    if t_name == "agent" and status == "thinking":
        return f"⚙️ Reasoning & planning steps...{step_str}"

    clean_name = t_name.replace("_", " ").title() if t_name else "Action"
    prefix = f"⚡ {clean_name}" if "terminal" in t_name or "command" in t_name or "cli" in t_name else f"⚙️ {clean_name}"

    if detail:
        clean_detail = str(detail).replace("\\", "/")
        if "/" in clean_detail:
            clean_detail = clean_detail.split("/")[-1]
        return f"{prefix}: {clean_detail[:40]}...{step_str}"

    if summary:
        return f"{prefix}: {str(summary)[:45]}...{step_str}"

    return f"{prefix}: {status}...{step_str}"


PLATFORM_MESSAGE_LIMITS = {
    "discord": 1950,
    "telegram": 2000,
    "whatsapp": 3500,
    "slack": 3500,
    "cli": 32000,
    "web_studio": 64000,
    "web": 64000,
}


def split_message_chunks(
    text: str,
    max_chars: Optional[int] = None,
    add_part_headers: bool = True,
    platform: Optional[str] = None
) -> List[str]:
    """
    Omnichannel fence-aware message chunker (Hermes Parity).
    Splits long messages along paragraph and newline boundaries without breaking markdown code blocks.
    Balances code fences across chunk boundaries so syntax highlighting never breaks.
    """
    if not text:
        return []

    limit = max_chars
    if limit is None:
        p_norm = (platform or "telegram").strip().lower()
        limit = PLATFORM_MESSAGE_LIMITS.get(p_norm, 2200)

    if len(text) <= limit:
        return [text]

    raw_chunks: List[str] = []
    current_text = text
    effective_limit = limit - 40 if add_part_headers else limit

    while len(current_text) > effective_limit:
        candidate = current_text[:effective_limit]
        code_fence_count = candidate.count("```")
        ends_inside_code = (code_fence_count % 2 == 1)

        split_idx = -1
        p_idx = candidate.rfind("\n\n")
        if p_idx > effective_limit // 3:
            split_idx = p_idx + 2
        else:
            l_idx = candidate.rfind("\n")
            if l_idx > effective_limit // 3:
                split_idx = l_idx + 1
            else:
                s_idx = candidate.rfind(" ")
                if s_idx > effective_limit // 3:
                    split_idx = s_idx + 1
                else:
                    split_idx = effective_limit

        chunk_part = current_text[:split_idx]
        current_text = current_text[split_idx:]

        if ends_inside_code:
            m_lang = re.search(r"```([a-zA-Z0-9_-]*)\n", chunk_part)
            last_lang = m_lang.group(1) if m_lang else ""
            chunk_part = chunk_part + "\n```"
            current_text = f"```{last_lang}\n" + current_text

        raw_chunks.append(chunk_part)

    if current_text:
        raw_chunks.append(current_text)

    total_parts = len(raw_chunks)
    if total_parts <= 1 or not add_part_headers:
        return raw_chunks

    final_chunks: List[str] = []
    is_discord = (platform == "discord")
    for idx, chunk in enumerate(raw_chunks, start=1):
        if is_discord:
            header = f"📄 **[Part {idx}/{total_parts}]**\n\n"
        else:
            header = f"📄 <b>[Part {idx}/{total_parts}]</b>\n\n"
        final_chunks.append(header + chunk)

    return final_chunks


class BaseChannelPresenter(ABC):
    """Abstract presenter interface for channel-specific UI and action decoupling."""
    @abstractmethod
    def render_approval(self, narration: str, action: PendingAction) -> Dict[str, Any]:
        """Renders platform-specific approval payload with decoupled UI elements."""
        pass

class UniversalChannelAdapter:
    """
    Unified channel adapter facade delegating to central PlatformRegistry (Hermes Parity).
    Single Source of Truth: All platforms, media dispatchers, and presenters live in integrations/platform_registry.py.
    """

    @classmethod
    def register(cls, channel: str, presenter: Any):
        """Backward-compatible registration hook delegating to central registry."""
        pass

    @classmethod
    def get_presenter(cls, channel: str) -> Any:
        from integrations.platform_registry import platform_registry
        return platform_registry.get_or_default(channel)

    @classmethod
    def render_approval_payload(cls, channel: str, narration: str, action: Any) -> Dict[str, Any]:
        from integrations.platform_registry import platform_registry
        return platform_registry.render_approval_payload(channel, narration, action)

    @classmethod
    def render_message_payload(cls, channel: str, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from integrations.platform_registry import platform_registry
        return platform_registry.render_message_payload(channel, narration, metadata=metadata)

    @classmethod
    def render_notice_payload(cls, channel: str, notice_type: str, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from integrations.platform_registry import platform_registry
        return platform_registry.render_notice_payload(channel, notice_type, narration, metadata=metadata)

    @classmethod
    def render_voice_payload(cls, narration: str, action: Optional[Any] = None) -> Dict[str, Any]:
        from integrations.platform_registry import platform_registry
        adapter = platform_registry.get_or_default("voice")
        if action:
            return adapter.render_approval(narration, action)
        return adapter.render_message(narration)


async def synthesize_action_rationale(tool_name: str, tool_args: Dict[str, Any], prompt: str = "") -> str:
    """
    Pure Model-Driven Rationale Synthesis (Hermes Parity).
    Queries the fast auxiliary model (e.g. gemini-3.1-flash / < 400ms) to formulate a natural,
    contextual 1-sentence conversational explanation of WHY this tool is being invoked for this prompt.
    Eliminates hardcoded if-else dictionaries and regexes.
    """
    from providers import call_universal_chat_model
    from core.capabilities import get_fast_auxiliary_model
    from core.prompt_loader import load_prompt

    args_summary = ", ".join(f"{k}={v}" for k, v in list(tool_args.items())[:3])
    sys_instruction = load_prompt("channel/action_rationale")
    user_p = (
        f"User request context: \"{prompt or 'Fulfill user task'}\"\n"
        f"Tool action being invoked: '{tool_name}' ({args_summary})\n"
        "Brief conversational rationale (1 friendly sentence):"
    )

    try:
        model_id = get_fast_auxiliary_model()
        res = await asyncio.wait_for(
            call_universal_chat_model(
                model_id=model_id,
                user_prompt=user_p,
                system_instruction=sys_instruction,
                max_tokens=None,
                temperature=0.3,
                read_only=True,
            ),
            timeout=3.5
        )
        if isinstance(res, str) and res.strip():
            clean = res.strip().strip('"\'`')
            # Anti-leak gate on synthesized output
            if "{" not in clean and "<" not in clean and len(clean) > 8:
                return clean
    except Exception as e:
        logger.debug(f"[RationaleSynthesis] Fast LLM pass notice: {e}")

    # Fallback to dynamic parameter-grounded rationale if LLM is unreachable offline
    return generate_dynamic_action_rationale(tool_name, tool_args, prompt)


def generate_dynamic_action_rationale(tool_name: str, tool_args: Dict[str, Any], prompt: str = "") -> str:
    """
    Factual parameter-grounded action summary (Hermes build_tool_preview parity).
    Clean, direct, and zero robotic canned templates.
    """
    t_clean = (tool_name or "tool").strip().lower()
    canonical = t_clean.replace("_", " ")

    # Dynamic target parameter discovery
    target_info = (
        tool_args.get("command")
        or tool_args.get("file_path")
        or tool_args.get("path")
        or tool_args.get("target")
        or tool_args.get("title")
        or tool_args.get("query")
        or tool_args.get("source_dir")
        or tool_args.get("task")
        or ""
    )
    clean_target = str(target_info).strip()

    # For CLI commands: format clean one-liner target
    if t_clean in ("execute_cli_command", "terminal", "run_terminal_command"):
        if "\n" in clean_target:
            clean_target = clean_target.splitlines()[0].strip()
        clean_target = clean_target.strip("`;| ")
        if clean_target:
            return f"Run: {clean_target[:100]}"
        clean_p = (prompt or "").strip()
        if clean_p:
            return f"Run terminal command: {clean_p[:80]}"
        return "Run terminal command"

    # For file, media, search, and other tools: clean parameter preview
    if clean_target:
        if "/" in clean_target or "\\" in clean_target:
            clean_display = clean_target.replace("\\", "/").split("/")[-1]
        else:
            clean_display = clean_target
        return f"{canonical.capitalize()}: {clean_display[:80]}"

    clean_p = (prompt or "").strip()
    return f"{canonical.capitalize()}: {clean_p[:80]}" if clean_p else canonical.capitalize()


async def synthesize_channel_notice(
    notice_type: str,
    channel: str = "telegram",
    task_description: str = "",
    error_detail: str = "",
    user_id: str = "",
) -> str:
    """
    Pure Model-Driven Channel Notice Synthesizer (Hermes Parity).
    Generates contextual, platform-tailored, zero-canned conversational notices
    (e.g., expiry, rejection, authorization denial, cancellation, or runtime failure)
    using the fast auxiliary model with graceful dynamic fallbacks.
    """
    from providers import call_universal_chat_model
    from core.capabilities import get_fast_auxiliary_model
    from core.prompt_loader import load_prompt

    sys_inst = load_prompt("channel/channel_notice")
    user_prompt = (
        f"Channel: {channel}\n"
        f"Status: {notice_type}\n"
        f"Task context: {task_description or 'System task'}\n"
        f"Additional detail: {error_detail or 'None'}\n"
        "Brief friendly notice (1 sentence):"
    )
    try:
        model_id = get_fast_auxiliary_model()
        res = await asyncio.wait_for(
            call_universal_chat_model(
                model_id=model_id,
                user_prompt=user_prompt,
                system_instruction=sys_inst,
                max_tokens=None,
                temperature=0.3,
                read_only=True,
            ),
            timeout=3.0
        )
        if isinstance(res, str) and res.strip():
            clean = res.strip().strip('"\'`')
            if "{" not in clean and "<tool" not in clean and len(clean) > 5:
                return clean
    except Exception as e:
        logger.debug(f"[ChannelNotice] Auxiliary synthesis notice: {e}")

    # Universal fallbacks formatted dynamically based on situation (Hermes Parity)
    task_info = f" '{task_description}'" if task_description else ""
    err_info = f": {error_detail}" if error_detail else ""
    if notice_type == "expired":
        return f"Action plan{task_info} expired."
    elif notice_type == "rejected":
        return f"Action{task_info} was cancelled."
    elif notice_type == "unauthorized":
        return f"Authorization required for action{task_info}."
    elif notice_type == "stopped":
        return f"Execution{task_info} has been stopped."
    elif notice_type == "error":
        return f"Execution failed{task_info}{err_info}."
    return f"Status: {notice_type}{task_info}."


class ChannelRequest(BaseModel):
    """Uniform internal request representation across all input channels (FR-9)."""
    text: str
    channel: str = "web"  # 'telegram', 'cli', 'whatsapp', 'web', 'scheduler'
    channel_id: str = "default"  # Chat ID or Terminal ID
    user_id: str = "default_user"
    sender_name: Optional[str] = "User"
    trigger_type: str = "interactive"  # 'interactive' or 'autonomous'
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChannelResponse(BaseModel):
    """Uniform response returned back to the originating channel (FR-10)."""
    text: str
    session_id: int
    mode: str = "conversational"
    plan_pending: bool = False
    plan_id: Optional[str] = None
    plan_steps: List[str] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "success"
    error: Optional[str] = None
    reply_markup: Optional[Dict[str, Any]] = None
    pending_action: Optional[Dict[str, Any]] = None
    rendered_payload: Optional[Dict[str, Any]] = None
    is_command: bool = False


def get_or_create_channel_session(req: ChannelRequest) -> int:
    """Binds an incoming channel request to an isolated persistent chat session."""
    speaker = req.sender_name or "User"
    clean_title = f"{req.channel.title()} Chat ({speaker})"

    # Find existing open session for this specific channel & channel_id
    sessions = memory_engine.get_sessions(speaker_name=speaker, session_type="chat", limit=50)
    for s in sessions:
        if s.get("channel") == req.channel and not s.get("is_archived"):
            return s["id"]

    # If none found, create a new one
    new_sess = memory_engine.create_session(
        speaker_name=speaker,
        title=clean_title,
        session_type="chat",
        channel=req.channel,
        session_mode="conversational"
    )
    return new_sess["id"]




async def _auto_dispatch_artifacts_to_channel(channel: str, channel_id: str, artifacts: List[Dict[str, Any]]):
    """Auto-dispatches generated documents and media directly to target channel via ChannelManager (Hermes Parity)."""
    if not artifacts or not channel_id or channel_id.startswith("default"):
        return
    from integrations.manager import channel_manager
    for art in artifacts:
        f_path = art.get("path")
        f_name = art.get("filename") or (os.path.basename(f_path) if f_path else "")
        if not f_path or not os.path.isfile(f_path):
            continue
        try:
            logger.info(f"[AutoDispatch] Dispatching media '{f_name}' to {channel} {channel_id}")
            ext = os.path.splitext(f_name)[1].lower()
            if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
                media_type = "photo"
                caption = f"📸 Bukti Tangkapan Layar: {f_name}" if "screen" in f_name.lower() or "verify" in f_name.lower() else f"📸 {f_name}"
            elif ext in (".mp4", ".mov", ".avi", ".mkv"):
                media_type = "video"
                caption = f"🎬 {f_name}"
            elif ext in (".mp3", ".m4a", ".wav"):
                media_type = "audio"
                caption = f"🎵 {f_name}"
            elif ext in (".ogg", ".opus"):
                media_type = "voice"
                caption = ""
            else:
                media_type = "document"
                caption = f"📄 File: {f_name}"

            await channel_manager.send_media(
                channel=channel,
                target_id=channel_id,
                file_path=f_path,
                caption=caption,
                media_type=media_type
            )
        except Exception as e:
            logger.error(f"[AutoDispatch] Failed to dispatch '{f_name}' to {channel}: {e}")

async def process_channel_request(
    req: ChannelRequest,
    progress_callback: Optional[Callable[[str], Any]] = None
) -> ChannelResponse:
    """
    Main omnichannel ingress pipeline: Normalizes, validates, and dispatches.
    Enforces Plan/Build safety gate and routes back to channel.
    """
    logger.info(f"[ChannelGateway] Incoming request from {req.channel} (user={req.user_id}): {req.text[:50]!r}")
    from tools.artifact_tools import clear_turn_artifacts
    clear_turn_artifacts()

    token_ctx = _ACTIVE_CHANNEL_CONTEXT.set({
        "channel": req.channel,
        "channel_id": req.channel_id,
        "user_id": req.user_id,
        "sender_name": req.sender_name
    })
    current_task = asyncio.current_task()
    is_stop_req = req.text.strip().lower().startswith(("/stop", "/cancel", "/abort"))
    if current_task and not is_stop_req:
        session_state_manager.register_active_task(req.channel, req.channel_id, current_task)

    try:
        return await _process_channel_request_core(req, progress_callback)
    finally:
        if current_task and not is_stop_req:
            session_state_manager.unregister_active_task(req.channel, req.channel_id, current_task)
        _ACTIVE_CHANNEL_CONTEXT.reset(token_ctx)


async def _enrich_message_with_vision(user_text: str, attachments: List[Dict[str, Any]]) -> str:
    """
    Universal Inbound Vision Enrichment (Hermes Parity: gateway/run_inbound.py lines 1866-1909).
    Auto-analyzes user-attached images with vision_analyze and prepends descriptions to prompt context.
    Works dynamically for ALL platforms (Telegram, WhatsApp, Discord, Slack, Web Studio, CLI).
    """
    if not attachments:
        return user_text

    image_paths = []
    for att in attachments:
        t = str(att.get("type", "")).lower()
        p = att.get("local_path") or att.get("path")
        if p and os.path.isfile(p):
            ext = os.path.splitext(p)[1].lower()
            if t in ("photo", "image") or ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"):
                image_paths.append(p)

    if not image_paths:
        return user_text

    from tools.vision_tools import _tool_vision_analyze
    from core.prompt_loader import load_prompt
    analysis_prompt = load_prompt("channel/vision_enrichment").strip()
    enriched_parts = []
    for img_path in image_paths:
        try:
            logger.info(f"[InboundVision] Auto-analyzing user attached image: {img_path}")
            res = await _tool_vision_analyze(image_path=img_path, question=analysis_prompt)
            if res.get("status") == "success" and res.get("analysis"):
                desc = res["analysis"].strip()
                note = (
                    f"[ATTACHED IMAGE ANALYSIS — {os.path.basename(img_path)}]:\n"
                    f"{desc}\n"
                    f"[If further visual detail is required, invoke 'vision_analyze' with image_path: '{img_path}']"
                )
            else:
                note = f"[Attached Image: '{os.path.basename(img_path)}' saved at '{img_path}'. Use 'vision_analyze' to inspect.]"
        except Exception as e:
            logger.error(f"[InboundVision] Error analyzing image {img_path}: {e}")
            note = f"[Attached Image: '{os.path.basename(img_path)}' saved at '{img_path}'. Use 'vision_analyze' to inspect.]"
        enriched_parts.append(note)

    if not enriched_parts:
        return user_text

    prefix = "\n\n".join(enriched_parts)
    return f"{prefix}\n\n{user_text}" if user_text else prefix


async def _process_channel_request_core(
    req: ChannelRequest,
    progress_callback: Optional[Callable[[str], Any]] = None
) -> ChannelResponse:
    # 1. Resolve Session
    session_id = get_or_create_channel_session(req)
    from core.agent import anara_agent
    anara_agent.set_active_session_id(session_id)
    from tools.artifact_tools import clear_turn_artifacts, get_turn_artifacts
    clear_turn_artifacts()

    # 2. Content Moderation & Prompt Injection Defense (FR-20)
    clean_text = req.text.strip()

    # Deduplication protection (Hermes Parity: gateway/run_inbound.py)
    msg_key = f"{req.channel}:{req.channel_id}:{clean_text}"
    if clean_text and _channel_message_dedup.is_duplicate(msg_key):
        logger.info(f"[ChannelGateway] Dropping duplicate message on {req.channel}: '{clean_text[:40]}'")
        return ChannelResponse(
            text="",
            session_id=session_id,
            mode="conversational",
            status="duplicate_dropped"
        )

    # 2b. Inbound Vision Auto-Enrichment (Hermes Parity)
    if req.attachments:
        clean_text = await _enrich_message_with_vision(clean_text, req.attachments)

    is_safe, denial_reason = check_prompt_injection(clean_text)
    if not is_safe:
        denial_msg = denial_reason or "Request denied by Anara security filter."
        return ChannelResponse(
            text=denial_msg,
            session_id=session_id,
            mode="conversational",
            status="blocked",
            error=denial_msg
        )

    # 3. Check for Unified System Commands (/help, /status, /model, /skills, /memory, /workspace, /clear, /stop, /plan)
    from core.command_hub import handle_channel_command
    cmd_response = await handle_channel_command(req)
    if cmd_response:
        cmd_response.session_id = session_id
        if cmd_response.text:
            memory_engine.log_conversation(
                user_text=req.text,
                ai_text=cmd_response.text,
                speaker_name=req.sender_name,
                session_id=session_id
            )
        return cmd_response

    # 4. First-Run Onboarding Guard (Hermes Multi-User Parity):
    # If the user or fresh installer has not yet configured ANY provider or key,
    # guide them with clean universal onboarding instructions.
    from providers import has_any_active_provider
    if not has_any_active_provider():
        logger.warning("[ChannelGateway] No active AI model provider configured. Triggering First-Run Onboarding Guide.")
        sender = req.sender_name or "User"
        from core.prompt_loader import load_prompt
        onboarding_msg = load_prompt("channel/onboarding", sender=sender)

        memory_engine.log_conversation(
            user_text=req.text,
            ai_text=onboarding_msg,
            speaker_name=req.sender_name,
            session_id=session_id
        )
        return ChannelResponse(
            text=onboarding_msg,
            session_id=session_id,
            mode="conversational",
            status="onboarding"
        )

    # 5. Check for Plan Approval (Semantic Intent Classifier + Session State Machine - Subsystem 3)
    session_plan_key = f"{req.channel}_{req.channel_id}"
    intent_state = session_state_manager.evaluate_intent(clean_text, req.channel, req.channel_id)
    active_pending = intent_state["pending"]

    from core.session_manager import ActionState
    from core.plan_detector import classify_approval_intent

    plan_id = None
    orig_prompt = ""
    pending_tool = None
    plan_dict = {}
    plan_ctx = ""
    had_expired_action = False

    if active_pending:
        plan_id = active_pending.plan_id if isinstance(active_pending, PendingAction) else active_pending.get("plan_id")
        orig_prompt = active_pending.original_prompt if isinstance(active_pending, PendingAction) else active_pending.get("original_prompt")
        pending_tool = active_pending.pending_tool_call if isinstance(active_pending, PendingAction) else active_pending.get("pending_tool_call")
        plan_dict = active_pending.to_dict() if isinstance(active_pending, PendingAction) else active_pending
        plan_ctx = active_pending.plan_text if isinstance(active_pending, PendingAction) else active_pending.get("plan_text", "")

        # Check if expired (> 300s TTL)
        is_expired = active_pending.is_expired if isinstance(active_pending, PendingAction) else False
        if is_expired:
            session_state_manager.resolve_action(req.channel, req.channel_id, plan_id, ActionState.EXPIRED)
            _PENDING_PLANS.pop(session_plan_key, None)
            active_pending = None
            had_expired_action = True

    recently_expired_act = session_state_manager.pop_recently_expired(req.channel, req.channel_id)
    if (had_expired_action or recently_expired_act):
        semantic_intent = await classify_approval_intent(clean_text, "expired action")
        if semantic_intent == "approve":
            expired_notice = await synthesize_channel_notice("expired", channel=req.channel)
            memory_engine.log_conversation(
                user_text=clean_text,
                ai_text=expired_notice,
                speaker_name=req.sender_name,
                session_id=session_id
            )
            return ChannelResponse(
                text=expired_notice,
                session_id=session_id,
                mode="conversational",
                status="expired_notice",
            )

    if active_pending:
        semantic_intent = await classify_approval_intent(clean_text, plan_ctx)

        # ── CASE A1: User explicitly rejects / cancels the pending action ──
        if semantic_intent == "reject":
            logger.info(f"[ChannelGateway] User rejected pending action #{plan_id} via '{clean_text}'. Cancelling...")
            session_state_manager.resolve_action(req.channel, req.channel_id, plan_id, ActionState.REJECTED)
            _PENDING_PLANS.pop(session_plan_key, None)

            cancel_reply = await synthesize_channel_notice(
                notice_type="rejected",
                channel=req.channel,
                task_description=orig_prompt or plan_ctx[:80],
                user_id=req.user_id,
            )

            memory_engine.log_conversation(
                user_text=clean_text,
                ai_text=cancel_reply,
                speaker_name=req.sender_name,
                session_id=session_id
            )
            return ChannelResponse(
                text=cancel_reply,
                session_id=session_id,
                mode="conversational",
                status="cancelled",
            )

        # ── CASE A2: User explicitly confirms / approves the pending action ──
        elif semantic_intent == "approve":
            logger.info(f"[ChannelGateway] User approved pending action #{plan_id} via '{clean_text}'. Executing BUILD MODE...")
            session_state_manager.resolve_action(req.channel, req.channel_id, plan_id, ActionState.EXECUTING)
            _PENDING_PLANS.pop(session_plan_key, None)

            try:
                build_res = await _execute_build_mode(
                    session_id=session_id,
                    user_prompt=orig_prompt,
                    req=req,
                    progress_callback=progress_callback,
                    pending_tool_call=pending_tool,
                    plan=plan_dict,
                )
                session_state_manager.resolve_action(req.channel, req.channel_id, plan_id, ActionState.EXECUTED)
                return build_res
            finally:
                session_state_manager.clear_pending(req.channel, req.channel_id)
                _PENDING_PLANS.pop(session_plan_key, None)

        # ── CASE A3: Topic Shift (User asked an unrelated question while action was pending) ──
        elif semantic_intent == "other":
            logger.info(f"[ChannelGateway] Topic shift detected while action #{plan_id} pending. Auto-expiring previous action...")
            session_state_manager.resolve_action(req.channel, req.channel_id, plan_id, ActionState.EXPIRED)
            _PENDING_PLANS.pop(session_plan_key, None)
            active_pending = None

    # 5. Check session mode (Hermes Model-Driven Parity: 0 regex guessing on user text)
    # In conversational mode, user turns execute directly with runtime tool interception.
    # Plan proposal gate is triggered only when the session is explicitly configured for Plan Mode.
    session_obj = memory_engine.get_session(session_id)
    actual_session_mode = (session_obj.get("session_mode") or "conversational") if session_obj else "conversational"
    requires_plan = (actual_session_mode in ("explicit_plan_build", "plan"))

    # ── CASE B: Request entails high-risk/mutating action -> Auto PLAN MODE ──
    if requires_plan:
        logger.info(f"[ChannelGateway] Request triggers Plan Gate -> Composing structured plan...")
        plan_id = str(uuid.uuid4())[:8]

        from core.prompt_loader import load_prompt
        plan_prompt = load_prompt("channel/plan_gate", clean_text=clean_text)

        sys_prompt = PromptAssembler.assemble(
            mode="plan",
            speaker_name=req.sender_name,
            is_chat_mode=True,
            session_type="chat"
        )

        plan_text = await call_universal_chat_model(
            model_id=get_active_model_id(),
            user_prompt=plan_prompt,
            system_instruction=sys_prompt,
            max_tokens=None,
            temperature=0.4,
            read_only=True
        )

        # Store pending action in State Machine
        pending_act = PendingAction(
            plan_id=plan_id,
            session_id=session_id,
            channel=req.channel,
            channel_id=req.channel_id,
            tool_name="plan_proposal",
            original_prompt=clean_text,
            plan_text=plan_text or "",
            lead_narration=plan_text or "",
            risk_level="mutating",
            status="pending",
            user_id=req.user_id,
        )
        session_state_manager.store_pending(pending_act)
        _PENDING_PLANS[session_plan_key] = pending_act.to_dict()

        # Fallback narration formulation matching Hermes Parity
        narration_text = plan_text
        if not narration_text:
            try:
                from core.capabilities import get_fast_auxiliary_model
                from core.prompt_loader import load_prompt
                aux_model = get_fast_auxiliary_model()
                narration_sys = load_prompt("channel/fallback_narration").strip()
                narration_text = await asyncio.wait_for(
                    call_universal_chat_model(
                        model_id=aux_model,
                        user_prompt=f"Formulate a brief 1-sentence action plan proposal for user request: \"{clean_text}\". Respond in the exact language of the request.",
                        system_instruction=narration_sys,
                        max_tokens=None,
                        temperature=0.3,
                        read_only=True
                    ),
                    timeout=2.5
                )
            except Exception:
                pass
        if not narration_text:
            narration_text = f"Action plan prepared for '{clean_text}'. Please confirm to begin execution."

        # Log AI Plan Proposal (natural narrative only, zero UI tags or buttons)
        memory_engine.log_conversation(
            user_text=clean_text,
            ai_text=narration_text,
            speaker_name=req.sender_name,
            session_id=session_id
        )

        rendered = UniversalChannelAdapter.render_approval_payload(
            channel=req.channel,
            narration=narration_text,
            action=pending_act
        )

        return ChannelResponse(
            text=rendered.get("text") or narration_text,
            session_id=session_id,
            mode="plan",
            plan_pending=True,
            plan_id=plan_id,
            status="pending_approval",
            reply_markup=rendered.get("reply_markup"),
            pending_action=pending_act.to_dict(),
            rendered_payload=rendered,
        )

    # ── CASE C: Direct Execution with Dynamic Runtime Tool Interception Gate ──
    from core.context_compactor import ContextCompactor
    from core.agent import anara_agent
    all_history = memory_engine.get_recent_conversations(
        limit=25,
        speaker_name=req.sender_name,
        session_id=session_id
    )
    prior_turns = []
    for h in all_history:
        ai_t = (h.get("ai_text") or "").strip()
        # Hermes parity: close interrupted/unclosed tool sequence in past transcript to prevent continuation hallucination
        is_tool_invocation = '"action": "tool_call"' in ai_t or '<tool_call>' in ai_t
        is_unclosed = ('<tool_call>' in ai_t and '</tool_call>' not in ai_t) or (
            '"action": "tool_call"' in ai_t and not ai_t.rstrip().endswith(('}', '```', '</tool_call>'))
        )
        if is_tool_invocation and is_unclosed:
            h_clean = dict(h)
            h_clean["ai_text"] = f"Previous inspection sequence concluded for '{clean_text}'."
            prior_turns.append(h_clean)
        else:
            prior_turns.append(h)
    dialogue_context = ContextCompactor.compact_history(prior_turns, verbatim_turns=5)
    full_user_prompt = f"{dialogue_context}User: {clean_text}" if dialogue_context else clean_text

    ws_tree = anara_agent.get_workspace_tree(session_id=session_id)
    sys_prompt = PromptAssembler.assemble(
        mode="build",
        speaker_name=req.sender_name,
        workspace_tree=ws_tree,
        is_chat_mode=True,
        session_type="chat",
        user_task=clean_text,
        channel=req.channel,
        session_id=session_id,
    )

    # Autonomous Turn Nudge (Anara Standard: turn % 10 -> memory, turn % 15 -> skill)
    from memory.memory_nudge import memory_nudge_manager
    nudge_instruction = memory_nudge_manager.increment_and_get_nudge(session_id)
    if nudge_instruction:
        sys_prompt += f"\n\n{nudge_instruction}"

    tools_used: List[str] = []

    def _track_tool(evt: Dict[str, Any]):
        t_name = evt.get("tool_name")
        if t_name and t_name not in tools_used:
            tools_used.append(t_name)
        if progress_callback:
            msg = _format_tool_progress_message(evt)
            try:
                if asyncio.iscoroutinefunction(progress_callback):
                    asyncio.create_task(progress_callback(msg))
                else:
                    progress_callback(msg)
            except Exception:
                pass
        try:
            from telemetry.event_bus import telemetry_bus, EventType, ActivityProvenance
            asyncio.create_task(
                telemetry_bus.emit(
                    event_type=EventType.TOOL_PROGRESS,
                    provenance=ActivityProvenance.TOOL_RUNNER,
                    session_id=str(session_id),
                    trace_id=f"tr_{session_id}",
                    payload={"tool_name": t_name, "status": evt.get("status") or "running"},
                )
            )
        except Exception:
            pass

    reply = None
    for attempt in range(2):
        reply = await call_universal_chat_model(
            model_id=get_active_model_id(),
            user_prompt=full_user_prompt,
            system_instruction=sys_prompt,
            max_tokens=None,
            temperature=0.7,
            read_only=False,
            progress_cb=_track_tool,
            intercept_mutating_tools=requires_plan,
            platform=req.channel,
        )
        if isinstance(reply, dict) and reply.get("intercepted"):
            break
        if isinstance(reply, str) and reply.strip():
            break
        if attempt == 0:
            logger.warning("[ChannelAdapter] Model returned empty output on turn attempt 1 — retrying...")
            await asyncio.sleep(0.4)

    # ── TOOL INTERCEPTION GATE (Zero-Regex Security & Zero Canned Text) ──
    # If the model attempted to invoke a mutating or ask tool without prior user approval,
    # intercept the execution in real-time, generate the dynamic rationale, and request user approval.
    if isinstance(reply, dict) and reply.get("intercepted"):
        plan_id = str(uuid.uuid4())[:8]
        tool_name = reply.get("tool_name", "system command")
        cmd_preview = reply.get("cmd_preview", "")
        lead_text = (reply.get("lead_text") or "").strip()
        raw_call = reply.get("raw_call")
        danger_reason = reply.get("danger_reason")

        # Model-Driven Contextual Rationale (Zero Canned Templates)
        lead_narration = lead_text
        # Discard stale lead_text if it is an echo of a prior conversation turn
        if lead_narration and prior_turns:
            is_stale_echo = any(
                len(h.get("ai_text", "")) > 15 and (
                    lead_narration.lower() in h.get("ai_text", "").lower()
                    or h.get("ai_text", "").lower() in lead_narration.lower()
                )
                for h in prior_turns
            )
            if is_stale_echo:
                logger.info(f"[ChannelAdapter] Discarded stale lead_text echoing past turn: {lead_narration[:60]!r}")
                lead_narration = ""

        if not lead_narration:
            lead_narration = await synthesize_action_rationale(
                tool_name=tool_name,
                tool_args=raw_call.get("arguments", {}) if raw_call else {},
                prompt=clean_text
            )

        # Store pending action in State Machine
        pending_act = PendingAction(
            plan_id=plan_id,
            session_id=session_id,
            channel=req.channel,
            channel_id=req.channel_id,
            tool_name=tool_name,
            tool_args=raw_call.get("arguments", {}) if raw_call else {},
            original_prompt=clean_text,
            pending_tool_call=raw_call,
            plan_text=lead_narration,
            lead_narration=lead_narration,
            risk_level=danger_reason or "mutating",
            status="pending",
            user_id=req.user_id,
        )
        session_state_manager.store_pending(pending_act)
        _PENDING_PLANS[session_plan_key] = pending_act.to_dict()

        # Pure conversational narration saved to memory — ZERO UI tags, ZERO canned templates
        memory_engine.log_conversation(
            user_text=clean_text,
            ai_text=lead_narration,
            speaker_name=req.sender_name,
            session_id=session_id
        )

        rendered = UniversalChannelAdapter.render_approval_payload(
            channel=req.channel,
            narration=lead_narration,
            action=pending_act
        )

        return ChannelResponse(
            text=rendered.get("text") or lead_narration,
            session_id=session_id,
            mode="plan",
            plan_pending=True,
            plan_id=plan_id,
            status="pending_approval",
            reply_markup=rendered.get("reply_markup"),
            pending_action=pending_act.to_dict(),
            rendered_payload=rendered,
        )

    if isinstance(reply, str) and reply.strip():
        # ── ANTI-LEAK GATE (Hermes Parity) ──
        # Ensure raw tool-call JSON blocks are NEVER presented as chat text to user
        from providers.caller import _clean_model_chat_text, _format_empty_model_notice
        if '"action": "tool_call"' in reply or '<tool_call>' in reply or not _clean_model_chat_text(reply):
            from providers.caller import _extract_and_parse_tool_call
            leaked_payload, lead, _ = _extract_and_parse_tool_call(reply)
            if leaked_payload:
                logger.info(f"[ChannelAdapter] Anti-leak caught unexecuted tool call '{leaked_payload.get('tool')}'. Auto-dispatching...")
                return await _execute_build_mode(
                    session_id=session_id,
                    user_prompt=clean_text,
                    req=req,
                    progress_callback=progress_callback,
                    pending_tool_call=leaked_payload,
                )
            else:
                cleaned = _clean_model_chat_text(reply)
                if not cleaned or '"action": "tool_call"' in cleaned or '<tool_call>' in cleaned:
                    try:
                        from core.capabilities import get_fast_auxiliary_model
                        cleaned_raw = await call_universal_chat_model(
                            model_id=get_fast_auxiliary_model(),
                            user_prompt=f"Provide a clear, direct, and complete response to: \"{clean_text}\" matching the user's active language.",
                            max_tokens=None,
                            temperature=0.3,
                            read_only=True
                        )
                        cleaned = _clean_model_chat_text(cleaned_raw or "")
                    except Exception:
                        cleaned = ""
                final_reply = (cleaned or _format_empty_model_notice(clean_text)).strip()
        else:
            final_reply = _clean_model_chat_text(reply) or reply.strip()
    else:
        # Dynamic model fallback instead of static canned apology
        try:
            from core.capabilities import get_fast_auxiliary_model
            final_reply = await call_universal_chat_model(
                model_id=get_fast_auxiliary_model(),
                user_prompt=clean_text,
                max_tokens=None,
                temperature=0.4,
                read_only=True
            )
        except Exception:
            final_reply = ""
        if not final_reply or not final_reply.strip():
            final_reply = _format_empty_model_notice(clean_text)

    memory_engine.log_conversation(
        user_text=clean_text,
        ai_text=final_reply,
        speaker_name=req.sender_name,
        session_id=session_id
    )

    turn_artifacts = get_turn_artifacts()
    if turn_artifacts and req.channel in ("telegram", "whatsapp"):
        await _auto_dispatch_artifacts_to_channel(req.channel, req.channel_id, turn_artifacts)

    return ChannelResponse(
        text=final_reply,
        session_id=session_id,
        mode="conversational",
        plan_pending=False,
        tools_used=tools_used,
        attachments=turn_artifacts,
        status="success"
    )


async def _execute_build_mode(
    session_id: int,
    user_prompt: str,
    req: ChannelRequest,
    progress_callback: Optional[Callable[[str], Any]] = None,
    pending_tool_call: Optional[Dict[str, Any]] = None,
    plan: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> ChannelResponse:
    """Executes the approved plan in Build Mode with system-reminder mode injection."""
    current_task = asyncio.current_task()
    if current_task:
        session_state_manager.register_active_task(req.channel, req.channel_id, current_task)
    token_ctx = _ACTIVE_CHANNEL_CONTEXT.set({
        "channel": req.channel,
        "channel_id": req.channel_id,
        "user_id": req.user_id,
        "sender_name": req.sender_name
    })

    try:
        return await _execute_build_mode_core(
            session_id=session_id,
            user_prompt=user_prompt,
            req=req,
            progress_callback=progress_callback,
            pending_tool_call=pending_tool_call,
            plan=plan,
            **kwargs
        )
    finally:
        if current_task:
            session_state_manager.unregister_active_task(req.channel, req.channel_id, current_task)
        _ACTIVE_CHANNEL_CONTEXT.reset(token_ctx)


async def _execute_build_mode_core(
    session_id: int,
    user_prompt: str,
    req: ChannelRequest,
    progress_callback: Optional[Callable[[str], Any]] = None,
    pending_tool_call: Optional[Dict[str, Any]] = None,
    plan: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> ChannelResponse:
    from core.agent import anara_agent
    anara_agent.set_active_session_id(session_id)
    from tools.artifact_tools import clear_turn_artifacts, get_turn_artifacts
    clear_turn_artifacts()

    if not pending_tool_call and plan:
        pending_tool_call = plan.get("pending_tool_call")

    resolved_task = str((plan or {}).get("original_prompt") or user_prompt)

    if progress_callback:
        try:
            msg = f"🔨 {resolved_task[:60]}..."
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback(msg)
            else:
                progress_callback(msg)
        except Exception:
            pass

    ws_tree = anara_agent.get_workspace_tree(session_id=session_id)
    sys_prompt = PromptAssembler.assemble(
        mode="build",
        speaker_name=req.sender_name,
        workspace_tree=ws_tree,
        is_chat_mode=True,
        session_type="chat",
        user_task=resolved_task,
        channel=req.channel,
        session_id=session_id,
    )

    tools_used: List[str] = []

    def _track_tool(evt: Dict[str, Any]):
        t_name = evt.get("tool_name")
        if t_name and t_name not in tools_used:
            tools_used.append(t_name)
        if progress_callback:
            msg = _format_tool_progress_message(evt)
            try:
                if asyncio.iscoroutinefunction(progress_callback):
                    asyncio.create_task(progress_callback(msg))
                else:
                    progress_callback(msg)
            except Exception:
                pass

    all_history = memory_engine.get_recent_conversations(
        limit=25,
        speaker_name=req.sender_name,
        session_id=session_id
    )
    dialogue_context = ContextCompactor.compact_history(all_history, verbatim_turns=5)

    if pending_tool_call:
        t_name = pending_tool_call.get("tool", "")
        t_args = pending_tool_call.get("arguments", {}) or {}
        from tools import dispatch_tool_call
        if progress_callback:
            msg = _format_tool_progress_message({"tool_name": t_name, "status": "running", "detail": str(t_args)[:80]})
            try:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(msg)
                else:
                    progress_callback(msg)
            except Exception:
                pass

        tool_res = await dispatch_tool_call(t_name, t_args, read_only=False)
        if t_name not in tools_used:
            tools_used.append(t_name)

        if progress_callback:
            try:
                summary_str = (tool_res.get("message") or tool_res.get("summary") or "")[:120] if isinstance(tool_res, dict) else str(tool_res)[:120]
                msg = _format_tool_progress_message({"tool_name": t_name, "status": "done", "summary": summary_str})
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(msg)
                else:
                    progress_callback(msg)
            except Exception:
                pass

        from core.prompt_loader import load_prompt
        tool_instruction = load_prompt("channel/tool_summary").strip()
        effective_prompt = (
            f"{dialogue_context}"
            f"Tool '{t_name}' was executed on the host system with the following observation:\n"
            f"```json\n{json.dumps(tool_res, ensure_ascii=False)}\n```\n\n"
            f"User request: \"{resolved_task}\"\n\n"
            f"{tool_instruction}"
        )
    elif dialogue_context:
        effective_prompt = f"{dialogue_context}User: {resolved_task}"
    else:
        effective_prompt = resolved_task

    reply = await call_universal_chat_model(
        model_id=get_active_model_id(),
        user_prompt=effective_prompt,
        system_instruction=sys_prompt,
        max_tokens=None,
        temperature=0.6,
        read_only=False,
        progress_cb=_track_tool,
        intercept_mutating_tools=False,
        platform=req.channel,
    )

    if isinstance(reply, str):
        from providers.caller import _clean_model_chat_text
        cleaned = _clean_model_chat_text(reply)
        if not cleaned or '"action": "tool_call"' in cleaned or '<tool_call>' in cleaned:
            try:
                final_reply = await synthesize_action_rationale(
                    tool_name=t_name if pending_tool_call else "execution",
                    tool_args=t_args if pending_tool_call else {},
                    prompt=resolved_task or clean_text
                )
                final_reply = _clean_model_chat_text(final_reply)
            except Exception:
                final_reply = ""
            if not final_reply:
                final_reply = f"Completed action '{resolved_task}'."
        else:
            final_reply = cleaned
    else:
        final_reply = str(reply) if reply else f"Completed action '{resolved_task}'."

    memory_engine.log_conversation(
        user_text=resolved_task or clean_text,
        ai_text=final_reply,
        speaker_name=req.sender_name,
        session_id=session_id
    )

    turn_artifacts = get_turn_artifacts()
    if turn_artifacts and req.channel in ("telegram", "whatsapp"):
        await _auto_dispatch_artifacts_to_channel(req.channel, req.channel_id, turn_artifacts)

    return ChannelResponse(
        text=final_reply,
        session_id=session_id,
        mode="build",
        plan_pending=False,
        tools_used=tools_used,
        attachments=turn_artifacts,
        status="success"
    )


def resolve_pending_plan_callback(plan_id: str, action: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Resolves an inline callback (e.g. Telegram button click) for a plan."""
    from core.session_manager import ActionState
    pending_act = session_state_manager.get_pending_by_id(plan_id)
    if pending_act:
        if action == "approve":
            session_state_manager.resolve_action(pending_act.channel, pending_act.channel_id, plan_id, ActionState.EXECUTING)
            for k in list(_PENDING_PLANS.keys()):
                if _PENDING_PLANS[k].get("plan_id") == plan_id:
                    _PENDING_PLANS.pop(k, None)
            return pending_act.to_dict()
        else:
            session_state_manager.resolve_action(pending_act.channel, pending_act.channel_id, plan_id, ActionState.REJECTED)
            for k in list(_PENDING_PLANS.keys()):
                if _PENDING_PLANS[k].get("plan_id") == plan_id:
                    _PENDING_PLANS.pop(k, None)
            return None

    target_key = None
    target_plan = None
    for key, data in list(_PENDING_PLANS.items()):
        if data.get("plan_id") == plan_id or key == plan_id:
            target_key = key
            target_plan = data
            break

    if not target_plan:
        logger.warning(f"[ChannelGateway] Pending plan {plan_id} not found or already consumed.")
        return None

    if action == "approve":
        target_plan["status"] = "executing"
        if target_key:
            _PENDING_PLANS.pop(target_key, None)
        return target_plan
    else:
        if target_key:
            _PENDING_PLANS.pop(target_key, None)
        return None


async def dispatch_channel_approval_resolution(
    channel: str,
    channel_id: str,
    plan_id: str,
    action: str,  # 'approve' | 'reject'
    user_id: str,
    sender_name: str = "User",
    message_id: Optional[str] = None,
    progress_callback: Optional[Callable[[str], Any]] = None,
) -> Dict[str, Any]:
    """
    Unified Omnichannel Approval Dispatcher (Hermes Parity).
    Centrally validates approver authorization, updates FSM state, executes build mode,
    dispatches clean responses, and sends generated artifacts.
    Shared across Telegram, WhatsApp, Discord, Slack, and Web Studio (Zero Code Duplication).
    """
    from core.session_manager import ActionState
    from core.security import is_authorized_approver
    from integrations.manager import channel_manager

    clean_chan = (channel or "telegram").lower().strip()
    norm_action = "approve" if (action or "").strip().lower() in ("approve", "yes") else "reject"

    pending_act = session_state_manager.get_pending_by_id(plan_id)
    plan_dict = pending_act.to_dict() if pending_act else _PENDING_PLANS.get(f"{clean_chan}_{channel_id}")

    if not pending_act and not plan_dict:
        logger.warning(f"[OmnichannelGateway] Action #{plan_id} on {clean_chan} not found or expired.")
        exp_text = await synthesize_channel_notice("expired", channel=clean_chan)
        rendered = UniversalChannelAdapter.render_notice_payload(clean_chan, "expired", exp_text)
        if clean_chan == "telegram" and message_id:
            try:
                from integrations.telegram.client import edit_telegram_message
                await edit_telegram_message(chat_id=channel_id, message_id=int(message_id), text=rendered.get("text", exp_text), reply_markup=None)
            except Exception:
                pass
        else:
            await channel_manager.send_message(channel=clean_chan, target_id=channel_id, text=rendered.get("text", exp_text))
        return {"status": "expired", "message": exp_text}

    target_user = plan_dict.get("user_id") if plan_dict else (pending_act.user_id if pending_act else user_id)
    session_id = plan_dict.get("session_id", 0) if plan_dict else (pending_act.session_id if pending_act else 0)

    # 1. Reject flow
    if norm_action != "approve":
        logger.info(f"[OmnichannelGateway] User rejected action #{plan_id} on {clean_chan}.")
        session_state_manager.resolve_action(clean_chan, channel_id, plan_id, ActionState.REJECTED)
        session_state_manager.clear_pending(clean_chan, channel_id)
        _PENDING_PLANS.pop(f"{clean_chan}_{channel_id}", None)

        task_desc = (plan_dict.get("original_prompt") or plan_dict.get("tool_name") or "") if plan_dict else ""
        cancel_msg = await synthesize_channel_notice("rejected", channel=clean_chan, task_description=task_desc)
        rendered = UniversalChannelAdapter.render_notice_payload(clean_chan, "rejected", cancel_msg)
        if clean_chan == "telegram" and message_id:
            try:
                from integrations.telegram.client import edit_telegram_message
                await edit_telegram_message(chat_id=channel_id, message_id=int(message_id), text=rendered.get("text", cancel_msg), reply_markup=None)
            except Exception:
                pass
        else:
            await channel_manager.send_message(channel=clean_chan, target_id=channel_id, text=rendered.get("text", cancel_msg))
        return {"status": "rejected", "message": cancel_msg}

    # 2. Approve flow - Verify authorization
    if not is_authorized_approver(user_id=user_id, plan_owner_id=target_user or user_id, channel=clean_chan):
        logger.warning(f"[OmnichannelGateway] User {user_id} unauthorized to approve #{plan_id} on {clean_chan}.")
        denied_msg = await synthesize_channel_notice("unauthorized", channel=clean_chan, user_id=user_id)
        rendered = UniversalChannelAdapter.render_notice_payload(clean_chan, "unauthorized", denied_msg)
        await channel_manager.send_message(channel=clean_chan, target_id=channel_id, text=rendered.get("text", denied_msg))
        return {"status": "denied", "message": denied_msg}

    # 3. Transition to EXECUTING
    session_state_manager.resolve_action(clean_chan, channel_id, plan_id, ActionState.EXECUTING)
    _PENDING_PLANS.pop(f"{clean_chan}_{channel_id}", None)

    if clean_chan == "telegram" and message_id:
        try:
            from integrations.telegram.client import edit_telegram_message
            raw_plan = plan_dict.get("lead_narration") or plan_dict.get("plan_text", "")
            plan_disp = re.sub(r"\n\s*<i>[^<]+</i>\s*$", "", raw_plan).strip() or raw_plan.strip()
            exec_rendered = UniversalChannelAdapter.render_notice_payload(clean_chan, "executing", f"{plan_disp}\n\n[Executing on host...]")
            await edit_telegram_message(
                chat_id=channel_id,
                message_id=int(message_id),
                text=exec_rendered.get("text", plan_disp),
                reply_markup=None,
            )
        except Exception:
            pass

    # 4. Execute Build Mode
    target_action = plan_dict.get('original_prompt') or plan_dict.get('tool_name', 'action')
    req = ChannelRequest(
        text=target_action,
        channel=clean_chan,
        channel_id=channel_id,
        user_id=user_id,
        sender_name=sender_name,
    )

    try:
        build_res = await _execute_build_mode(
            session_id=session_id,
            user_prompt=req.text,
            req=req,
            progress_callback=progress_callback,
            pending_tool_call=plan_dict.get("pending_tool_call"),
            plan=plan_dict,
        )
        session_state_manager.resolve_action(clean_chan, channel_id, plan_id, ActionState.EXECUTED)
        await channel_manager.send_message(channel=clean_chan, target_id=channel_id, text=build_res.text)
        return {"status": "success", "result": build_res.text}

    except asyncio.CancelledError:
        session_state_manager.resolve_action(clean_chan, channel_id, plan_id, ActionState.CANCELLED)
        logger.info(f"[OmnichannelGateway] Action #{plan_id} execution on {clean_chan} was stopped.")
        stop_msg = await synthesize_channel_notice("stopped", channel=clean_chan)
        rendered = UniversalChannelAdapter.render_notice_payload(clean_chan, "stopped", stop_msg)
        await channel_manager.send_message(channel=clean_chan, target_id=channel_id, text=rendered.get("text", stop_msg))
        return {"status": "cancelled", "message": stop_msg}

    except Exception as exec_err:
        session_state_manager.resolve_action(clean_chan, channel_id, plan_id, ActionState.FAILED)
        logger.error(f"[OmnichannelGateway] Action #{plan_id} execution error: {exec_err}", exc_info=True)
        err_msg = await synthesize_channel_notice("error", channel=clean_chan, error_detail=str(exec_err))
        rendered = UniversalChannelAdapter.render_notice_payload(clean_chan, "error", err_msg)
        await channel_manager.send_message(channel=clean_chan, target_id=channel_id, text=rendered.get("text", err_msg))
        return {"status": "error", "message": err_msg}

    finally:
        session_state_manager.clear_pending(clean_chan, channel_id)

