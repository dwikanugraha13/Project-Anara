"""
tracer.py — Tool Execution Tracer (Anara Standard).
Measures execution latency and wraps tool calls with structured telemetry events.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional
from telemetry.event_bus import telemetry_bus, EventType, ActivityProvenance


class ToolTracer:
    """Async context manager wrapping tool execution with telemetry events."""

    def __init__(
        self,
        session_id: str,
        trace_id: Optional[str],
        tool_name: str,
        args: Dict[str, Any],
    ):
        self.session_id = str(session_id or "default")
        self.trace_id = str(trace_id or f"tr_{uuid.uuid4().hex[:8]}")
        self.tool_name = tool_name
        self.args = args
        self.start_time = 0.0

    async def __aenter__(self):
        self.start_time = time.time()
        await telemetry_bus.emit(
            event_type=EventType.TOOL_START,
            provenance=ActivityProvenance.TOOL_RUNNER,
            session_id=self.session_id,
            trace_id=self.trace_id,
            payload={
                "tool": self.tool_name,
                "arguments": self.args,
            },
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
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
