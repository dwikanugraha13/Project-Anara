"""
platforms/voice.py — Voice / Audio Platform Adapter for Project Anara (Hermes Parity).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from ..base import BasePlatformAdapter

logger = logging.getLogger("anara.integrations.voice")


class VoicePlatformAdapter(BasePlatformAdapter):
    name = "voice"

    async def get_status(self) -> Dict[str, Any]:
        return {"name": "voice", "status": "connected", "is_configured": True, "connected": True}

    async def send_message(self, target_id: str, text: str, **kwargs: Any) -> Dict[str, Any]:
        return {"status": "success", "platform": "voice", "text": text}

    def render_approval(self, narration: str, action: Any) -> Dict[str, Any]:
        from cognition.audio import filter_tts_speech_text
        spoken = filter_tts_speech_text(narration)
        verbal_prompt = spoken
        action_id = getattr(action, "action_id", getattr(action, "plan_id", "act"))
        return {
            "text": verbal_prompt,
            "speech_text": verbal_prompt,
            "narration": narration,
            "has_pending_action": True,
            "action_id": action_id,
            "tool_name": getattr(action, "tool_name", "action"),
            "tool_args": getattr(action, "tool_args", {}),
            "reply_markup": None,
        }

    def render_message(self, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from cognition.audio import filter_tts_speech_text
        spoken = filter_tts_speech_text(narration)
        return {
            "text": narration,
            "speech_text": spoken,
            "reply_markup": None,
        }

    def render_notice(self, notice_type: str, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from cognition.audio import filter_tts_speech_text
        spoken = filter_tts_speech_text(narration)
        return {
            "text": narration,
            "speech_text": spoken,
            "reply_markup": None,
        }
