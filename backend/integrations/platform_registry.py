"""
platform_registry.py — Central Dynamic Platform Registry for Project Anara.
Hermes Agent Parity (gateway/platform_registry.py):
Provides a clean, modular registry connecting all platform adapters (Telegram, WhatsApp,
Discord, Slack, WebStudio, CLI, Voice).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import BasePlatformAdapter
from .platforms import (
    TelegramPlatformAdapter,
    WhatsAppPlatformAdapter,
    DiscordPlatformAdapter,
    SlackPlatformAdapter,
    WebStudioPlatformAdapter,
    CliPlatformAdapter,
    VoicePlatformAdapter,
)

logger = logging.getLogger("anara.integrations.registry")


class PlatformRegistry:
    """
    Central dynamic registry of communication platforms (Hermes Parity).
    Manages adapters, status, messaging, media dispatch, and presentation rendering in one place.
    """

    def __init__(self):
        self._adapters: Dict[str, BasePlatformAdapter] = {}
        self._aliases: Dict[str, str] = {
            "tg": "telegram",
            "tele": "telegram",
            "wa": "whatsapp",
            "web": "web_studio",
            "terminal": "cli",
            "voice_hud": "voice",
            "audio": "voice",
        }
        self._init_defaults()

    def _init_defaults(self):
        self.register(TelegramPlatformAdapter())
        self.register(WhatsAppPlatformAdapter())
        self.register(DiscordPlatformAdapter())
        self.register(SlackPlatformAdapter())
        self.register(WebStudioPlatformAdapter())
        self.register(CliPlatformAdapter())
        self.register(VoicePlatformAdapter())

    def register(self, adapter: BasePlatformAdapter):
        """Registers a platform adapter dynamically."""
        key = adapter.name.lower().strip()
        self._adapters[key] = adapter
        logger.info(f"[PlatformRegistry] Registered platform: {key}")

    def get(self, name: str) -> Optional[BasePlatformAdapter]:
        """Resolves adapter by name or alias."""
        clean = (name or "").lower().strip()
        canonical = self._aliases.get(clean, clean)
        return self._adapters.get(canonical)

    def get_or_default(self, name: str) -> BasePlatformAdapter:
        """Resolves adapter or falls back to CLI."""
        return self.get(name) or self._adapters.get("cli", CliPlatformAdapter())

    def list_platforms(self) -> List[str]:
        return sorted(list(self._adapters.keys()))

    async def start_all(self):
        """Connects all configured adapters."""
        for name, adapter in self._adapters.items():
            try:
                await adapter.connect()
            except Exception as e:
                logger.warning(f"[PlatformRegistry] Error starting {name}: {e}")

    async def stop_all(self):
        """Gracefully disconnects all adapters."""
        for name, adapter in self._adapters.items():
            try:
                await adapter.disconnect()
            except Exception as e:
                logger.warning(f"[PlatformRegistry] Error stopping {name}: {e}")

    async def get_all_status(self) -> Dict[str, Any]:
        """Returns aggregated connectivity status for all platforms."""
        statuses = {}
        for name, adapter in self._adapters.items():
            try:
                statuses[name] = await adapter.get_status()
            except Exception as e:
                statuses[name] = {"status": "error", "error": str(e)}
        return statuses

    async def send_message(self, platform: str, target_id: str, text: str, **kwargs: Any) -> Dict[str, Any]:
        """Dispatches text message through the resolved platform adapter."""
        adapter = self.get(platform)
        if not adapter:
            return {"status": "error", "message": f"Platform '{platform}' tidak didukung."}
        return await adapter.send_message(target_id=target_id, text=text, **kwargs)

    async def send_media(
        self,
        platform: str,
        target_id: str,
        file_path: str,
        caption: Optional[str] = None,
        media_type: str = "document",
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Dispatches media through the resolved platform adapter."""
        adapter = self.get(platform)
        if not adapter:
            return {"status": "error", "message": f"Platform '{platform}' tidak didukung."}
        return await adapter.send_media(target_id=target_id, file_path=file_path, caption=caption, media_type=media_type, **kwargs)

    def render_approval_payload(self, platform: str, narration: str, action: Any) -> Dict[str, Any]:
        adapter = self.get_or_default(platform)
        return adapter.render_approval(narration, action)

    def render_message_payload(self, platform: str, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        adapter = self.get_or_default(platform)
        return adapter.render_message(narration, metadata=metadata)

    def render_notice_payload(self, platform: str, notice_type: str, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        adapter = self.get_or_default(platform)
        return adapter.render_notice(notice_type, narration, metadata=metadata)


# Global singleton instance
platform_registry = PlatformRegistry()
