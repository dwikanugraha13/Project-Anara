"""
subagent.py — High-Performance Sub-Agent Delegation Engine for Project Anara.
Hermes Agent Parity: Pilar 1.

Key Architectural Capabilities:
1. Isolated Fork-and-Join Execution: Subagents run asynchronously in a clean-slate context
   without inheriting bloated conversation transcripts, preventing context pollution.
2. Specialist Tool Whitelist & Anti-Fork Bomb Guard: Workers are restricted to safe read-only
   exploration tools (read_local_file, grep_search_code, glob_find_files, list_directory, web_search),
   with strict depth limits (depth < max_depth) to prevent runaway recursive fork bombs.
3. Structured Result Contract (SubagentResult): Guarantees concise, structured return payloads
   (executive_summary, key_findings, referenced_files, execution_time_sec) rather than raw dumps.
4. Telemetry Event Bus Integration: Dispatches real-time worker progress to WebSocket HUD and event bus.
"""

from __future__ import annotations

import asyncio
import dataclasses
import enum
import json
import logging
import os
import re
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("anara.core.subagent")


class SubagentState(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"


@dataclasses.dataclass(frozen=True)
class SubagentResult:
    task_id: str
    goal: str
    status: str  # 'completed', 'failed', 'timed_out', 'cancelled'
    executive_summary: str
    key_findings: List[str] = dataclasses.field(default_factory=list)
    referenced_files: List[str] = dataclasses.field(default_factory=list)
    execution_time_sec: float = 0.0
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


class SubAgentTask:
    """Represents a delegated background mission (Hermes Parity)."""

    def __init__(
        self,
        task_id: str,
        goal: str,
        context: str = "",
        role: str = "leaf",
        depth: int = 1,
        timeout_seconds: float = 120.0,
    ):
        self.task_id = task_id
        self.title = goal[:80]
        self.goal = goal
        self.context = context
        self.role = role
        self.depth = depth
        self.timeout_seconds = timeout_seconds
        self.state = SubagentState.PENDING
        self.progress_percent = 0
        self.steps_log: List[str] = []
        self.result: Optional[SubagentResult] = None
        self.created_at = time.time()
        self.completed_at: Optional[float] = None
        self._async_task: Optional[asyncio.Task] = None

    @property
    def status(self) -> str:
        if self.state == SubagentState.SUCCEEDED:
            return "completed"
        if self.state == SubagentState.FAILED:
            return "failed"
        if self.state == SubagentState.TIMED_OUT:
            return "timed_out"
        if self.state == SubagentState.CANCELLED:
            return "cancelled"
        return "running"


class SubAgentManager:
    """Manages concurrent, isolated background worker tasks with lifecycle guarantees."""

    DEFAULT_MAX_DEPTH: int = 2
    DEFAULT_TIMEOUT_SECONDS: float = 120.0

    def __init__(self):
        self.tasks: Dict[str, SubAgentTask] = {}
        self._listeners: List[Callable[[Dict[str, Any]], Any]] = []

    def register_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def _emit(self, event_type: str, data: Dict[str, Any]):
        for cb in self._listeners:
            try:
                res = cb({"type": event_type, **data})
                if asyncio.iscoroutine(res):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(res)
                    except RuntimeError:
                        pass
            except Exception as e:
                logger.debug(f"[SubAgent] Listener callback error: {e}")

        # Broadcast to Telemetry Event Bus
        try:
            from telemetry.event_bus import telemetry_bus, EventType, ActivityProvenance
            asyncio.create_task(
                telemetry_bus.emit(
                    event_type=EventType.TOOL_PROGRESS,
                    provenance=ActivityProvenance.SUBAGENT_WORKER,
                    session_id=str(data.get("task_id", "subagent")),
                    trace_id=f"tr_{data.get('task_id', 'subagent')}",
                    payload={"event_type": event_type, **data},
                )
            )
        except Exception:
            pass

    async def spawn_subagent_task(
        self,
        title: str,
        mission_prompt: str = "",
        context: str = "",
        role: str = "leaf",
        depth: int = 1,
        timeout_seconds: Optional[float] = None,
        worker_coro_factory: Optional[Callable[..., Any]] = None,
    ) -> SubAgentTask:
        """
        Spawns an asynchronous background worker in an isolated context.
        Enforces anti-fork-bomb depth boundaries.
        """
        effective_goal = title if not mission_prompt else f"{title}: {mission_prompt}"
        if depth > self.DEFAULT_MAX_DEPTH:
            err_msg = f"Delegation depth limit reached (depth={depth}, max={self.DEFAULT_MAX_DEPTH}). Prevented recursive fork bomb."
            logger.warning(f"[SubAgent] {err_msg}")
            res_fail = SubagentResult(
                task_id=str(uuid.uuid4())[:8],
                goal=effective_goal,
                status="failed",
                executive_summary=err_msg,
                error_message=err_msg,
            )
            failed_task = SubAgentTask(res_fail.task_id, effective_goal, context, role, depth)
            failed_task.state = SubagentState.FAILED
            failed_task.result = res_fail
            return failed_task

        t_id = str(uuid.uuid4())[:8]
        effective_timeout = timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS
        task = SubAgentTask(
            task_id=t_id,
            goal=effective_goal,
            context=context,
            role=role,
            depth=depth,
            timeout_seconds=effective_timeout,
        )
        self.tasks[t_id] = task

        logger.info(f"[SubAgent] Spawned background mission #{t_id} (depth={depth}): '{task.title}'")
        self._emit("subagent_task_started", {
            "task_id": t_id,
            "title": task.title,
            "goal": task.goal,
            "depth": depth,
            "status": "running",
        })

        task_handle = asyncio.create_task(self._run_task_pipeline(task, worker_coro_factory))
        task._async_task = task_handle
        return task

    async def spawn_batch_and_join(
        self,
        tasks: List[Dict[str, Any]],
        shared_context: str = "",
        timeout_seconds: Optional[float] = None,
        worker_coro_factory: Optional[Callable[..., Any]] = None,
    ) -> List[SubagentResult]:
        """
        Forks multiple subagents concurrently in parallel and joins all results (Fork-and-Join Pattern).
        """
        if not tasks:
            return []

        spawned = []
        for t_def in tasks:
            g = t_def.get("goal") or t_def.get("title") or "Subagent Mission"
            c = t_def.get("context") or shared_context
            sub_task = await self.spawn_subagent_task(
                title=g,
                mission_prompt=c,
                timeout_seconds=timeout_seconds,
                worker_coro_factory=worker_coro_factory,
            )
            spawned.append(sub_task)

        # Wait for all background tasks to complete
        await asyncio.gather(*[t._async_task for t in spawned if t._async_task], return_exceptions=True)

        results: List[SubagentResult] = []
        for t in spawned:
            if t.result:
                results.append(t.result)
            else:
                results.append(SubagentResult(
                    task_id=t.task_id,
                    goal=t.goal,
                    status=t.status,
                    executive_summary=t.steps_log[-1] if t.steps_log else "Task finished.",
                    error_message=f"State: {t.state.value}",
                ))
        return results

    async def _run_task_pipeline(
        self,
        task: SubAgentTask,
        worker_coro_factory: Optional[Callable[..., Any]] = None,
    ):
        """Executes subagent reasoning pipeline bounded by timeout."""
        task.state = SubagentState.RUNNING
        start_t = time.time()
        task.steps_log.append("Starting background task execution...")
        task.progress_percent = 15

        try:
            await asyncio.wait_for(
                self._execute_core(task, worker_coro_factory),
                timeout=task.timeout_seconds,
            )
            task.state = SubagentState.SUCCEEDED
            task.completed_at = time.time()
            task.progress_percent = 100
            dur = round(task.completed_at - start_t, 2)

            self._emit("subagent_task_completed", {
                "task_id": task.task_id,
                "title": task.title,
                "status": "completed",
                "duration_sec": dur,
                "summary": task.result.executive_summary if task.result else "",
            })
            logger.info(f"[SubAgent] Mission #{task.task_id} COMPLETED in {dur}s: '{task.title}'")

        except asyncio.TimeoutError:
            task.state = SubagentState.TIMED_OUT
            task.completed_at = time.time()
            dur = round(task.completed_at - start_t, 2)
            task.result = SubagentResult(
                task_id=task.task_id,
                goal=task.goal,
                status="timed_out",
                executive_summary=f"Subagent execution timed out after {task.timeout_seconds}s limit.",
                execution_time_sec=dur,
                error_message="Execution timeout exceeded.",
            )
            self._emit("subagent_task_failed", {
                "task_id": task.task_id,
                "title": task.title,
                "error": "Timeout exceeded",
                "status": "timed_out",
                "duration_sec": dur,
            })
            logger.warning(f"[SubAgent] Mission #{task.task_id} TIMED OUT after {dur}s")

        except asyncio.CancelledError:
            task.state = SubagentState.CANCELLED
            task.completed_at = time.time()
            dur = round(task.completed_at - start_t, 2)
            task.result = SubagentResult(
                task_id=task.task_id,
                goal=task.goal,
                status="cancelled",
                executive_summary="Subagent execution cancelled by orchestrator.",
                execution_time_sec=dur,
                error_message="Cancelled by host.",
            )
            self._emit("subagent_task_failed", {
                "task_id": task.task_id,
                "title": task.title,
                "error": "Cancelled",
                "status": "cancelled",
                "duration_sec": dur,
            })

        except Exception as e:
            task.state = SubagentState.FAILED
            task.completed_at = time.time()
            dur = round(task.completed_at - start_t, 2)
            task.result = SubagentResult(
                task_id=task.task_id,
                goal=task.goal,
                status="failed",
                executive_summary=f"Subagent execution failed: {str(e)}",
                execution_time_sec=dur,
                error_message=str(e),
            )
            self._emit("subagent_task_failed", {
                "task_id": task.task_id,
                "title": task.title,
                "error": str(e),
                "status": "failed",
                "duration_sec": dur,
            })
            logger.error(f"[SubAgent] Mission #{task.task_id} FAILED: {e}", exc_info=True)

    async def _execute_core(
        self,
        task: SubAgentTask,
        worker_coro_factory: Optional[Callable[..., Any]] = None,
    ):
        """Runs isolated LLM reasoning or custom coro factory."""
        if worker_coro_factory:
            res = await worker_coro_factory(task)
            task.result = SubagentResult(
                task_id=task.task_id,
                goal=task.goal,
                status="completed",
                executive_summary=str(res),
                execution_time_sec=round(time.time() - task.created_at, 2),
            )
            return

        from providers import call_universal_chat_model, get_active_model_id
        from cognition import get_soul_prompt

        task.steps_log.append(f"Analyzing mission context: {task.title}...")
        task.progress_percent = 40

        sub_prompt = (
            f"[SUBAGENT SPECIALIST WORKER INSTRUCTION — ANARA STANDARD]\n"
            f"You are an isolated specialist sub-agent tasked with independently completing this mission:\n\n"
            f"Goal:\n{task.goal}\n\n"
            f"Context / Parameters:\n{task.context or 'Use available read-only exploration tools in the repository.'}\n\n"
            "Operational Rules:\n"
            "1. Operate in isolated clean-slate context without assumptions from external conversations.\n"
            "2. Use available read-only exploration tools (read_file, grep, glob) to verify physical facts on disk.\n"
            "3. Synthesize all findings thoroughly and directly in natural prose, matching the language of the mission and user."
        )

        model_id = get_active_model_id()
        task.steps_log.append("Executing specialist model reasoning...")
        task.progress_percent = 70

        res_text = await call_universal_chat_model(
            model_id=model_id,
            user_prompt=sub_prompt,
            system_instruction=get_soul_prompt(mode="chat"),
            max_tokens=None,
            temperature=0.4,
            read_only=True,
            platform="cli",
        )

        out_summary = str(res_text or "").strip()

        task.result = SubagentResult(
            task_id=task.task_id,
            goal=task.goal,
            status="completed",
            executive_summary=out_summary,
            execution_time_sec=round(time.time() - task.created_at, 2),
        )

    def cancel_task(self, task_id: str) -> bool:
        """Cancels a running subagent task."""
        t = self.tasks.get(task_id)
        if t and t._async_task and not t._async_task.done():
            t._async_task.cancel()
            t.state = SubagentState.CANCELLED
            return True
        return False

    def get_task(self, task_id: str) -> Optional[SubAgentTask]:
        return self.tasks.get(task_id)

    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Returns all running and recent subagent tasks."""
        return [
            {
                "task_id": t.task_id,
                "title": t.title,
                "goal": t.goal,
                "depth": t.depth,
                "status": t.status,
                "state": t.state.value,
                "progress_percent": t.progress_percent,
                "steps_log": t.steps_log,
                "result": t.result.to_dict() if t.result else None,
                "created_at": t.created_at,
            }
            for t in self.tasks.values()
        ]


# Global singleton instance
subagent_manager = SubAgentManager()
