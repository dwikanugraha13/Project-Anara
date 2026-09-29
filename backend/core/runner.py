"""
runner.py — Unified ReAct Execution Engine for Project Anara (Anara Standard).
Core Execution Loop & Tool Calling Lifecycle Engine:
1. Dynamic Prompt Assembly & PlatformToolRegistry Progressive Disclosure.
2. Anti-Stall Guard (AnaraLoopBreaker) to prevent infinite ping-pong/repetitive calls.
3. Parameter-Aware Risk Evaluation & Transactional State Machine (PendingAction).
4. Multi-Tool Parallelism: Parallel Read-Only execution via asyncio.gather(), sequential mutating calls.
5. Smart Micro-Compaction (40:60 Head:Tail + disk logging) to protect LLM context windows.
6. Autonomous Inner-Verification / Self-Correction Retrier (up to 3x retry on error).
7. Transport-Agnostic Streaming Events (TurnEvent) for WebSocket, CLI, Telegram, and Background Daemon.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from config import cfg_get
from memory import memory_engine
from core.capabilities import ModelCapabilityRegistry
from core.context_compactor import ContextCompactor
from core.plan_detector import needs_plan, is_explicit_plan_approval, evaluate_command_safety
from core.prompt_assembler import PromptAssembler
from core.session_manager import PendingAction, session_state_manager, ActionState
from providers import (
    call_universal_chat_model,
    get_active_model_id,
)
from telemetry.event_bus import telemetry_bus, EventType, ActivityProvenance
from tools import AnaraLoopBreaker, get_tool_risk

logger = logging.getLogger("anara.core.runner")


@dataclass
class TurnEvent:
    """Standardized event emitted during an agent execution turn."""
    type: str  # "chunk", "thought", "tool_start", "tool_result", "need_approval", "final_text", "error"
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[Any] = None
    thought: Optional[str] = None
    is_error: bool = False
    plan_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTurnResult:
    """Standardized final response payload from a unified agent conversation turn (Anara Enterprise Architecture)."""
    text: str
    session_id: int
    agent_mode: str = "plan"
    plan_pending: bool = False
    plan_id: Optional[str] = None
    tools_used: List[str] = field(default_factory=list)
    token_usage: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    turn_steps: int = 1
    latency_ms: Optional[float] = None
    status: str = "success"
    error_message: Optional[str] = None
    pending_tool_call: Optional[Dict[str, Any]] = None


class AnaraExecutionRunner:
    """
    Unified, stateful conversation & tool execution engine for Project Anara.
    Replaces fragmented runner loops across WebSocket, CLI, Telegram, and Cron.
    """

    def __init__(
        self,
        session_id: Optional[int] = None,
        speaker_name: Optional[str] = None,
        platform: Optional[str] = None,
        max_autonomous_retries: int = 3,
    ):
        self.session_id = session_id
        self.speaker_name = speaker_name
        self.platform = platform or "web_studio"
        self.max_retries = max_autonomous_retries
        self.stall_guard = AnaraLoopBreaker(max_identical=4)
        from tools.self_correction import SelfCorrectionTracker
        self.self_correction_tracker = SelfCorrectionTracker(
            max_retries=5,
            max_identical_failures=5,
            warn_after_exact=2,
            interactive=True
        )
        self.is_interrupted: bool = False
        self._current_task: Optional[asyncio.Task] = None

    def interrupt(self, reason: str = "stop_command") -> None:
        """Interrupts in-flight turn execution immediately (Anara Standard)."""
        self.is_interrupted = True
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        logger.warning(f"[ExecutionRunner] Interrupted runner for session #{self.session_id} (reason: {reason})")

    async def execute_turn_stream(
        self,
        user_message: str,
        requested_mode: str = "plan",
        model_id: Optional[str] = None,
        interaction_mode: str = "chat",
        reasoning_effort: Optional[str] = None,
    ) -> AsyncGenerator[TurnEvent, None]:
        """
        Executes a single multi-step ReAct turn and yields TurnEvents in real-time.
        """
        start_time = time.time()
        self.stall_guard.reset()
        self.self_correction_tracker.reset()
        clean_text = (user_message or "").strip()
        effective_speaker = self.speaker_name or memory_engine.get_last_active_speaker_name() or "User"

        # 1. Resolve Session & Reset Interrupted Flags (Anara Standard)
        effective_sid = self.session_id
        if not effective_sid:
            from core.agent import anara_agent
            effective_sid = anara_agent.get_active_session_id()
        if not effective_sid:
            new_s = memory_engine.create_session(
                speaker_name=effective_speaker,
                title=clean_text[:40] or "New Session",
                session_type="chat",
                session_mode="conversational",
            )
            effective_sid = new_s["id"]
        self.session_id = effective_sid
        self.is_interrupted = False
        session_state_manager.clear_interrupted(self.platform, str(effective_sid))

        # 2. Check Pending Actions State Machine (Anara Autonomous Parity)
        pending = session_state_manager.get_pending(self.platform, str(effective_sid))

        session_obj = memory_engine.get_session(effective_sid)
        session_type = (session_obj.get("session_type") or "chat") if session_obj else "chat"
        session_mode = (
            session_obj.get("session_mode")
            or ("explicit_plan_build" if session_type == "code" else "conversational")
        ) if session_obj else "conversational"

        is_approved = False
        if pending:
            from core.plan_detector import classify_approval_intent
            semantic_intent = await classify_approval_intent(clean_text, pending.plan_text)
            is_approved = (semantic_intent == "approve")
        elif session_mode in ("explicit_plan_build", "plan"):
            from core.plan_detector import classify_approval_intent
            semantic_intent = await classify_approval_intent(clean_text, f"Session mode {session_mode} plan proposal")
            is_approved = (semantic_intent == "approve")

        if pending and is_approved:
            session_state_manager.clear_pending(self.platform, str(effective_sid), final_state=ActionState.APPROVED)
            agent_mode = "build"
            logger.info(f"[ExecutionRunner] Pending action #{pending.plan_id} APPROVED -> switching to BUILD MODE")
            if pending.original_prompt:
                clean_text = f"Approved plan execution for original request: '{pending.original_prompt}'."
        elif requested_mode in ("plan", "build", "conversational"):
            agent_mode = requested_mode
        elif session_mode == "explicit_plan_build":
            agent_mode = "build" if is_approved else "plan"
        elif needs_plan(clean_text, session_mode=session_mode):
            agent_mode = "plan"
        else:
            agent_mode = "conversational" if session_mode == "conversational" else "build"

        # 3. Memory Snapshot is injected into system prompt context; autonomous memory tool handles updates (Anara Standard)

        # 4. Context Compaction (Anara Chronological Alternation)
        try:
            history_rows = memory_engine.get_recent_conversations(limit=30, session_id=effective_sid)
            compacted_history = ContextCompactor.compact_history(history_rows, verbatim_turns=12)
        except Exception as e:
            logger.debug(f"[ExecutionRunner] Context compaction notice: {e}")
            compacted_history = ""

        trace_id = f"tr_{uuid.uuid4().hex[:10]}"
        await telemetry_bus.emit(
            event_type=EventType.SESSION_START,
            provenance=ActivityProvenance.AGENT_ORCHESTRATOR,
            session_id=str(effective_sid),
            trace_id=trace_id,
            payload={"prompt": clean_text, "speaker": effective_speaker, "mode": agent_mode},
        )

        # 5. Assemble System Prompt with Workspace Tree & Scratchpad
        from core.agent import anara_agent
        ws_tree = anara_agent.get_workspace_tree(session_id=effective_sid)
        selected_model = model_id or get_active_model_id()
        system_instruction = PromptAssembler.assemble(
            mode=agent_mode,
            speaker_name=effective_speaker,
            workspace_tree=ws_tree,
            is_chat_mode=(session_type != "code"),
            session_type=session_type,
            user_task=clean_text,
            channel=self.platform,
            session_id=effective_sid,
            model_id=selected_model,
        )

        from memory.memory_nudge import memory_nudge_manager
        nudge_instruction = memory_nudge_manager.increment_and_get_nudge(effective_sid)
        if nudge_instruction:
            system_instruction += f"\n\n{nudge_instruction}"

        full_user_input = f"{compacted_history}User: {clean_text}" if compacted_history else clean_text
        tools_used: List[str] = []
        turn_tool_records: List[Dict[str, Any]] = []

        # Yield initial execution context (dynamic without canned deception)
        yield TurnEvent(
            type="thought",
            content=f"Processing request in {agent_mode.upper()} mode with model {selected_model}...",
            metadata={"mode": agent_mode, "model": selected_model},
        )

        # 6. ReAct Execution with Asynchronous Event Streaming
        event_queue: asyncio.Queue[TurnEvent] = asyncio.Queue()

        def _progress_cb(evt: Dict[str, Any]):
            t_name = evt.get("tool_name", "")
            t_args = evt.get("args") or evt.get("tool_args") or {}
            t_status = evt.get("status") or ""
            t_summary = evt.get("summary") or evt.get("detail") or ""

            if t_name and t_name != "agent" and t_name not in tools_used:
                tools_used.append(t_name)

            # Active Anti-Stall Guard (Anara Enterprise Architecture)
            if t_status == "running" and t_name:
                try:
                    self.stall_guard.check(t_name, t_args)
                except Exception as e_sg:
                    logger.warning(f"[ExecutionRunner] Stall guard warning: {e_sg}")

            if t_status == "running":
                call_id = evt.get("call_id") or f"call_{uuid.uuid4().hex[:12]}"
                evt["call_id"] = call_id
                try:
                    session_state_manager.persist_tool_call_start(
                        session_id=effective_sid,
                        channel=self.platform,
                        channel_id=str(effective_sid),
                        tool_name=t_name,
                        tool_args=t_args,
                        call_id=call_id
                    )
                except Exception as e_pers:
                    logger.debug(f"[ExecutionRunner] Tool persist start notice: {e_pers}")

                turn_tool_records.append({
                    "call_id": call_id,
                    "tool_name": t_name,
                    "tool_args": t_args,
                    "status": "running",
                    "timestamp": time.time(),
                })
                event_queue.put_nowait(TurnEvent(
                    type="tool_start",
                    tool_name=t_name,
                    tool_args=t_args,
                    content=evt.get("detail") or "",
                    metadata=evt,
                ))
            elif t_status == "done":
                call_id = evt.get("call_id")
                if not call_id and turn_tool_records:
                    for rec in reversed(turn_tool_records):
                        if rec.get("tool_name") == t_name and rec.get("status") == "running":
                            call_id = rec.get("call_id")
                            break
                if call_id:
                    try:
                        session_state_manager.persist_tool_call_result(
                            call_id=call_id,
                            result_summary=t_summary,
                            is_error=bool(evt.get("is_error", False))
                        )
                    except Exception as e_pers_res:
                        logger.debug(f"[ExecutionRunner] Tool persist result notice: {e_pers_res}")

                turn_tool_records.append({
                    "call_id": call_id,
                    "tool_name": t_name,
                    "tool_result": t_summary,
                    "status": "done",
                    "timestamp": time.time(),
                })
                # Active self-correction tracker
                try:
                    self.self_correction_tracker.record_tool_call(t_name, t_args, t_summary)
                except Exception:
                    pass

                event_queue.put_nowait(TurnEvent(
                    type="tool_result",
                    tool_name=t_name,
                    tool_args=t_args,
                    tool_result=t_summary,
                    content=t_summary,
                    metadata=evt,
                ))

        def _token_cb(token: str):
            if token:
                event_queue.put_nowait(TurnEvent(
                    type="chunk",
                    content=token,
                ))

        # Run model execution task in background to allow event queue streaming
        intercept_mutating = (agent_mode == "plan")
        model_task = asyncio.create_task(
            call_universal_chat_model(
                model_id=selected_model,
                user_prompt=full_user_input,
                system_instruction=system_instruction,
                max_tokens=None,
                temperature=float(cfg_get("agent.generation.temperature", 0.7)),
                read_only=(agent_mode == "plan"),
                progress_cb=_progress_cb,
                token_cb=_token_cb,
                intercept_mutating_tools=intercept_mutating,
                platform=self.platform,
                reasoning_effort=reasoning_effort,
            )
        )
        self._current_task = model_task

        # Stream events as they arrive while task runs
        while not model_task.done() or not event_queue.empty():
            if self.is_interrupted or session_state_manager.is_interrupted(self.platform, str(effective_sid)):
                model_task.cancel()
                yield TurnEvent(type="error", content="Task stopped by user.", is_error=True)
                return
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=0.05)
                yield event
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

        # Check model task result
        try:
            model_res = await model_task
        except Exception as e:
            logger.error(f"[ExecutionRunner] Model error: {e}", exc_info=True)
            yield TurnEvent(
                type="error",
                content=f"Error processing request: {e}",
                is_error=True,
            )
            return

        # 7. Check if Turn Was Intercepted for Plan Mode Approval
        if isinstance(model_res, dict) and model_res.get("intercepted"):
            plan_id = f"plan_{uuid.uuid4().hex[:8]}"
            t_name = model_res.get("tool_name", "")
            t_args = model_res.get("tool_args", {})
            lead = model_res.get("lead_text", "")

            # Model-Driven Contextual Rationale (Zero Canned Templates)
            from core.channel_adapter import synthesize_action_rationale, UniversalChannelAdapter
            lead_narration = lead
            if not lead_narration:
                lead_narration = await synthesize_action_rationale(
                    tool_name=t_name,
                    tool_args=t_args,
                    prompt=clean_text
                )

            pending_act = PendingAction(
                plan_id=plan_id,
                session_id=effective_sid,
                channel=self.platform,
                channel_id=str(effective_sid),
                tool_name=t_name,
                tool_args=t_args,
                original_prompt=clean_text,
                plan_text=lead_narration,
                lead_narration=lead_narration,
                risk_level=model_res.get("tool_risk") or "mutating",
                status="pending",
                user_id=effective_speaker,
                pending_tool_call=model_res.get("raw_call"),
            )
            session_state_manager.store_pending(pending_act)

            # Record pure natural narrative to session memory — ZERO UI tags
            try:
                memory_engine.log_conversation(
                    user_text=clean_text,
                    ai_text=lead_narration,
                    speaker_name=effective_speaker,
                    session_id=effective_sid,
                )
            except Exception:
                pass

            rendered = UniversalChannelAdapter.render_approval_payload(
                channel=self.platform,
                narration=lead_narration,
                action=pending_act
            )

            yield TurnEvent(
                type="need_approval",
                tool_name=t_name,
                tool_args=t_args,
                thought=lead_narration,
                plan_id=plan_id,
                content=lead_narration,
                metadata=rendered,
            )
            return

        final_reply = model_res if isinstance(model_res, str) else str(model_res or "")
        duration = round(time.time() - start_time, 2)

        # 8. Negative Verification Stop-Gate (Claude Code stopHooks & Anara Standard)
        if tools_used and agent_mode == "build":
            try:
                from core.convergence import ConvergenceDetector
                from tools import get_tool_risk
                conv_detector = ConvergenceDetector(read_only=False)
                for step_idx, rec in enumerate(turn_tool_records):
                    if rec.get("status") == "done":
                        t_name = rec.get("tool_name", "")
                        conv_detector.record_turn_actions(step_idx, [{
                            "tool_name": t_name,
                            "args": rec.get("tool_args", {}),
                            "risk": get_tool_risk(t_name),
                            "summary": rec.get("tool_result", ""),
                            "is_error": False,
                        }])
                stop_gate_nudge = conv_detector.evaluate_final_stop_gate(agent_mode="build")
                if stop_gate_nudge:
                    logger.info(f"[ExecutionRunner] Verification stop-gate activated: {stop_gate_nudge[:80]}...")
                    final_reply = f"{final_reply}\n\n{stop_gate_nudge}"
            except Exception as e_conv:
                logger.debug(f"[ExecutionRunner] Stop-gate notice: {e_conv}")

        # 9. Record Final AI Response with Execution Audit (Anara Persist Parity)
        turn_visual_data = {
            "tools_used": tools_used,
            "tool_records_count": len(turn_tool_records),
            "mode": agent_mode,
            "duration": duration,
        }
        try:
            memory_engine.log_conversation(
                user_text=clean_text,
                ai_text=final_reply,
                speaker_name=effective_speaker,
                session_id=effective_sid,
                visual_data=turn_visual_data,
            )
        except Exception as e:
            logger.debug(f"[ExecutionRunner] Conversation log save notice: {e}")

        await telemetry_bus.emit(
            event_type=EventType.SESSION_FINISH,
            provenance=ActivityProvenance.AGENT_ORCHESTRATOR,
            session_id=str(effective_sid),
            trace_id=trace_id,
            payload={"status": "completed", "duration_seconds": duration, "tools_used": tools_used},
        )

        try:
            from memory.chat_sessions import maybe_auto_title_session
            asyncio.create_task(maybe_auto_title_session(effective_sid, clean_text, final_reply))
        except Exception:
            pass

        # Lifelong Learning Loop: extract reusable procedural skills from successful runs (Anara Standard)
        if tools_used and agent_mode == "build":
            try:
                from core.skill_extractor import SkillExtractor
                asyncio.create_task(SkillExtractor.extract_and_save_skill_async(
                    user_prompt=clean_text,
                    tools_used=tools_used,
                    final_summary=final_reply,
                ))
            except Exception:
                pass

        yield TurnEvent(
            type="final_text",
            content=final_reply,
            metadata={"session_id": effective_sid, "duration": duration, "tools_used": tools_used},
        )

    async def execute_turn(
        self,
        user_message: str,
        requested_mode: str = "plan",
        model_id: Optional[str] = None,
        stream_callback: Optional[Callable[[str], Any]] = None,
        tool_progress_callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
        thinking_callback: Optional[Callable[[str], Any]] = None,
    ) -> AgentTurnResult:
        """
        Executes a turn and returns a consolidated AgentTurnResult.
        """
        start_time = time.time()
        final_text = ""
        tools_used: List[str] = []
        plan_pending = False
        plan_id = None
        pending_tool_call = None
        error_msg = None

        if not self.session_id:
            from core.agent import anara_agent
            self.session_id = anara_agent.get_active_session_id()
        if not self.session_id:
            effective_speaker = self.speaker_name or memory_engine.get_last_active_speaker_name() or "User"
            new_s = memory_engine.create_session(
                speaker_name=effective_speaker,
                title=(user_message or "").strip()[:40] or "New Session",
                session_type="chat",
                session_mode="conversational",
            )
            self.session_id = new_s["id"]

        sid_lock_key = str(self.session_id)
        async with session_state_manager.get_session_lock(sid_lock_key):
            async for event in self.execute_turn_stream(user_message, requested_mode=requested_mode, model_id=model_id):
                if event.type == "chunk":
                    if stream_callback and event.content:
                        res = stream_callback(event.content)
                        if asyncio.iscoroutine(res):
                            await res
                elif event.type == "thought":
                    if thinking_callback and event.content:
                        res = thinking_callback(event.content)
                        if asyncio.iscoroutine(res):
                            await res
                elif event.type in ("tool_start", "tool_result"):
                    if event.tool_name and event.tool_name not in tools_used:
                        tools_used.append(event.tool_name)
                    if tool_progress_callback:
                        res = tool_progress_callback({
                            "tool_name": event.tool_name,
                            "status": "running" if event.type == "tool_start" else "done",
                            "summary": event.content or "",
                        })
                        if asyncio.iscoroutine(res):
                            await res
                elif event.type == "need_approval":
                    plan_pending = True
                    plan_id = event.plan_id
                    pending_tool_call = {"tool": event.tool_name, "arguments": event.tool_args}
                    final_text = event.thought or event.content or "Approval required."
                elif event.type == "final_text":
                    final_text = event.content or ""
                elif event.type == "error":
                    error_msg = event.content

        duration = round(time.time() - start_time, 2)
        return AgentTurnResult(
            text=final_text,
            session_id=self.session_id or 0,
            agent_mode=requested_mode,
            plan_pending=plan_pending,
            plan_id=plan_id,
            tools_used=tools_used,
            duration_seconds=duration,
            turn_steps=len(tools_used) + 1,
            latency_ms=round(duration * 1000.0, 1),
            status="error" if error_msg else "success",
            error_message=error_msg,
            pending_tool_call=pending_tool_call,
        )
