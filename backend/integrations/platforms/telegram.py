"""
platforms/telegram.py — Telegram Platform Adapter for Project Anara (Hermes Parity).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from ..base import BasePlatformAdapter

logger = logging.getLogger("anara.integrations.telegram")


class TelegramPlatformAdapter(BasePlatformAdapter):
    name = "telegram"

    async def connect(self, is_reconnect: bool = False) -> bool:
        from ..telegram import start_telegram_polling_daemon, get_stored_telegram_token
        token = get_stored_telegram_token()
        if token:
            start_telegram_polling_daemon()
            return True
        return False

    async def disconnect(self) -> None:
        from ..telegram import stop_telegram_polling_daemon
        stop_telegram_polling_daemon()

    async def get_status(self) -> Dict[str, Any]:
        from ..telegram import get_telegram_status
        return await get_telegram_status()

    async def send_message(self, target_id: str, text: str, **kwargs: Any) -> Dict[str, Any]:
        from ..telegram import send_telegram_message
        parse_mode = kwargs.get("parse_mode", "HTML")
        reply_markup = kwargs.get("reply_markup")
        return await send_telegram_message(text=text, chat_id=target_id, parse_mode=parse_mode, reply_markup=reply_markup)

    async def send_media(
        self,
        target_id: str,
        file_path: str,
        caption: Optional[str] = None,
        media_type: str = "document",
        **kwargs: Any
    ) -> Dict[str, Any]:
        from ..telegram import (
            send_telegram_document,
            send_telegram_photo,
            send_telegram_video,
            send_telegram_voice,
        )
        if media_type == "voice":
            return await send_telegram_voice(file_path=file_path, caption=caption or "", chat_id=target_id)
        elif media_type == "photo":
            return await send_telegram_photo(photo=file_path, caption=caption or "", chat_id=target_id)
        elif media_type == "video":
            return await send_telegram_video(file_path=file_path, caption=caption or "", chat_id=target_id)
        else:
            return await send_telegram_document(file_path=file_path, caption=caption or "", chat_id=target_id)

    def render_approval(self, narration: str, action: Any) -> Dict[str, Any]:
        text_parts = [narration.strip()]
        args = getattr(action, "tool_args", {}) or {}
        pending_tc = getattr(action, "pending_tool_call", None) or {}
        cmd = args.get("command") or pending_tc.get("arguments", {}).get("command")
        t_name = getattr(action, "tool_name", "")
        if cmd:
            text_parts.append(f"\n```shell\n{cmd}\n```")
        elif args.get("file_path"):
            text_parts.append(f"\n`Target: {args.get('file_path')}`")
        elif t_name == "computer_use":
            act = args.get("action", "action")
            target_desc = args.get("text") or args.get("key") or args.get("keys") or args.get("app") or (f"({args.get('x')}, {args.get('y')})" if args.get("x") is not None else "")
            text_parts.append(f"\n`Computer Use ({act}): {target_desc}`")

        full_text = "\n".join(text_parts)
        action_id = getattr(action, "action_id", getattr(action, "plan_id", "act"))
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Approve", "callback_data": f"approve:{action_id}"},
                    {"text": "❌ Deny", "callback_data": f"reject:{action_id}"}
                ]
            ]
        }
        return {
            "text": full_text,
            "parse_mode": "HTML",
            "reply_markup": keyboard,
        }

    def render_message(self, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "text": narration,
            "parse_mode": "HTML",
            "reply_markup": None,
        }

    def render_notice(self, notice_type: str, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        icons = {
            "expired": "⏱️ ",
            "rejected": "❌ ",
            "unauthorized": "🛡️ ",
            "stopped": "🛑 ",
            "error": "⚠️ ",
            "executing": "⏳ ",
            "success": "✅ ",
        }
        icon = icons.get(notice_type, "")
        clean_text = narration.strip()
        formatted = f"{icon}<b>{clean_text}</b>" if notice_type in ("unauthorized", "stopped", "error") else f"{icon}{clean_text}"
        return {
            "text": formatted,
            "parse_mode": "HTML",
            "reply_markup": None,
        }
