"""
reasoning_effort.py — Reasoning Effort Normalization & Ladder for Project Anara.
Anara Standard Reasoning Effort Ladder.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

EFFORT_LADDER: List[str] = ["none", "low", "medium", "high", "max", "ultra"]


def clamp_effort(requested: Optional[str], allowed: List[str]) -> str:
    """Clamps a requested reasoning effort value to the highest supported tier in allowed."""
    if not requested or not allowed:
        return allowed[0] if allowed else "none"

    clean = str(requested).strip().lower()
    if clean in allowed:
        return clean

    # Map aliases
    alias_map = {
        "xhigh": "max",
        "ultra": "ultra" if "ultra" in allowed else "max",
        "extreme": "ultra" if "ultra" in allowed else "max",
        "minimal": "low",
        "minimum": "low",
        "default": "medium",
        "off": "none",
        "false": "none",
        "0": "none",
    }
    # Preserve standard ladder items before falling back to aliases
    target = clean if clean in EFFORT_LADDER else alias_map.get(clean, "none")
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
    if model:
        m_low = model.lower()
        # Guard: standard chat models (e.g. gpt-4o, gpt-4o-mini, gpt-3.5) reject reasoning_effort with HTTP 400
        if not any(k in m_low for k in ("o1", "o3", "o4", "gpt-5", "gpt-6", "astra", "codex", "thinking", "reason")):
            return {}
    # Astra / frontier reasoning routes accept up to ultra
    allowed = ["low", "medium", "high", "ultra"] if any(k in (model or "").lower() for k in ("astra", "gpt-6", "ultra")) else ["low", "medium", "high"]
    clamped = clamp_effort(effort, allowed)
    return {"reasoning_effort": clamped}


def to_anthropic_thinking(effort: Optional[str], model: str = "") -> Dict[str, Any]:
    """
    Translates effort to Anthropic API extended thinking parameter (Anara Standard).
    Budget scales monotonically from 2,048 to 64,000 tokens.
    """
    if not effort or effort == "none":
        return {}
    if model:
        m_low = model.lower()
        # Guard: non-thinking Claude models (e.g. claude-3-5-sonnet, claude-3-opus) reject thinking block with HTTP 400
        if not any(k in m_low for k in ("claude-3-7", "claude-3.7", "claude-4", "thinking", "reason")):
            return {}
    budget_map = {
        "low": 2048,
        "medium": 8192,
        "high": 16384,
        "max": 32000,
        "ultra": 64000,
    }
    clamped = clamp_effort(effort, ["low", "medium", "high", "max", "ultra"])
    budget = budget_map.get(clamped, 8192)
    return {"thinking": {"type": "enabled", "budget_tokens": budget}}


def to_gemini_thinking(effort: Optional[str], model: str = "") -> Dict[str, Any]:
    """Translates effort to Google Gemini API thinking configuration."""
    if not effort or effort == "none":
        return {"thinking_config": {"thinking_budget": 0}}
    if model:
        m_low = model.lower()
        # Guard: embeddings or non-generative models
        if any(k in m_low for k in ("embedding", "text-bison", "aqa", "imagen")):
            return {}
    budget_map = {
        "low": 2048,
        "medium": 8192,
        "high": 16384,
        "max": 24576,
        "ultra": 32768,
    }
    clamped = clamp_effort(effort, ["low", "medium", "high", "max", "ultra"])
    budget = budget_map.get(clamped, 8192)
    return {"thinking_config": {"thinking_budget": budget}}
