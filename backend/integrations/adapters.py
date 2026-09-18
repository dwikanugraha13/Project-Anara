"""
adapters.py — Concrete Platform Adapters for Project Anara Omnichannel Gateway.
Anara Standard gateway/platforms/
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from .base import BasePlatformAdapter

logger = logging.getLogger(__name__)


class TelegramPlatformAdapter(BasePlatformAdapter):
    name = "telegram"

    async def connect(self, is_reconnect: bool = False) -> bool:
        from .telegram import start_telegram_polling_daemon, get_stored_telegram_token
        token = get_stored_telegram_token()
        if token:
            start_telegram_polling_daemon()
            return True
        return False

    async def disconnect(self) -> None:
        from .telegram import stop_telegram_polling_daemon
        stop_telegram_polling_daemon()

    async def get_status(self) -> Dict[str, Any]:
        from .telegram import get_telegram_status
        return await get_telegram_status()

    async def send_message(self, target_id: str, text: str, **kwargs) -> Dict[str, Any]:
        from .telegram import send_telegram_message
        parse_mode = kwargs.get("parse_mode", "HTML")
        return await send_telegram_message(text=text, chat_id=target_id, parse_mode=parse_mode)

    async def send_media(self, target_id: str, file_path: str, caption: Optional[str] = None, media_type: str = "document") -> Dict[str, Any]:
        from .telegram import send_telegram_document, send_telegram_photo, send_telegram_video, send_telegram_voice
        if media_type == "voice":
            return await send_telegram_voice(file_path=file_path, caption=caption or "", chat_id=target_id)
        elif media_type == "photo":
            return await send_telegram_photo(file_path=file_path, caption=caption or "", chat_id=target_id)
        elif media_type == "video":
            return await send_telegram_video(file_path=file_path, caption=caption or "", chat_id=target_id)
        else:
            return await send_telegram_document(file_path=file_path, caption=caption or "", chat_id=target_id)


class WhatsAppPlatformAdapter(BasePlatformAdapter):
    name = "whatsapp"

    async def connect(self, is_reconnect: bool = False) -> bool:
        from .whatsapp import start_whatsapp_bridge
        start_whatsapp_bridge()
        return True

    async def disconnect(self) -> None:
        from .whatsapp import stop_whatsapp_bridge
        stop_whatsapp_bridge()

    async def get_status(self) -> Dict[str, Any]:
        from .whatsapp import get_whatsapp_status
        return await get_whatsapp_status()

    async def send_message(self, target_id: str, text: str, **kwargs) -> Dict[str, Any]:
        from .whatsapp import send_whatsapp_message
        return await send_whatsapp_message(to=target_id, message=text)

    async def send_media(self, target_id: str, file_path: str, caption: Optional[str] = None, media_type: str = "document") -> Dict[str, Any]:
        from .whatsapp import send_whatsapp_document
        return await send_whatsapp_document(to=target_id, file_path=file_path, caption=caption or "")


class DiscordPlatformAdapter(BasePlatformAdapter):
    name = "discord"

    async def connect(self, is_reconnect: bool = False) -> bool:
        from .discord import start_discord_polling_daemon, get_stored_discord_token
        token = get_stored_discord_token()
        if token:
            start_discord_polling_daemon()
            return True
        return False

    async def disconnect(self) -> None:
        from .discord import stop_discord_polling_daemon
        stop_discord_polling_daemon()

    async def get_status(self) -> Dict[str, Any]:
        from .discord import get_discord_status
        return await get_discord_status()

    async def send_message(self, target_id: str, text: str, **kwargs) -> Dict[str, Any]:
        from .discord import send_discord_message
        return await send_discord_message(channel_id=target_id, content=text)


class SlackPlatformAdapter(BasePlatformAdapter):
    name = "slack"

    async def connect(self, is_reconnect: bool = False) -> bool:
        from .slack import start_slack_polling_daemon, get_stored_slack_token
        token = get_stored_slack_token()
        if token:
            start_slack_polling_daemon()
            return True
        return False

    async def disconnect(self) -> None:
        from .slack import stop_slack_polling_daemon
        stop_slack_polling_daemon()

    async def get_status(self) -> Dict[str, Any]:
        from .slack import get_slack_status
        return await get_slack_status()

    async def send_message(self, target_id: str, text: str, **kwargs) -> Dict[str, Any]:
        from .slack import send_slack_message
        return await send_slack_message(channel_id=target_id, text=text)
