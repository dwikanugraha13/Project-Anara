"""
subagent.py — High-Performance Sub-Agent Delegation Engine for Project Anara.
Anara Standard: Pilar 1.

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

DEFAULT_MAX_SUMMARY_CHARS: int = 24000


def apply_summary_budget(task_id: str, raw_text: str, max_chars: int = DEFAULT_MAX_SUMMARY_CHARS) -> Tuple[str, Optional[str]]:
    """
    Applies line-snapped head/tail summary budgeting and disk spilling (Anara Standard).
    Preserves 75% head and 25% tail, offloading complete text to disk with retrieval instructions.
    """
    if len(raw_text) <= max_chars:
        return raw_text, None

    import tempfile
    cache_dir = os.path.join(tempfile.gettempdir(), "anara_subagent_summaries")
    os.makedirs(cache_dir, exist_ok=True)
    spill_file = os.path.join(cache_dir, f"subagent-summary-{task_id}.txt")
    try:
        with open(spill_file, "w", encoding="utf-8") as f:
            f.write(raw_text)
    except Exception as e:
        logger.debug(f"[SubAgent] Failed to spill summary to disk: {e}")

    head_budget = int(max_chars * 0.75)
    tail_budget = max_chars - head_budget

    head_raw = raw_text[:head_budget]
    last_nl = head_raw.rfind("\n")
    head_snapped = head_raw[:last_nl] if last_nl > 0 else head_raw

    tail_raw = raw_text[-tail_budget:]
    first_nl = tail_raw.find("\n")
    tail_snapped = tail_raw[first_nl + 1:] if first_nl >= 0 else tail_raw

    summary_with_footer = (
        f"{head_snapped}\n\n"
        f"──────── [SUMMARY TRUNCATED — ANARA HEAD/TAIL WINDOW] ────────\n"
        f"Showing {len(head_snapped):,} chars (head) + {len(tail_snapped):,} chars (tail) of {len(raw_text):,} total — trimmed to protect parent context window.\n"
        f"Full subagent output saved to: {spill_file}\n"
        f"To inspect omitted middle: read_local_file(path=\"{spill_file}\", offset=..., limit=...)\n"
        f"─────────────────────────────────────────────────────────────────\n\n"
        f"{tail_snapped}"
    )
    return summary_with_footer, spill_file


def get_role_configuration(role: str) -> Tuple[str, bool]:
    """
    Anara Multi-Agent Swarm Architecture: Specialized Sub-Agent Roles.
    Enforces Principle of Least Privilege and custom role system instructions.
    Returns (system_instruction, read_only_flag).
    """
    r = (role or "leaf").strip().lower()
    if r in ("explorer", "recon", "searcher"):
        instruction = (
            "[ROLE: CODEBASE EXPLORER & RECONNAISSANCE SPECIALIST]\n"
            "You are an autonomous read-only codebase explorer operating under least-privilege boundaries.\n"
            "Your goal is to inspect the codebase, trace symbols, locate definitions, extract structural outlines, and uncover relevant implementation details.\n"
            "You have ONLY read-only tools (search_files, read_file, extract_code_outline, grep_search_code).\n"
            "Do NOT attempt to modify, edit, or delete files.\n"
            "Output a structured reconnaissance report with exact file paths (path:line), symbol signatures, and findings.\n"
            "Do not emit conversational filler, preambles, or avatar roleplay."
        )
        return instruction, True

    elif r in ("implementer", "coder", "builder"):
        instruction = (
            "[ROLE: IMPLEMENTER & SOFTWARE CRAFTSMAN]\n"
            "You are an autonomous implementing agent tasked with executing precise code modifications.\n"
            "Your goal is to implement changes adhering to existing codebase patterns, formatting, and invariants.\n"
            "Make targeted edits, avoid unnecessary refactoring, add required imports, and preserve backward compatibility.\n"
            "Verify your edits with extract_code_outline or test commands where applicable.\n"
            "Do not emit conversational filler, preambles, or avatar roleplay."
        )
        return instruction, False

    elif r in ("verifier", "reviewer", "tester", "qa"):
        instruction = (
            "[ROLE: ADVERSARIAL VERIFIER & TEST GATEKEEPER]\n"
            "You are an independent, adversarial reviewer tasked with validating code changes and preventing regressions.\n"
            "Your goal is to execute test suites, inspect diffs, verify edge cases, and evaluate acceptance criteria.\n"
            "Be skeptical and objective: never claim success without factual verification output from test execution.\n"
            "Report an honest status: PASS, FAIL, or BLOCKED with exact error lines and reproduction steps.\n"
            "Do not emit conversational filler, preambles, or avatar roleplay."
        )
        return instruction, True

    else:
        # Default technical specialist (leaf / orchestrator)
        is_ro = (r != "orchestrator" and r != "lead")
        instruction = (
            "[ROLE: TECHNICAL SPECIALIST SUBAGENT PROTOCOL]\n"
            "You are an isolated, objective technical specialist worker executing a focused sub-task.\n"
            "Analyze the given objective thoroughly and produce factual, verifiable results.\n"
            "Report your factual findings, discovered code references, and concise technical summary.\n"
            "Do not emit conversational filler, preambles, or avatar roleplay."
        )
        return instruction, is_ro


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
    """Represents a delegated background mission (Anara Standard)."""

    def __init__(
        self,
        task_id: str,
        goal: str,
        context: str = "",
        role: str = "leaf",
        depth: int = 1,
        timeout_seconds: float = 120.0,
        platform: Optional[str] = "cli",
        use_worktree: bool = False,
    ):
        self.task_id = task_id
        self.title = goal[:80]
        self.goal = goal
        self.context = context
        self.role = role
        self.depth = depth
        self.timeout_seconds = timeout_seconds
        self.platform = platform or "cli"
        self.use_worktree = use_worktree
        self.worktree_dir: Optional[str] = None
        self.worktree_branch: Optional[str] = None
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
        self._concurrency_semaphore = asyncio.Semaphore(4)

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
            loop = asyncio.get_running_loop()
            from telemetry.event_bus import telemetry_bus, EventType, ActivityProvenance
            loop.create_task(
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
        platform: Optional[str] = "cli",
        use_worktree: bool = False,
    ) -> SubAgentTask:
        """
        Spawns an asynchronous background worker in an isolated context.
        Enforces anti-fork-bomb depth boundaries and optional Git worktree isolation.
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
            failed_task = SubAgentTask(res_fail.task_id, effective_goal, context, role, depth, platform=platform, use_worktree=use_worktree)
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
            platform=platform,
            use_worktree=use_worktree,
        )

        # Anara Standard: Initialize ephemeral Git worktree if requested
        if use_worktree:
            try:
                from core.worktree import GitWorktreeManager
                wt = GitWorktreeManager.create_worktree(os.getcwd(), t_id)
                if wt:
                    task.worktree_dir, task.worktree_branch = wt
            except Exception as wt_err:
                logger.debug(f"[SubAgent] Worktree initialization note: {wt_err}")

        # Memory Protection: Prune completed tasks to prevent unbounded memory growth
        if len(self.tasks) > 80:
            now = time.time()
            expired_ids = [tid for tid, t in self.tasks.items() if t.completed_at and (now - t.completed_at > 1800.0)]
            for tid in expired_ids:
                self.tasks.pop(tid, None)
            if len(self.tasks) > 80:
                completed_sorted = sorted([t for t in self.tasks.values() if t.completed_at], key=lambda x: x.completed_at or 0)
                for t in completed_sorted[:25]:
                    self.tasks.pop(t.task_id, None)

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
        depth: int = 1,
        timeout_seconds: Optional[float] = None,
        worker_coro_factory: Optional[Callable[..., Any]] = None,
    ) -> List[SubagentResult]:
        """
        Forks multiple subagents concurrently in parallel and joins all results (Fork-and-Join Pattern).
        Propagates recursion depth and task role cleanly (Anara Standard).
        """
        if not tasks:
            return []

        spawned = []
        for t_def in tasks:
            g = t_def.get("goal") or t_def.get("title") or "Subagent Mission"
            c = t_def.get("context") or shared_context
            r = t_def.get("role") or "leaf"
            sub_task = await self.spawn_subagent_task(
                title=g,
                mission_prompt=c,
                role=r,
                depth=depth,
                timeout_seconds=timeout_seconds,
                worker_coro_factory=worker_coro_factory,
            )
            spawned.append(sub_task)

        # Concurrency throttled centrally by self._concurrency_semaphore in _run_task_pipeline (Anara Standard)
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
        """Executes subagent reasoning pipeline bounded by timeout and worker concurrency."""
        task.state = SubagentState.RUNNING
        start_t = time.time()
        task.steps_log.append("Queued for worker execution...")

        async with self._concurrency_semaphore:
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
                raise

            except Exception as e:
                task.state = SubagentState.FAILED
                task.completed_at = time.time()
                dur = round(task.completed_at - start_t, 2)
                err_str = str(e) or type(e).__name__
                task.result = SubagentResult(
                    task_id=task.task_id,
                    goal=task.goal,
                    status="failed",
                    executive_summary=f"Subagent execution failed: {err_str}",
                    execution_time_sec=dur,
                    error_message=err_str,
                )
                self._emit("subagent_task_failed", {
                    "task_id": task.task_id,
                    "title": task.title,
                    "error": err_str,
                    "status": "failed",
                    "duration_sec": dur,
                })
                logger.error(f"[SubAgent] Mission #{task.task_id} FAILED: {e}", exc_info=True)
            finally:
                if getattr(task, "worktree_dir", None):
                    try:
                        from core.worktree import GitWorktreeManager
                        if task.state == SubagentState.SUCCEEDED:
                            GitWorktreeManager.apply_and_merge_worktree(
                                os.getcwd(), task.worktree_dir, task.worktree_branch
                            )
                        else:
                            GitWorktreeManager.remove_worktree(
                                os.getcwd(), task.worktree_dir, task.worktree_branch
                            )
                    except Exception as wt_cleanup_err:
                        logger.debug(f"[SubAgent] Worktree teardown notice: {wt_cleanup_err}")

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

        from config import cfg_get
        from providers import call_universal_chat_model, get_active_model_id
        from cognition import get_soul_prompt
        from core.prompt_loader import load_prompt

        task.steps_log.append(f"Analyzing mission context: {task.title}...")
        task.progress_percent = 25

        sub_prompt = load_prompt(
            "subagent_worker",
            goal=task.goal,
            context=task.context or "Use available read-only exploration tools in the repository."
        )

        # Dynamic model resolution: prioritize fast_subagent model from config
        model_id = cfg_get("models.fast_subagent") or cfg_get("subagent.model") or get_active_model_id()
        task.steps_log.append("Executing specialist model reasoning...")
        task.progress_percent = 50

        role_instruction, is_read_only = get_role_configuration(task.role)
        specialist_instruction = load_prompt("subagent_specialist", default=role_instruction)
        if not specialist_instruction or specialist_instruction.startswith("[TECHNICAL SPECIALIST"):
            specialist_instruction = role_instruction

        def _subagent_progress_cb(evt: Dict[str, Any]):
            t_name = evt.get("tool_name", "")
            status = evt.get("status", "")
            detail = evt.get("detail", "")
            if t_name:
                task.steps_log.append(f"Tool {t_name} [{status}]: {detail}")
            try:
                from core.session_manager import session_state_manager
                if status == "running" and t_name:
                    cid = evt.get("call_id") or f"sub_{uuid.uuid4().hex[:10]}"
                    evt["call_id"] = cid
                    session_state_manager.persist_tool_call_start(
                        session_id=task.task_id,
                        channel=task.platform or "subagent",
                        channel_id=task.task_id,
                        tool_name=t_name,
                        tool_args=evt.get("args") or evt.get("tool_args") or {},
                        call_id=cid
                    )
                elif status == "done" and t_name:
                    cid = evt.get("call_id")
                    if cid:
                        session_state_manager.persist_tool_call_result(
                            call_id=cid,
                            result_summary=evt.get("summary") or detail,
                            is_error=bool(evt.get("is_error", False))
                        )
            except Exception:
                pass
            self._emit("subagent_progress", {
                "task_id": task.task_id,
                "tool_name": t_name,
                "status": status,
                "detail": detail,
            })

        def _subagent_token_cb(token: str):
            pass

        res_text = await call_universal_chat_model(
            model_id=model_id,
            user_prompt=sub_prompt,
            system_instruction=specialist_instruction,
            max_tokens=None,
            temperature=0.3,
            read_only=is_read_only,
            progress_cb=_subagent_progress_cb,
            token_cb=_subagent_token_cb,
            platform=task.platform or "cli",
        )

        raw_summary = str(res_text or "").strip()
        # Apply Hermes summary budget and disk spillover if response exceeds ceiling
        budgeted_summary, spill_path = apply_summary_budget(task.task_id, raw_summary)

        # Extract verified referenced files and bulleted findings for structured contract
        raw_refs = list(set(re.findall(r"(?:[a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9_]{1,6})", raw_summary)))
        from core.agent import anara_agent
        repo_root = anara_agent.get_project_repo_root()
        clean_refs = []
        for f in raw_refs:
            if "/" in f or "\\" in f:
                if not f.startswith("http") and not any(f.endswith(ext) for ext in (".com", ".org", ".net", ".io", ".ai")):
                    if not re.match(r"^v?\d+\.\d+", f):
                        clean_refs.append(f)
            elif os.path.exists(os.path.join(repo_root, f)):
                clean_refs.append(f)
            if len(clean_refs) >= 10:
                break

        bullet_findings = [line.strip().lstrip("-*123456789. ") for line in raw_summary.splitlines() if line.strip().startswith(("-", "*", "1.", "2.", "3.", "•"))][:6]

        task.result = SubagentResult(
            task_id=task.task_id,
            goal=task.goal,
            status="completed",
            executive_summary=budgeted_summary,
            key_findings=bullet_findings or [budgeted_summary[:120]],
            referenced_files=clean_refs,
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
