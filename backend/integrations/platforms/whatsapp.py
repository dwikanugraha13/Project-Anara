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
        """Converts Markdown syntax to WhatsApp formatting conventions (Hermes Standard)."""
        if not content:
            return content

        # 0. Sanitize zero-width characters and odd unicode spaces that render as mojibake on WhatsApp
        sanitized = re.sub(r"[\u200b\u2060\u2063\ufeff]", "", content)
        sanitized = re.sub(r"[\u00a0\u1680\u180e\u2000-\u200a\u202f\u205f\u3000]", " ", sanitized)

        # 1. Preserve fenced code blocks
        fences: list[str] = []
        def _stash_fence(m: re.Match) -> str:
            fences.append(m.group(0))
            return f"\x00FENCE{len(fences)-1}\x00"

        res = re.sub(r"```[\s\S]*?```", _stash_fence, sanitized)

        # 2. Preserve inline code
        codes: list[str] = []
        def _stash_code(m: re.Match) -> str:
            codes.append(m.group(0))
            return f"\x00CODE{len(codes)-1}\x00"

        res = re.sub(r"`[^`\n]+`", _stash_code, res)

        # 3. Convert markdown links: [text](url) -> text (url)
        res = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", res)

        # 4. Convert markdown strike ~~text~~ to WhatsApp ~text~
        res = re.sub(r"~~(.+?)~~", r"~\1~", res)

        # 5. Convert markdown italic *text* to WhatsApp _text_ BEFORE bold (when not bullet list)
        res = re.sub(r"(?<!\*)\*(?!\s|\*)([^*\n]*?\S[^*\n]*?)\*(?!\*)", r"_\1_", res)

        # 6. Convert markdown headers to bold (avoiding double asterisks)
        def _header_to_bold(m: re.Match) -> str:
            inner = m.group(1).strip()
            inner = re.sub(r"^\*\*(.+?)\*\*$", r"\1", inner)
            inner = re.sub(r"^__(.+?)__$", r"\1", inner)
            return f"*{inner}*"

        res = re.sub(r"^#{1,6}\s+(.+)$", _header_to_bold, res, flags=re.MULTILINE)

        # 7. Convert markdown bold **text** and __text__ to WhatsApp *text*
        res = re.sub(r"\*\*(.+?)\*\*", r"*\1*", res)
        res = re.sub(r"__(.+?)__", r"*\1*", res)

        # 8. Restore code blocks and inline code
        for i, original in enumerate(fences):
            res = res.replace(f"\x00FENCE{i}\x00", original)
        for i, original in enumerate(codes):
            res = res.replace(f"\x00CODE{i}\x00", original)

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
            res = await send_whatsapp_message(to=target_id, message=chunk)
            if not res or res.get("status") == "error":
                return res or {"status": "error", "message": f"Failed to send chunk {idx+1}/{len(chunks)} to WhatsApp."}
            last_res = res
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
