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
import re
import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from pydantic import BaseModel, Field

from memory import memory_engine, file_memory
from core.context_compactor import ContextCompactor
from core.plan_detector import needs_plan, is_explicit_plan_approval
from core.prompt_assembler import PromptAssembler
from core.skill_library import skill_library
from core.security import check_prompt_injection
from core.session_manager import session_state_manager, PendingAction
from providers import call_universal_chat_model, get_active_model_id

logger = logging.getLogger(__name__)

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

    step_str = f" [Langkah {step}]" if step else ""

    if t_name == "agent" and status == "thinking":
        return f"⚙️ Sedang bernalar & merumuskan langkah...{step_str}"

    clean_name = t_name.replace("_", " ").title() if t_name else "Operasi"
    prefix = f"⚡ {clean_name}" if "terminal" in t_name or "command" in t_name or "cli" in t_name else f"⚙️ {clean_name}"

    if detail:
        clean_detail = str(detail).replace("\\", "/")
        if "/" in clean_detail:
            clean_detail = clean_detail.split("/")[-1]
        return f"{prefix}: {clean_detail[:40]}...{step_str}"

    if summary:
        return f"{prefix}: {str(summary)[:45]}...{step_str}"

    return f"{prefix}: {status}...{step_str}"


def split_message_chunks(text: str, max_chars: int = 3000, add_part_headers: bool = True) -> List[str]:
    """
    Semantic code-block-aware message chunker for remote chat platforms (Anara Standard).
    Splits long messages along paragraph and newline boundaries without breaking markdown code blocks.
    Guarantees unlimited parts and adds header badges [Bagian X/N] when message exceeds threshold.
    """
    if not text or len(text) <= max_chars:
        return [text] if text else []

    raw_chunks: List[str] = []
    current_text = text
    effective_limit = max_chars - 40 if add_part_headers else max_chars

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
    for idx, chunk in enumerate(raw_chunks, start=1):
        header = f"📄 <b>[Bagian {idx}/{total_parts}]</b>\n\n"
        final_chunks.append(header + chunk)

    return final_chunks


