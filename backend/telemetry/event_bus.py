"""
event_bus.py — Anara Unified Telemetry, Activity Provenance & Streaming Event Bus.
Provides real-time event distribution for Web Studio, HUD, WebSocket, and multi-channel adapters.
"""

from __future__ import annotations

import asyncio
import collections
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    SESSION_START = "session_start"
    REASONING_START = "reasoning_start"
    REASONING_CHUNK = "reasoning_chunk"      # Streaming thought tokens
    TOOL_START = "tool_start"                # Tool execution start
    TOOL_PROGRESS = "tool_progress"          # Long process streaming log
    TOOL_COMPLETED = "tool_completed"        # Tool execution result + latency
    TEXT_CHUNK = "text_chunk"                # Final text answer streaming
    TOKEN_TELEMETRY = "token_telemetry"      # Token usage & cost report
    ERROR = "error"
    SESSION_FINISH = "session_finish"

    # ── Code Studio & HUD Visual Telemetry (Pilar 2 & Subsystem 5) ──
    FILE_MODIFIED = "file_modified"              # Live Split-Diff & workspace updates
    GUARDRAIL_TRIGGERED = "guardrail_triggered"  # Blast radius & protection events
    GROUND_TRUTH_CHECK = "ground_truth_check"    # Test validation & disk readback
    ADR_RECORDED = "adr_recorded"                # Episodic architecture decision (Pilar 3)


class ActivityProvenance(str, Enum):
    AGENT_ORCHESTRATOR = "agent_orchestrator"
    REASONING_ENGINE = "reasoning_engine"
    TOOL_RUNNER = "tool_runner"
    CONTEXT_COMPACTOR = "context_compactor"
    SUBAGENT_WORKER = "subagent_worker"
    WORKSPACE_SENTINEL = "workspace_sentinel"


