"""
platforms/cli.py — Terminal CLI Platform Adapter for Project Anara (Hermes Parity).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from ..base import BasePlatformAdapter

logger = logging.getLogger("anara.integrations.cli")


class CliPlatformAdapter(BasePlatformAdapter):
    name = "cli"

    async def get_status(self) -> Dict[str, Any]:
        return {"name": "cli", "status": "connected", "is_configured": True, "connected": True}

    async def send_message(self, target_id: str, text: str, **kwargs: Any) -> Dict[str, Any]:
        print(text)
        return {"status": "success", "platform": "cli"}

    def render_approval(self, narration: str, action: Any) -> Dict[str, Any]:
        args = getattr(action, "tool_args", {}) or {}
        pending_tc = getattr(action, "pending_tool_call", None) or {}
        cmd = args.get("command") or pending_tc.get("arguments", {}).get("command")
        cmd_hint = f"\n  Command: {cmd}" if cmd else (f"\n  File: {args.get('file_path')}" if args.get("file_path") else "")
        prompt = f"\n[Konfirmasi Persetujuan: {getattr(action, 'tool_name', 'action')}]{cmd_hint}\nSetujui dan jalankan? [y/N]: "
        return {
            "text": f"{narration}\n{prompt}",
            "narration": narration,
            "prompt": prompt,
            "reply_markup": None,
        }

    def render_message(self, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"text": narration, "reply_markup": None}

    def render_notice(self, notice_type: str, narration: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"text": f"[{notice_type.upper()}] {narration}", "reply_markup": None}
