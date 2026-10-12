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
import contextlib
import contextvars
import dataclasses
import enum
import json
import logging
import os
import re
import threading
import time
import uuid
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple, Union

logger = logging.getLogger("anara.core.subagent")

DEFAULT_MAX_SUMMARY_CHARS: int = 24000
DEFAULT_MAX_CONCURRENT_CHILDREN: int = 8
DEFAULT_MAX_DEPTH: int = 2
DEFAULT_TIMEOUT_SECONDS: float = 120.0
_MAX_TASK_IMAGES: int = 8
_MIN_BATCH_GOAL_LEN: int = 10

# Prohibited toolsets for delegated child workers (Child Safety Barriers)
DELEGATE_BLOCKED_TOOLS: frozenset[str] = frozenset([
    "delegate_subagent",
    "delegate_task",
    "interactive_question",
    "clarify",
    "memory",
    "manage_memory_and_todos",
    "cronjob",
    "cronjob_manage",
    "send_message",
    "send_document_file",
    "start_chat",
])

CONTROL_ACTIONS: frozenset[str] = frozenset(["spawn", "list", "steer", "stop"])

# Context-local markers for subagent child execution
_DELEGATED_CHILD_CONTEXT: contextvars.ContextVar[bool] = contextvars.ContextVar("anara_delegated_child_context", default=False)
_CHILD_ROLE_CONTEXT: contextvars.ContextVar[str] = contextvars.ContextVar("anara_child_role_context", default="leaf")
_CHILD_DEPTH_CONTEXT: contextvars.ContextVar[int] = contextvars.ContextVar("anara_child_depth_context", default=1)
_CURRENT_SUBAGENT_TASK: contextvars.ContextVar[Optional[Any]] = contextvars.ContextVar("anara_current_subagent_task", default=None)


@contextlib.contextmanager
def delegated_child_context(role: str = "leaf", depth: int = 1) -> Iterator[None]:
    """Context manager marking active execution of a delegated subagent worker."""
    token_flag = _DELEGATED_CHILD_CONTEXT.set(True)
    token_role = _CHILD_ROLE_CONTEXT.set(role or "leaf")
    token_depth = _CHILD_DEPTH_CONTEXT.set(depth)
    try:
        yield
    finally:
        _DELEGATED_CHILD_CONTEXT.reset(token_flag)
        _CHILD_ROLE_CONTEXT.reset(token_role)
        _CHILD_DEPTH_CONTEXT.reset(token_depth)


def is_delegated_child_context() -> bool:
    """Returns True if the current thread/coroutine is executing within a delegated child subagent."""
    return bool(_DELEGATED_CHILD_CONTEXT.get())


def get_current_subagent_task() -> Optional[Any]:
    """Returns the SubAgentTask instance currently executing in the local context, if any."""
    return _CURRENT_SUBAGENT_TASK.get()


def is_tool_blocked_for_child(tool_name: str) -> bool:
    """
    Evaluates whether a tool is barred for delegated child execution.
    Orchestrators with remaining depth budget may delegate; leaf workers and specialist
    subagents are hard-blocked from delegation and all interactive/state-mutating tools.
    """
    if not is_delegated_child_context():
        return False
    clean = (tool_name or "").strip().lower()
    role = (_CHILD_ROLE_CONTEXT.get() or "leaf").strip().lower()
    depth = _CHILD_DEPTH_CONTEXT.get() or 1
    if clean in ("delegate_subagent", "delegate_task"):
        return not (role == "orchestrator" and depth < DEFAULT_MAX_DEPTH)
    return clean in DELEGATE_BLOCKED_TOOLS


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

    elif r in ("orchestrator", "lead"):
        instruction = (
            "[ROLE: SUBAGENT ORCHESTRATOR PROTOCOL]\n"
            "You are an autonomous orchestrating worker tasked with decomposing objectives and coordinating worker tasks.\n"
            "You may delegate focused sub-missions while depth budget permits.\n"
            "Synthesize findings from worker tasks into a coherent executive report.\n"
            "Do not emit conversational filler, preambles, or avatar roleplay."
        )
        return instruction, False

    else:
        # Default technical specialist (leaf)
        instruction = (
            "[ROLE: TECHNICAL SPECIALIST SUBAGENT PROTOCOL]\n"
            "You are an isolated, objective technical specialist worker executing a focused sub-task.\n"
            "Analyze the given objective thoroughly and produce factual, verifiable results.\n"
            "Report your factual findings, discovered code references, and concise technical summary.\n"
            "Do not emit conversational filler, preambles, or avatar roleplay."
        )
        return instruction, True


