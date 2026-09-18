"""
context_compactor.py — Production-Grade Rolling Context Window Compactor.
Summarizes older dialogue turns into a structured cognitive memory capsule
when conversation history grows long, retaining the most recent turns 100% verbatim.
"""

import re
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


def prune_tool_output(content: str, max_chars: int = 1500) -> str:
    """Hermes Parity: Prunes massive code or tool outputs inside context history."""
    if len(content) <= max_chars:
        return content
    if "```" in content:
        return re.sub(r"```[\s\S]*?```", "[... cuplikan kode dipangkas ...]", content)
    head = max_chars // 2
    tail = max_chars - head
    return content[:head] + "\n[... cuplikan kode dipangkas ...]\n" + content[-tail:]


class ContextCompactor:
    """Manages context window compaction to maintain infinite multi-turn dialogue without token overflow."""

    @staticmethod
    def compact_history(
        history: List[Dict[str, Any]],
        verbatim_turns: int = 5,
        max_summary_tokens: int = 400,
        protect_head_n: int = 0
    ) -> str:
        """
        Compresses older turns into a compact structured summary capsule while preserving
        the most recent `verbatim_turns` turns completely verbatim, and optionally protecting
        the initial `protect_head_n` turns.
        """
        if not history:
            return ""

        # Filter out empty turns or internal leaked control frames
        cleaned = []
        for h in history:
            u = (h.get("user_text") or "").strip()
            a = (h.get("ai_text") or "").strip()
            if u.startswith("{") and '"type"' in u:
                continue
            if u or a:
                cleaned.append(h)

        if not cleaned:
            return ""

        head_block = ""
        if protect_head_n > 0 and len(cleaned) > verbatim_turns:
            head_items = cleaned[:protect_head_n]
            head_lines = [f"• Goal: {h.get('user_text', '').strip()}" for h in head_items if h.get('user_text')]
            head_block = "[TUJUAN AWAL / INISIASI SESI (PROTECTED HEAD)]:\n" + "\n".join(head_lines) + "\n\n"
            cleaned = cleaned[protect_head_n:]

        # If short session, render all verbatim
        if len(cleaned) <= verbatim_turns:
            turns_str = []
            for h in cleaned:
                u = (h.get("user_text") or "").strip()
                a = (h.get("ai_text") or "").strip()
                turns_str.append(f"User: {u}\nAnara: {a}")
            return f"{head_block}PERCAKAPAN TERBARU:\n" + "\n---\n".join(turns_str) + "\n\n"

        # Split into older turns and recent verbatim turns
        older_turns = cleaned[:-verbatim_turns]
        recent_turns = cleaned[-verbatim_turns:]

        # Build structured capsule from older turns
        capsule_lines = []
        for h in older_turns[-8:]:
            u = (h.get("user_text") or "").strip()
            a = (h.get("ai_text") or "").strip()
            if u:
                first_u = u.split("\n")[0][:90]
                capsule_lines.append(f"• User: {first_u}")
            if a:
                summary_a = re.sub(r"```[\s\S]*?```", "[cuplikan kode/file]", a)
                first_a = summary_a.split("\n")[0][:110]
                capsule_lines.append(f"  Anara: {first_a}")

        capsule_header = "[KAPSUL RINGKASAN SESI SEBELUMNYA]:\n" + "\n".join(capsule_lines) + "\n\n"

        # Render recent turns verbatim
        recent_lines = []
        for h in recent_turns:
            u = (h.get("user_text") or "").strip()
            a = (h.get("ai_text") or "").strip()
            recent_lines.append(f"User: {u}\nAnara: {a}")

        return f"{head_block}{capsule_header}PERCAKAPAN TERBARU:\n" + "\n---\n".join(recent_lines) + "\n\n"
