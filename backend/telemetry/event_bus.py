"""
event_bus.py — Anara Unified Telemetry, Activity Provenance & Streaming Event Bus.
Provides real-time event distribution for Web Studio, HUD, WebSocket, and multi-channel adapters.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


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


@dataclass
class AgentEvent:
    event_type: EventType
    provenance: ActivityProvenance
    trace_id: str
    session_id: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["provenance"] = self.provenance.value
        return data


class TelemetryEventBus:
    """Central asynchronous Event Bus for distributing Anara agent telemetry."""

    def __init__(self):
        # Active listener queues per session_id: Dict[str, List[asyncio.Queue]]
        self._listeners: Dict[str, List[asyncio.Queue]] = {}
        self._global_hooks: List[Callable[[AgentEvent], Any]] = []
        self._active_tasks: Set[asyncio.Task] = set()

    def register_hook(self, callback: Callable[[AgentEvent], Any]):
        """Registers a global hook (e.g. terminal logger or metric collector)."""
        if callback not in self._global_hooks:
            self._global_hooks.append(callback)

    def unregister_hook(self, callback: Callable[[AgentEvent], Any]):
        """Unregisters a previously registered global telemetry hook (Claude Code Parity)."""
        if callback in self._global_hooks:
            self._global_hooks.remove(callback)

    def subscribe(self, session_id: str, max_queue_size: int = 500) -> asyncio.Queue:
        """Subscribes an SSE or WebSocket client queue to a session's telemetry events with bounded capacity."""
        s_key = str(session_id or "default")
        queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        if s_key not in self._listeners:
            self._listeners[s_key] = []
        self._listeners[s_key].append(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue):
        """Unsubscribes a client queue when connection closes."""
        s_key = str(session_id or "default")
        if s_key in self._listeners:
            if queue in self._listeners[s_key]:
                self._listeners[s_key].remove(queue)
            if not self._listeners[s_key]:
                del self._listeners[s_key]

    async def emit(
        self,
        event_type: EventType,
        provenance: ActivityProvenance,
        session_id: str,
        trace_id: str,
        payload: Dict[str, Any],
    ):
        """Broadcasts an agent event to session subscribers and global hooks."""
        event = AgentEvent(
            event_type=event_type,
            provenance=provenance,
            trace_id=trace_id,
            session_id=str(session_id or "default"),
            payload=payload,
        )

        # 1. Run global hooks with strong-reference task retention (Python 3.11+ GC Parity)
        for hook in list(self._global_hooks):
            try:
                res = hook(event)
                if asyncio.iscoroutine(res):
                    task = asyncio.create_task(res)
                    self._active_tasks.add(task)
                    task.add_done_callback(self._active_tasks.discard)
            except Exception:
                pass

        # 2. Forward to session queues with drop-oldest eviction policy to prevent OOM
        s_key = str(session_id or "default")
        if s_key in self._listeners:
            for q in list(self._listeners[s_key]):
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    try:
                        q.get_nowait()
                        q.put_nowait(event)
                    except Exception:
                        pass


# Singleton instance
telemetry_bus = TelemetryEventBus()
