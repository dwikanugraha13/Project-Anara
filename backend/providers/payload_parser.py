"""
payload_parser.py — Model Output & Tool Call Parsing Utilities for Project Anara.
Robust JSON deserialization, anti-leak lead text sanitization, deterministic bracket balancing,
and multi-tool XML/Markdown/JSON block extraction.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from providers.think_scrubber import THINK_TAG_NAMES

logger = logging.getLogger("anara.payload_parser")


def _robust_parse_json(candidate_str: str) -> Optional[Any]:
    """Attempts standard and fault-tolerant JSON deserialization with safe repair."""
    if not candidate_str or not candidate_str.strip():
        return None
    s = candidate_str.strip()

    # Attempt 1: Standard load
    try:
        return json.loads(s)
    except Exception:
        pass

    # Attempt 2: Trailing comma repair
    try:
        repaired = re.sub(r',\s*([\}\]])', r'\1', s)
        return json.loads(repaired)
    except Exception:
        pass

    # Attempt 3: AST literal eval fallback for Python dict/list structures
    try:
        import ast
        val = ast.literal_eval(s)
        if isinstance(val, (dict, list)):
            return val
    except Exception:
        pass

    return None


def _sanitize_lead_narration(raw_lead: str) -> str:
    """
    Anara Anti-Leak Sanitizer for narrative text:
    Strips raw tool call blocks, XML tags, observation dumps, and directory listings.
    Guarantees pure human conversational prose without technical payload residue.
    """
    if not raw_lead or not raw_lead.strip():
        return ""

    text = raw_lead.strip()

    # 1. Strip any markdown code blocks containing tool calls or JSON
    text = re.sub(r"```(?:json)?\s*\{[\s\S]*?\"action\"\s*:\s*\"tool_call\"[\s\S]*?\}\s*```", "", text)
    text = re.sub(r"<tool_call>[\s\S]*?</tool_call>", "", text, flags=re.IGNORECASE)

    # 2. Strip standalone JSON objects with action: tool_call
    text = re.sub(r"\{[\s\S]*?\"action\"\s*:\s*\"tool_call\"[\s\S]*?\}", "", text)

    # 3. Strip observation artifacts (e.g. \f"...", [TOOL RESULT], [OBSERVATION], [DIRECTORY STATUS])
    text = re.sub(r'\\f["\'][^\n]*', "", text)
    text = re.sub(r'\[(?:TOOL[ _](?:RESULT|OBSERVATION|ERROR)|OBSERVATION|DIRECTORY[ _]STATUS|TOOL RESULT|STATUS[^\]]*|OBSERVASI|HASIL)[^\]]*\][^\n]*', "", text, flags=re.IGNORECASE)

    # 4. Strip directory listing lines (e.g. - [DIR] ..., - [FILE] ...)
    text = re.sub(r"(?m)^\s*-\s*\[(?:DIR|FILE)\][^\n]*\n?", "", text)

    # 5. Strip isolated backticks or broken fence remnants
    text = re.sub(r"```(?:json|shell|bash)?\s*```", "", text)
    text = text.strip()

    # If the text has no meaningful narrative words (only punctuation, whitespace, or technical tokens)
    words = [w for w in re.findall(r"\b\w+\b", text) if w.lower() not in ("json", "action", "tool", "tool_call", "arguments")]
    if len(words) < 2:
        return ""

    return text


def _format_empty_model_notice(prompt: str = "") -> str:
    """
    Anara Universal Fallback Notice:
    Returns a clean, natural technical fallback notice when the model produces an empty turn,
    without brittle Unicode character range checks or robotic jargon.
    """
    return "Belum ada respons teks yang dihasilkan pada giliran ini. Coba ulangi atau berikan instruksi yang lebih spesifik, Bro."


def _strip_think_blocks(text: str) -> str:
    """
    Anara Standard:
    Strips inline <think>, <thought>, <reasoning>, and multilingual thinking blocks,
    orphan tags, and bare thinking monologue preambles from model responses.
    """
    if not text:
        return ""
    tag_pattern = "|".join(re.escape(name) for name in THINK_TAG_NAMES)
    pattern = rf"(?is)<(?:{tag_pattern})\b[^>]*>[\s\S]*?</(?:{tag_pattern})>"
    text = re.sub(pattern, "", text)
    # Strip unclosed opening think tag at start of output
    text = re.sub(rf"(?is)^<(?:{tag_pattern})\b[^>]*>[\s\S]*?(?:(?=```)|$)", "", text)
    # Strip orphan closing tags
    text = re.sub(rf"(?i)</(?:{tag_pattern})>", "", text)
    return text.strip()


def _extract_think_blocks(text: str) -> Tuple[str, str]:
    """
    Extracts thoughts/reasoning blocks and clean response text from raw model output.
    Returns: (clean_text, reasoning_text)
    """
    if not text:
        return ("", "")
    tag_pattern = "|".join(re.escape(name) for name in THINK_TAG_NAMES)
    pattern = rf"(?is)<(?:{tag_pattern})\b[^>]*>([\s\S]*?)</(?:{tag_pattern})>"
    thoughts = re.findall(pattern, text)
    reasoning_text = "\n\n".join(t.strip() for t in thoughts if t.strip())
    clean = _strip_think_blocks(text)
    return (clean, reasoning_text)


def _clean_model_chat_text(raw_text: str) -> str:
    """
    Cleans model chat responses by removing markdown tool-call fences,
    bare JSON tool payloads, reasoning/think blocks, observation tags, and trailing punctuation/braces (Anara Standard).
    Guarantees that responses consisting solely of brackets or punctuation (e.g. '}', '{}', '```')
    are treated as empty so proper conversational synthesis is executed.
    """
    if not raw_text or not isinstance(raw_text, str):
        return ""
    text = _strip_think_blocks(raw_text.strip())

    # 1. Strip markdown fences containing tool calls
    text = re.sub(r"```(?:json)?\s*\{[\s\S]*?\"action\"\s*:\s*\"tool_call\"[\s\S]*?\}\s*```", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<tool_call>[\s\S]*?</tool_call>", "", text, flags=re.IGNORECASE)

    # 2. Strip standalone/bare JSON blocks containing action: tool_call
    text = re.sub(r"\{[\s\S]*?\"action\"\s*:\s*\"tool_call\"[\s\S]*?\}", "", text, flags=re.IGNORECASE)

    # 3. Strip observation tags
    text = re.sub(r'\[(?:TOOL[ _](?:RESULT|OBSERVATION|ERROR)|OBSERVATION|DIRECTORY[ _]STATUS|TOOL RESULT)[^\]]*\][^\n]*', "", text, flags=re.IGNORECASE)

    # 4. Strip empty fences and trailing/leading structural punctuation
    text = re.sub(r"```(?:json|shell|bash)?\s*```", "", text)
    text = text.strip()
    text = text.strip("{}[]` \t\r\n")

    # 5. Check if remaining text contains actual words (Unicode word characters)
    words = [w for w in re.findall(r"[\w\d]+", text, re.UNICODE) if w.lower() not in ("json", "action", "tool", "tool_call", "arguments")]
    if not words:
        return ""

    return text


def _extract_json_balanced(text: str) -> List[Tuple[str, int, int]]:
    """
    Deterministic bracket-balancing parser for JSON objects in text (Anara Standard).
    Accurately extracts top-level { ... } pairs while respecting quotes and escape characters.
    Returns: list of (json_str, start_pos, end_pos)
    """
    results: List[Tuple[str, int, int]] = []
    in_str = False
    escape = False
    depth = 0
    start = None

    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == '\\' and in_str:
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if not in_str:
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start is not None:
                    results.append((text[start:i+1], start, i+1))
                    start = None
                elif depth < 0:
                    depth = 0
                    start = None

    return results


def _extract_and_parse_tool_calls(raw_out: str) -> Tuple[List[Dict[str, Any]], str, bool]:
    """
    Extracts and robustly parses one or more tool call payloads from model output text.
    Supports:
    - Multiple ```json ... ``` blocks
    - Array of tool calls: [ {"action": "tool_call", ...}, ... ]
    - Multiple XML style: <tool_call>{ ... }</tool_call>
    - Bare JSON object: { "action": "tool_call", ... }
    Guarantees earliest-boundary lead text extraction with Anara Anti-Leak Sanitization.
    Returns: (list_of_payloads, lead_text, is_malformed_candidate)
    """
    if not raw_out or not raw_out.strip():
        return [], "", False

    text = raw_out.strip()
    calls: List[Dict[str, Any]] = []
    earliest_tool_start = None

    def _normalize_and_add(parsed_obj: Any):
        if isinstance(parsed_obj, dict):
            if parsed_obj.get("action") == "tool_call" or "tool" in parsed_obj:
                calls.append({
                    "action": "tool_call",
                    "tool": parsed_obj.get("tool", ""),
                    "arguments": parsed_obj.get("arguments", {}) or {},
                })
            elif isinstance(parsed_obj.get("tool_calls"), list):
                for sub in parsed_obj["tool_calls"]:
                    _normalize_and_add(sub)
        elif isinstance(parsed_obj, list):
            for sub in parsed_obj:
                _normalize_and_add(sub)

    # 1. Look for all XML style <tool_call>...</tool_call> blocks
    xml_matches = list(re.finditer(r"<tool_call>\s*([\s\S]*?)\s*</tool_call>", text, re.IGNORECASE))
    if xml_matches:
        for xm in xml_matches:
            parsed = _robust_parse_json(xm.group(1))
            if parsed is not None:
                if earliest_tool_start is None or xm.start() < earliest_tool_start:
                    earliest_tool_start = xm.start()
                _normalize_and_add(parsed)

    # 2. Look for all markdown code blocks ```json ... ``` or ``` ... ```
    block_matches = list(re.finditer(r"```(?:json)?\s*([\s\S]*?)\s*```", text))
    if block_matches:
        for bm in block_matches:
            block_content = bm.group(1).strip()
            if ('"action"' in block_content and '"tool"' in block_content) or ('"tool"' in block_content and '{' in block_content):
                parsed = _robust_parse_json(block_content)
                if parsed is not None:
                    if earliest_tool_start is None or bm.start() < earliest_tool_start:
                        earliest_tool_start = bm.start()
                    _normalize_and_add(parsed)

    # 3. Look for bare JSON objects or array if no blocks matched
    if not calls:
        if (text.startswith("{") or text.startswith("[")) and ('"tool"' in text or '"action"' in text):
            parsed = _robust_parse_json(text)
            if parsed is not None:
                earliest_tool_start = 0
                _normalize_and_add(parsed)
        else:
            # Deterministic Bracket-Balancing JSON extraction (Anara Standard)
            for candidate, start_idx, _ in _extract_json_balanced(text):
                if ('"action"' in candidate and '"tool_call"' in candidate) or ('"tool"' in candidate and '"arguments"' in candidate):
                    parsed = _robust_parse_json(candidate)
                    if parsed is not None:
                        if earliest_tool_start is None or start_idx < earliest_tool_start:
                            earliest_tool_start = start_idx
                        _normalize_and_add(parsed)

    lead_text = ""
    if earliest_tool_start is not None and earliest_tool_start > 0:
        lead_text = text[:earliest_tool_start].strip()

    lead_text = _sanitize_lead_narration(lead_text)

    if calls:
        return calls, lead_text, False

    # Check if text was likely an intended tool call that failed parsing
    if re.search(r'["\']action["\']\s*:\s*["\']tool_call["\']', text) or "<tool_call>" in text:
        return [], text, True

    return [], text, False


def _extract_and_parse_tool_call(raw_out: str) -> Tuple[Optional[Dict[str, Any]], str, bool]:
    """Compatibility wrapper returning single tool call payload."""
    calls, lead_text, is_malformed = _extract_and_parse_tool_calls(raw_out)
    return (calls[0] if calls else None, lead_text, is_malformed)


def _build_closing_history(history: List[Any], closing_instruction: str) -> List[Any]:
    """Builds a closing turn history ensuring strict role alternation (prevents consecutive user messages)."""
    if not history:
        return [{"role": "user", "content": closing_instruction}]

    if not isinstance(history[0], dict):
        from google.genai import types as genai_types
        closing_history = list(history)
        if closing_history and getattr(closing_history[-1], "role", "") == "user":
            last_c = closing_history[-1]
            if hasattr(last_c, "parts"):
                last_c.parts.append(genai_types.Part.from_text(text=f"\n\n{closing_instruction}"))
            else:
                closing_history.append(genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=closing_instruction)]))
        else:
            closing_history.append(genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=closing_instruction)]))
        return closing_history
    else:
        closing_history = list(history)
        if closing_history and isinstance(closing_history[-1], dict) and closing_history[-1].get("role") == "user":
            last_c = dict(closing_history[-1])
            c_val = last_c.get("content")
            if isinstance(c_val, list):
                last_c["content"] = [*c_val, {"type": "text", "text": f"\n\n{closing_instruction}"}]
            elif isinstance(c_val, str):
                last_c["content"] = f"{c_val}\n\n{closing_instruction}"
            closing_history[-1] = last_c
        else:
            closing_history.append({"role": "user", "content": closing_instruction})
        return closing_history
