"""
output_manager.py — Smart Tool Output Truncation & Context Compaction for Project Anara.
Anara Standard Smart Output Limiter & Compactor:
1. Prevents context window explosion and token exhaustion on massive CLI/file/test outputs.
2. Persists untruncated raw output to %LOCALAPPDATA%/anara/logs/tool_logs/ for offline debugging.
3. Preserves Head (context of what ran) + Tail (failure trace / exit summary / test result).
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional, Any
from constants import get_anara_logs_dir

TOOL_LOGS_DIR = get_anara_logs_dir("tool_logs")
TOOL_LOGS_DIR.mkdir(parents=True, exist_ok=True)


def compact_tool_output(
    output: str,
    max_lines: int = 60,
    max_chars: int = 4000,
    head_ratio: float = 0.4,
    source_label: str = "output",
) -> str:
    """
    Truncates massive outputs into a clean Head + Tail snippet with an informative notice,
    writing the full raw output to disk for auditability.
    """
    if not output:
        return ""

    from tools.self_correction import ContextMicroCompactor
    text = ContextMicroCompactor.clean_terminal_noise(str(output)).strip()
    line_count = text.count("\n") + 1

    # If within safe limits, return verbatim
    if len(text) <= max_chars and line_count <= max_lines:
        return text

    # 1. Save full untruncated dump to disk
    dump_id = uuid.uuid4().hex[:8]
    dump_file = TOOL_LOGS_DIR / f"{source_label}_{dump_id}.log"
    try:
        dump_file.write_text(text, encoding="utf-8", errors="replace")
        log_notice = f"Full log ({len(text):,} chars) saved to: {dump_file}"
    except Exception:
        log_notice = f"Total chars: {len(text):,}"

    # 2. Line-based truncation if multi-line
    lines = text.splitlines()
    if len(lines) > max_lines:
        head_lines_count = max(1, int(max_lines * head_ratio))
        tail_lines_count = max(1, max_lines - head_lines_count)
        head = "\n".join(lines[:head_lines_count])
        tail = "\n".join(lines[-tail_lines_count:])
        omitted = len(lines) - (head_lines_count + tail_lines_count)

        return (
            f"{head}\n\n"
            f"--- [OUTPUT TRUNCATED: {omitted} lines omitted. {log_notice}] ---\n\n"
            f"{tail}"
        )

    # 3. Char-based truncation (single or few very long lines, e.g. minified code/JSON)
    head_len = max(1, int(max_chars * head_ratio))
    tail_len = max(1, max_chars - head_len)
    head_text = text[:head_len]
    tail_text = text[-tail_len:]
    omitted_chars = len(text) - (head_len + tail_len)

    return (
        f"{head_text}\n\n"
        f"--- [OUTPUT TRUNCATED: {omitted_chars:,} chars omitted. {log_notice}] ---\n\n"
        f"{tail_text}"
    )


def compact_tool_payload(
    payload: Any,
    tool_name: str = "tool",
    max_lines: int = 60,
    max_chars: int = 4000,
    head_ratio: float = 0.4,
    max_list_items: int = 40,
    _depth: int = 0,
) -> Any:
    """
    Normalizes and compacts any tool execution payload (dict, str, or list)
    recursively preserving structured metadata while preventing token bloat.
    Handles giant lists (e.g. 500+ files from glob/find) and nested collections (Hermes Standard).
    """
    if payload is None or _depth > 4:
        return payload

    if isinstance(payload, str):
        return compact_tool_output(
            payload,
            max_lines=max_lines,
            max_chars=max_chars,
            head_ratio=head_ratio,
            source_label=tool_name,
        )

    if isinstance(payload, list):
        items = payload
        # 1. Truncate giant collections (e.g. hundreds of search results)
        if len(items) > max_list_items:
            head_count = max(1, int(max_list_items * head_ratio))
            tail_count = max(1, max_list_items - head_count)
            omitted = len(items) - (head_count + tail_count)
            stub = f"[... {omitted:,} additional items omitted to conserve context ...]"
            items = items[:head_count] + [stub] + items[-tail_count:]

        # 2. Recursively compact each item
        return [
            compact_tool_payload(
                it,
                tool_name=tool_name,
                max_lines=max_lines,
                max_chars=max_chars,
                head_ratio=head_ratio,
                max_list_items=max_list_items,
                _depth=_depth + 1,
            )
            for it in items
        ]

    if isinstance(payload, dict):
        compacted = dict(payload)
        for k, v in compacted.items():
            if isinstance(v, str):
                # Claude Code Parity: File reading tools self-bound their pagination via offset/limit.
                # Do not truncate legitimate source code views.
                is_file_read_content = (k == "content" and any(fn in str(tool_name).lower() for fn in ("read_local_file", "read_file", "file_read")))
                if not is_file_read_content and (k in ("output", "stdout", "stderr", "content", "message", "result", "diff", "raw", "summary") or len(v) > max_chars):
                    compacted[k] = compact_tool_output(
                        v,
                        max_lines=max_lines,
                        max_chars=max_chars,
                        head_ratio=head_ratio,
                        source_label=f"{tool_name}_{k}",
                    )
            elif isinstance(v, (list, dict)):
                compacted[k] = compact_tool_payload(
                    v,
                    tool_name=f"{tool_name}_{k}",
                    max_lines=max_lines,
                    max_chars=max_chars,
                    head_ratio=head_ratio,
                    max_list_items=max_list_items,
                    _depth=_depth + 1,
                )
        return compacted

    return payload
