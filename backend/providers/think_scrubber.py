"""
think_scrubber.py — Stateful Reasoning Tag Scrubber for Project Anara.
Buffers across chunk boundaries to strip progressive <think>...</think> blocks in real-time,
while preserving non-tag literal mentions of <think> within normal conversational prose.
"""

from __future__ import annotations

import re
from typing import Tuple, List

THINK_TAG_NAMES: Tuple[str, ...] = (
    "think", "thinking", "reasoning", "thought", "REASONING_SCRATCHPAD",
    "思考", "反思", "推理", "推敲",
)
THINK_OPEN_TAGS: Tuple[str, ...] = tuple(f"<{name.lower()}>" for name in THINK_TAG_NAMES)
THINK_CLOSE_TAGS: Tuple[str, ...] = tuple(f"</{name.lower()}>" for name in THINK_TAG_NAMES)


class StreamingThinkScrubber:
    """
    Anara Enterprise Architecture: Stateful reasoning tag scrubber buffering across chunk boundaries.
    Preserves mid-line mentions of '<think>' while stripping bona-fide open blocks and closed pairs.
    """
    _OPEN_TAGS: Tuple[str, ...] = THINK_OPEN_TAGS
    _CLOSE_TAGS: Tuple[str, ...] = THINK_CLOSE_TAGS
    _ALL_TAGS: Tuple[str, ...] = _OPEN_TAGS + _CLOSE_TAGS
    _MAX_TAG_LEN: int = max(len(tag) for tag in _ALL_TAGS)
    _ORPHAN_CLOSE_RE = re.compile(
        "(?:" + "|".join(re.escape(t) for t in _CLOSE_TAGS) + r")[ \t\n\r]*", re.IGNORECASE
    )

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset all state. Call at the top of every new turn."""
        self._in_block: bool = False
        self._buf: str = ""
        self._last_emitted_ended_newline: bool = True
        self.last_hidden: str = ""

    def _emit(self, out: List[str], text: str) -> None:
        """Append visible prose to out (orphan close tags stripped) and track the newline flag."""
        text = self._strip_orphan_close_tags(text)
        if text:
            out.append(text)
            self._last_emitted_ended_newline = text.endswith("\n")

    def feed(self, text: str) -> str:
        """Feed one delta; return the scrubbed visible portion."""
        self.last_hidden = ""
        if not text:
            return ""
        buf = self._buf + text
        self._buf = ""
        out: List[str] = []
        hidden: List[str] = []

        while buf:
            if self._in_block:
                close_idx, close_len = self._find_first_tag(buf, self._CLOSE_TAGS)
                if close_idx == -1:
                    hidden.append(self._hold_partial(buf, self._CLOSE_TAGS))
                    break
                hidden.append(buf[:close_idx])
                buf = buf[close_idx + close_len:]
                self._in_block = False
                continue

            pair = self._find_earliest_closed_pair(buf)
            open_idx, open_len = self._find_open_at_boundary(buf, out)
            if pair is not None and (open_idx == -1 or pair[0] <= open_idx):
                self._emit(out, buf[:pair[0]])
                hidden.append(buf[buf.index(">", pair[0]) + 1:buf.rindex("<", pair[0], pair[1])])
                buf = buf[pair[1]:]
                continue
            if open_idx != -1:
                self._emit(out, buf[:open_idx])
                self._in_block = True
                buf = buf[open_idx + open_len:]
                continue

            self._emit(out, self._hold_partial(buf, self._ALL_TAGS))
            break

        self.last_hidden = "".join(hidden)
        return "".join(out)

    def _hold_partial(self, buf: str, tags: Tuple[str, ...]) -> str:
        held = self._max_partial_suffix(buf, tags)
        self._buf = buf[-held:] if held else ""
        return buf[:-held] if held else buf

    def flush(self) -> str:
        tail = "" if self._in_block else self._buf
        self._buf = ""
        self._in_block = False
        self._last_emitted_ended_newline = True
        return self._strip_orphan_close_tags(tail) if tail else ""

    @staticmethod
    def _find_first_tag(buf: str, tags: Tuple[str, ...]) -> Tuple[int, int]:
        buf_lower = buf.lower()
        hits = [(idx, len(tag)) for tag in tags if (idx := buf_lower.find(tag)) != -1]
        return min(hits) if hits else (-1, 0)

    def _find_earliest_closed_pair(self, buf: str):
        buf_lower = buf.lower()
        pairs = []
        for open_tag, close_tag in zip(self._OPEN_TAGS, self._CLOSE_TAGS):
            open_idx = buf_lower.find(open_tag)
            close_idx = buf_lower.find(close_tag, open_idx + len(open_tag)) if open_idx != -1 else -1
            if close_idx != -1:
                pairs.append((open_idx, close_idx + len(close_tag)))
        return min(pairs) if pairs else None

    def _find_open_at_boundary(self, buf: str, already_emitted: List[str]) -> Tuple[int, int]:
        buf_lower = buf.lower()
        hits = []
        for tag in self._OPEN_TAGS:
            idx = buf_lower.find(tag)
            while idx != -1 and not self._is_block_boundary(buf, idx, already_emitted):
                idx = buf_lower.find(tag, idx + 1)
            if idx != -1:
                hits.append((idx, len(tag)))
        return min(hits) if hits else (-1, 0)

    def _is_block_boundary(self, buf: str, idx: int, already_emitted: List[str]) -> bool:
        prior_newline = already_emitted[-1].endswith("\n") if already_emitted else self._last_emitted_ended_newline
        if idx == 0:
            return prior_newline
        preceding = buf[:idx]
        last_nl = preceding.rfind("\n")
        return (prior_newline if last_nl == -1 else True) and preceding[last_nl + 1:].strip() == ""

    @classmethod
    def _max_partial_suffix(cls, buf: str, tags: Tuple[str, ...]) -> int:
        buf_lower = buf.lower()
        for i in range(min(len(buf_lower), cls._MAX_TAG_LEN - 1), 0, -1):
            suffix = buf_lower[-i:]
            if any(len(tag) > i and tag.startswith(suffix) for tag in tags):
                return i
        return 0

    @classmethod
    def _strip_orphan_close_tags(cls, text: str) -> str:
        return cls._ORPHAN_CLOSE_RE.sub("", text) if "</" in text else text
