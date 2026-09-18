"""
base.py — Abstract Base Platform Adapter for Project Anara Omnichannel Gateway.
Anara Standard gateway/platforms/base.py:
Provides a unified polymorphic interface for all messaging platforms.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BasePlatformAdapter(ABC):
    """Abstract base adapter for messaging platforms."""

    name: str

    @abstractmethod
    async def connect(self, is_reconnect: bool = False) -> bool:
        """Connects or initiates the background polling/bridge process."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully disconnects and stops background processes."""
        pass

    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """Returns structured dictionary of platform connectivity and bot identity."""
        pass

    @abstractmethod
    async def send_message(self, target_id: str, text: str, **kwargs) -> Dict[str, Any]:
        """Sends a message to the target chat_id or channel_id."""
        pass

    async def send_media(self, target_id: str, file_path: str, caption: Optional[str] = None, media_type: str = "document") -> Dict[str, Any]:
        """Optional media dispatch handler."""
        return {"status": "unsupported", "message": f"{self.name} does not support native media dispatch"}
