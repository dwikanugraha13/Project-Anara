"""
reasoning_effort.py — Reasoning Effort Normalization & Ladder for Project Anara.
Anara Standard Reasoning Effort Ladder.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

EFFORT_LADDER: List[str] = ["none", "low", "medium", "high", "max"]


def clamp_effort(requested: Optional[str], allowed: List[str]) -> str:
    """Clamps a requested reasoning effort value to the highest supported tier in allowed."""
    if not requested or not allowed:
        return allowed[0] if allowed else "none"

    clean = str(requested).strip().lower()
    if clean in allowed:
        return clean

    # Map aliases
    alias_map = {
        "xhigh": "high",
        "ultra": "high",
        "extreme": "high",
        "minimal": "low",
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


def to_openai_reasoning(effort: Optional[str], model: str = "") -> Dict[str, Any]:
    """Translates effort to OpenAI API reasoning_effort parameter (Anara Standard)."""
    if not effort or effort == "none":
        return {}
    allowed = ["low", "medium", "high"]
    clamped = clamp_effort(effort, allowed)
    return {"reasoning_effort": clamped}


def to_anthropic_thinking(effort: Optional[str], model: str = "") -> Dict[str, Any]:
    """
    Translates effort to Anthropic API extended thinking parameter (Anara Standard).
    Budget scales monotonically from 2,048 to 32,000 tokens.
    """
    if not effort or effort == "none":
        return {}
    budget_map = {
        "low": 2048,
        "medium": 8192,
        "high": 16384,
        "max": 32000,
    }
    clamped = clamp_effort(effort, ["low", "medium", "high", "max"])
    budget = budget_map.get(clamped, 8192)
    return {"thinking": {"type": "enabled", "budget_tokens": budget}}


def to_gemini_thinking(effort: Optional[str], model: str = "") -> Dict[str, Any]:
    """Translates effort to Google Gemini API thinking configuration."""
    if not effort or effort == "none":
        return {"thinking_config": {"thinking_budget": 0}}
    budget_map = {
        "low": 2048,
        "medium": 8192,
        "high": 16384,
        "max": 24576,
    }
    clamped = clamp_effort(effort, ["low", "medium", "high", "max"])
    budget = budget_map.get(clamped, 8192)
    return {"thinking_config": {"thinking_budget": budget}}
