"""
message_chunker.py — Omnichannel Fence-Aware Message Chunker & Formatter for Project Anara.
Splits long messages along paragraph and newline boundaries without breaking markdown code blocks.
Balances code fences across chunk boundaries so syntax highlighting never breaks.
"""

from __future__ import annotations

import re
from typing import Dict, Any, Optional, List

PLATFORM_MESSAGE_LIMITS: Dict[str, int] = {
    "discord": 1950,
    "telegram": 2000,
    "whatsapp": 3500,
    "slack": 3500,
    "cli": 32000,
    "web_studio": 64000,
    "web": 64000,
}


def _format_tool_progress_message(evt: Dict[str, Any]) -> str:
    """Formats an informative, user-friendly live status message for tool execution via dynamic introspection."""
    t_name = evt.get("tool_name", "")
    status = evt.get("status", "running")
    detail = evt.get("detail", "")
    summary = evt.get("summary", "")
    step = evt.get("step")

    step_str = f" [Step {step}]" if step else ""

    if t_name == "agent" and status == "thinking":
        return f"⚙️ Reasoning & planning steps...{step_str}"

    clean_name = t_name.replace("_", " ").title() if t_name else "Action"

    if status == "done":
        summary_val = str(summary or detail or "Complete")[:50]
        return f"✓ {clean_name}: {summary_val}{step_str}"
    elif status in ("error", "failed"):
        summary_val = str(summary or detail or "Failed")[:50]
        return f"✗ {clean_name}: {summary_val}{step_str}"

    prefix = f"⚡ {clean_name}" if "terminal" in t_name or "command" in t_name or "cli" in t_name else f"⚙️ {clean_name}"

    if detail:
        clean_detail = str(detail).replace("\\", "/")
        if "/" in clean_detail:
            clean_detail = clean_detail.split("/")[-1]
        return f"{prefix}: {clean_detail[:40]}...{step_str}"

    if summary:
        return f"{prefix}: {str(summary)[:45]}...{step_str}"

    return f"{prefix}: {status}...{step_str}"


def split_message_chunks(
    text: str,
    max_chars: Optional[int] = None,
    add_part_headers: bool = True,
    platform: Optional[str] = None
) -> List[str]:
    """
    Omnichannel fence-aware message chunker (Anara Standard).
    Splits long messages along paragraph and newline boundaries without breaking markdown code blocks.
    Balances code fences across chunk boundaries so syntax highlighting never breaks.
    """
    if not text:
        return []

    limit = max_chars
    if limit is None:
        p_norm = (platform or "telegram").strip().lower()
        limit = PLATFORM_MESSAGE_LIMITS.get(p_norm, 2200)

    if len(text) <= limit:
        return [text]

    raw_chunks: List[str] = []
    current_text = text
    effective_limit = limit - 40 if add_part_headers else limit

    while len(current_text) > effective_limit:
        candidate = current_text[:effective_limit]
        code_fence_count = candidate.count("```")
        ends_inside_code = (code_fence_count % 2 == 1)

        split_idx = -1
        p_idx = candidate.rfind("\n\n")
        if p_idx > effective_limit // 3:
            split_idx = p_idx + 2
        else:
            l_idx = candidate.rfind("\n")
            if l_idx > effective_limit // 3:
                split_idx = l_idx + 1
            else:
                s_idx = candidate.rfind(" ")
                if s_idx > effective_limit // 3:
                    split_idx = s_idx + 1
                else:
                    split_idx = effective_limit

        chunk_part = current_text[:split_idx]
        current_text = current_text[split_idx:]

        if ends_inside_code:
            matches = list(re.finditer(r"```([a-zA-Z0-9_-]*)\n", chunk_part))
            last_lang = matches[-1].group(1) if matches else ""
            chunk_part = chunk_part + "\n```"
            current_text = f"```{last_lang}\n" + current_text

        raw_chunks.append(chunk_part)

    if current_text:
        raw_chunks.append(current_text)

    total_parts = len(raw_chunks)
    if total_parts <= 1 or not add_part_headers:
        return raw_chunks

    final_chunks: List[str] = []
    is_discord = (platform == "discord")
    for idx, chunk in enumerate(raw_chunks, start=1):
        if is_discord:
            header = f"📄 **[Part {idx}/{total_parts}]**\n\n"
        elif platform in ("whatsapp", "slack"):
            header = f"📄 *[Part {idx}/{total_parts}]*\n\n"
        elif platform == "cli":
            header = f"[Part {idx}/{total_parts}]\n\n"
        else:
            header = f"📄 <b>[Part {idx}/{total_parts}]</b>\n\n"
        final_chunks.append(header + chunk)

    return final_chunks
