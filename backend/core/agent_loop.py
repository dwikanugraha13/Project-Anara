"""
agent_loop.py — Transport-Agnostic Core ReAct Turn Loop for Project Anara.
Full parity with Hermes Agent agent/conversation_loop.py & run_agent.py:
Provides a single, decoupled agent turn execution engine reusable across
WebSocket, CLI REPL, Telegram, WhatsApp, Discord, Slack, and Background Cron tasks.
"""

import asyncio
from dataclasses import dataclass, field
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from config import cfg_get
from memory import memory_engine
from core.capabilities import ModelCapabilityRegistry
from core.context_compactor import ContextCompactor
from core.plan_detector import needs_plan, is_explicit_plan_approval
from core.prompt_assembler import PromptAssembler
from providers import call_universal_chat_model, stream_universal_chat_model, get_active_model_id
from telemetry.event_bus import telemetry_bus, EventType, ActivityProvenance

logger = logging.getLogger(__name__)


@dataclass
class AgentTurnResult:
    """Standardized response payload from a unified agent conversation turn."""
    text: str
    session_id: int
    agent_mode: str = "plan"
    plan_pending: bool = False
    plan_id: Optional[str] = None
    tools_used: List[str] = field(default_factory=list)
    token_usage: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    status: str = "success"
    error_message: Optional[str] = None