def _safe_serialize_val(val: Any) -> Any:
    """Recursively converts objects to JSON-serializable primitives."""
    if val is None or isinstance(val, (str, int, float, bool)):
        return val
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, dict):
        return {str(k): _safe_serialize_val(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [_safe_serialize_val(item) for item in val]
    if hasattr(val, "to_dict") and callable(val.to_dict):
        try:
            return _safe_serialize_val(val.to_dict())
        except Exception:
            return str(val)
    return str(val)


@dataclass
class AgentEvent:
    event_type: EventType | str
    provenance: ActivityProvenance | str
    trace_id: str
    session_id: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    seq_id: int = 0

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["event_type"] = self.event_type.value if hasattr(self.event_type, "value") else str(self.event_type)
        data["provenance"] = self.provenance.value if hasattr(self.provenance, "value") else str(self.provenance)
        data["payload"] = _safe_serialize_val(self.payload)
        return data


class TelemetryEventBus:
    """Central asynchronous Event Bus for distributing Anara agent telemetry (Anara Enterprise Architecture)."""

    def __init__(self):
        self._lock = threading.RLock()
        self._listeners: Dict[str, List[asyncio.Queue[AgentEvent]]] = {}
        self._global_hooks: List[Callable[[AgentEvent], Any]] = []
        self._active_tasks: Set[asyncio.Task] = set()
        self._session_seqs: Dict[str, int] = collections.OrderedDict()
        self._session_dropped: Dict[str, int] = collections.OrderedDict()
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        self._max_tracked_sessions: int = 2000

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Explicitly registers the main asyncio event loop for threadsafe dispatches."""
        with self._lock:
            self._main_loop = loop

    def register_hook(self, callback: Callable[[AgentEvent], Any]):
        """Registers a global hook (e.g. terminal logger or metric collector)."""
        with self._lock:
            if callback not in self._global_hooks:
                self._global_hooks.append(callback)

    def unregister_hook(self, callback: Callable[[AgentEvent], Any]):
        """Unregisters a previously registered global telemetry hook (Anara Standard)."""
        with self._lock:
            if callback in self._global_hooks:
                self._global_hooks.remove(callback)

    def subscribe(self, session_id: str, max_queue_size: int = 500) -> asyncio.Queue[AgentEvent]:
        """Subscribes an SSE or WebSocket client queue to a session's telemetry events with bounded capacity."""
        try:
            loop = asyncio.get_running_loop()
            with self._lock:
                if not self._main_loop or not self._main_loop.is_running():
                    self._main_loop = loop
        except RuntimeError:
            pass

        s_key = str(session_id or "default")
        bounded_size = max(1, min(int(max_queue_size), 5000))
        queue: asyncio.Queue[AgentEvent] = asyncio.Queue(maxsize=bounded_size)
        with self._lock:
            if s_key not in self._listeners:
                self._listeners[s_key] = []
            self._listeners[s_key].append(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue[AgentEvent]):
        """Unsubscribes a client queue when connection closes, preserving metrics in a bounded window."""
        s_key = str(session_id or "default")
        with self._lock:
            if s_key in self._listeners:
                if queue in self._listeners[s_key]:
                    self._listeners[s_key].remove(queue)
                if not self._listeners[s_key]:
                    del self._listeners[s_key]

            # Bounded LRU-style cleanup of stale historical session metadata
            while len(self._session_seqs) > self._max_tracked_sessions:
                oldest = next(iter(self._session_seqs))
                if oldest not in self._listeners:
                    self._session_seqs.pop(oldest, None)
                    self._session_dropped.pop(oldest, None)
                else:
                    break

    def _hook_done_callback(self, task: asyncio.Task):
        with self._lock:
            self._active_tasks.discard(task)
        if not task.cancelled():
            exc = task.exception()
            if exc:
                logger.error(f"[TelemetryBus] Async hook error: {exc}")

    async def emit(
        self,
        event_type: EventType | str,
        provenance: ActivityProvenance | str,
        session_id: str,
        trace_id: str,
        payload: Dict[str, Any],
    ):
        """Broadcasts an agent event to session subscribers and global hooks."""
        try:
            self._main_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        s_key = str(session_id or "default")
        with self._lock:
            seq = self._session_seqs.get(s_key, 0) + 1
            self._session_seqs[s_key] = seq
            hooks_snapshot = list(self._global_hooks)
            listeners_snapshot = list(self._listeners.get(s_key, []))

        event = AgentEvent(
            event_type=event_type,
            provenance=provenance,
            trace_id=trace_id,
            session_id=s_key,
            payload=payload,
            seq_id=seq,
        )

        # 1. Run global hooks with strong-reference task retention and thread safety
        for hook in hooks_snapshot:
            try:
                res = hook(event)
                if asyncio.iscoroutine(res):
                    task = asyncio.create_task(res)
                    with self._lock:
                        self._active_tasks.add(task)
                    task.add_done_callback(self._hook_done_callback)
            except Exception as e:
                logger.error(f"[TelemetryBus] Hook {hook} failed: {e}")

        # 2. Forward to session queues with drop-oldest eviction policy to prevent OOM
        for q in listeners_snapshot:
            for _ in range(5):  # Bounded eviction loop
                try:
                    q.put_nowait(event)
                    break
                except asyncio.QueueFull:
                    try:
                        q.get_nowait()
                        with self._lock:
                            self._session_dropped[s_key] = self._session_dropped.get(s_key, 0) + 1
                    except asyncio.QueueEmpty:
                        continue

    def emit_threadsafe(
        self,
        event_type: EventType | str,
        provenance: ActivityProvenance | str,
        session_id: str,
        trace_id: str,
        payload: Dict[str, Any],
    ) -> None:
        """
        Thread-safe bridge to emit telemetry from worker threads or sync tools
        without raising 'no running event loop' errors.
        """
        target_loop = None
        try:
            target_loop = asyncio.get_running_loop()
        except RuntimeError:
            with self._lock:
                if self._main_loop and self._main_loop.is_running():
                    target_loop = self._main_loop

        if target_loop and target_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.emit(event_type, provenance, session_id, trace_id, payload),
                target_loop
            )
        else:
            logger.debug(f"[TelemetryBus] Event dropped (no active loop for threadsafe emit): {event_type}")

    def get_dropped_count(self, session_id: str) -> int:
        """Returns the count of events dropped due to queue saturation for a session (Anara Standard)."""
        s_key = str(session_id or "default")
        with self._lock:
            return self._session_dropped.get(s_key, 0)

    def get_total_dropped(self) -> int:
        """Returns total events dropped across all active session queues."""
        with self._lock:
            return sum(self._session_dropped.values())

    def get_stats(self) -> Dict[str, Any]:
        """Returns a telemetry metrics snapshot including drop counters and subscriber load."""
        with self._lock:
            return {
                "active_sessions": len(self._listeners),
                "total_listeners": sum(len(q_list) for q_list in self._listeners.values()),
                "global_hooks_count": len(self._global_hooks),
                "total_dropped_events": sum(self._session_dropped.values()),
                "session_dropped": dict(self._session_dropped),
                "session_seqs": dict(self._session_seqs),
            }

    async def shutdown(self):
        """Gracefully cancels active hook tasks and drains listeners."""
        with self._lock:
            tasks = list(self._active_tasks)
            self._active_tasks.clear()
            self._listeners.clear()
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# Singleton instance
telemetry_bus = TelemetryEventBus()
