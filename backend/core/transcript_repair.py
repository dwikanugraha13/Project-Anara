"""
transcript_repair.py — Conversation Transcript Sanitization & Repair Engine (Hermes Parity).

Ensures multi-turn message transcripts conform strictly to LLM provider requirements
(OpenAI, Anthropic, Gemini, Groq, Ollama) before dispatch and upon recovery:
1. Lone Surrogate Code Point Scrubbing (prevents UTF-8 / json.dumps exceptions).
2. Tool Name Coercion (enforces valid identifier schema ^[A-Za-z0-9_-]{1,64}$).
3. Orphaned Tool Call Healing (synthesizes error response if tool_call_id is missing a tool turn).
4. Interrupted Tail Tool Closure (closes trailing tool response so next user turn is not tool -> user).
5. Blank Content Healing (provides non-empty fallback for empty assistant turns).
6. Strict Role Alternation (merges adjacent same-role messages for Claude / Gemini).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("anara.transcript_repair")

_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")
_VALID_TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def sanitize_surrogates(text: str) -> str:
    """Replaces lone surrogate code points with unicode replacement char U+FFFD."""
    if not isinstance(text, str) or text.isascii():
        return text
    return _SURROGATE_RE.sub("\ufffd", text)


def coerce_tool_name(name: Any, fallback: str = "invalid_tool_call") -> str:
    """Coerces tool name to valid identifier regex ^[A-Za-z0-9_-]{1,64}$."""
    if not isinstance(name, str):
        return fallback
    clean = name.strip()
    if _VALID_TOOL_NAME_RE.fullmatch(clean):
        return clean
    coerced = re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9_-]", "_", clean)).strip("_")
    return coerced[:64] or fallback


def close_interrupted_tool_sequence(messages: List[Dict[str, Any]], final_response: Optional[str] = None) -> bool:
    """
    Appends a synthetic assistant turn when transcript tail is a raw tool response.
    Prevents invalid tool -> user sequence rejection in Anthropic and Gemini.
    """
    if not messages:
        return False
    last = messages[-1]
    if isinstance(last, dict) and last.get("role") in ("tool", "function"):
        content = (final_response or "").strip() or "Operation interrupted."
        messages.append({"role": "assistant", "content": content})
        return True
    return False


def uniquify_tool_call_ids(tool_calls: List[Any]) -> List[Any]:
    """
    Hermes Parity (agent/message_sanitization.py: uniquify_tool_call_ids).
    Ensures every tool call in one turn has a distinct ID.
    If collisions exist (e.g. call_0, call_0), renames subsequent ones with deterministic
    _d<n> suffixes (e.g. call_0_d2, call_0_d3) to prevent OpenAI/Anthropic/Gemini HTTP 400 Bad Request.
    Mutates dicts or tool call objects in place and returns tool_calls.
    """
    if not tool_calls:
        return tool_calls

    seen: set = set()
    for tc in tool_calls:
        cid = None
        if isinstance(tc, dict):
            cid = tc.get("id") or tc.get("call_id")
        elif hasattr(tc, "id"):
            cid = getattr(tc, "id", None)
        elif hasattr(tc, "call_id"):
            cid = getattr(tc, "call_id", None)

        if not cid:
            continue
        cid_str = str(cid).strip()
        if not cid_str:
            continue

        if cid_str not in seen:
            seen.add(cid_str)
            continue

        # Collision detected! Compute deterministic unique suffix
        suffix_n = 2
        new_id = f"{cid_str}_d{suffix_n}"
        while new_id in seen:
            suffix_n += 1
            new_id = f"{cid_str}_d{suffix_n}"
        seen.add(new_id)

        # Mutate in place
        if isinstance(tc, dict):
            tc["id"] = new_id
            if "call_id" in tc:
                tc["call_id"] = new_id
        else:
            if hasattr(tc, "id"):
                setattr(tc, "id", new_id)
            if hasattr(tc, "call_id"):
                setattr(tc, "call_id", new_id)

        logger.warning(
            f"[TranscriptRepair] Duplicate tool call id '{cid_str}' detected; "
            f"uniquified to '{new_id}' to prevent HTTP 400 rejection."
        )

    return tool_calls


def validate_and_filter_tool_batch(
    tool_calls: List[Any],
    valid_tool_names: Set[str]
) -> Tuple[List[Any], List[Dict[str, Any]]]:
    """
    Hermes Parity (agent/turn_tool_validation.py: validate_tool_calls).
    Separates a batch of tool calls into valid calls (to execute) and invalid/hallucinated
    calls (to return synthetic tool error observations for).
    Returns (executable_calls, invalid_tool_error_results).
    """
    valid_calls: List[Any] = []
    error_results: List[Dict[str, Any]] = []

    if not tool_calls:
        return valid_calls, error_results

    for tc in tool_calls:
        name = ""
        cid = ""
        if isinstance(tc, dict):
            name = (tc.get("function") or {}).get("name") or tc.get("name") or ""
            cid = tc.get("id") or tc.get("tool_call_id") or ""
        elif hasattr(tc, "name"):
            name = getattr(tc, "name", "")
            cid = getattr(tc, "id", "") or getattr(tc, "call_id", "")
        elif hasattr(tc, "function"):
            fn = getattr(tc, "function", None)
            name = getattr(fn, "name", "") if fn else ""
            cid = getattr(tc, "id", "") or getattr(tc, "call_id", "")

        coerced_name = coerce_tool_name(name) if name else "unknown_tool"
        if not valid_tool_names or name in valid_tool_names or coerced_name in valid_tool_names:
            valid_calls.append(tc)
        else:
            logger.warning(
                f"[ToolValidation] Tool '{name}' not found in registered tools. "
                f"Generating synthetic tool error observation."
            )
            error_results.append({
                "role": "tool",
                "tool_call_id": cid or f"call_{coerced_name}",
                "name": name or coerced_name,
                "content": json.dumps({
                    "status": "error",
                    "error": f"Unknown tool '{name}'. Available tools: {sorted(list(valid_tool_names))[:15]}"
                })
            })

    return valid_calls, error_results


def repair_transcript_sequence(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validates and repairs a conversation message sequence for provider compatibility.
    - Resolves missing tool responses for assistant tool_calls.
    - Merges consecutive turns of identical roles (user -> user or assistant -> assistant).
    - Cleans surrogate characters.
    - Closes trailing tool responses.
    - Heals blank assistant messages.
    """
    if not messages:
        return []

    # Step 1: Deep copy and scrub surrogates
    cleaned: List[Dict[str, Any]] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        msg = dict(m)
        content = msg.get("content")
        if isinstance(content, str):
            msg["content"] = sanitize_surrogates(content)
        elif isinstance(content, list):
            new_parts = []
            for p in content:
                if isinstance(p, dict):
                    p_copy = dict(p)
                    if isinstance(p_copy.get("text"), str):
                        p_copy["text"] = sanitize_surrogates(p_copy["text"])
                    new_parts.append(p_copy)
                else:
                    new_parts.append(p)
            msg["content"] = new_parts

        # Sanitize tool calls if present
        tool_calls = msg.get("tool_calls")
        if isinstance(tool_calls, list):
            new_tcs = []
            for tc in tool_calls:
                if isinstance(tc, dict):
                    tc_copy = dict(tc)
                    fn = tc_copy.get("function")
                    if isinstance(fn, dict):
                        fn_copy = dict(fn)
                        if "name" in fn_copy:
                            fn_copy["name"] = coerce_tool_name(fn_copy["name"])
                        if isinstance(fn_copy.get("arguments"), str):
                            fn_copy["arguments"] = sanitize_surrogates(fn_copy["arguments"])
                        tc_copy["function"] = fn_copy
                    new_tcs.append(tc_copy)
                else:
                    new_tcs.append(tc)
            msg["tool_calls"] = new_tcs

        cleaned.append(msg)

    if not cleaned:
        return []

    # Step 2: Orphaned Tool Calls Resolution & Tool Batch Validation
    repaired: List[Dict[str, Any]] = []
    i = 0
    while i < len(cleaned):
        current = cleaned[i]
        repaired.append(current)
        i += 1

        # Check if current assistant turn emitted tool_calls
        tcs = current.get("tool_calls") if current.get("role") == "assistant" else None
        if isinstance(tcs, list) and len(tcs) > 0:
            expected_ids = set()
            id_to_name = {}
            for tc in tcs:
                if isinstance(tc, dict):
                    cid = tc.get("id") or (tc.get("function") or {}).get("name")
                    if cid:
                        expected_ids.add(str(cid))
                        fn_name = (tc.get("function") or {}).get("name") or "tool"
                        id_to_name[str(cid)] = fn_name

            # Look ahead for existing tool result messages
            answered_ids = set()
            while i < len(cleaned):
                next_msg = cleaned[i]
                if next_msg.get("role") in ("tool", "function"):
                    repaired.append(next_msg)
                    tid = str(next_msg.get("tool_call_id") or next_msg.get("name") or "")
                    if tid in expected_ids:
                        answered_ids.add(tid)
                    i += 1
                else:
                    break

            # Synthesize responses for missing tool calls
            missing = expected_ids - answered_ids
            for missing_id in sorted(list(missing)):
                tool_name = id_to_name.get(missing_id, "unknown_tool")
                logger.warning(f"[TranscriptRepair] Healing orphaned tool_call '{missing_id}' ({tool_name}) with synthetic error result")
                repaired.append({
                    "role": "tool",
                    "tool_call_id": missing_id,
                    "name": tool_name,
                    "content": json.dumps({
                        "status": "interrupted",
                        "error": f"Tool execution for '{tool_name}' was interrupted or result was dropped."
                    })
                })

    # Step 3: Close interrupted trailing tool response
    close_interrupted_tool_sequence(repaired)

    # Step 4: Strict Role Alternation & Blank Content Healing
    final_sequence: List[Dict[str, Any]] = []
    for msg in repaired:
        role = msg.get("role")
        content = msg.get("content")
        has_tools = bool(msg.get("tool_calls"))

        # Heal blank assistant content
        if role == "assistant" and not has_tools:
            if content is None or (isinstance(content, str) and not content.strip()):
                msg["content"] = "[No response recorded]"

        if not final_sequence:
            final_sequence.append(msg)
            continue

        prev = final_sequence[-1]
        prev_role = prev.get("role")

        # Merge consecutive identical user turns
        if role == "user" and prev_role == "user":
            prev_text = prev.get("content") or ""
            curr_text = msg.get("content") or ""
            if isinstance(prev_text, str) and isinstance(curr_text, str):
                prev["content"] = f"{prev_text}\n\n{curr_text}".strip()
                continue

        # Merge consecutive plain assistant turns (without tool_calls)
        if role == "assistant" and prev_role == "assistant" and not has_tools and not prev.get("tool_calls"):
            prev_text = prev.get("content") or ""
            curr_text = msg.get("content") or ""
            if isinstance(prev_text, str) and isinstance(curr_text, str):
                prev["content"] = f"{prev_text}\n\n{curr_text}".strip()
                continue

        final_sequence.append(msg)

    return final_sequence
