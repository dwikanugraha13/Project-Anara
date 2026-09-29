"""
platforms/cli.py — Terminal CLI Platform Adapter for Project Anara (Anara Standard).
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
        try:
            from .terminal_ui import terminal_ui
            terminal_ui.print_response(text, speaker_name="Anara")
        except Exception:
            print(text)
        return {"status": "success", "platform": "cli"}

    def render_approval(self, narration: str, action: Any) -> Dict[str, Any]:
        import json
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
        file_p = (args if isinstance(args, dict) else {}).get("file_path") or (tc_args if isinstance(tc_args, dict) else {}).get("file_path")
        cmd_hint = f"\n  Command: {cmd}" if cmd else (f"\n  File: {file_p}" if file_p else "")
        prompt = f"\n[Approval Confirmation: {getattr(action, 'tool_name', 'action')}]{cmd_hint}\nApprove and execute? [y/N]: "
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
