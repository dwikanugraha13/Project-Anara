"""
platforms/web_studio.py — Web Studio / HUD Platform Adapter for Project Anara (Hermes Parity).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional
from ..base import BasePlatformAdapter

logger = logging.getLogger("anara.integrations.web_studio")


class WebStudioPlatformAdapter(BasePlatformAdapter):
    name = "web_studio"

    async def get_status(self) -> Dict[str, Any]:
        return {"name": "web_studio", "status": "connected", "is_configured": True, "connected": True}

    async def send_message(self, target_id: str, text: str, **kwargs: Any) -> Dict[str, Any]:
        try:
            from telemetry.event_bus import telemetry_bus, EventType, ActivityProvenance
            asyncio.create_task(
                telemetry_bus.emit(
                    event_type=EventType.TEXT_CHUNK,
                    provenance=ActivityProvenance.AGENT_ORCHESTRATOR,
                    session_id=str(target_id or "default"),
                    trace_id="web_text",
                    payload={"text": text, "status": "completed"}
                )
            )
            return {"status": "success", "platform": "web_studio"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def render_approval(self, narration: str, action: Any) -> Dict[str, Any]:
        action_id = getattr(action, "action_id", getattr(action, "plan_id", "act"))
        return {
            "type": "agent_response",
            "narration": narration,
            "has_pending_action": True,
            "action_metadata": {
                "id": action_id,
                "tool": getattr(action, "tool_name", "action"),
                "args": getattr(action, "tool_args", {}),
                "risk": getattr(action, "risk_level", "mutating"),
                "created_at": getattr(action, "created_at", 0),
            },
            "text": narration,
            "reply_markup": None,
        }

    def render_message(self, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "type": "agent_response",
            "narration": narration,
            "has_pending_action": False,
            "action_metadata": None,
            "text": narration,
            "reply_markup": None,
        }

    def render_notice(self, notice_type: str, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "type": "channel_notice",
            "notice_type": notice_type,
            "text": narration,
            "narration": narration,
            "metadata": metadata or {},
            "reply_markup": None,
        }
