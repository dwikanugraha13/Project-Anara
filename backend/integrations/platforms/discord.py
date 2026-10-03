"""
platforms/discord.py — Discord Platform Adapter for Project Anara (Anara Standard).
"""

from __future__ import annotations

import asyncio
import os
import logging
from typing import Any, Dict, Optional
import httpx
from ..base import BasePlatformAdapter
from core.logger import redact_sensitive_text

logger = logging.getLogger("anara.integrations.discord")

MAX_SPLIT_MESSAGES = 8
MAX_DISCORD_CAPTION = 1950


async def _post_discord_with_retry(client: httpx.AsyncClient, url: str, headers: dict, payload: dict, max_retries: int = 3):
    """Handles Discord rate-limits (HTTP 429) gracefully with exponential backoff (Anara Standard)."""
    resp = None
    for attempt in range(max_retries):
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code == 429:
            retry_after = 1.0
            try:
                retry_after = float(resp.json().get("retry_after", 1.0))
            except Exception:
                pass
            await asyncio.sleep(min(retry_after, 5.0))
            continue
        return resp
    return resp


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
                    "error": redact_sensitive_text(str(e)),
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
                chunks = split_message_chunks(text, max_chars=1950, add_part_headers=False, platform="discord") or [""]
                if len(chunks) > MAX_SPLIT_MESSAGES:
                    chunks = chunks[:MAX_SPLIT_MESSAGES]
                    chunks.append("⚠️ *[Output truncated: Exceeded Discord maximum 8-message burst limit]*")

                last_res = {}
                async with httpx.AsyncClient(timeout=10.0) as client:
                    for chunk in chunks:
                        payload = {"content": chunk, "allowed_mentions": {"parse": []}}
                        resp = await _post_discord_with_retry(
                            client,
                            f"https://discord.com/api/v10/channels/{effective_channel}/messages",
                            headers=headers,
                            payload=payload,
                        )
                        if resp is None or resp.status_code not in (200, 201):
                            code = resp.status_code if resp else 500
                            detail = resp.text if resp else "request_failed"
                            return {"status": "error", "code": code, "detail": redact_sensitive_text(detail)}
                        last_res = resp.json()
                        if len(chunks) > 1:
                            await asyncio.sleep(0.35)
                return {"status": "success", "platform": "discord", "response": last_res}
            except Exception as e:
                return {"status": "error", "message": redact_sensitive_text(str(e))}

        if webhook:
            try:
                from core.channel_adapter import split_message_chunks
                chunks = split_message_chunks(text, max_chars=1950, add_part_headers=False, platform="discord") or [""]
                if len(chunks) > MAX_SPLIT_MESSAGES:
                    chunks = chunks[:MAX_SPLIT_MESSAGES]
                    chunks.append("⚠️ *[Output truncated: Exceeded Discord maximum 8-message burst limit]*")

                async with httpx.AsyncClient(timeout=10.0) as client:
                    for chunk in chunks:
                        payload = {"content": chunk, "allowed_mentions": {"parse": []}}
                        resp = await _post_discord_with_retry(client, webhook, headers={}, payload=payload)
                        if not resp or resp.status_code not in (200, 204):
                            code = resp.status_code if resp else 500
                            detail = redact_sensitive_text(resp.text) if resp else "No response"
                            return {"status": "error", "code": code, "detail": detail}
                        if len(chunks) > 1:
                            await asyncio.sleep(0.35)
                return {"status": "success", "platform": "discord_webhook"}
            except Exception as e:
                return {"status": "error", "message": redact_sensitive_text(str(e))}

        return {"status": "error", "reason": "not_configured"}

    async def send_media(
        self,
        target_id: str,
        file_path: str,
        caption: Optional[str] = None,
        media_type: str = "document",
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Dispatches media file to Discord channel or webhook (Anara Standard)."""
        if not file_path or not os.path.isfile(file_path):
            return {"status": "error", "message": f"File not found: {file_path}"}

        token = self.token
        webhook = self.webhook_url
        effective_channel = target_id if (target_id and not target_id.startswith("default")) else self.default_channel_id

        f_name = os.path.basename(file_path)
        content_text = (caption or "")[:MAX_DISCORD_CAPTION]

        # Enforce Discord 25MB attachment upload ceiling to prevent RAM exhaustion
        MAX_UPLOAD_SIZE = 25 * 1024 * 1024
        try:
            f_size = os.path.getsize(file_path)
            if f_size > MAX_UPLOAD_SIZE:
                return {
                    "status": "error",
                    "message": f"File '{f_name}' exceeds Discord 25MB upload ceiling ({round(f_size / (1024 * 1024), 2)}MB)."
                }
        except OSError:
            pass

        if token and effective_channel:
            try:
                headers = {"Authorization": f"Bot {token}", "User-Agent": "AnaraAgent/1.0"}
                async with httpx.AsyncClient(timeout=30.0) as client:
                    file_bytes = await asyncio.to_thread(lambda: open(file_path, "rb").read())
                    files = {"files[0]": (f_name, file_bytes)}
                    data = {"content": content_text} if content_text else {}
                    resp = await client.post(
                        f"https://discord.com/api/v10/channels/{effective_channel}/messages",
                        headers=headers,
                        data=data,
                        files=files,
                    )
                    if resp.status_code in (200, 201):
                        return {"status": "success", "platform": "discord", "file": f_name}
                    return {"status": "error", "code": resp.status_code, "detail": redact_sensitive_text(resp.text)}
            except Exception as e:
                return {"status": "error", "message": redact_sensitive_text(str(e))}

        if webhook:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    file_bytes = await asyncio.to_thread(lambda: open(file_path, "rb").read())
                    files = {"file": (f_name, file_bytes)}
                    data = {"content": content_text} if content_text else {}
                    resp = await client.post(webhook, data=data, files=files)
                    if resp.status_code in (200, 204):
                        return {"status": "success", "platform": "discord_webhook", "file": f_name}
                    return {"status": "error", "code": resp.status_code, "detail": redact_sensitive_text(resp.text)}
            except Exception as e:
                return {"status": "error", "message": redact_sensitive_text(str(e))}

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
