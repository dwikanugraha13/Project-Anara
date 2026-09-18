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
    Core entrypoint for all non-web channels (Telegram, CLI, WhatsApp, Schedulers).
    Enforces Plan/Build safety gate and routes back to channel.
    """
    logger.info(f"[ChannelGateway] Incoming request from {req.channel} (user={req.user_id}): {req.text[:50]!r}")
    from tools.artifact_tools import clear_turn_artifacts, get_turn_artifacts
    clear_turn_artifacts()

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

    # 4. Check for Plan Approval keywords and Session State Machine
    session_plan_key = f"{req.channel}_{req.channel_id}"
    intent_state = session_state_manager.evaluate_intent(clean_text, req.channel, req.channel_id)
    is_approval = intent_state["is_approval"] or is_explicit_plan_approval(clean_text)

    # Check active pending action
    active_pending = intent_state["pending"] or _PENDING_PLANS.get(session_plan_key)

    # ── CASE A: User is approving a previously pending plan ──
    if is_approval and active_pending:
        plan_id = active_pending.plan_id if isinstance(active_pending, PendingAction) else active_pending.get("plan_id")
        orig_prompt = active_pending.original_prompt if isinstance(active_pending, PendingAction) else active_pending.get("original_prompt")
        pending_tool = active_pending.pending_tool_call if isinstance(active_pending, PendingAction) else active_pending.get("pending_tool_call")
        plan_dict = active_pending.to_dict() if isinstance(active_pending, PendingAction) else active_pending

        logger.info(f"[ChannelGateway] User approved pending action #{plan_id} via text ('{clean_text}'). Executing BUILD MODE...")
        session_state_manager.clear_pending(req.channel, req.channel_id)
        _PENDING_PLANS.pop(session_plan_key, None)

        return await _execute_build_mode(
            session_id=session_id,
            user_prompt=f"Eksekusi rencana: {orig_prompt}",
            req=req,
            progress_callback=progress_callback,
            pending_tool_call=pending_tool,
            plan=plan_dict,
        )

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
            user_id=req.user_id,
        )
        session_state_manager.store_pending(pending_act)
        _PENDING_PLANS[session_plan_key] = pending_act.to_dict()

        # Log AI Plan Proposal
        memory_engine.log_conversation(
            user_text=clean_text,
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

    # ── CASE C: Direct Execution with Dynamic Runtime Tool Interception Gate ──
    from core.context_compactor import ContextCompactor
    from core.agent import anara_agent
    all_history = memory_engine.get_recent_conversations(
        limit=25,
        speaker_name=req.sender_name,
        session_id=session_id
    )
    prior_turns = [h for h in all_history if (h.get("ai_text") or "").strip()]
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
            msg = f"🔧 Menjalankan {t_name}..."
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

    # ── TOOL INTERCEPTION GATE (Zero-Regex Security) ──
    # If the model attempted to invoke a mutating or ask tool without prior user approval,
    # intercept the execution in real-time, generate the Plan Card, and request user approval.
    if isinstance(reply, dict) and reply.get("intercepted"):
        plan_id = str(uuid.uuid4())[:8]
        tool_name = reply.get("tool_name", "perintah sistem")
        cmd_preview = reply.get("cmd_preview", "")
        lead_text = (reply.get("lead_text") or "").strip()
        raw_call = reply.get("raw_call")
        danger_reason = reply.get("danger_reason")

        proposal_parts = []
        if lead_text:
            proposal_parts.append(lead_text)
        elif danger_reason:
            proposal_parts.append(f"Tindakan ini memerlukan konfirmasimu ({danger_reason}):")
        else:
            proposal_parts.append(f"Untuk menyelesaikan tugas ini, aku akan menjalankan tindakan <code>{tool_name}</code> di komputermu:")

        if cmd_preview:
            proposal_parts.append(f"<pre><code>{cmd_preview}</code></pre>")

        proposal_text = "\n\n".join(proposal_parts)

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
            plan_text=proposal_text,
            user_id=req.user_id,
        )
        session_state_manager.store_pending(pending_act)
        _PENDING_PLANS[session_plan_key] = pending_act.to_dict()

        memory_engine.log_conversation(
            user_text=clean_text,
            ai_text=proposal_text,
            speaker_name=req.sender_name,
            session_id=session_id
        )

        return ChannelResponse(
            text=proposal_text,
            session_id=session_id,
            mode="plan",
            plan_pending=True,
            plan_id=plan_id,
            status="pending_approval"
        )

    if isinstance(reply, str) and reply.strip():
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
            msg = f"⚙️ {t_name}: {evt.get('status', 'running')}"
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
        t_args = pending_tool_call.get("arguments", {})
        effective_prompt = (
            f"{dialogue_context}"
            f"Pengguna telah menyetujui eksekusi tindakan berikut:\n"
            f"• Alat: {t_name}\n"
            f"• Parameter: {json.dumps(t_args, ensure_ascii=False)}\n"
            f"Permintaan asli pengguna: \"{resolved_task}\"\n\n"
            f"Jalankan tindakan di atas menggunakan alat yang tersedia, dan laporkan hasilnya secara tuntas."
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

    final_reply = reply if isinstance(reply, str) else "Eksekusi berhasil diselesaikan."

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