async def run_agent_turn(
    user_text: str,
    session_id: Optional[int] = None,
    speaker_name: Optional[str] = None,
    requested_mode: str = "plan",
    model_id: Optional[str] = None,
    stream_callback: Optional[Callable[[str], Any]] = None,
    tool_progress_callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
    thinking_callback: Optional[Callable[[str], Any]] = None,
) -> AgentTurnResult:
    """
    Executes a single unified ReAct conversation turn (Anara Standard).
    Transport-agnostic: Works natively across WebSocket, CLI, Telegram, WhatsApp, Discord, Slack, and Cron.
    """
    start_time = time.time()
    clean_text = (user_text or "").strip()
    effective_speaker = speaker_name or memory_engine.get_last_active_speaker_name() or "User"

    # 1. Resolve Session
    effective_sid = session_id
    if not effective_sid:
        from core.agent import anara_agent
        effective_sid = anara_agent.get_active_session_id()
    if not effective_sid:
        new_s = memory_engine.create_session(
            speaker_name=effective_speaker,
            title=clean_text[:40] or "New Session",
            session_type="chat",
            session_mode="conversational"
        )
        effective_sid = new_s["id"]

    # 2. Resolve Agent Mode (Plan vs Build)
    session_obj = memory_engine.get_session(effective_sid)
    session_type = (session_obj.get("session_type") or "chat") if session_obj else "chat"
    session_mode = (session_obj.get("session_mode") or ("explicit_plan_build" if session_type == "code" else "conversational")) if session_obj else "conversational"

    norm_text = clean_text.lower()
    is_approved = is_explicit_plan_approval(norm_text)

    if session_mode == "explicit_plan_build":
        if is_approved:
            agent_mode = "build"
        else:
            agent_mode = requested_mode if requested_mode in ("plan", "build") else "plan"
    else:
        if is_approved:
            agent_mode = "build"
        elif needs_plan(clean_text, session_mode="conversational"):
            agent_mode = "plan"
        else:
            agent_mode = "build"

    # 3. Optimistic Conversation Log
    try:
        memory_engine.log_conversation(
            user_text=clean_text,
            ai_text="",
            speaker_name=effective_speaker,
            session_id=effective_sid
        )
        from memory import file_memory
        file_memory.detect_and_record_memory(clean_text, speaker_name=effective_speaker)
    except Exception as e:
        logger.debug(f"[AgentLoop] Optimistic log notice: {e}")

    # 4. Context Compaction & History Gathering
    try:
        history_rows = memory_engine.get_conversation_history(limit=30, session_id=effective_sid)
        compacted_history = ContextCompactor.compact_history(history_rows, verbatim_turns=12)
    except Exception as e:
        logger.debug(f"[AgentLoop] Context compaction notice: {e}")
        compacted_history = ""

    trace_id = f"tr_{uuid.uuid4().hex[:10]}"

    # Emit telemetry: Session Turn Start
    await telemetry_bus.emit(
        event_type=EventType.SESSION_START,
        provenance=ActivityProvenance.AGENT_ORCHESTRATOR,
        session_id=str(effective_sid),
        trace_id=trace_id,
        payload={"prompt": clean_text, "speaker": effective_speaker, "mode": agent_mode}
    )

    # 5. Assemble Structured 3-Tier System Prompt with Working Scratchpad
    from core.agent import anara_agent
    ws_tree = anara_agent.get_workspace_tree(session_id=effective_sid)
    system_instruction = PromptAssembler.assemble(
        mode=agent_mode,
        speaker_name=effective_speaker,
        workspace_tree=ws_tree,
        is_chat_mode=True,
        session_type=session_type,
        user_task=clean_text,
        session_id=effective_sid,
    )

    # Autonomous Turn Nudge (Anara Standard: turn % 10 -> memory, turn % 15 -> skill)
    from cognition.memory_nudge import memory_nudge_manager
    nudge_instruction = memory_nudge_manager.increment_and_get_nudge(effective_sid)
    if nudge_instruction:
        system_instruction += f"\n\n{nudge_instruction}"

    full_user_input = f"{compacted_history}User: {clean_text}" if compacted_history else clean_text
    selected_model = model_id or get_active_model_id()
    tools_used: List[str] = []

    def _tool_cb(evt: Dict[str, Any]):
        t_name = evt.get("tool_name")
        if t_name and t_name not in tools_used:
            tools_used.append(t_name)
        if tool_progress_callback:
            res = tool_progress_callback(evt)
            if asyncio.iscoroutine(res):
                asyncio.create_task(res)
        asyncio.create_task(
            telemetry_bus.emit(
                event_type=EventType.TOOL_PROGRESS,
                provenance=ActivityProvenance.TOOL_RUNNER,
                session_id=str(effective_sid),
                trace_id=trace_id,
                payload={"tool_name": t_name, "status": evt.get("status") or "running"},
            )
        )

    if thinking_callback:
        res_th = thinking_callback("Merumuskan pemikiran dan strategi..." if agent_mode == "plan" else "Mempersiapkan tindakan...")
        if asyncio.iscoroutine(res_th):
            asyncio.create_task(res_th)

    # Emit telemetry: Reasoning Start
    await telemetry_bus.emit(
        event_type=EventType.REASONING_START,
        provenance=ActivityProvenance.REASONING_ENGINE,
        session_id=str(effective_sid),
        trace_id=trace_id,
        payload={"status": "evaluating_context", "model": selected_model}
    )

    # 6. Execute Model with Autonomous Tool Loop
    try:
        reply_text = await call_universal_chat_model(
            model_id=selected_model,
            user_prompt=full_user_input,
            system_instruction=system_instruction,
            max_tokens=None,
            temperature=float(cfg_get("agent.generation.temperature", 0.7)),
            read_only=(agent_mode == "plan"),
            progress_cb=_tool_cb,
            token_cb=stream_callback
        )
    except Exception as e:
        logger.error(f"[AgentLoop] Model execution error: {e}")
        await telemetry_bus.emit(
            event_type=EventType.ERROR,
            provenance=ActivityProvenance.AGENT_ORCHESTRATOR,
            session_id=str(effective_sid),
            trace_id=trace_id,
            payload={"error_message": str(e)}
        )
        return AgentTurnResult(
            text=f"Terjadi kesalahan saat memproses permintaan: {e}",
            session_id=effective_sid,
            agent_mode=agent_mode,
            status="error",
            error_message=str(e),
            duration_seconds=round(time.time() - start_time, 2)
        )

    # 7. Finalize and Record AI Response
    duration = round(time.time() - start_time, 2)
    try:
        memory_engine.log_conversation(
            user_text=clean_text,
            ai_text=reply_text,
            speaker_name=effective_speaker,
            session_id=effective_sid
        )
    except Exception:
        pass

    # Emit telemetry: Session Turn Finish
    await telemetry_bus.emit(
        event_type=EventType.SESSION_FINISH,
        provenance=ActivityProvenance.AGENT_ORCHESTRATOR,
        session_id=str(effective_sid),
        trace_id=trace_id,
        payload={"status": "completed", "duration_seconds": duration, "tools_used": tools_used}
    )

    # Background async title generation if session has no title yet
    try:
        from memory.chat_sessions import maybe_auto_title_session
        asyncio.create_task(maybe_auto_title_session(effective_sid, clean_text, reply_text))
    except Exception:
        pass

    return AgentTurnResult(
        text=reply_text,
        session_id=effective_sid,
        agent_mode=agent_mode,
        tools_used=tools_used,
        duration_seconds=duration,
        status="success"
    )
