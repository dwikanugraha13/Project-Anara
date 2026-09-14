"""
channel_adapter.py — Multi-Channel Request Normalization & Execution Gateway.
Implements FR-8, FR-9, FR-10 from prd-general-agent.md & Bab 4/12 from rancangan-general-agent.md.

Normalizes requests from Telegram, CLI, WhatsApp, Web, and Scheduler into a uniform
internal request format, routing through Unified Plan Detector and Permission Gate.
"""
import asyncio
import json
import logging
import uuid
from typing import Dict, List, Any, Optional, Callable
from pydantic import BaseModel, Field

from memory import memory_engine, file_memory
from core.plan_detector import needs_plan, is_explicit_plan_approval
from core.prompt_assembler import PromptAssembler
from core.skill_library import skill_library
from providers import call_universal_chat_model, get_active_model_id

logger = logging.getLogger(__name__)

# Active pending plans memory store: plan_id -> plan_metadata
_PENDING_PLANS: Dict[str, Dict[str, Any]] = {}


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
    status: str = "success"
    error: Optional[str] = None


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


async def process_channel_request(
    req: ChannelRequest,
    progress_callback: Optional[Callable[[str], Any]] = None
) -> ChannelResponse:
    """
    Core entrypoint for all non-web channels (Telegram, CLI, WhatsApp, Schedulers).
    Enforces Plan/Build safety gate and routes back to channel.
    """
    logger.info(f"[ChannelGateway] Incoming request from {req.channel} (user={req.user_id}): {req.text[:50]!r}")

    # 1. Resolve Session
    session_id = get_or_create_channel_session(req)

    # 2. Log User Turn & Trigger Memory Detection
    memory_engine.log_conversation(
        user_text=req.text,
        ai_text="",
        speaker_name=req.sender_name,
        session_id=session_id
    )
    file_memory.detect_and_record_memory(req.text, speaker_name=req.sender_name)

    # 3. Check for Plan Approval keywords
    clean_text = req.text.strip()
    is_approval = is_explicit_plan_approval(clean_text)

    # 4. Check if this request needs a plan
    requires_plan = needs_plan(clean_text, session_mode="conversational")

    # Check if there is an existing pending plan waiting in this session
    session_plan_key = f"{req.channel}_{req.channel_id}"
    active_pending = _PENDING_PLANS.get(session_plan_key)

    # ── CASE A: User is approving a previously pending plan ──
    if is_approval and active_pending:
        plan_id = active_pending["plan_id"]
        logger.info(f"[ChannelGateway] User approved pending plan #{plan_id} via text. Executing BUILD MODE...")
        del _PENDING_PLANS[session_plan_key]

        return await _execute_build_mode(
            session_id=session_id,
            user_prompt=f"Eksekusi rencana: {active_pending['original_prompt']}",
            req=req,
            progress_callback=progress_callback
        )

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

        # Store pending plan
        _PENDING_PLANS[session_plan_key] = {
            "plan_id": plan_id,
            "session_id": session_id,
            "original_prompt": clean_text,
            "plan_text": plan_text,
            "user_id": req.user_id,
        }

        # Log AI Plan Proposal
        memory_engine.log_conversation(
            user_text="",
            ai_text=plan_text,
            speaker_name=req.sender_name,
            session_id=session_id
        )

        return ChannelResponse(
            text=plan_text or "Saya telah menyusun rencana. Silakan setujui untuk mulai eksekusi.",
            session_id=session_id,
            mode="plan",
            plan_pending=True,
            plan_id=plan_id,
            status="pending_approval"
        )

    # ── CASE C: Casual Chat / Read-Only / Safe Action -> Direct Answer ──
    sys_prompt = PromptAssembler.assemble(
        mode="build",
        speaker_name=req.sender_name,
        is_chat_mode=True,
        session_type="chat"
    )

    tools_used: List[str] = []

    def _track_tool(evt: Dict[str, Any]):
        t_name = evt.get("tool_name")
        if t_name and t_name not in tools_used:
            tools_used.append(t_name)
        if progress_callback:
            msg = f"🔧 Menjalankan {t_name}..."
            try:
                if asyncio.iscoroutinefunction(progress_callback):
                    asyncio.create_task(progress_callback(msg))
                else:
                    progress_callback(msg)
            except Exception:
                pass

    reply = await call_universal_chat_model(
        model_id=get_active_model_id(),
        user_prompt=clean_text,
        system_instruction=sys_prompt,
        max_tokens=800,
        temperature=0.7,
        read_only=False,
        progress_cb=_track_tool
    )

    final_reply = reply or "Pesan Anda telah diterima oleh Anara."

    memory_engine.log_conversation(
        user_text="",
        ai_text=final_reply,
        speaker_name=req.sender_name,
        session_id=session_id
    )

    return ChannelResponse(
        text=final_reply,
        session_id=session_id,
        mode="conversational",
        plan_pending=False,
        tools_used=tools_used,
        status="success"
    )


async def _execute_build_mode(
    session_id: int,
    user_prompt: str,
    req: ChannelRequest,
    progress_callback: Optional[Callable[[str], Any]] = None
) -> ChannelResponse:
    """Executes the approved plan in Build Mode with tool tracking."""
    if progress_callback:
        try:
            msg = "🔨 Rencana disetujui! Memulai eksekusi Build Mode..."
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback(msg)
            else:
                progress_callback(msg)
        except Exception:
            pass

    sys_prompt = PromptAssembler.assemble(
        mode="build",
        speaker_name=req.sender_name,
        is_chat_mode=True,
        session_type="chat"
    )

    tools_used: List[str] = []

    def _track_tool(evt: Dict[str, Any]):
        t_name = evt.get("tool_name")
        if t_name and t_name not in tools_used:
            tools_used.append(t_name)
        if progress_callback:
            msg = f"⚙️ {t_name}: {evt.get('status', 'running')}"
            try:
                if asyncio.iscoroutinefunction(progress_callback):
                    asyncio.create_task(progress_callback(msg))
                else:
                    progress_callback(msg)
            except Exception:
                pass

    reply = await call_universal_chat_model(
        model_id=get_active_model_id(),
        user_prompt=user_prompt,
        system_instruction=sys_prompt,
        max_tokens=1000,
        temperature=0.6,
        read_only=False,
        progress_cb=_track_tool
    )

    final_reply = reply or "Eksekusi berhasil diselesaikan."

    memory_engine.log_conversation(
        user_text="",
        ai_text=final_reply,
        speaker_name=req.sender_name,
        session_id=session_id
    )

    return ChannelResponse(
        text=final_reply,
        session_id=session_id,
        mode="build",
        plan_pending=False,
        tools_used=tools_used,
        status="success"
    )


def resolve_pending_plan_callback(plan_id: str, action: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Resolves an inline callback (e.g. Telegram button click) for a plan."""
    for key, data in list(_PENDING_PLANS.items()):
        if data["plan_id"] == plan_id:
            del _PENDING_PLANS[key]
            return data
    return None