def coerce_output_schema(raw: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Validates and coerces a requested JSON output_schema."""
    if raw is None:
        return None, None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception as e:
            return None, f"output_schema must be a JSON Schema object, got non-JSON string: {e}"
    if not isinstance(raw, dict):
        return None, f"output_schema must be a JSON Schema object, got {type(raw).__name__}."
    try:
        from jsonschema.validators import validator_for
        validator_for(raw).check_schema(raw)
    except ImportError:
        pass
    except Exception as exc:
        return None, f"output_schema is not a valid JSON Schema: {exc}"
    return raw, None


def append_output_contract(context: Optional[str], schema: Dict[str, Any]) -> str:
    """Appends an explicit machine-validated JSON output contract to context."""
    try:
        schema_text = json.dumps(schema, indent=2, ensure_ascii=False)
    except Exception:
        schema_text = str(schema)
    block = (
        "OUTPUT CONTRACT (machine-validated):\n"
        "Your FINAL response must be ONLY the JSON value that validates against this JSON Schema — "
        "no prose before or after it, no code fence, no explanation. Anything else costs a correction "
        "turn and, if it fails again, is handed to the caller unvalidated.\n"
        f"{schema_text}"
    )
    base = (context or "").rstrip()
    return f"{base}\n\n{block}" if base else block


def extract_json_candidate(text: str) -> str:
    """Extracts raw JSON payload from candidate text, removing fences and wrapping prose."""
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.rstrip().endswith("```"):
            raw = raw.rstrip()[:-3]
        raw = raw.strip()
        if raw.lower().startswith("json\n"):
            raw = raw.split("\n", 1)[1]
    spans = []
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = raw.find(opener), raw.rfind(closer)
        if start >= 0 and end > start:
            spans.append((start, raw[start : end + 1]))
    for _start, candidate in sorted(spans):
        try:
            json.loads(candidate)
            return candidate
        except ValueError:
            continue
    return spans[0][1] if spans else raw


def validate_output_schema(text: str, schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validates raw text against JSON Schema contract."""
    candidate = extract_json_candidate(text or "")
    if not candidate.strip():
        return False, ["Response was empty — expected JSON matching output_schema."]
    try:
        parsed = json.loads(candidate)
    except Exception as exc:
        return False, [f"Response is not valid JSON: {exc}"]

    try:
        from jsonschema.validators import validator_for
        validator = validator_for(schema)(schema)
        errors = sorted(validator.iter_errors(parsed), key=lambda e: list(e.absolute_path))
        rendered = [
            "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in err.absolute_path) + f": {err.message}"
            for err in errors[:10]
        ]
        return not rendered, rendered
    except ImportError:
        # Graceful pure-Python baseline validation when external package is absent
        errors = []
        expected_type = schema.get("type")
        if expected_type == "object" and not isinstance(parsed, dict):
            errors.append(f"Expected object, got {type(parsed).__name__}")
        elif expected_type == "array" and not isinstance(parsed, list):
            errors.append(f"Expected array, got {type(parsed).__name__}")
        elif expected_type == "string" and not isinstance(parsed, str):
            errors.append(f"Expected string, got {type(parsed).__name__}")
        elif expected_type in ("integer", "number") and not isinstance(parsed, (int, float)):
            errors.append(f"Expected number, got {type(parsed).__name__}")

        if isinstance(parsed, dict):
            required = schema.get("required", [])
            for req in required:
                if req not in parsed:
                    errors.append(f"Missing required property: '{req}'")
        return not errors, errors


_PLACEHOLDER_GOAL_RE = re.compile(r"^(todo|task\s*\d+)$", re.IGNORECASE)
_TEMPLATE_MARKER_RE = re.compile(
    r"<[A-Za-z][A-Za-z0-9]*(?:[ _-][A-Za-z0-9]+)+>|\{[A-Za-z][A-Za-z0-9]*(?:[ _-][A-Za-z0-9]+)+\}"
)


def normalize_task_list(
    goal: Optional[str] = None,
    context: Optional[str] = None,
    tasks: Optional[Union[List[Dict[str, Any]], str]] = None,
    output_schema: Optional[Dict[str, Any]] = None,
    images: Optional[List[str]] = None,
    role: Optional[str] = None,
    max_children: int = DEFAULT_MAX_CONCURRENT_CHILDREN,
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    Normalizes single goal or tasks batch array to canonical task dictionary format.
    Enforces quality checks (non-empty goals, no unexpanded templates, length checks, limits).
    """
    if isinstance(tasks, str):
        raw_str = tasks.strip()
        if not raw_str:
            tasks = None
        else:
            try:
                parsed = json.loads(raw_str)
                if isinstance(parsed, list):
                    tasks = parsed
                else:
                    return None, f"tasks must be a JSON array of objects, parsed {type(parsed).__name__}."
            except Exception as e:
                return None, f"tasks must be a valid JSON array: {e}"

    if tasks and isinstance(tasks, list):
        if len(tasks) > max_children:
            return None, (
                f"Too many tasks: {len(tasks)} provided, but max_concurrent_children is {max_children}. "
                f"Either reduce the task count, split into multiple delegation calls, or increase "
                f"delegation.max_concurrent_children in config."
            )
        task_list = list(tasks)
    elif goal and isinstance(goal, str) and goal.strip():
        single_task: Dict[str, Any] = {
            "goal": goal.strip(),
            "context": context or "",
            "role": role or "leaf",
        }
        if output_schema is not None:
            single_task["output_schema"] = output_schema
        if images is not None:
            single_task["images"] = images
        task_list = [single_task]
    else:
        return None, "No tasks provided. Pass tasks=[{goal: '...', context: '...'}, ...] or a single 'goal'."

    for i, t in enumerate(task_list):
        if not isinstance(t, dict):
            return None, f"Task {i} must be an object, got {type(t).__name__}."
        g = str(t.get("goal") or t.get("title") or "").strip()
        if not g:
            return None, f"Task {i} is missing a 'goal'."
        t["goal"] = g

        if _PLACEHOLDER_GOAL_RE.match(" ".join(g.lower().split())):
            return None, f"Task {i} has a placeholder goal ({g!r}). Replace with a specific description."
        marker = _TEMPLATE_MARKER_RE.search(g)
        if marker:
            return None, f"Task {i} goal contains an unexpanded template marker ({marker.group(0)!r})."
        if len(task_list) >= 2 and len(g) < _MIN_BATCH_GOAL_LEN:
            return None, f"Task {i} goal is too short ({g!r}). Write a goal of at least {_MIN_BATCH_GOAL_LEN} chars."

        t_schema = t.get("output_schema")
        if t_schema is None and len(task_list) == 1 and output_schema is not None:
            t_schema = output_schema
        if t_schema is not None:
            coerced_s, s_err = coerce_output_schema(t_schema)
            if s_err:
                return None, f"Task {i} output_schema invalid: {s_err}"
            t["output_schema"] = coerced_s

        t_imgs = t.get("images")
        if t_imgs is None and len(task_list) == 1 and images is not None:
            t_imgs = images
        if t_imgs is not None:
            if isinstance(t_imgs, str):
                t_imgs = [t_imgs]
            if not isinstance(t_imgs, list):
                return None, f"Task {i} 'images' must be an array of image paths/URLs."
            cleaned_imgs = [str(img).strip() for img in t_imgs if str(img).strip()]
            if len(cleaned_imgs) > _MAX_TASK_IMAGES:
                return None, f"Task {i} has {len(cleaned_imgs)} images; limit is {_MAX_TASK_IMAGES}."
            t["images"] = cleaned_imgs

    return task_list, None


class SubagentState(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"


@dataclasses.dataclass
class SubagentResult:
    task_id: str
    goal: str
    status: str  # 'completed', 'failed', 'timed_out', 'cancelled', 'error'
    executive_summary: str
    key_findings: List[str] = dataclasses.field(default_factory=list)
    referenced_files: List[str] = dataclasses.field(default_factory=list)
    execution_time_sec: float = 0.0
    error_message: Optional[str] = None
    task_index: int = 0
    subagent_id: Optional[str] = None
    summary: Optional[str] = None
    duration_seconds: Optional[float] = None
    schema_valid: Optional[bool] = None
    schema_errors: Optional[List[str]] = None
    summary_truncated: bool = False
    summary_full_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        if not d.get("summary"):
            d["summary"] = d.get("executive_summary", "")
        if d.get("duration_seconds") is None:
            d["duration_seconds"] = d.get("execution_time_sec", 0.0)
        return d


class SubAgentTask:
    """Represents a delegated background mission with lifecycle and in-flight tracking (Anara Standard)."""

    def __init__(
        self,
        task_id: str,
        goal: str,
        context: str = "",
        role: str = "leaf",
        depth: int = 1,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        platform: Optional[str] = "cli",
        use_worktree: bool = False,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        images: Optional[List[str]] = None,
        task_index: int = 0,
        parent_id: Optional[str] = None,
    ):
        self.task_id = task_id
        self.subagent_id = task_id
        self.parent_id = parent_id
        self.task_index = task_index
        self.title = goal[:80]
        self.goal = goal
        self.context = context
        self.role = role
        self.depth = depth
        self.timeout_seconds = timeout_seconds
        self.platform = platform or "cli"
        self.use_worktree = use_worktree
        self.model = model
        self.provider = provider
        self.output_schema = output_schema
        self.images = images or []
        self.worktree_dir: Optional[str] = None
        self.worktree_branch: Optional[str] = None
        self.state = SubagentState.PENDING
        self.progress_percent = 0
        self.steps_log: List[str] = []
        self.pending_steers: List[str] = []
        self.interrupt_requested: bool = False
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

    def steer(self, message: str) -> bool:
        """Enqueues an in-flight steering directive into this active subagent."""
        if self.state in (SubagentState.PENDING, SubagentState.RUNNING) and not self.interrupt_requested:
            self.pending_steers.append(message)
            self.steps_log.append(f"Steer received: {message[:60]}")
            try:
                from core.session_manager import session_state_manager
                session_state_manager.push_steering_message("subagent", self.task_id, message)
            except Exception:
                pass
            return True
        return False

    def pop_steering_message(self) -> Optional[str]:
        """Pops the next queued in-flight steering directive, if any."""
        if self.pending_steers:
            return self.pending_steers.pop(0)
        return None

    def interrupt(self) -> bool:
        """Interrupts and cancels execution of this subagent."""
        self.interrupt_requested = True
        self.state = SubagentState.CANCELLED
        if self._async_task and not self._async_task.done():
            self._async_task.cancel()
        return True


# Global registry for active and recent subagents (In-flight tracking)
_active_subagents: Dict[str, SubAgentTask] = {}
_active_subagents_lock = threading.Lock()
_recent_subagents: Dict[str, Dict[str, Any]] = {}
_RECENT_SUBAGENTS_CAP: int = 200


def _register_subagent(task: SubAgentTask) -> None:
    with _active_subagents_lock:
        _active_subagents[task.task_id] = task


def _unregister_subagent(task_id: str) -> None:
    with _active_subagents_lock:
        task = _active_subagents.pop(task_id, None)
        if task:
            _recent_subagents[task_id] = {
                "subagent_id": task.task_id,
                "goal": task.goal,
                "status": task.status,
                "created_at": task.created_at,
                "completed_at": task.completed_at or time.time(),
            }
            while len(_recent_subagents) > _RECENT_SUBAGENTS_CAP:
                _recent_subagents.pop(next(iter(_recent_subagents)), None)


def get_subagent_attribution(task_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Returns subagent attribution info for a given task ID."""
    if not task_id:
        return None
    with _active_subagents_lock:
        t = _active_subagents.get(task_id)
        if t:
            return {"subagent_id": t.task_id, "goal": t.goal, "status": t.status}
        r = _recent_subagents.get(task_id)
        if r:
            return {"subagent_id": r["subagent_id"], "goal": r["goal"], "status": r["status"]}
    return None


def list_active_subagents(parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns a snapshot list of live subagents currently in flight."""
    with _active_subagents_lock:
        items = list(_active_subagents.values())
    if parent_id:
        items = [t for t in items if getattr(t, "parent_id", None) == parent_id]
    return [
        {
            "subagent_id": t.task_id,
            "task_id": t.task_id,
            "parent_id": getattr(t, "parent_id", None),
            "goal": t.goal,
            "model": t.model,
            "status": t.status,
            "running_seconds": round(time.time() - t.created_at, 1),
            "accepting_steer": t.state in (SubagentState.PENDING, SubagentState.RUNNING) and not t.interrupt_requested,
            "steps_log": t.steps_log[-5:],
        }
        for t in items
    ]


def steer_subagent(subagent_id: str, message: str) -> bool:
    """Delivers an in-flight steering directive to a live subagent."""
    if not message or not message.strip():
        return False
    with _active_subagents_lock:
        task = _active_subagents.get(subagent_id)
    if not task:
        return False
    return task.steer(message.strip())


def interrupt_subagent(subagent_id: str) -> bool:
    """Requests immediate interrupt of an in-flight subagent."""
    with _active_subagents_lock:
        task = _active_subagents.get(subagent_id)
    if not task:
        return False
    return task.interrupt()


class SubAgentManager:
    """Manages concurrent, isolated background worker tasks with lifecycle guarantees."""

    DEFAULT_MAX_DEPTH: int = DEFAULT_MAX_DEPTH
    DEFAULT_TIMEOUT_SECONDS: float = DEFAULT_TIMEOUT_SECONDS

    def __init__(self):
        self.tasks: Dict[str, SubAgentTask] = {}
        self._listeners: List[Callable[[Dict[str, Any]], Any]] = []
        self._concurrency_semaphore = asyncio.Semaphore(DEFAULT_MAX_CONCURRENT_CHILDREN)

    @property
    def max_concurrent_children(self) -> int:
        from config import cfg_get
        try:
            val = cfg_get("delegation.max_concurrent_children") or cfg_get("subagent.max_concurrent_children")
            return int(val) if val else DEFAULT_MAX_CONCURRENT_CHILDREN
        except Exception:
            return DEFAULT_MAX_CONCURRENT_CHILDREN

    def register_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unregister_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        if callback in self._listeners:
            self._listeners.remove(callback)

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
        model: Optional[str] = None,
        provider: Optional[str] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        images: Optional[List[str]] = None,
        task_index: int = 0,
        parent_id: Optional[str] = None,
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
                task_index=task_index,
            )
            failed_task = SubAgentTask(
                res_fail.task_id, effective_goal, context, role, depth,
                platform=platform, use_worktree=use_worktree, model=model, provider=provider,
                output_schema=output_schema, images=images, task_index=task_index, parent_id=parent_id,
            )
            failed_task.state = SubagentState.FAILED
            failed_task.result = res_fail
            return failed_task

        t_id = str(uuid.uuid4())[:8]
        effective_timeout = timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS
        task = SubAgentTask(
            task_id=t_id,
            goal=effective_goal,
            context=context or mission_prompt,
            role=role,
            depth=depth,
            timeout_seconds=effective_timeout,
            platform=platform,
            use_worktree=use_worktree,
            model=model,
            provider=provider,
            output_schema=output_schema,
            images=images,
            task_index=task_index,
            parent_id=parent_id,
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
        _register_subagent(task)

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
        parent_id: Optional[str] = None,
    ) -> List[SubagentResult]:
        """
        Forks multiple subagents concurrently in parallel and joins all results (Fork-and-Join Pattern).
        Propagates recursion depth and task role cleanly (Anara Standard).
        """
        if not tasks:
            return []

        spawned = []
        for idx, t_def in enumerate(tasks):
            g = t_def.get("goal") or t_def.get("title") or "Subagent Mission"
            c = t_def.get("context") or shared_context
            r = t_def.get("role") or "leaf"
            m = t_def.get("model")
            p = t_def.get("provider")
            s = t_def.get("output_schema")
            imgs = t_def.get("images")
            sub_task = await self.spawn_subagent_task(
                title=g,
                mission_prompt=c,
                role=r,
                depth=depth,
                timeout_seconds=timeout_seconds,
                worker_coro_factory=worker_coro_factory,
                model=m,
                provider=p,
                output_schema=s,
                images=imgs,
                task_index=idx,
                parent_id=parent_id,
            )
            spawned.append(sub_task)

        # Concurrency throttled centrally by self._concurrency_semaphore in _run_task_pipeline
        await asyncio.gather(*[t._async_task for t in spawned if t._async_task], return_exceptions=True)

        results: List[SubagentResult] = []
        for t in spawned:
            if t.result:
                results.append(t.result)
            else:
                fallback_res = SubagentResult(
                    task_id=t.task_id,
                    goal=t.goal,
                    status=t.status,
                    executive_summary=t.steps_log[-1] if t.steps_log else "Task finished.",
                    error_message=f"State: {t.state.value}",
                    task_index=t.task_index,
                    subagent_id=t.task_id,
                )
                results.append(fallback_res)
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

        # Ensure semaphore tracks configured limit
        if self._concurrency_semaphore._value != self.max_concurrent_children and not self._concurrency_semaphore.locked():
            self._concurrency_semaphore = asyncio.Semaphore(self.max_concurrent_children)

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
                    duration_seconds=dur,
                    error_message="Execution timeout exceeded.",
                    task_index=task.task_index,
                    subagent_id=task.task_id,
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
                    duration_seconds=dur,
                    error_message="Cancelled by host.",
                    task_index=task.task_index,
                    subagent_id=task.task_id,
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
                    duration_seconds=dur,
                    error_message=err_str,
                    task_index=task.task_index,
                    subagent_id=task.task_id,
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
                _unregister_subagent(task.task_id)
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
        """Runs isolated subagent reasoning pipeline with Child Safety Barriers."""
        token_task = _CURRENT_SUBAGENT_TASK.set(task)
        try:
            with delegated_child_context(role=task.role, depth=task.depth):
                if worker_coro_factory:
                    res = await worker_coro_factory(task)
                    raw_summary = str(res)
                    dur = round(time.time() - task.created_at, 2)

                    schema_valid = None
                    schema_errors = None
                    if task.output_schema:
                        schema_valid, schema_errors = validate_output_schema(raw_summary, task.output_schema)

                    budgeted_summary, spill_path = apply_summary_budget(task.task_id, raw_summary)

                    task.result = SubagentResult(
                        task_id=task.task_id,
                        goal=task.goal,
                        status="completed",
                        executive_summary=budgeted_summary,
                        summary=budgeted_summary,
                        execution_time_sec=dur,
                        duration_seconds=dur,
                        task_index=task.task_index,
                        subagent_id=task.task_id,
                        schema_valid=schema_valid,
                        schema_errors=schema_errors,
                        summary_truncated=bool(spill_path),
                        summary_full_path=spill_path,
                    )
                    return

                from config import cfg_get
                from providers import call_universal_chat_model, get_active_model_id
                from core.prompt_loader import load_prompt

                task.steps_log.append(f"Analyzing mission context: {task.title}...")
                task.progress_percent = 25

                eff_context = task.context or "Use available read-only exploration tools in the repository."
                if task.output_schema:
                    eff_context = append_output_contract(eff_context, task.output_schema)
                if task.images:
                    eff_context = f"{eff_context}\n\n[ATTACHED IMAGES]:\n" + "\n".join(f"- {img}" for img in task.images)

                sub_prompt = load_prompt(
                    "subagent_worker",
                    goal=task.goal,
                    context=eff_context
                )

                # Dynamic model resolution (Anara Standard):
                # 1. Explicit model pinned on this task
                # 2. Configured delegation.model / fast_subagent
                # 3. Inherit active parent session model
                from providers.accounts import is_provider_configured, get_fallback_model_id
                parent_model = get_active_model_id()
                model_id = (task.model or "").strip()
                if not model_id:
                    fast_m = (
                        cfg_get("model.fast_subagent")
                        or cfg_get("models.fast_subagent")
                        or cfg_get("delegation.model")
                        or cfg_get("subagent.model")
                        or ""
                    ).strip()
                    if fast_m:
                        prov_prefix = fast_m.split("/")[0] if "/" in fast_m else fast_m
                        if is_provider_configured(prov_prefix):
                            model_id = fast_m

                if not model_id:
                    model_id = parent_model or get_fallback_model_id()

                if task.provider and "/" not in model_id:
                    model_id = f"{task.provider}/{model_id}"

                task.steps_log.append(f"Executing specialist model reasoning ({model_id})...")
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
                                channel="subagent",
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
                    platform="subagent",
                )

                raw_summary = str(res_text or "").strip()

                # Output schema validation if requested
                schema_valid = None
                schema_errors = None
                if task.output_schema:
                    schema_valid, schema_errors = validate_output_schema(raw_summary, task.output_schema)

                # Apply summary budget and disk spillover if response exceeds ceiling
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

                bullet_findings = [
                    line.strip().lstrip("-*123456789. ")
                    for line in raw_summary.splitlines()
                    if line.strip().startswith(("-", "*", "1.", "2.", "3.", "•"))
                ][:6]

                dur = round(time.time() - task.created_at, 2)
                task.result = SubagentResult(
                    task_id=task.task_id,
                    goal=task.goal,
                    status="completed",
                    executive_summary=budgeted_summary,
                    summary=budgeted_summary,
                    key_findings=bullet_findings or [budgeted_summary[:120]],
                    referenced_files=clean_refs,
                    execution_time_sec=dur,
                    duration_seconds=dur,
                    task_index=task.task_index,
                    subagent_id=task.task_id,
                    schema_valid=schema_valid,
                    schema_errors=schema_errors,
                    summary_truncated=bool(spill_path),
                    summary_full_path=spill_path,
                )
        finally:
            _CURRENT_SUBAGENT_TASK.reset(token_task)

    async def handle_delegate_call(
        self,
        goal: Optional[str] = None,
        context: Optional[str] = None,
        tasks: Optional[Union[List[Dict[str, Any]], str]] = None,
        action: Optional[str] = None,
        subagent_id: Optional[str] = None,
        message: Optional[str] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        images: Optional[List[str]] = None,
        role: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        background: bool = False,
        depth: int = 1,
        title: Optional[str] = None,
        mission_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Unified handler for delegate_task / delegate_subagent calls (Anara Standard).
        Supports canonical schema (tasks array, goal, context, images, output_schema),
        action parameter ('spawn', 'list', 'steer', 'stop'), concurrency controls,
        child safety barriers, and unified result synthesis.
        """
        # Child safety barrier check: child workers cannot delegate unless orchestrator within depth budget
        if is_delegated_child_context() and is_tool_blocked_for_child("delegate_task"):
            return {
                "status": "error",
                "message": "Child subagent is prohibited from delegating (recursive delegation safety barrier).",
            }

        act = (action or "spawn").strip().lower()

        # Action: list
        if act == "list":
            active_list = list_active_subagents()
            return {
                "status": "success",
                "action": "list",
                "count": len(active_list),
                "subagents": active_list,
                "note": "No live subagents right now." if not active_list else "",
            }

        # Action: steer
        elif act == "steer":
            sid = (subagent_id or "").strip()
            if not sid:
                return {"status": "error", "action": "steer", "message": "action='steer' requires subagent_id."}
            msg = (message or "").strip()
            if not msg:
                return {"status": "error", "action": "steer", "message": "action='steer' requires a non-empty 'message'."}
            ok = steer_subagent(sid, msg)
            if ok:
                return {
                    "status": "success",
                    "action": "steer",
                    "subagent_id": sid,
                    "status_detail": "queued",
                    "note": "Steering text queued. The subagent sees it at its next iteration boundary.",
                }
            return {
                "status": "error",
                "action": "steer",
                "message": f"Subagent '{sid}' is not live or no longer accepting steering.",
            }

        # Action: stop
        elif act == "stop":
            sid = (subagent_id or "").strip()
            if not sid:
                return {"status": "error", "action": "stop", "message": "action='stop' requires subagent_id."}
            ok = interrupt_subagent(sid)
            if ok:
                return {
                    "status": "success",
                    "action": "stop",
                    "subagent_id": sid,
                    "status_detail": "interrupt_requested",
                    "note": "The subagent stops at its next iteration boundary.",
                }
            return {
                "status": "error",
                "action": "stop",
                "message": f"Subagent '{sid}' is not found or already finished.",
            }

        elif act != "spawn":
            return {
                "status": "error",
                "message": f"Unknown action '{action}'. Use spawn (default), list, steer, or stop.",
            }

        # Action: spawn
        effective_goal = (goal or title or "").strip()
        effective_context = (context or mission_prompt or "").strip()

        # Anti-fork-bomb barrier check
        if depth > self.DEFAULT_MAX_DEPTH:
            err_msg = f"Delegation depth limit reached (depth={depth}, max={self.DEFAULT_MAX_DEPTH}). Prevented recursive fork bomb."
            logger.warning(f"[SubAgent] {err_msg}")
            return {"status": "error", "message": err_msg}

        task_list, err = normalize_task_list(
            goal=effective_goal,
            context=effective_context,
            tasks=tasks,
            output_schema=output_schema,
            images=images,
            role=role,
            max_children=self.max_concurrent_children,
        )
        if err or not task_list:
            return {"status": "error", "message": err or "Failed to normalize task list."}

        # Batch execution (more than 1 task or tasks explicitly provided as list)
        if len(task_list) > 1 or (tasks is not None and isinstance(tasks, list)):
            if not background:
                results = await self.spawn_batch_and_join(
                    task_list,
                    shared_context=effective_context,
                    depth=depth,
                    timeout_seconds=kwargs.get("timeout_seconds"),
                    worker_coro_factory=kwargs.get("worker_coro_factory"),
                )
                return {
                    "status": "success",
                    "mode": "batch",
                    "batch_size": len(results),
                    "results": [r.to_dict() for r in results],
                }
            else:
                spawned = []
                for idx, t_item in enumerate(task_list):
                    t_g = t_item.get("goal") or "Subagent Mission"
                    t_c = t_item.get("context") or effective_context
                    t_m = t_item.get("model") or model
                    t_p = t_item.get("provider") or provider
                    t_s = t_item.get("output_schema")
                    t_i = t_item.get("images")
                    t_r = t_item.get("role") or role or "leaf"
                    sub_t = await self.spawn_subagent_task(
                        title=t_g,
                        mission_prompt=t_c,
                        role=t_r,
                        depth=depth,
                        model=t_m,
                        provider=t_p,
                        output_schema=t_s,
                        images=t_i,
                        task_index=idx,
                    )
                    spawned.append(sub_t)
                return {
                    "status": "success",
                    "mode": "batch_background",
                    "batch_size": len(spawned),
                    "task_ids": [t.task_id for t in spawned],
                }

        # Single task execution
        t_single = task_list[0]
        s_goal = t_single.get("goal") or effective_goal
        s_ctx = t_single.get("context") or effective_context
        s_model = t_single.get("model") or model
        s_prov = t_single.get("provider") or provider
        s_schema = t_single.get("output_schema") or output_schema
        s_images = t_single.get("images") or images
        s_role = t_single.get("role") or role or "leaf"

        task = await self.spawn_subagent_task(
            title=s_goal,
            mission_prompt=s_ctx,
            role=s_role,
            depth=depth,
            model=s_model,
            provider=s_prov,
            output_schema=s_schema,
            images=s_images,
            timeout_seconds=kwargs.get("timeout_seconds"),
            worker_coro_factory=kwargs.get("worker_coro_factory"),
        )

        if not background:
            if task._async_task:
                await task._async_task
            findings_text = task.result.executive_summary if task.result else ""
            return {
                "status": "success",
                "task_id": task.task_id,
                "subagent_id": task.task_id,
                "goal": task.goal,
                "findings": findings_text,
                "summary": findings_text,
                "key_findings": task.result.key_findings if task.result else [],
                "referenced_files": task.result.referenced_files if task.result else [],
                "execution_time_sec": task.result.execution_time_sec if task.result else 0.0,
                "duration_seconds": task.result.execution_time_sec if task.result else 0.0,
                "schema_valid": task.result.schema_valid if task.result else None,
            }

        return {
            "status": "success",
            "task_id": task.task_id,
            "subagent_id": task.task_id,
            "goal": task.goal,
            "action_title": f"Subagent #{task.task_id} Active",
        }

    def cancel_task(self, task_id: str) -> bool:
        """Cancels a running subagent task."""
        return interrupt_subagent(task_id) or self._cancel_local_task(task_id)

    def _cancel_local_task(self, task_id: str) -> bool:
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
                "subagent_id": t.task_id,
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