class BaseChannelPresenter(ABC):
    """Abstract presenter interface for channel-specific UI and action decoupling."""
    @abstractmethod
    def render_approval(self, narration: str, action: PendingAction) -> Dict[str, Any]:
        """Renders platform-specific approval payload with decoupled UI elements."""
        pass

    @abstractmethod
    def render_message(self, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Renders standard conversational message."""
        pass


class TelegramChannelPresenter(BaseChannelPresenter):
    def render_approval(self, narration: str, action: PendingAction) -> Dict[str, Any]:
        """
        Telegram: pure natural narration + technical command preview (if shell) + inline keyboard.
        Zero canned phrases.
        """
        text_parts = [narration.strip()]
        cmd = action.tool_args.get("command") or (action.pending_tool_call or {}).get("arguments", {}).get("command")
        if cmd:
            text_parts.append(f"\n```shell\n{cmd}\n```")
        elif action.tool_args.get("file_path"):
            fp = action.tool_args.get("file_path")
            text_parts.append(f"\n`Target: {fp}`")

        full_text = "\n".join(text_parts)
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Setujui & Jalankan", "callback_data": f"approve:{action.action_id}"},
                    {"text": "❌ Batalkan", "callback_data": f"reject:{action.action_id}"}
                ]
            ]
        }
        return {
            "text": full_text,
            "parse_mode": "HTML",
            "reply_markup": keyboard,
        }

    def render_message(self, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "text": narration,
            "parse_mode": "HTML",
            "reply_markup": None,
        }


class WebStudioChannelPresenter(BaseChannelPresenter):
    def render_approval(self, narration: str, action: PendingAction) -> Dict[str, Any]:
        """
        Web HUD / Studio: emits decoupled WebSocket event with metadata for UI drawer.
        """
        return {
            "type": "agent_response",
            "narration": narration,
            "has_pending_action": True,
            "action_metadata": {
                "id": action.action_id,
                "tool": action.tool_name,
                "args": action.tool_args,
                "risk": action.risk_level,
                "created_at": action.created_at,
            },
            "text": narration,
            "reply_markup": None,
        }

    def render_message(self, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "type": "agent_response",
            "narration": narration,
            "has_pending_action": False,
            "action_metadata": None,
            "text": narration,
            "reply_markup": None,
        }


class WhatsAppChannelPresenter(BaseChannelPresenter):
    def render_approval(self, narration: str, action: PendingAction) -> Dict[str, Any]:
        cmd_hint = ""
        cmd = action.tool_args.get("command") or (action.pending_tool_call or {}).get("arguments", {}).get("command")
        if cmd:
            cmd_hint = f"\nPerintah: {cmd}"

        text = (
            f"{narration}{cmd_hint}\n\n"
            f"Balas *setujui* untuk menjalankan tindakan ini, atau *batal* untuk membatalkannya."
        )
        return {
            "text": text,
            "reply_markup": None,
        }

    def render_message(self, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "text": narration,
            "reply_markup": None,
        }


class CliChannelPresenter(BaseChannelPresenter):
    def render_approval(self, narration: str, action: PendingAction) -> Dict[str, Any]:
        cmd_hint = ""
        cmd = action.tool_args.get("command") or (action.pending_tool_call or {}).get("arguments", {}).get("command")
        if cmd:
            cmd_hint = f"\n  Command: {cmd}"
        elif action.tool_args.get("file_path"):
            cmd_hint = f"\n  File: {action.tool_args.get('file_path')}"

        prompt = f"\n[Konfirmasi Persetujuan: {action.tool_name}]{cmd_hint}\nSetujui dan jalankan? [y/N]: "
        return {
            "text": f"{narration}\n{prompt}",
            "narration": narration,
            "prompt": prompt,
            "reply_markup": None,
        }

    def render_message(self, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "text": narration,
            "reply_markup": None,
        }


class VoiceChannelPresenter(BaseChannelPresenter):
    def render_approval(self, narration: str, action: PendingAction) -> Dict[str, Any]:
        """
        Voice / Audio: strips technical shell syntax, code blocks, and paths so TTS speaks clean,
        pure Indonesian narration and invites natural verbal approval ('gas', 'lanjut', 'oke').
        """
        from cognition.audio import filter_tts_speech_text
        spoken = filter_tts_speech_text(narration)
        verbal_prompt = f"{spoken} Katakan 'gas' atau 'lanjutkan' jika kamu ingin aku menjalankannya, atau 'batal' untuk membatalkan."
        return {
            "text": verbal_prompt,
            "speech_text": verbal_prompt,
            "narration": narration,
            "has_pending_action": True,
            "action_id": action.action_id,
            "tool_name": action.tool_name,
            "tool_args": action.tool_args,
            "reply_markup": None,
        }

    def render_message(self, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from cognition.audio import filter_tts_speech_text
        spoken = filter_tts_speech_text(narration)
        return {
            "text": narration,
            "speech_text": spoken,
            "reply_markup": None,
        }


class UniversalChannelAdapter:
    """Dynamic presenter registry and presentation layer (Hermes Decoupled Architecture)."""
    _presenters: Dict[str, BaseChannelPresenter] = {}

    @classmethod
    def register(cls, channel: str, presenter: BaseChannelPresenter):
        cls._presenters[channel.lower().strip()] = presenter

    @classmethod
    def get_presenter(cls, channel: str) -> BaseChannelPresenter:
        clean = (channel or "cli").lower().strip()
        from tools.platform_registry import PLATFORM_ALIASES
        resolved = PLATFORM_ALIASES.get(clean, clean)
        return cls._presenters.get(resolved) or cls._presenters.get(clean) or cls._presenters.get("cli", CliChannelPresenter())

    @classmethod
    def render_approval_payload(cls, channel: str, narration: str, action: PendingAction) -> Dict[str, Any]:
        presenter = cls.get_presenter(channel)
        return presenter.render_approval(narration, action)

    @classmethod
    def render_message_payload(cls, channel: str, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        presenter = cls.get_presenter(channel)
        return presenter.render_message(narration, metadata=metadata)

    @classmethod
    def render_voice_payload(cls, narration: str, action: Optional[PendingAction] = None) -> Dict[str, Any]:
        presenter = cls.get_presenter("voice")
        if action:
            return presenter.render_approval(narration, action)
        return presenter.render_message(narration)


# Register standard platform presenters
UniversalChannelAdapter.register("telegram", TelegramChannelPresenter())
UniversalChannelAdapter.register("web_studio", WebStudioChannelPresenter())
UniversalChannelAdapter.register("whatsapp", WhatsAppChannelPresenter())
UniversalChannelAdapter.register("cli", CliChannelPresenter())
UniversalChannelAdapter.register("voice", VoiceChannelPresenter())
UniversalChannelAdapter.register("voice_hud", VoiceChannelPresenter())
UniversalChannelAdapter.register("audio", VoiceChannelPresenter())


async def synthesize_action_rationale(tool_name: str, tool_args: Dict[str, Any], prompt: str = "") -> str:
    """
    Pure Model-Driven Rationale Synthesis (Hermes Parity).
    Queries the fast auxiliary model (e.g. gemini-3.1-flash / < 400ms) to formulate a natural,
    contextual 1-sentence conversational explanation of WHY this tool is being invoked for this prompt.
    Eliminates hardcoded if-else dictionaries and regexes.
    """
    from providers import call_universal_chat_model
    from core.capabilities import get_fast_auxiliary_model

    args_summary = ", ".join(f"{k}={v}" for k, v in list(tool_args.items())[:3])
    sys_instruction = (
        "Kamu adalah Anara, asisten AI cerdas dan ramah. "
        "Tugasmu: berikan 1 kalimat percakapan alami dalam bahasa Indonesia yang santai dan bersahabat kepada pengguna "
        "menjelaskan mengapa tindakan ini kamu jalankan untuk menyelesaikan tugasnya. Dilarang menggunakan format JSON atau kalimat kaku."
    )
    user_p = (
        f"Konteks permintaan pengguna: \"{prompt or 'Menyelesaikan tugas'}\"\n"
        f"Tindakan alat yang dipanggil: '{tool_name}' ({args_summary})\n"
        "Alasan naratif singkat (1 kalimat ramah):"
    )

    try:
        model_id = get_fast_auxiliary_model()
        res = await asyncio.wait_for(
            call_universal_chat_model(
                model_id=model_id,
                user_prompt=user_p,
                system_instruction=sys_instruction,
                max_tokens=60,
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

    # Fallback to dynamic tool name translation if LLM is unreachable offline
    return generate_dynamic_action_rationale(tool_name, tool_args, prompt)


def generate_dynamic_action_rationale(tool_name: str, tool_args: Dict[str, Any], prompt: str = "") -> str:
    """
    Introspects tool metadata and runtime parameters dynamically without static rule branches (Hermes Parity).
    Zero hardcoded strings or rigid keyword mappings.
    """
    t_clean = (tool_name or "perangkat sistem").strip().lower()

    # Dynamic target parameter discovery
    target_info = tool_args.get("command") or tool_args.get("file_path") or tool_args.get("title") or tool_args.get("query") or tool_args.get("task") or ""
    clean_target = str(target_info).strip()

    # Dynamic tool description introspection from registry
    desc = ""
    try:
        from tools import get_tools_catalog
        cat = get_tools_catalog()
        for t in cat:
            if t.get("name") == t_clean:
                desc = t.get("description", "")
                break
    except Exception:
        pass

    clean_name = t_clean.replace("_", " ")
    if clean_target:
        if "/" in clean_target or "\\" in clean_target:
            clean_target = clean_target.replace("\\", "/").split("/")[-1]
        return f"Aku akan menjalankan tindakan {clean_name} pada '{clean_target[:60]}' untuk menyelesaikan tugasmu."

    if desc:
        short_desc = desc.split(".")[0].strip()
        return f"Aku akan {short_desc.lower()} untuk melanjutkan pengerjaan tugas kita."

    return f"Aku akan mengeksekusi tindakan {clean_name} untuk melanjutkan proses ini."


class ChannelRequest(BaseModel):
    """Uniform internal request representation across all input channels (FR-9)."""
    text: str
    channel: str = "web"  # 'telegram', 'cli', 'whatsapp', 'web', 'scheduler'
    channel_id: str = "default"  # Chat ID or Terminal ID
    user_id: str = "default_user"
    sender_name: Optional[str] = "Pengguna"
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
    speaker = req.sender_name or "Pengguna"
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
    """Auto-dispatches generated documents (.pdf, .docx, .zip) directly to Telegram or WhatsApp."""
    if not artifacts or not channel_id or channel_id.startswith("default"):
        return
    for art in artifacts:
        f_path = art.get("path")
        f_name = art.get("filename") or (os.path.basename(f_path) if f_path else "")
        if not f_path or not os.path.isfile(f_path):
            continue
        try:
            if channel == "telegram":
                from integrations.telegram import send_telegram_document
                logger.info(f"[AutoDispatch] Sending document '{f_name}' to Telegram chat {channel_id}")
                await send_telegram_document(file_path=f_path, chat_id=channel_id, caption=f"?? Berkas: {f_name}")
            elif channel == "whatsapp":
                from integrations.whatsapp import send_whatsapp_document
                logger.info(f"[AutoDispatch] Sending document '{f_name}' to WhatsApp {channel_id}")
                await send_whatsapp_document(to=channel_id, file_path=f_path, caption=f"?? Berkas: {f_name}")
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
    is_stop_req = req.text.strip().lower().startswith(("/stop", "/cancel", "/abort", "/batal"))
    if current_task and not is_stop_req:
        session_state_manager.register_active_task(req.channel, req.channel_id, current_task)

    try:
        return await _process_channel_request_core(req, progress_callback)
    finally:
        if current_task and not is_stop_req:
            session_state_manager.unregister_active_task(req.channel, req.channel_id, current_task)
        _ACTIVE_CHANNEL_CONTEXT.reset(token_ctx)


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
    is_safe, denial_reason = check_prompt_injection(clean_text)
    if not is_safe:
        denial_msg = denial_reason or "Permintaan ditolak oleh filter keamanan Anara."
        return ChannelResponse(
            text=denial_msg,
            session_id=session_id,
            mode="conversational",
            status="blocked",
            error=denial_msg
        )

    # 3. Log User Turn & Trigger Memory Detection
    memory_engine.log_conversation(
        user_text=req.text,
        ai_text="",
        speaker_name=req.sender_name,
        session_id=session_id
    )
    file_memory.detect_and_record_memory(req.text, speaker_name=req.sender_name)

    # 4. Check for Unified System Commands (/help, /status, /model, /skills, /memory, /workspace, /clear, /stop, /plan)
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

    # 5. Check for Plan Approval (Semantic Intent Classifier + Session State Machine - Subsystem 3)
    session_plan_key = f"{req.channel}_{req.channel_id}"
    intent_state = session_state_manager.evaluate_intent(clean_text, req.channel, req.channel_id)
    active_pending = intent_state["pending"] or _PENDING_PLANS.get(session_plan_key)

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
    if (had_expired_action or recently_expired_act) and len(clean_text.split()) <= 3 and is_explicit_plan_approval(clean_text):
        expired_notice = (
            "Rencana aksi sebelumnya telah kedaluwarsa demi keamanan (batas waktu 5 menit). "
            "Seluruh ingatan dan konteks obrolan kita tetap tersimpan dengan aman. "
            "Silakan beri tahu apa yang ingin kita kerjakan sekarang!"
        )
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
        if semantic_intent == "reject" or any(clean_text == w or clean_text.startswith(f"{w} ") for w in ("batal", "batalkan", "jangan", "stop", "cancel", "skip", "tidak")):
            logger.info(f"[ChannelGateway] User rejected pending action #{plan_id} via '{clean_text}'. Cancelling...")
            session_state_manager.resolve_action(req.channel, req.channel_id, plan_id, ActionState.REJECTED)
            _PENDING_PLANS.pop(session_plan_key, None)
            cancel_reply = "Baik, rencana tindakan telah dibatalkan. Tidak ada perubahan yang dilakukan pada sistem."
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
        elif semantic_intent == "approve" or intent_state["is_approval"] or is_explicit_plan_approval(clean_text):
            logger.info(f"[ChannelGateway] User approved pending action #{plan_id} via '{clean_text}'. Executing BUILD MODE...")
            session_state_manager.resolve_action(req.channel, req.channel_id, plan_id, ActionState.EXECUTING)
            _PENDING_PLANS.pop(session_plan_key, None)

            build_res = await _execute_build_mode(
                session_id=session_id,
                user_prompt=f"Eksekusi rencana: {orig_prompt}",
                req=req,
                progress_callback=progress_callback,
                pending_tool_call=pending_tool,
                plan=plan_dict,
            )
            session_state_manager.resolve_action(req.channel, req.channel_id, plan_id, ActionState.EXECUTED)
            return build_res

        # ── CASE A3: Topic Shift (User asked an unrelated question while action was pending) ──
        elif semantic_intent == "other" and len(clean_text.split()) > 2:
            logger.info(f"[ChannelGateway] Topic shift detected while action #{plan_id} pending. Auto-expiring previous action...")
            session_state_manager.resolve_action(req.channel, req.channel_id, plan_id, ActionState.EXPIRED)
            _PENDING_PLANS.pop(session_plan_key, None)
            active_pending = None

    # 5. Check if this request needs a plan
    requires_plan = needs_plan(clean_text, session_mode="conversational")

    # ── CASE B: Request entails high-risk/mutating action -> Auto PLAN MODE ──
    if requires_plan:
        logger.info(f"[ChannelGateway] Request triggers Plan Gate -> Composing structured plan...")
        plan_id = str(uuid.uuid4())[:8]

        plan_prompt = (
            f"[INSTRUKSI SISTEM: PLAN GATE DIAKTIFKAN OTOMATIS]\n"
            f"Pengguna meminta: \"{clean_text}\"\n"
            "Tindakan ini memerlukan perubahan sistem/file atau eksekusi terminal. "
            "Kamu beroperasi dalam PLAN MODE (Read-Only). "
            "Susun rencana kerja ringkas dalam 2-4 langkah konkret, jelaskan risiko singkatnya, "
            "dan minta persetujuan pengguna sebelum mengeksekusi."
        )

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
            max_tokens=600,
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

        # Log AI Plan Proposal (natural narrative only, zero UI tags or buttons)
        memory_engine.log_conversation(
            user_text=clean_text,
            ai_text=plan_text or "Saya telah menyusun rencana kerja ini.",
            speaker_name=req.sender_name,
            session_id=session_id
        )

        rendered = UniversalChannelAdapter.render_approval_payload(
            channel=req.channel,
            narration=plan_text or "Saya telah menyusun rencana. Silakan setujui untuk mulai eksekusi.",
            action=pending_act
        )

        return ChannelResponse(
            text=rendered.get("text") or (plan_text or "Saya telah menyusun rencana. Silakan setujui untuk mulai eksekusi."),
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
        if not ai_t:
            continue
        # Hermes parity: close interrupted tool sequence in past transcript to prevent continuation hallucination
        if ('"action": "tool_call"' in ai_t or '<tool_call>' in ai_t) and not any(w in ai_t.lower() for w in ("selesai", "berhasil", "laporan")):
            h_clean = dict(h)
            h_clean["ai_text"] = "Tindakan pemeriksaan sistem sebelumnya telah selesai diproses."
            prior_turns.append(h_clean)
        else:
            prior_turns.append(h)
    dialogue_context = ContextCompactor.compact_history(prior_turns, verbatim_turns=15)
    full_user_prompt = f"{dialogue_context}Pesan User: {clean_text}" if dialogue_context else clean_text

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
    from cognition.memory_nudge import memory_nudge_manager
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
            max_tokens=4096,
            temperature=0.7,
            read_only=False,
            progress_cb=_track_tool,
            intercept_mutating_tools=True,
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
        tool_name = reply.get("tool_name", "perintah sistem")
        cmd_preview = reply.get("cmd_preview", "")
        lead_text = (reply.get("lead_text") or "").strip()
        raw_call = reply.get("raw_call")
        danger_reason = reply.get("danger_reason")

        # Model-Driven Contextual Rationale (Zero Canned Templates)
        lead_narration = lead_text
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
        if '"action": "tool_call"' in reply or '<tool_call>' in reply:
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
                cleaned = re.sub(r"```(?:json)?\s*\{[\s\S]*?\"action\"\s*:\s*\"tool_call\"[\s\S]*?\}\s*```", "", reply).strip()
                cleaned = re.sub(r"<tool_call>[\s\S]*?</tool_call>", "", cleaned).strip()
                final_reply = cleaned if (cleaned and '"action": "tool_call"' not in cleaned) else "Tugas sedang diproses dan dianalisis."
        else:
            final_reply = reply.strip()
    else:
        final_reply = "Maaf, respon dari model AI tidak menghasilkan teks atau terputus. Silakan coba tanyakan kembali."

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
            msg = "🔨 Rencana disetujui! Memulai eksekusi Build Mode..."
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback(msg)
            else:
                progress_callback(msg)
        except Exception:
            pass

    system_reminder = (
        "\n\n<system-reminder>\n"
        "Your operational mode has changed from plan to build.\n"
        "You are no longer in read-only mode.\n"
        "You are permitted to make file changes, run shell commands, and utilize your arsenal of tools as needed.\n"
        "</system-reminder>\n"
    )

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
    ) + system_reminder

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
    prior_turns = [h for h in all_history if (h.get("ai_text") or "").strip()]
    dialogue_context = ContextCompactor.compact_history(prior_turns, verbatim_turns=15)

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

        effective_prompt = (
            f"{dialogue_context}"
            f"Tindakan '{t_name}' telah dieksekusi di sistem dengan hasil observasi berikut:\n"
            f"```json\n{json.dumps(tool_res, ensure_ascii=False)}\n```\n\n"
            f"Permintaan asli pengguna: \"{resolved_task}\"\n"
            "Berdasarkan hasil observasi alat di atas, jelaskan laporannya kepada pengguna secara cerdas, ramah, dan tuntas dalam teks percakapan biasa (tanpa format JSON pemanggilan alat)."
        )
    elif dialogue_context:
        effective_prompt = f"{dialogue_context}Pesan User: {resolved_task}"
    else:
        effective_prompt = resolved_task

    reply = await call_universal_chat_model(
        model_id=get_active_model_id(),
        user_prompt=effective_prompt,
        system_instruction=sys_prompt,
        max_tokens=4096,
        temperature=0.6,
        read_only=False,
        progress_cb=_track_tool,
        intercept_mutating_tools=False,
    )

    if isinstance(reply, str):
        cleaned = re.sub(r"```(?:json)?\s*\{[\s\S]*?\"action\"\s*:\s*\"tool_call\"[\s\S]*?\}\s*```", "", reply).strip()
        cleaned = re.sub(r"<tool_call>[\s\S]*?</tool_call>", "", cleaned).strip()
        if not cleaned or '"action": "tool_call"' in cleaned or '<tool_call>' in cleaned:
            final_reply = "Tindakan telah selesai dieksekusi oleh sistem."
        else:
            final_reply = cleaned
    else:
        final_reply = "Eksekusi berhasil diselesaikan."

    memory_engine.log_conversation(
        user_text="",
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
