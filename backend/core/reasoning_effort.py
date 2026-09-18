"""
reasoning_effort.py — Reasoning Effort Normalization & Ladder for Project Anara.
Anara Standard Reasoning Effort Ladder.
"""

from __future__ import annotations

from typing import List, Optional

EFFORT_LADDER: List[str] = ["none", "low", "medium", "high", "max"]


def clamp_effort(requested: Optional[str], allowed: List[str]) -> str:
    """Clamps a requested reasoning effort value to the highest supported tier in allowed."""
    if not requested or not allowed:
        return allowed[0] if allowed else "none"

    clean = str(requested).strip().lower()
    if clean in allowed:
        return clean

    # Map unknown aliases
    alias_map = {
        "xhigh": "high",
        "ultra": "high",
        "extreme": "high",
        "minimum": "low",
        "default": "medium",
        "off": "none",
        "false": "none",
        "0": "none",
    }
    target = alias_map.get(clean, "none")
    if target in allowed:
        return target

    # Fallback to nearest lower ladder value
    try:
        req_idx = EFFORT_LADDER.index(target)
    except ValueError:
        req_idx = 0

    for candidate in reversed(EFFORT_LADDER[: req_idx + 1]):
        if candidate in allowed:
            return candidate

    return allowed[0]
