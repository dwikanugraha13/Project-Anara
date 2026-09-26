"""
platforms/whatsapp.py — WhatsApp Platform Adapter for Project Anara (Hermes Parity).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional
from ..base import BasePlatformAdapter

logger = logging.getLogger("anara.integrations.whatsapp")


class WhatsAppPlatformAdapter(BasePlatformAdapter):
    name = "whatsapp"

    async def connect(self, is_reconnect: bool = False) -> bool:
        from ..whatsapp import start_whatsapp_bridge, get_whatsapp_status
        start_whatsapp_bridge()
        try:
            st = await get_whatsapp_status()
            return st.get("status") in ("connected", "waiting_qr", "ready")
        except Exception:
            return True

    async def disconnect(self) -> None:
        from ..whatsapp import stop_whatsapp_bridge
        stop_whatsapp_bridge()

    async def get_status(self) -> Dict[str, Any]:
        from ..whatsapp import get_whatsapp_status
        return await get_whatsapp_status()

    async def send_message(self, target_id: str, text: str, **kwargs: Any) -> Dict[str, Any]:
        from ..whatsapp import send_whatsapp_message
        from core.channel_adapter import split_message_chunks
        chunks = split_message_chunks(text, max_chars=3500, add_part_headers=True, platform="whatsapp") or [""]
        last_res = {}
        for idx, chunk in enumerate(chunks):
            last_res = await send_whatsapp_message(to=target_id, message=chunk)
            if idx < len(chunks) - 1:
                await asyncio.sleep(0.35)
        return last_res

    async def send_media(
        self,
        target_id: str,
        file_path: str,
        caption: Optional[str] = None,
        media_type: str = "document",
        **kwargs: Any
    ) -> Dict[str, Any]:
        from ..whatsapp import send_whatsapp_document
        return await send_whatsapp_document(to=target_id, file_path=file_path, caption=caption or "")

    def render_approval(self, narration: str, action: Any) -> Dict[str, Any]:
        args = getattr(action, "tool_args", {}) or {}
        pending_tc = getattr(action, "pending_tool_call", None) or {}
        cmd = args.get("command") or pending_tc.get("arguments", {}).get("command")

        cmd_hint = f"\n*Command:* `{cmd}`" if cmd else ""
        instruction = "Reply *approve* to proceed, or *cancel* to abort."
        text = f"{narration}{cmd_hint}\n\n{instruction}"
        return {"text": text, "reply_markup": None}

    def render_message(self, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"text": narration, "reply_markup": None}

    def render_notice(self, notice_type: str, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"text": narration, "reply_markup": None}
