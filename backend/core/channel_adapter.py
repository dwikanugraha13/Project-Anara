"""
channel_adapter.py — Multi-Channel Request Normalization & Execution Gateway.
Implements FR-8, FR-9, FR-10 from prd-general-agent.md & Bab 4/12 from rancangan-general-agent.md.

Normalizes requests from Telegram, CLI, WhatsApp, Web, and Scheduler into a uniform
internal request format, routing through Unified Plan Detector and Permission Gate.
"""
import asyncio
import contextvars
import json
import logging
import os
import re
import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from pydantic import BaseModel, Field

from memory import memory_engine
from core.context_compactor import ContextCompactor
# NOTE: classify_approval_intent is imported lazily at line ~636 when needed
# needs_plan and is_explicit_plan_approval were removed (dead imports — never called in this file)
from core.prompt_assembler import PromptAssembler
from core.security import check_prompt_injection
from core.session_manager import session_state_manager, PendingAction, ActionState
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

from core.message_chunker import (
    _format_tool_progress_message,
    PLATFORM_MESSAGE_LIMITS,
    split_message_chunks,
)


class BaseChannelPresenter(ABC):
    """Abstract presenter interface for channel-specific UI and action decoupling."""
    @abstractmethod
    def render_approval(self, narration: str, action: PendingAction) -> Dict[str, Any]:
        """Renders platform-specific approval payload with decoupled UI elements."""
        pass

class UniversalChannelAdapter:
    """
    Unified channel adapter facade delegating to central PlatformRegistry (Anara Standard).
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


from core.action_rationale import (
    synthesize_action_rationale,
    generate_dynamic_action_rationale,
    synthesize_channel_notice,
)


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
    session_id: Optional[int] = None


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


_CHANNEL_ACTIVE_SESSION: Dict[str, int] = {}


def set_channel_active_session(channel: str, channel_id: str, session_id: int):
    """Sets active session override for a channel / chat (e.g. from /resume)."""
    key = f"{channel}_{str(channel_id).strip()}"
    _CHANNEL_ACTIVE_SESSION[key] = session_id
    try:
        from core.agent import anara_agent
        anara_agent.set_active_session_id(session_id)
    except Exception:
        pass


def get_channel_active_session(channel: str, channel_id: str) -> Optional[int]:
    key = f"{channel}_{str(channel_id).strip()}"
    return _CHANNEL_ACTIVE_SESSION.get(key)


def get_or_create_channel_session(req: ChannelRequest) -> int:
    """Binds an incoming channel request to an isolated persistent chat session (Anara Standard)."""
    if req.session_id:
        return req.session_id

    speaker = req.sender_name or "User"
    cid = str(req.channel_id or "default").strip()

    # Check explicit runtime resume/switch mapping first
    active_key = f"{req.channel}_{cid}"
    if active_key in _CHANNEL_ACTIVE_SESSION:
        bound_id = _CHANNEL_ACTIVE_SESSION[active_key]
        sess = memory_engine.get_session(bound_id)
        if sess and not sess.get("is_archived"):
            return sess["id"]

    canonical_key = f"channel_{req.channel}_{cid}"

    # 1. Direct indexed resolution via canonical session_key (immune to title renames)
    sess = memory_engine.get_session(canonical_key)
    if sess and not sess.get("is_archived"):
        return sess["id"]

    # 2. Fallback: Check existing session by channel & channel_id title tag (backward compatibility)
    session_tag = f"[{req.channel}:{cid}]"
    clean_title = f"{req.channel.title()} Chat ({speaker}) {session_tag}" if cid != "default" else f"{req.channel.title()} Chat ({speaker})"

    sessions = memory_engine.get_sessions(speaker_name=speaker, session_type="chat", limit=50)
    for s in sessions:
        if s.get("channel") == req.channel and not s.get("is_archived"):
            s_title = s.get("title") or ""
            if (cid != "default" and session_tag in s_title) or (cid == "default" and f"[{req.channel}:" not in s_title):
                # Backfill canonical session_key if missing
                try:
                    with memory_engine._get_connection() as conn:
                        conn.cursor().execute(
                            "UPDATE chat_sessions SET session_key = ? WHERE id = ? AND (session_key IS NULL OR session_key NOT LIKE 'channel_%')",
                            (canonical_key, s["id"])
                        )
                        conn.commit()
                except Exception:
                    pass
                return s["id"]

    # 3. If none found, create a new isolated session bound to canonical_key
    new_sess = memory_engine.create_session(
        session_key=canonical_key,
        speaker_name=speaker,
        title=clean_title,
        session_type="chat",
        channel=req.channel,
        session_mode="conversational"
    )
    return new_sess["id"]


from core.media_dispatcher import (
    _auto_dispatch_artifacts_to_channel,
    _extract_and_dispatch_media_tags,
)


async def process_channel_request(
    req: ChannelRequest,
    progress_callback: Optional[Callable[[str], Any]] = None,
    token_callback: Optional[Callable[[str], Any]] = None,
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
        session_id = get_or_create_channel_session(req)
        if is_stop_req:
            # Anara Cancel Fence Parity: /stop must execute immediately without blocking behind session lock
            return await _process_channel_request_core(req, progress_callback, token_callback)
        async with session_state_manager.get_session_lock(str(session_id)):
            return await _process_channel_request_core(req, progress_callback, token_callback)
    finally:
        if current_task and not is_stop_req:
            session_state_manager.unregister_active_task(req.channel, req.channel_id, current_task)
        _ACTIVE_CHANNEL_CONTEXT.reset(token_ctx)


async def _enrich_message_with_vision(user_text: str, attachments: List[Dict[str, Any]]) -> str:
    """
    Universal Inbound Vision Enrichment (Anara Standard: gateway/run_inbound.py lines 1866-1909).
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


