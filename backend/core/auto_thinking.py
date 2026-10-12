"""
auto_thinking.py — Zero-Latency Dynamic Effort Classifier for Project Anara.
Parity with Oh My Pi (packages/coding-agent/src/auto-thinking/classifier.ts).

Dynamically scales reasoning/thinking depth ('none', 'low', 'medium', 'high', 'max')
based on prompt complexity and task requirements, preventing token waste on trivial tasks
while ensuring deep reasoning on complex architectural challenges.
"""

from __future__ import annotations

import re
from typing import List, Optional

from core.reasoning_effort import clamp_effort


_TRIVIAL_GREETING_RE = re.compile(
    r"^(?:halo|hai|hi|hello|hey|p|ping|test|tes|siang|pagi|malam|apa kabar|yo|assalamualaikum|bro|nan|\s+)+[.?!]*$",
    re.IGNORECASE
)

_TRIVIAL_INSPECT_PATTERNS = [
    r"\b(?:baca|lihat|tampilkan|cek|cat|read|show|view|inspect)\s+(?:file|berkas|folder|isi)\b",
    r"\b(?:list|ls|dir)\b",
    r"\b(?:beautify|prettify)\b",
    r"\b(?:apa\s+isi|isi\s+dari)\b",
    r"\b(?:status|version|versi)\b",
]

_HARD_ARCHITECTURE_PATTERNS = [
    r"\b(?:arsitektur|architecture|state\s*machine|lifecycle)\b",
    r"\b(?:kombinasi|gabungin|synthesiz|merge\s+architecture)\b",
    r"\b(?:refactor|redesign|overhaul)\b",
    r"\b(?:race\s*condition|deadlock|concurrency|thread\s*safety|asyncio\s*lock)\b",
    r"\b(?:memory\s*leak|buffer\s*overflow|profiling|tracemalloc)\b",
    r"\b(?:algoritma|algorithm|heuristic|dynamic\s*programming)\b",
    r"\b(?:benchmark|evals|evaluasi\s*empiris|metaharness)\b",
    r"\b(?:security|sandbox|vulnerability|exploit|injection)\b",
    r"\b(?:multi-agent|swarm|subagent\s*fanout|orchestrator)\b",
    r"\b(?:harness|parity|compiler\s*guard|hashline)\b",
]


def classify_prompt_difficulty(prompt: str) -> str:
    """
    Classifies prompt difficulty into:
    - 'trivial': Minimalist read-only inspection or greeting (0-1K tokens).
    - 'moderate': Standard coding, localized bug fixes, UI updates (4K-8K tokens).
    - 'hard': Complex multi-component architecture, refactoring, or algorithmic work (16K-32K tokens).
    """
    clean = (prompt or "").strip().lower()
    if not clean:
        return "trivial"

    # 1. Pure conversational greetings or pings -> trivial
    if _TRIVIAL_GREETING_RE.match(clean):
        return "trivial"

    # 2. Check hard architectural triggers
    for pat in _HARD_ARCHITECTURE_PATTERNS:
        if re.search(pat, clean):
            return "hard"

    # 3. Check trivial inspect/show triggers
    word_count = len(clean.split())
    if word_count <= 15:
        for pat in _TRIVIAL_INSPECT_PATTERNS:
            if re.search(pat, clean):
                return "trivial"

    # Multi-step complex prompts with bullet points or >60 words
    if clean.count("\n- ") >= 2 or clean.count("\n1.") >= 2 or word_count > 60:
        return "hard"

    # 4. Default to moderate
    return "moderate"


def resolve_auto_thinking_effort(
    prompt: str,
    requested_effort: Optional[str] = "auto",
    allowed_efforts: Optional[List[str]] = None
) -> str:
    """
    Resolves the active reasoning effort for a turn.
    If requested_effort is 'auto' (or None), dynamically classifies the prompt
    and clamps to allowed model efforts. Otherwise, preserves explicit user selection.
    """
    if allowed_efforts is None:
        allowed_efforts = ["none", "low", "medium", "high", "max"]

    req_clean = str(requested_effort or "auto").strip().lower()
    if req_clean != "auto":
        return clamp_effort(req_clean, allowed_efforts)

    # Dynamic Classification
    difficulty = classify_prompt_difficulty(prompt)

    if difficulty == "trivial":
        target = "none" if "none" in allowed_efforts else "low"
    elif difficulty == "hard":
        target = "high" if "high" in allowed_efforts else "max"
    else:
        # moderate
        target = "medium"

    return clamp_effort(target, allowed_efforts)
