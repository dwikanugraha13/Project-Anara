"""
prompt_caching.py — Provider-Level Prompt Caching & Rolling Breakpoint Planner.
Hermes Parity: Distributes Anthropic ephemeral cache_control breakpoints across system, tools, and message history.

Anthropic hard-caps cache_control markers at 4 per request:
- 1 marker reserved for static system prompt prefix / instruction
- 1 marker reserved for the last registered tool in the tool catalog
- Up to 2 rolling markers placed on the tail of conversation history to maximize KV-cache reuse.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("anara.core.prompt_caching")

EPHEMERAL_MARKER: Dict[str, str] = {"type": "ephemeral"}


def can_carry_cache_marker(msg: Dict[str, Any]) -> bool:
    """True if message is eligible to carry an Anthropic prompt caching breakpoint."""
    if not isinstance(msg, dict):
        return False
    role = msg.get("role")
    if role not in ("user", "assistant"):
        return False
    content = msg.get("content")
    if isinstance(content, str) and content.strip():
        return True
    if isinstance(content, list) and len(content) > 0:
        return isinstance(content[-1], dict)
    return False


def _mark_single_message(msg: Dict[str, Any], marker: Dict[str, str]) -> Dict[str, Any]:
    """Applies cache_control marker to a message, converting plain string content into a text block."""
    new_msg = dict(msg)
    content = msg.get("content")
    if isinstance(content, str):
        new_msg["content"] = [
            {
                "type": "text",
                "text": content,
                "cache_control": dict(marker),
            }
        ]
    elif isinstance(content, list) and content:
        new_content = [dict(c) if isinstance(c, dict) else c for c in content]
        if isinstance(new_content[-1], dict):
            new_content[-1]["cache_control"] = dict(marker)
        new_msg["content"] = new_content
    return new_msg


def apply_rolling_prompt_cache(
    messages: List[Dict[str, Any]],
    max_message_markers: int = 2,
    marker: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Creates a decorated shallow copy of messages with rolling cache_control markers
    placed on the most recent eligible messages.

    Does NOT mutate the original input list or messages in-place.
    """
    if not messages or max_message_markers <= 0:
        return list(messages)

    active_marker = marker or EPHEMERAL_MARKER

    # 1. Identify indices of eligible messages from tail backwards
    eligible_indices: List[int] = []
    for idx in range(len(messages) - 1, -1, -1):
        if can_carry_cache_marker(messages[idx]):
            eligible_indices.append(idx)
            if len(eligible_indices) >= max_message_markers:
                break

    target_set = set(eligible_indices)

    # 2. Rebuild list decorating only the targeted messages
    decorated: List[Dict[str, Any]] = []
    for idx, msg in enumerate(messages):
        if idx in target_set:
            decorated.append(_mark_single_message(msg, active_marker))
        else:
            decorated.append(msg)

    return decorated


def strip_prompt_cache_markers(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Removes cache_control markers and restores single text part lists back to strings."""
    stripped: List[Dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            stripped.append(msg)
            continue

        new_msg = dict(msg)
        new_msg.pop("cache_control", None)
        content = new_msg.get("content")

        if isinstance(content, list):
            cleaned_parts = []
            for part in content:
                if isinstance(part, dict):
                    p_copy = {k: v for k, v in part.items() if k != "cache_control"}
                    cleaned_parts.append(p_copy)
                else:
                    cleaned_parts.append(part)

            # If it's a single text block, restore plain string
            if len(cleaned_parts) == 1 and isinstance(cleaned_parts[0], dict) and cleaned_parts[0].get("type") == "text":
                new_msg["content"] = cleaned_parts[0].get("text", "")
            else:
                new_msg["content"] = cleaned_parts

        stripped.append(new_msg)

    return stripped


def count_cache_markers_in_payload(payload: Dict[str, Any]) -> int:
    """Utility to count total cache_control breakpoints configured in an Anthropic payload."""
    count = 0
    # Check system
    sys = payload.get("system")
    if isinstance(sys, list):
        for block in sys:
            if isinstance(block, dict) and "cache_control" in block:
                count += 1
    # Check tools
    tools = payload.get("tools")
    if isinstance(tools, list):
        for tool in tools:
            if isinstance(tool, dict) and "cache_control" in tool:
                count += 1
    # Check messages
    msgs = payload.get("messages")
    if isinstance(msgs, list):
        for m in msgs:
            if isinstance(m, dict):
                if "cache_control" in m:
                    count += 1
                c = m.get("content")
                if isinstance(c, list):
                    for part in c:
                        if isinstance(part, dict) and "cache_control" in part:
                            count += 1
    return count
