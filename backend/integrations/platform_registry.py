"""
platform_registry.py — Central Dynamic Platform Registry for Project Anara.
Hermes Agent Parity (gateway/platform_registry.py):
Provides a clean, modular registry connecting all platform adapters (Telegram, WhatsApp,
Discord, Slack, WebStudio, CLI, Voice).
"""

from __future__ import annotations

import asyncio
import logging
import os
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
        """Connects all configured adapters concurrently (Hermes Parity)."""
        async def _connect_safe(name: str, adapter: BasePlatformAdapter):
            try:
                await adapter.connect()
            except Exception as e:
                logger.warning(f"[PlatformRegistry] Error starting {name}: {e}")

        await asyncio.gather(*[_connect_safe(n, a) for n, a in self._adapters.items()], return_exceptions=True)

    async def stop_all(self):
        """Gracefully disconnects all adapters concurrently (Hermes Parity)."""
        async def _disconnect_safe(name: str, adapter: BasePlatformAdapter):
            try:
                await adapter.disconnect()
            except Exception as e:
                logger.warning(f"[PlatformRegistry] Error stopping {name}: {e}")

        await asyncio.gather(*[_disconnect_safe(n, a) for n, a in self._adapters.items()], return_exceptions=True)

    async def get_all_status(self) -> Dict[str, Any]:
        """Returns aggregated connectivity status for all platforms concurrently (Hermes Parity)."""
        async def _get_status_safe(name: str, adapter: BasePlatformAdapter) -> tuple[str, Dict[str, Any]]:
            try:
                st = await adapter.get_status()
                return name, st
            except Exception as e:
                return name, {"status": "error", "error": str(e)}

        results = await asyncio.gather(*[_get_status_safe(n, a) for n, a in self._adapters.items()], return_exceptions=True)
        statuses = {}
        for item in results:
            if isinstance(item, tuple):
                n, st = item
                statuses[n] = st
        return statuses

    async def send_message(self, platform: str, target_id: str, text: str, **kwargs: Any) -> Dict[str, Any]:
        """Dispatches text message through the resolved platform adapter with fault isolation."""
        adapter = self.get(platform)
        if not adapter:
            return {"status": "error", "message": f"Platform '{platform}' not supported."}
        try:
            return await adapter.send_message(target_id=target_id, text=text, **kwargs)
        except Exception as e:
            logger.error(f"[PlatformRegistry] send_message error on platform '{platform}': {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    async def send_media(
        self,
        platform: str,
        target_id: str,
        file_path: str,
        caption: Optional[str] = None,
        media_type: str = "document",
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Dispatches media through the resolved platform adapter with path verification."""
        adapter = self.get(platform)
        if not adapter:
            return {"status": "error", "message": f"Platform '{platform}' not supported."}
        
        # Verify file path before dispatch (Hermes security parity)
        clean_path = (file_path or "").strip()
        if not clean_path or not os.path.isfile(clean_path):
            return {"status": "error", "message": f"Media file not found or invalid: '{clean_path}'"}

        try:
            from core.workspace_sentinel import workspace_sentinel
            is_valid, reason = workspace_sentinel.validate_file_access(clean_path, action="read")
            if not is_valid:
                return {"status": "error", "message": f"Media dispatch blocked by security sentinel: {reason}"}
        except Exception:
            pass

        try:
            return await adapter.send_media(target_id=target_id, file_path=clean_path, caption=caption, media_type=media_type, **kwargs)
        except Exception as e:
            logger.error(f"[PlatformRegistry] send_media error on platform '{platform}': {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def render_approval_payload(self, platform: str, narration: str, action: Any) -> Dict[str, Any]:
        try:
            adapter = self.get_or_default(platform)
            return adapter.render_approval(narration, action)
        except Exception as e:
            logger.warning(f"[PlatformRegistry] render_approval error: {e}")
            return {"text": narration, "reply_markup": None}

    def render_message_payload(self, platform: str, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            adapter = self.get_or_default(platform)
            return adapter.render_message(narration, metadata=metadata)
        except Exception as e:
            logger.warning(f"[PlatformRegistry] render_message error: {e}")
            return {"text": narration, "reply_markup": None}

    def render_notice_payload(self, platform: str, notice_type: str, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            adapter = self.get_or_default(platform)
            return adapter.render_notice(notice_type, narration, metadata=metadata)
        except Exception as e:
            logger.warning(f"[PlatformRegistry] render_notice error: {e}")
            return {"text": narration, "reply_markup": None}


# Global singleton instance
platform_registry = PlatformRegistry()
