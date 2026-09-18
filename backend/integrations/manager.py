"""
manager.py — Centralized Channel Manager for Project Anara Omnichannel Gateway.
Anara Standard gateway/run.py & platform_registry.py:
Provides supervised lifecycle management, unified messaging dispatch, and multi-channel routing.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .base import BasePlatformAdapter
from .adapters import (
    TelegramPlatformAdapter,
    WhatsAppPlatformAdapter,
    DiscordPlatformAdapter,
    SlackPlatformAdapter,
)

logger = logging.getLogger(__name__)


class ChannelManager:
    """Orchestrates all messaging platform adapters with unified lifecycle management."""

    def __init__(self):
        self._adapters: Dict[str, BasePlatformAdapter] = {
            "telegram": TelegramPlatformAdapter(),
            "whatsapp": WhatsAppPlatformAdapter(),
            "discord": DiscordPlatformAdapter(),
            "slack": SlackPlatformAdapter(),
        }

    def register_adapter(self, adapter: BasePlatformAdapter):
        """Registers an additional custom platform adapter dynamically."""
        self._adapters[adapter.name.lower()] = adapter
        logger.info(f"[ChannelManager] Registered platform adapter: {adapter.name}")

    def get_adapter(self, name: str) -> Optional[BasePlatformAdapter]:
        """Retrieves adapter instance by platform name."""
        return self._adapters.get((name or "").lower().strip())

    async def start_all(self):
        """Starts all configured platform adapters."""
        logger.info("[ChannelManager] Starting all configured omnichannel adapters...")
        for name, adapter in self._adapters.items():
            try:
                await adapter.connect()
            except Exception as e:
                logger.warning(f"[ChannelManager] Error starting {name} adapter: {e}")

    async def stop_all(self):
        """Gracefully disconnects all platform adapters."""
        logger.info("[ChannelManager] Stopping all omnichannel adapters...")
        for name, adapter in self._adapters.items():
            try:
                await adapter.disconnect()
            except Exception as e:
                logger.warning(f"[ChannelManager] Error disconnecting {name} adapter: {e}")

    async def get_all_status(self) -> Dict[str, Any]:
        """Returns aggregated connectivity status for all platforms."""
        statuses = {}
        for name, adapter in self._adapters.items():
            try:
                statuses[name] = await adapter.get_status()
            except Exception as e:
                statuses[name] = {"status": "error", "error": str(e)}
        return statuses

    async def send_message(self, channel: str, target_id: str, text: str, **kwargs) -> Dict[str, Any]:
        """Dispatches a text message through the appropriate platform adapter."""
        clean_chan = (channel or "").lower().strip()
        adapter = self._adapters.get(clean_chan)
        if not adapter:
            return {"status": "error", "message": f"Platform '{channel}' tidak didukung atau tidak aktif."}
        return await adapter.send_message(target_id=target_id, text=text, **kwargs)

    async def send_media(
        self,
        channel: str,
        target_id: str,
        file_path: str,
        caption: Optional[str] = None,
        media_type: str = "document"
    ) -> Dict[str, Any]:
        """Dispatches media through the appropriate platform adapter."""
        clean_chan = (channel or "").lower().strip()
        adapter = self._adapters.get(clean_chan)
        if not adapter:
            return {"status": "error", "message": f"Platform '{channel}' tidak didukung."}
        return await adapter.send_media(target_id=target_id, file_path=file_path, caption=caption, media_type=media_type)


# Global singleton instance
channel_manager = ChannelManager()
