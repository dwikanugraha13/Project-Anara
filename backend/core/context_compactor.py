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
    """Anara Standard: Prunes massive code or tool outputs inside context history (language-neutral Hermes Parity)."""
    if len(content) <= max_chars:
        return content
    if "```" in content:
        return re.sub(r"```[\s\S]*?```", "[... truncated output ...]", content)
    head = max_chars // 2
    tail = max_chars - head
    return content[:head] + "\n[... truncated output ...]\n" + content[-tail:]


class ContextCompactor:
    """Manages context window compaction to maintain infinite multi-turn dialogue without token overflow."""

    @classmethod
    def normalize_history(cls, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalizes conversation history into strictly chronological, cleanly paired turns (Hermes Parity).
        - Detects newest-first SQL results (id descending) and inverts them to chronological order (oldest-first).
        - Re-stitches orphaned half-turns (e.g. user_text without ai_text followed by ai_text without user_text).
        - Discards internal websocket JSON control frames.
        """
        if not history:
            return []

        # 1. Invert if newest-first (SQL ORDER BY id DESC)
        if len(history) > 1:
            first_id = history[0].get("id") or 0
            last_id = history[-1].get("id") or 0
            if first_id > last_id:
                chronological = list(reversed(history))
            else:
                chronological = list(history)
        else:
            chronological = list(history)

        # 2. Pair and clean
        paired: List[Dict[str, Any]] = []
        i = 0
        while i < len(chronological):
            curr = dict(chronological[i])
            u = (curr.get("user_text") or "").strip()
            a = (curr.get("ai_text") or "").strip()

            if u.startswith("{") and '"type"' in u:
                i += 1
                continue

            # Check if this row is an orphaned user prompt and next row is the orphaned AI response
            if u and not a and i + 1 < len(chronological):
                next_row = chronological[i + 1]
                next_u = (next_row.get("user_text") or "").strip()
                next_a = (next_row.get("ai_text") or "").strip()
                if not next_u and next_a:
                    curr["ai_text"] = next_a
                    paired.append(curr)
                    i += 2
                    continue

            if u or a:
                paired.append(curr)
            i += 1

        return paired

    @classmethod
    def compact_history(
        cls,
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

        cleaned = cls.normalize_history(history)
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
                summary_a = re.sub(r"```[\s\S]*?```", "[code block]", a)
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
