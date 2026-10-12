"""
empty_response_guard.py — Thinking-Only & Empty Response Guard for Project Anara.
Parity with Hermes Agent empty_response_guard & turn_empty_response (Nous Research).

Detects when reasoning models (DeepSeek-R1, QwQ, Gemini Thinking, Claude Thinking, etc.)
consume their turn entirely within reasoning scratchpads (<think>...</think>)
and emit zero visible public prose, preventing blank messages and rescuing the turn.
"""

from __future__ import annotations

import re
from typing import Optional

THINK_PATTERNS = re.compile(r"(?:<think>|<thought>|<reasoning>|思考|推理)", re.IGNORECASE)

DEFAULT_THINKING_NUDGE = (
    "[System Notice]: You completed your internal reasoning thoughts but provided no visible final response text. "
    "Please synthesize and output your final response to the user now based on your reasoning above."
)


def has_thinking_blocks(text: str) -> bool:
    """Returns True if the raw model output contained reasoning scratchpad tags."""
    if not isinstance(text, str):
        return False
    return bool(THINK_PATTERNS.search(text))


def should_nudge_for_empty(raw_text: str, clean_text: str, step: int, max_steps: int) -> bool:
    """
    Evaluates whether the turn qualifies for an automatic Thinking-Only Nudge.
    Criteria:
    1. Visible prose (clean_text) is empty or whitespace-only.
    2. Raw output contained reasoning thoughts.
    3. Step has not exceeded turn limit.
    """
    if step >= max_steps - 1:
        return False
    is_clean_empty = not clean_text or not clean_text.strip()
    return is_clean_empty and has_thinking_blocks(raw_text)


def build_thinking_nudge_prompt() -> str:
    """Returns the standardized technical prompt for the internal nudge."""
    return DEFAULT_THINKING_NUDGE


# ── THINKING TIMEOUT DETECTION & USER GUIDANCE (Hermes Parity) ──
_THINKING_TIMEOUT_SUBSTRINGS: tuple[str, ...] = (
    "broken pipe",
    "errno 32",
    "remote protocol",
    "connection reset",
    "connection lost",
    "peer closed",
    "server disconnected",
    "timeout",
    "timed out",
    "read timed out",
    "stream closed",
)

_REASONING_MODEL_HINTS: tuple[str, ...] = (
    "r1",
    "o1",
    "o3",
    "thinking",
    "thought",
    "reasoning",
    "deepseek-reasoner",
    "claude-3-7",
    "flash-thinking",
    "high",
)


def is_reasoning_timeout(model_name: str, error: Exception | str) -> bool:
    """True when a reasoning model hit a transport kill or timeout during thinking."""
    model_lower = (model_name or "").lower()
    is_reasoning = any(hint in model_lower for hint in _REASONING_MODEL_HINTS)
    if not is_reasoning:
        return False

    err_str = str(error).lower()
    return any(sub in err_str for sub in _THINKING_TIMEOUT_SUBSTRINGS)


def format_thinking_timeout_guidance(model_name: str, raw_error: Exception | str) -> str:
    """Constructs constructive, user-facing guidance when a thinking timeout occurs."""
    return (
        f"⏳ <b>[Reasoning Timeout Notice]</b>\n"
        f"Model <code>{model_name}</code> was thinking for too long and the upstream gateway "
        f"closed the connection before the first text token was received.\n\n"
        f"<b>Recommended Fixes:</b>\n"
        f"• Lower the reasoning budget via <code>/reasoning low</code> or <code>/reasoning medium</code>\n"
        f"• Switch to a faster/standard model via <code>/model</code>\n"
        f"• Or retry your prompt with a more specific directive."
    )


# ── SILENCE NARRATION SUPPRESSION (Hermes Gateway Parity) ──
_SILENCE_NARRATION = re.compile(
    r'^[\s*_~`]*\(?\s*(silent|silence|no\s+response|no\s+reply)\s*\.?\)?[\s*_~`]*$'
    r'|^[\s*_~`]*[\U0001F507\.\u2026]+[\s*_~`]*$',
    re.IGNORECASE,
)


def is_silence_narration(content: Optional[str]) -> bool:
    """True when content is solely a silence-narration token (e.g. '*(silent)*', '(no reply)', '...')."""
    stripped = content.strip() if content else ""
    return bool(stripped) and len(stripped) <= 64 and bool(_SILENCE_NARRATION.match(stripped))