def prepend_reasoning_block(response: str, reasoning: str, channel: str = "telegram") -> str:
    """
    Prepends the formatted reasoning block to the final response matching the reference gateway standard:
    e.g.
    💭 **Reasoning:**
    ```
    The user wants a repo check...
    ```

    {response}
    """
    from config import cfg_get
    show_reasoning = cfg_get("display.show_reasoning", True)
    if not show_reasoning or not reasoning or not reasoning.strip():
        return response

    cleaned = reasoning.strip()
    lines = cleaned.splitlines()
    if len(lines) > 20:
        display_reasoning = "\n".join(lines[:20]) + f"\n... ({len(lines) - 20} more lines)"
    else:
        display_reasoning = cleaned

    # Escape fences inside reasoning so they don't break the outer code block
    display_reasoning = display_reasoning.replace("```", "'''")

    reasoning_style = cfg_get("display.reasoning_style", "code")
    if reasoning_style == "blockquote" or channel == "whatsapp":
        quoted = "\n".join(f"> {ln}" if ln.strip() else ">" for ln in display_reasoning.splitlines())
        return f"💭 *Reasoning:*\n{quoted}\n\n{response}"
    elif reasoning_style == "subtext" or channel == "discord":
        quoted = "\n".join(f"-# {ln}" if ln.strip() else "-#" for ln in display_reasoning.splitlines())
        return f"-# 💭 **Reasoning:**\n{quoted}\n\n{response}"
    else:
        # Default: Telegram / standard markdown code fence
        return f"💭 **Reasoning:**\n```\n{display_reasoning}\n```\n\n{response}"


