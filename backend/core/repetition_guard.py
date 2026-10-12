"""
repetition_guard.py — Streaming Text Degenerate Repetition Guard for Project Anara.
Parity with Hermes Agent repetition_guard (Nous Research).

Detects degenerate repetition loops in LLM streaming generation BEFORE runaway token burn.
A model in a degenerate loop can echo the same fragment/sentence indefinitely.
This module checks for:
1. Exact-repeat windows (60+ chars recurring >= 5 times covering >= 50% of fragment).
2. Periodic runs expanded from evenly spaced anchors.
3. Multi-line runaway repetition (mostly duplicate lines).
4. Fast line repetition for normalized line echoes.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List, Optional, Tuple

# Below this length the check doesn't run: short truncations legitimately contain repeated tokens.
MIN_FRAGMENT_LENGTH = 400

# Exact-repeat window: far beyond ordinary phrasing reuse (citations, headings, code templates).
_REPEAT_WINDOW = 60

# A window repeating at least this often is a signal even for short fragments.
_MIN_REPEAT_COUNT = 5

# "Repetition-dominated" = repeated windows cover at least this fraction.
_DOMINANCE_RATIO = 0.5

# Standard interruption message when a degenerate repetition loop is caught.
REPETITION_LOOP_INTERRUPTED = "[Response degenerated into an infinite repetition loop and was interrupted by Anara Harness]"

_MAX_ANCHOR_SAMPLES = 32
_MAX_ANCHOR_MATCHES = 8
_RUNAWAY_DISTINCT_LINE_RATIO = 0.5
STOP_PATH_MIN_CHARS = 16_000
_STREAM_TAIL_CHARS = 4 * STOP_PATH_MIN_CHARS


def is_repetition_dominated(text: str) -> bool:
    """
    True when a contiguous run of at least five exact repetitions covers at least half of text.
    Signature of a model degenerate repetition loop (Hermes / Anara Standard).
    """
    if not isinstance(text, str):
        return False
    n = len(text)
    if n < MIN_FRAGMENT_LENGTH:
        return False

    # Fast path: one normalized line duplicated enough to cover half the fragment.
    if _line_repetition_dominated(text, n):
        return True

    return _window_count_dominated(text, n) or _periodic_run_dominated(text, n)


def _line_repetition_dominated(text: str, n: int) -> bool:
    """Detects when a single non-empty line covers more than half of the text."""
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) >= 15]
    if len(lines) < 4:
        return False

    counts = Counter(lines)
    most_common_line, count = counts.most_common(1)[0]
    if count >= 4 and (len(most_common_line) * count) >= (n * _DOMINANCE_RATIO):
        return True
    return False


def _window_count_dominated(text: str, n: int) -> bool:
    """True when one 60-char window recurs often enough to cover half of text."""
    window = _REPEAT_WINDOW
    needed = max(_MIN_REPEAT_COUNT, math.ceil(n * _DOMINANCE_RATIO / window))
    counts: Dict[str, int] = {}
    for i in range(n - window + 1):
        key = text[i : i + window]
        c = counts.get(key, 0) + 1
        if c >= needed:
            return True
        counts[key] = c
    return False


def _periodic_run_dominated(text: str, n: int) -> bool:
    """
    Detects a dominant exact periodic run from evenly spaced anchors.
    Expands candidate period in both directions to measure coverage using the true repeating unit.
    """
    window = _REPEAT_WINDOW
    max_start = n - window
    if max_start < 1:
        return False

    sample_step = max(1, (max_start + _MAX_ANCHOR_SAMPLES - 2) // (_MAX_ANCHOR_SAMPLES - 1))
    sample_starts = list(range(0, max_start + 1, sample_step))
    if sample_starts[-1] != max_start:
        sample_starts.append(max_start)

    rejected: List[Tuple[int, int, int]] = []
    for start in sample_starts:
        anchor = text[start : start + window]
        search_from = start + 1
        for _ in range(_MAX_ANCHOR_MATCHES):
            match = text.find(anchor, search_from)
            if match < 0:
                break
            period = match - start
            search_from = match + 1
            if any(lo <= start < hi and period % p == 0 for lo, hi, p in rejected):
                continue

            # Expand left
            left = start
            while left >= period and text[left - period : left] == text[left : left + period]:
                left -= period

            # Expand right
            right = start + window
            while right + period <= n and text[right : right + period] == text[right - period : right]:
                right += period

            run_len = right - left
            repeat_count = run_len / period
            if repeat_count >= _MIN_REPEAT_COUNT and run_len >= (n * _DOMINANCE_RATIO):
                return True
            rejected.append((left, right, period))

    return False


def is_runaway_repetition(text: str) -> bool:
    """
    True when output is large and dominated by repetitive lines or periodic windows.
    Protects stop-path final answers from dumping hundred-kilobyte loops.
    """
    if not isinstance(text, str) or len(text) < STOP_PATH_MIN_CHARS:
        return False

    tail = text[-_STREAM_TAIL_CHARS:]
    lines = [line.strip() for line in tail.splitlines() if line.strip()]
    if len(lines) >= 10:
        distinct = len(set(lines))
        if distinct / len(lines) < _RUNAWAY_DISTINCT_LINE_RATIO:
            return True

    return is_repetition_dominated(tail)
