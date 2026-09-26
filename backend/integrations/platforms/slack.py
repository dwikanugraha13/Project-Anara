"""
platforms/slack.py — Slack Platform Adapter for Project Anara (Hermes Parity).
"""

from __future__ import annotations

import asyncio
import os
import logging
from typing import Any, Dict, Optional
import httpx
from ..base import BasePlatformAdapter

logger = logging.getLogger("anara.integrations.slack")


class SlackPlatformAdapter(BasePlatformAdapter):
    name = "slack"

    @property
    def token(self) -> str:
        return (os.getenv("SLACK_BOT_TOKEN") or "").strip()

    @property
    def webhook_url(self) -> str:
        return (os.getenv("SLACK_WEBHOOK_URL") or "").strip()

    @property
    def default_channel(self) -> str:
        return (os.getenv("SLACK_CHANNEL_ID") or "").strip()

    async def connect(self, is_reconnect: bool = False) -> bool:
        status_info = await self.get_status()
        return bool(status_info.get("connected", False))

    async def get_status(self) -> Dict[str, Any]:
        token = self.token
        webhook = self.webhook_url
        if not token and not webhook:
            return {
                "name": "slack",
                "status": "not_configured",
                "is_configured": False,
                "connected": False,
                "reason": "missing_credentials",
            }

        if token:
            try:
                headers = {"Authorization": f"Bearer {token}", "User-Agent": "AnaraAgent/1.0"}
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.post("https://slack.com/api/auth.test", headers=headers)
                    data = resp.json()
                    if data.get("ok"):
                        return {
                            "name": "slack",
                            "status": "connected",
                            "is_configured": True,
                            "connected": True,
                            "mode": "bot",
                            "bot": {
                                "user_id": data.get("user_id"),
                                "user": data.get("user"),
                                "team": data.get("team"),
                            },
                        }
                    else:
                        return {
                            "name": "slack",
                            "status": "error",
                            "is_configured": True,
                            "connected": False,
                            "error": data.get("error", "auth_failed"),
                        }
            except Exception as e:
                return {
                    "name": "slack",
                    "status": "error",
                    "is_configured": True,
                    "connected": False,
                    "error": str(e),
                }

        if webhook:
            return {
                "name": "slack",
                "status": "connected",
                "is_configured": True,
                "connected": True,
                "mode": "webhook",
            }

        return {
            "name": "slack",
            "status": "disconnected",
            "is_configured": True,
            "connected": False,
            "reason": "connection_failed",
        }

    async def send_message(self, target_id: str, text: str, **kwargs: Any) -> Dict[str, Any]:
        token = self.token
        webhook = self.webhook_url
        effective_channel = (target_id or self.default_channel).strip()

        if token and effective_channel:
            try:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }
                from core.channel_adapter import split_message_chunks
                chunks = split_message_chunks(text, max_chars=3500, add_part_headers=True, platform="slack") or [""]
                last_data = {}
                async with httpx.AsyncClient(timeout=10.0) as client:
                    for idx, chunk in enumerate(chunks):
                        resp = await client.post(
                            "https://slack.com/api/chat.postMessage",
                            headers=headers,
                            json={"channel": effective_channel, "text": chunk},
                        )
                        data = resp.json()
                        if not data.get("ok"):
                            return {"status": "error", "error": data.get("error")}
                        last_data = data
                        if idx < len(chunks) - 1:
                            await asyncio.sleep(0.35)
                    return {"status": "success", "platform": "slack", "data": last_data}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        if webhook:
            try:
                from core.channel_adapter import split_message_chunks
                chunks = split_message_chunks(text, max_chars=3500, add_part_headers=True, platform="slack") or [""]
                async with httpx.AsyncClient(timeout=10.0) as client:
                    for idx, chunk in enumerate(chunks):
                        resp = await client.post(webhook, json={"text": chunk})
                        if resp.status_code != 200:
                            return {"status": "error", "code": resp.status_code, "detail": resp.text}
                        if idx < len(chunks) - 1:
                            await asyncio.sleep(0.35)
                return {"status": "success", "platform": "slack_webhook"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {"status": "error", "reason": "not_configured"}

    def render_approval(self, narration: str, action: Any) -> Dict[str, Any]:
        return {"text": f"{narration}\n*(Reply 'approve' or 'cancel')*", "reply_markup": None}

    def render_message(self, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"text": narration, "reply_markup": None}

    def render_notice(self, notice_type: str, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"text": f"*[{notice_type.upper()}]* {narration}", "reply_markup": None}
