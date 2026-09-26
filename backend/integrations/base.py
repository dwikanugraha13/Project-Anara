"""
base.py — Abstract Base Platform Adapter for Project Anara Omnichannel Gateway.
Anara Standard gateway/platforms/base.py (Hermes Parity):
Provides a unified polymorphic interface for transport, media dispatch, and UI presentation across all platforms.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BasePlatformAdapter(ABC):
    """Abstract base adapter for messaging platforms (Hermes Parity)."""

    name: str = "generic"

    async def connect(self, is_reconnect: bool = False) -> bool:
        """Connects or initiates the background polling/bridge process."""
        return True

    async def disconnect(self) -> None:
        """Gracefully disconnects and stops background processes."""
        pass

    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """Returns structured dictionary of platform connectivity and bot identity."""
        pass

    @abstractmethod
    async def send_message(self, target_id: str, text: str, **kwargs: Any) -> Dict[str, Any]:
        """Sends a message to the target chat_id or channel_id."""
        pass

    async def send_media(
        self,
        target_id: str,
        file_path: str,
        caption: Optional[str] = None,
        media_type: str = "document",
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Optional media dispatch handler."""
        return {"status": "unsupported", "message": f"{self.name} does not support native media dispatch"}

    # ── Presentation & Formatting (Decoupled Platform UI) ──
    def render_approval(self, narration: str, action: Any) -> Dict[str, Any]:
        """Renders platform-specific approval payload with decoupled UI elements."""
        return {
            "text": narration,
            "reply_markup": None,
        }

    def render_message(self, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Renders standard conversational message."""
        return {
            "text": narration,
            "reply_markup": None,
        }

    def render_notice(self, notice_type: str, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Renders platform-specific notice (expired, rejected, unauthorized, stopped, error)."""
        return {
            "text": narration,
            "reply_markup": None,
        }

