"""
platforms/whatsapp.py — WhatsApp Platform Adapter for Project Anara (Anara Standard).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, Optional
from ..base import BasePlatformAdapter

logger = logging.getLogger("anara.integrations.whatsapp")


class WhatsAppPlatformAdapter(BasePlatformAdapter):
    name = "whatsapp"

    def format_message(self, content: str) -> str:
        """Converts Markdown syntax to WhatsApp formatting conventions (Anara Standard)."""
        if not content:
            return content

        # Preserve fenced code blocks
        fences: list[str] = []
        def _stash_fence(m: re.Match) -> str:
            fences.append(m.group(0))
            return f"\x00FENCE{len(fences)-1}\x00"

        res = re.sub(r"```[\s\S]*?```", _stash_fence, content)
        # Convert markdown headers to bold
        res = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", res, flags=re.MULTILINE)
        # Convert markdown bold **text** to WhatsApp *text*
        res = re.sub(r"\*\*(.+?)\*\*", r"*\1*", res)
        # Convert markdown strike ~~text~~ to WhatsApp ~text~
        res = re.sub(r"~~(.+?)~~", r"~\1~", res)

        for i, original in enumerate(fences):
            res = res.replace(f"\x00FENCE{i}\x00", original)
        return res

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
        formatted = self.format_message(text)
        chunks = split_message_chunks(formatted, max_chars=3500, add_part_headers=True, platform="whatsapp") or [""]
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
        formatted_caption = self.format_message(caption or "")
        return await send_whatsapp_document(to=target_id, file_path=file_path, caption=formatted_caption)

    def render_approval(self, narration: str, action: Any) -> Dict[str, Any]:
        args = getattr(action, "tool_args", {}) or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        pending_tc = getattr(action, "pending_tool_call", None) or {}
        tc_args = pending_tc.get("arguments", {})
        if isinstance(tc_args, str):
            try:
                tc_args = json.loads(tc_args)
            except Exception:
                tc_args = {}
        cmd = (args if isinstance(args, dict) else {}).get("command") or (tc_args if isinstance(tc_args, dict) else {}).get("command")

        cmd_hint = f"\n*Command:* `{cmd}`" if cmd else ""
        instruction = "Reply *approve* to proceed, or *cancel* to abort."
        text = f"{narration}{cmd_hint}\n\n{instruction}"
        return {"text": text, "reply_markup": None}

    def render_message(self, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"text": narration, "reply_markup": None}

    def render_notice(self, notice_type: str, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"text": narration, "reply_markup": None}
