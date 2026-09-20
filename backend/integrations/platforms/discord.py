"""
platforms/discord.py — Discord Platform Adapter for Project Anara (Hermes Parity).
"""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, Optional
import httpx
from ..base import BasePlatformAdapter

logger = logging.getLogger("anara.integrations.discord")


class DiscordPlatformAdapter(BasePlatformAdapter):
    name = "discord"

    @property
    def token(self) -> str:
        return (os.getenv("DISCORD_BOT_TOKEN") or "").strip()

    @property
    def webhook_url(self) -> str:
        return (os.getenv("DISCORD_WEBHOOK_URL") or "").strip()

    @property
    def default_channel_id(self) -> str:
        return (os.getenv("DISCORD_CHANNEL_ID") or "").strip()

    async def connect(self, is_reconnect: bool = False) -> bool:
        status_info = await self.get_status()
        return bool(status_info.get("connected", False))

    async def get_status(self) -> Dict[str, Any]:
        token = self.token
        webhook = self.webhook_url
        if not token and not webhook:
            return {
                "name": "discord",
                "status": "not_configured",
                "is_configured": False,
                "connected": False,
                "reason": "missing_credentials",
            }

        if token:
            try:
                headers = {"Authorization": f"Bot {token}", "User-Agent": "AnaraAgent/1.0"}
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.get("https://discord.com/api/v10/users/@me", headers=headers)
                    if resp.status_code == 200:
                        bot_data = resp.json()
                        return {
                            "name": "discord",
                            "status": "connected",
                            "is_configured": True,
                            "connected": True,
                            "mode": "bot",
                            "bot": {
                                "id": bot_data.get("id"),
                                "username": bot_data.get("username"),
                                "discriminator": bot_data.get("discriminator"),
                            },
                        }
                    elif resp.status_code in (401, 403):
                        return {
                            "name": "discord",
                            "status": "error",
                            "is_configured": True,
                            "connected": False,
                            "error": f"HTTP_{resp.status_code}_UNAUTHORIZED",
                        }
            except Exception as e:
                return {
                    "name": "discord",
                    "status": "error",
                    "is_configured": True,
                    "connected": False,
                    "error": str(e),
                }

        if webhook:
            return {
                "name": "discord",
                "status": "connected",
                "is_configured": True,
                "connected": True,
                "mode": "webhook",
            }

        return {
            "name": "discord",
            "status": "disconnected",
            "is_configured": True,
            "connected": False,
            "reason": "connection_failed",
        }

    async def send_message(self, target_id: str, text: str, **kwargs: Any) -> Dict[str, Any]:
        token = self.token
        webhook = self.webhook_url
        effective_channel = (target_id or self.default_channel_id).strip()

        if token and effective_channel:
            try:
                headers = {
                    "Authorization": f"Bot {token}",
                    "Content-Type": "application/json",
                    "User-Agent": "AnaraAgent/1.0",
                }
                from core.channel_adapter import split_message_chunks
                chunks = split_message_chunks(text, max_chars=1950, add_part_headers=True, platform="discord") or [""]
                last_res = {}
                async with httpx.AsyncClient(timeout=10.0) as client:
                    for chunk in chunks:
                        resp = await client.post(
                            f"https://discord.com/api/v10/channels/{effective_channel}/messages",
                            headers=headers,
                            json={"content": chunk},
                        )
                        if resp.status_code not in (200, 201):
                            return {"status": "error", "code": resp.status_code, "detail": resp.text}
                        last_res = resp.json()
                        if len(chunks) > 1:
                            await asyncio.sleep(0.35)
                return {"status": "success", "platform": "discord", "response": last_res}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        if webhook:
            try:
                from core.channel_adapter import split_message_chunks
                chunks = split_message_chunks(text, max_chars=1950, add_part_headers=True, platform="discord") or [""]
                async with httpx.AsyncClient(timeout=10.0) as client:
                    for chunk in chunks:
                        resp = await client.post(webhook, json={"content": chunk})
                        if resp.status_code not in (200, 204):
                            return {"status": "error", "code": resp.status_code, "detail": resp.text}
                        if len(chunks) > 1:
                            await asyncio.sleep(0.35)
                return {"status": "success", "platform": "discord_webhook"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {"status": "error", "reason": "not_configured"}

    def render_approval(self, narration: str, action: Any) -> Dict[str, Any]:
        args = getattr(action, "tool_args", {}) or {}
        pending_tc = getattr(action, "pending_tool_call", None) or {}
        cmd = args.get("command") or pending_tc.get("arguments", {}).get("command")
        cmd_hint = f"\n```shell\n{cmd}\n```" if cmd else ""
        return {"text": f"{narration}{cmd_hint}\n*Reply `approve` or `cancel`*", "reply_markup": None}

    def render_message(self, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"text": narration, "reply_markup": None}

    def render_notice(self, notice_type: str, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"text": f"**[{notice_type.upper()}]** {narration}", "reply_markup": None}
