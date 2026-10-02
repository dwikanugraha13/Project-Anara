"""
tracer.py — Tool Execution Tracer (Anara Standard).
Measures execution latency and wraps tool calls with structured telemetry events.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, Optional
from telemetry.event_bus import telemetry_bus, EventType, ActivityProvenance

_SENSITIVE_ARG_KEYS = frozenset({
    "password", "passwd", "secret", "token", "auth", "authorization",
    "api_key", "apikey", "access_token", "refresh_token", "private_key"
})


def _scrub_args(obj: Any) -> Any:
    """Recursively redacts credential keys from telemetry arguments."""
    if isinstance(obj, dict):
        scrubbed = {}
        for k, v in obj.items():
            if str(k).lower() in _SENSITIVE_ARG_KEYS:
                scrubbed[k] = "******"
            else:
                scrubbed[k] = _scrub_args(v)
        return scrubbed
    elif isinstance(obj, (list, tuple)):
        return [_scrub_args(item) for item in obj]
    return obj


class ToolTracer:
    """Thread-safe context manager (supporting async and sync) wrapping tool execution with telemetry events."""

    def __init__(
        self,
        session_id: str,
        trace_id: Optional[str],
        tool_name: str,
        args: Dict[str, Any],
    ):
        self._lock = threading.RLock()
        self.session_id = str(session_id or "default")
        self.trace_id = str(trace_id or f"tr_{uuid.uuid4().hex[:8]}")
        self.tool_name = str(tool_name or "unknown")
        # Defensive copy to prevent mutation race conditions
        self.args = dict(args) if isinstance(args, dict) else args
        self.start_time = 0.0
        self._perf_start = 0.0

    async def __aenter__(self):
        with self._lock:
            self.start_time = time.time()
            self._perf_start = time.perf_counter()
            safe_args = _scrub_args(self.args)
        await telemetry_bus.emit(
            event_type=EventType.TOOL_START,
            provenance=ActivityProvenance.TOOL_RUNNER,
            session_id=self.session_id,
            trace_id=self.trace_id,
            payload={
                "tool": self.tool_name,
                "arguments": safe_args,
            },
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        with self._lock:
            if self._perf_start > 0:
                duration_ms = round((time.perf_counter() - self._perf_start) * 1000, 2)
            else:
                duration_ms = round((time.time() - self.start_time) * 1000, 2)
            status = "error" if exc_type else "success"
            error_msg = str(exc_val) if exc_val else None

        await telemetry_bus.emit(
            event_type=EventType.TOOL_COMPLETED,
            provenance=ActivityProvenance.TOOL_RUNNER,
            session_id=self.session_id,
            trace_id=self.trace_id,
            payload={
                "tool": self.tool_name,
                "status": status,
                "duration_ms": duration_ms,
                "error": error_msg,
            },
        )
        return False

    def __enter__(self):
        with self._lock:
            self.start_time = time.time()
            self._perf_start = time.perf_counter()
            safe_args = _scrub_args(self.args)
        telemetry_bus.emit_threadsafe(
            event_type=EventType.TOOL_START,
            provenance=ActivityProvenance.TOOL_RUNNER,
            session_id=self.session_id,
            trace_id=self.trace_id,
            payload={
                "tool": self.tool_name,
                "arguments": safe_args,
            },
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        with self._lock:
            if self._perf_start > 0:
                duration_ms = round((time.perf_counter() - self._perf_start) * 1000, 2)
            else:
                duration_ms = round((time.time() - self.start_time) * 1000, 2)
            status = "error" if exc_type else "success"
            error_msg = str(exc_val) if exc_val else None

        telemetry_bus.emit_threadsafe(
            event_type=EventType.TOOL_COMPLETED,
            provenance=ActivityProvenance.TOOL_RUNNER,
            session_id=self.session_id,
            trace_id=self.trace_id,
            payload={
                "tool": self.tool_name,
                "status": status,
                "duration_ms": duration_ms,
                "error": error_msg,
            },
        )
        return False
