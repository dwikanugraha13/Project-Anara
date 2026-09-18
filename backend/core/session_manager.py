"""
session_manager.py — State Machine Intent & Pending Action Tracker for Project Anara.
Anara Standard multi-channel session state management:
1. Tracks active transaction states (IDLE, AWAITING_APPROVAL, EXECUTING).
2. Holds pending high-risk tool actions with automatic TTL expiration.
3. Decouples conversational approval intent tracking from rigid regex dictionaries.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from core.plan_detector import is_explicit_plan_approval

logger = logging.getLogger(__name__)


@dataclass
class PendingAction:
    """Represents a paused mutating action waiting for user confirmation."""
    plan_id: str
    session_id: int
    channel: str
    channel_id: str
    tool_name: str
    tool_args: Dict[str, Any] = field(default_factory=dict)
    original_prompt: str = ""
    plan_text: str = ""
    user_id: str = "default_user"
    pending_tool_call: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = 3600.0  # 1 hour expiration

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "session_id": self.session_id,
            "channel": self.channel,
            "channel_id": self.channel_id,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "original_prompt": self.original_prompt,
            "plan_text": self.plan_text,
            "user_id": self.user_id,
            "pending_tool_call": self.pending_tool_call,
            "created_at": self.created_at,
        }


class SessionStateManager:
    """Multi-channel state machine tracking pending action states per chat channel."""

    def __init__(self):
        self._pending: Dict[str, PendingAction] = {}

    def _make_key(self, channel: str, channel_id: str) -> str:
        return f"{str(channel).strip().lower()}_{str(channel_id).strip()}"

    def store_pending(self, action: PendingAction) -> None:
        key = self._make_key(action.channel, action.channel_id)
        self._pending[key] = action
        logger.info(f"[SessionManager] Stored pending action #{action.plan_id} ({action.tool_name}) for key: {key}")

    def get_pending(self, channel: str, channel_id: str) -> Optional[PendingAction]:
        key = self._make_key(channel, channel_id)
        action = self._pending.get(key)
        if action and action.is_expired:
            logger.info(f"[SessionManager] Pending action #{action.plan_id} has expired.")
            del self._pending[key]
            return None
        return action

    def clear_pending(self, channel: str, channel_id: str) -> Optional[PendingAction]:
        key = self._make_key(channel, channel_id)
        return self._pending.pop(key, None)

    def evaluate_intent(self, text: str, channel: str, channel_id: str) -> Dict[str, Any]:
        """
        Evaluates incoming user message against session state.
        Returns {'has_pending': bool, 'is_approval': bool, 'pending': Optional[PendingAction]}
        """
        pending = self.get_pending(channel, channel_id)
        if not pending:
            return {"has_pending": False, "is_approval": False, "pending": None}

        # User sent a message while an action is pending
        is_app = is_explicit_plan_approval(text)
        return {
            "has_pending": True,
            "is_approval": is_app,
            "pending": pending
        }


# Global singleton session manager
session_state_manager = SessionStateManager()
