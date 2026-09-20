"""
manager.py — Backward-compatible Channel Manager proxy delegating to PlatformRegistry.
Hermes Agent Parity: Central Platform Registry as Single Source of Truth.
"""

import logging
from typing import Any, Dict, Optional
from .platform_registry import platform_registry, BasePlatformAdapter

logger = logging.getLogger(__name__)


class ChannelManager:
    """Delegates all omnichannel operations to the central PlatformRegistry."""

    def register_adapter(self, adapter: BasePlatformAdapter):
        platform_registry.register(adapter)

    def get_adapter(self, name: str) -> Optional[BasePlatformAdapter]:
        return platform_registry.get(name)

    async def start_all(self):
        await platform_registry.start_all()

    async def stop_all(self):
        await platform_registry.stop_all()

    async def get_all_status(self) -> Dict[str, Any]:
        return await platform_registry.get_all_status()

    async def send_message(self, channel: str, target_id: str, text: str, **kwargs) -> Dict[str, Any]:
        return await platform_registry.send_message(channel, target_id, text, **kwargs)

    async def send_media(
        self,
        channel: str,
        target_id: str,
        file_path: str,
        caption: Optional[str] = None,
        media_type: str = "document",
        **kwargs
    ) -> Dict[str, Any]:
        return await platform_registry.send_media(channel, target_id, file_path, caption=caption, media_type=media_type, **kwargs)


# Global singleton instance
channel_manager = ChannelManager()