async def _process_channel_request_core(
    req: ChannelRequest,
    progress_callback: Optional[Callable[[str], Any]] = None,
    token_callback: Optional[Callable[[str], Any]] = None,
) -> ChannelResponse:
    # 1. Resolve Session
    session_id = get_or_create_channel_session(req)
    req.session_id = session_id
    from core.agent import anara_agent
    anara_agent.set_active_session_id(session_id)
    from tools.artifact_tools import clear_turn_artifacts, get_turn_artifacts
    clear_turn_artifacts()

    # 2. Content Moderation & Prompt Injection Defense (FR-20)
    clean_text = req.text.strip()

    # Deduplication protection (Anara Standard: gateway/run_inbound.py)
    msg_id = (req.metadata or {}).get("message_id") or (req.metadata or {}).get("update_id")
    msg_key = f"{req.channel}:{req.channel_id}:{msg_id}" if msg_id else f"{req.channel}:{req.channel_id}:{clean_text}"
    if clean_text and _channel_message_dedup.is_duplicate(msg_key):
        logger.info(f"[ChannelGateway] Dropping duplicate message on {req.channel}: '{clean_text[:40]}'")
        return ChannelResponse(
            text="",
            session_id=session_id,
            mode="conversational",
            status="duplicate_dropped"
        )

    # 2b. Inbound Vision Auto-Enrichment (Anara Standard)
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

    # 4. First-Run Onboarding Guard (Anara Standard):
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
    intent_state = await session_state_manager.async_evaluate_intent(clean_text, req.channel, req.channel_id)
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

    # 5. Check session mode (Anara Model-Driven Parity: 0 regex guessing on user text)
    # In conversational mode, user turns execute directly with runtime tool interception.
    # Plan proposal gate is triggered only when the session is explicitly configured for Plan Mode.
    session_obj = memory_engine.get_session(session_id)
    actual_session_mode = (session_obj.get("session_mode") or "build") if session_obj else "build"
    requires_plan = (actual_session_mode == "plan")

    # ── CASE B: Request entails high-risk/mutating action -> Auto PLAN MODE ──
    if requires_plan:
        logger.info(f"[ChannelGateway] Request triggers Plan Gate -> Composing structured plan...")
        plan_id = str(uuid.uuid4())[:8]

        from core.prompt_loader import load_prompt
        plan_prompt = load_prompt("channel/plan_gate", clean_text=clean_text)

        sys_prompt = await asyncio.to_thread(PromptAssembler.assemble,
            mode="plan",
            speaker_name=req.sender_name,
            is_chat_mode=True,
            session_type="chat",
            channel=req.channel,
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

        # Fallback narration formulation matching Anara Standard
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
        # Anara Standard: close unclosed tool markup syntax safely without heuristic text rewriting
        is_tool_invocation = '"action": "tool_call"' in ai_t or '<tool_call>' in ai_t
        is_unclosed = ('<tool_call>' in ai_t and '</tool_call>' not in ai_t) or (
            '"action": "tool_call"' in ai_t and not ai_t.rstrip().endswith(('}', '```', '</tool_call>'))
        )
        if is_tool_invocation and is_unclosed:
            h_clean = dict(h)
            if "<tool_call>" in ai_t and "</tool_call>" not in ai_t:
                h_clean["ai_text"] = ai_t + "\n</tool_call>"
            elif '"action": "tool_call"' in ai_t and not ai_t.rstrip().endswith(('}', '```')):
                h_clean["ai_text"] = ai_t + "\n}"
            prior_turns.append(h_clean)
        else:
            prior_turns.append(h)
    dialogue_context = ContextCompactor.compact_history(prior_turns, verbatim_turns=5)
    full_user_prompt = f"{dialogue_context}User: {clean_text}" if dialogue_context else clean_text

    ws_tree = anara_agent.get_workspace_tree_shallow(session_id=session_id)
    eff_mode = "conversational" if actual_session_mode == "conversational" else "build"
    sys_prompt = await asyncio.to_thread(PromptAssembler.assemble,
        mode=eff_mode,
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
    last_reasoning_chunks: List[str] = []

    def _track_tool(evt: Dict[str, Any]):
        if evt.get("type") == "thought":
            t_thought = evt.get("thought") or evt.get("content") or ""
            if t_thought:
                last_reasoning_chunks.append(t_thought)
            return

        t_name = evt.get("tool_name")
        if t_name and t_name not in tools_used:
            tools_used.append(t_name)
        status = evt.get("status")
        if status == "running" and t_name:
            cid = evt.get("call_id") or f"ch_{uuid.uuid4().hex[:10]}"
            evt["call_id"] = cid
            try:
                session_state_manager.persist_tool_call_start(
                    session_id=session_id,
                    channel=req.channel,
                    channel_id=req.channel_id,
                    tool_name=t_name,
                    tool_args=evt.get("args") or evt.get("tool_args") or {},
                    call_id=cid
                )
            except Exception:
                pass
        elif status == "done" and t_name:
            cid = evt.get("call_id")
            if cid:
                try:
                    session_state_manager.persist_tool_call_result(
                        call_id=cid,
                        result_summary=evt.get("summary") or evt.get("detail") or "",
                        is_error=bool(evt.get("is_error", False))
                    )
                except Exception:
                    pass
        if progress_callback:
            msg = _format_tool_progress_message(evt)
            if msg:
                try:
                    if asyncio.iscoroutinefunction(progress_callback):
                        asyncio.create_task(progress_callback(msg))
                    else:
                        progress_callback(msg)
                except Exception:
                    pass
        try:
            from shared_state import register_session_run
            register_session_run(session_id, status="thinking", live_tool=evt)
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
            token_cb=token_callback,
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
        # ── ANTI-LEAK GATE (Anara Standard) ──
        # Ensure raw tool-call JSON blocks are NEVER presented as chat text to user
        from providers.caller import _clean_model_chat_text, _format_empty_model_notice
        if '"action": "tool_call"' in reply or '<tool_call>' in reply or not _clean_model_chat_text(reply):
            from providers.caller import _extract_and_parse_tool_call
            leaked_payload, lead, _ = _extract_and_parse_tool_call(reply)
            if leaked_payload:
                from tools import get_tool_risk
                leaked_tool = str(leaked_payload.get("tool") or "")
                t_risk = get_tool_risk(leaked_tool)
                if t_risk in ("mutating", "ask"):
                    # Anara Standard: NEVER auto-execute mutating tools unvetted! Route to Approval State Machine
                    logger.info(f"[ChannelAdapter] Anti-leak caught mutating tool call '{leaked_tool}'. Routing to approval gate...")
                    plan_id = f"plan_{uuid.uuid4().hex[:8]}"
                    t_args = leaked_payload.get("arguments") or {}
                    pending_act = PendingAction(
                        plan_id=plan_id,
                        session_id=session_id,
                        channel=req.channel,
                        channel_id=req.channel_id,
                        tool_name=leaked_tool,
                        tool_args=t_args,
                        original_prompt=clean_text,
                        state=ActionState.PENDING,
                        ttl_seconds=300.0,
                        user_id=req.user_id,
                    )
                    session_state_manager.set_pending_action(req.channel, req.channel_id, pending_act)
                    _PENDING_PLANS[f"{req.channel}_{req.channel_id}"] = pending_act.to_dict()

                    rationale = await synthesize_action_rationale(leaked_tool, t_args, clean_text)
                    plan_disp = f"Proposed Action: `{leaked_tool}`\n{rationale}\n\nPlease confirm to execute."
                    rendered = UniversalChannelAdapter.render_approval_payload(
                        channel=req.channel,
                        narration=plan_disp,
                        action=pending_act
                    )
                    return ChannelResponse(
                        text=rendered.get("text") or plan_disp,
                        session_id=session_id,
                        mode="plan",
                        plan_pending=True,
                        plan_id=plan_id,
                        status="pending_approval",
                        reply_markup=rendered.get("reply_markup"),
                        pending_action=pending_act.to_dict(),
                        rendered_payload=rendered,
                    )
                else:
                    logger.info(f"[ChannelAdapter] Anti-leak caught harmless read-only tool call '{leaked_tool}'. Auto-dispatching...")
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
            from providers.payload_parser import _extract_think_blocks
            _, think_part = _extract_think_blocks(reply)
            if think_part:
                last_reasoning_chunks.append(think_part)
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

    # Prepend Reasoning block if reasoning was produced
    accumulated_reasoning = "\n\n".join(c for c in last_reasoning_chunks if c.strip()).strip()
    if accumulated_reasoning:
        final_reply = prepend_reasoning_block(final_reply, accumulated_reasoning, channel=req.channel)

    # Extract native MEDIA: and [[audio_as_voice]] directives (Anara Omnichannel Standard)
    final_reply = await _extract_and_dispatch_media_tags(req.channel, req.channel_id, final_reply)

    memory_engine.log_conversation(
        user_text=clean_text,
        ai_text=final_reply,
        speaker_name=req.sender_name,
        session_id=session_id
    )

    turn_artifacts = get_turn_artifacts()
    if turn_artifacts:
        await _auto_dispatch_artifacts_to_channel(req.channel, req.channel_id, turn_artifacts)

    # Spawn background self-improvement review (Anara Native Omnichannel)
    try:
        from core.self_improvement import self_improvement_reviewer
        async def _receipt_cb(receipt_text: str):
            try:
                from integrations.manager import channel_manager
                await channel_manager.send_message(channel=req.channel, target_id=req.channel_id, text=f"<i>{receipt_text}</i>")
            except Exception:
                pass

        asyncio.create_task(
            self_improvement_reviewer.run_review_async(
                user_prompt=clean_text,
                ai_response=final_reply,
                tools_used=tools_used,
                channel=req.channel,
                channel_id=req.channel_id,
                summary_callback=_receipt_cb,
            )
        )
    except Exception as e_si:
        logger.debug(f"[ChannelGateway] Self-improvement trigger error: {e_si}")

    try:
        from shared_state import unregister_session_run
        unregister_session_run(session_id)
    except Exception:
        pass

    return ChannelResponse(
        text=final_reply,
        session_id=session_id,
        mode="conversational",
        plan_pending=False,
        tools_used=tools_used,
        attachments=turn_artifacts,
        status="success"
    )


from core.build_mode_runner import execute_build_mode, execute_build_mode_core

_execute_build_mode = execute_build_mode
_execute_build_mode_core = execute_build_mode_core


from core.approval_dispatcher import (
    resolve_pending_plan_callback as _core_resolve_pending_plan_callback,
    dispatch_channel_approval_resolution as _core_dispatch_channel_approval_resolution,
)


def resolve_pending_plan_callback(plan_id: str, action: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Resolves an inline callback (e.g. Telegram button click) for a plan."""
    return _core_resolve_pending_plan_callback(plan_id, action, user_id, _PENDING_PLANS)


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
    Unified Omnichannel Approval Dispatcher (Anara Standard).
    Centrally validates approver authorization, updates FSM state, executes build mode,
    dispatches clean responses, and sends generated artifacts.
    Shared across Telegram, WhatsApp, Discord, Slack, and Web Studio (Zero Code Duplication).
    """
    return await _core_dispatch_channel_approval_resolution(
        channel=channel,
        channel_id=channel_id,
        plan_id=plan_id,
        action=action,
        user_id=user_id,
        sender_name=sender_name,
        message_id=message_id,
        progress_callback=progress_callback,
        pending_plans_map=_PENDING_PLANS,
        execute_build_mode_fn=_execute_build_mode,
    )


