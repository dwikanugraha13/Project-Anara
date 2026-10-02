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
    """
    Structured head/tail windowing snapped to line boundaries with disk spillover (Anara Enterprise Architecture).
    Preserves diagnostic stack traces, compiler errors, and exit codes without unverified regex code block wiping.
    """
    if not content or len(content) <= max_chars:
        return content or ""

    raw_text = str(content)
    raw_len = len(raw_text)

    # Disk spillover for oversized outputs (> 2,000 chars)
    disk_pointer = ""
    if raw_len > 2000:
        try:
            from constants import get_anara_logs_dir
            import uuid, time
            log_dir = get_anara_logs_dir("tool_logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            spill_file = log_dir / f"pruned_{uuid.uuid4().hex[:8]}.log"
            spill_file.write_text(raw_text, encoding="utf-8", errors="replace")
            disk_pointer = f" — full output ({raw_len:,} chars, {raw_text.count(chr(10))+1:,} lines) saved to: {spill_file}"
            # Keep log directory bounded: prune logs older than 48 hours or when count > 200
            try:
                all_logs = list(log_dir.glob("pruned_*.log"))
                if len(all_logs) > 200:
                    now = time.time()
                    for f in sorted(all_logs, key=lambda p: p.stat().st_mtime):
                        if len(all_logs) > 150 or (now - f.stat().st_mtime > 172800):
                            f.unlink(missing_ok=True)
                            all_logs.remove(f)
            except Exception:
                pass
        except Exception:
            disk_pointer = f" — {raw_len:,} chars omitted"

    lines = raw_text.splitlines()
    if len(lines) > 2:
        # Snap to line boundaries
        head_budget = int(max_chars * 0.55)
        tail_budget = max_chars - head_budget

        head_lines = []
        head_chars = 0
        for line in lines:
            if head_chars + len(line) + 1 > head_budget and head_lines:
                break
            head_lines.append(line)
            head_chars += len(line) + 1

        tail_lines = []
        tail_chars = 0
        for line in reversed(lines):
            if tail_chars + len(line) + 1 > tail_budget and tail_lines:
                break
            tail_lines.append(line)
            tail_chars += len(line) + 1
        tail_lines.reverse()

        omitted_lines = max(0, len(lines) - len(head_lines) - len(tail_lines))
        head_block = "\n".join(head_lines)
        tail_block = "\n".join(tail_lines)
        return f"{head_block}\n[... truncated output ({omitted_lines} lines omitted{disk_pointer}) ...]\n{tail_block}"
    else:
        # Single-line or short content truncation
        head_chars = int(max_chars * 0.6)
        tail_chars = max_chars - head_chars
        return f"{raw_text[:head_chars]}\n[... truncated output{disk_pointer} ...]\n{raw_text[-tail_chars:]}"


def estimate_tokens(text: str) -> int:
    """Estimates token count. Uses tiktoken if available, otherwise heuristic."""
    if not text:
        return 0
    try:
        from core.token_budget import count_tokens
        return count_tokens(text)
    except Exception:
        # Fallback heuristic: ~3.4 chars per token
        return max(1, int(len(text) / 3.4))


class ContextCompactor:
    """Manages context window compaction to maintain infinite multi-turn dialogue without token overflow."""

    @classmethod
    def normalize_history(cls, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalizes conversation history into strictly chronological, cleanly paired turns (Anara Standard).
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
            head_block = "[INITIAL SESSION GOAL (PROTECTED HEAD)]:\n" + "\n".join(head_lines) + "\n\n"
            cleaned = cleaned[protect_head_n:]

        # If short session, render all verbatim
        if len(cleaned) <= verbatim_turns:
            turns_str = []
            for h in cleaned:
                u = (h.get("user_text") or "").strip()
                a = (h.get("ai_text") or "").strip()
                turns_str.append(f"User: {u}\nAnara: {a}")
            return f"{head_block}RECENT CONVERSATION:\n" + "\n---\n".join(turns_str) + "\n\n"

        # Split into older turns and recent verbatim turns
        older_turns = cleaned[:-verbatim_turns]
        recent_turns = cleaned[-verbatim_turns:]

        # Build structured capsule from older turns honoring max_summary_tokens budget
        capsule_lines = []
        chars_budget = max(1200, max_summary_tokens * 4)
        accumulated_chars = 0
        for h in reversed(older_turns):
            u = (h.get("user_text") or "").strip()
            a = (h.get("ai_text") or "").strip()
            turn_capsule = []
            if u:
                u_clean = re.sub(r"\s+", " ", u).strip()[:180]
                turn_capsule.append(f"• User: {u_clean}")
            if a:
                # Line-bounded head/tail compaction for code blocks rather than destructive blanking
                def _compact_code(match: re.Match) -> str:
                    code = match.group(0).strip()
                    lines = [ln.strip() for ln in code.splitlines() if ln.strip()]
                    if len(lines) <= 3:
                        return code
                    return f"{lines[0]}\n    ... ({len(lines)-2} lines omitted) ...\n    {lines[-1]}"

                a_compact = re.sub(r"```[\s\S]*?```", _compact_code, a)
                a_clean = re.sub(r"[ \t]+", " ", a_compact).strip()
                if len(a_clean) > 300:
                    a_clean = a_clean[:280] + "..."
                turn_capsule.append(f"  Anara: {a_clean}")

            block_str = "\n".join(turn_capsule)
            if accumulated_chars + len(block_str) > chars_budget and capsule_lines:
                break
            capsule_lines.insert(0, block_str)
            accumulated_chars += len(block_str)

        capsule_header = "[SESSION SUMMARY CAPSULE]:\n" + "\n".join(capsule_lines) + "\n\n"

        # Render recent turns verbatim
        recent_lines = []
        for h in recent_turns:
            u = (h.get("user_text") or "").strip()
            a = (h.get("ai_text") or "").strip()
            recent_lines.append(f"User: {u}\nAnara: {a}")

        return f"{head_block}{capsule_header}RECENT CONVERSATION:\n" + "\n---\n".join(recent_lines) + "\n\n"

    @classmethod
    def estimate_history_tokens(cls, history: List[Dict[str, Any]]) -> int:
        """Estimates total token count of a conversation history."""
        total = 0
        for h in history:
            u = h.get("user_text", "") or ""
            a = h.get("ai_text", "") or ""
            total += estimate_tokens(u) + estimate_tokens(a) + 8  # overhead per turn
        return total
