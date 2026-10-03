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
    "telegram": 3900,
    "whatsapp": 3500,
    "slack": 3500,
    "cli": 32000,
    "web_studio": 64000,
    "web": 64000,
}


def format_omnichannel_tool_progress(evt: Dict[str, Any]) -> Optional[str]:
    """
    Formats live tool execution lines matching reference gateway standard:
    e.g.
    ```shell
    netstat -ano | grep 3000
    ```
    📖 Reading HomePageClient.tsx L950-1049
    🔍 Searching files for interactionMode
    """
    if not isinstance(evt, dict):
        return None

    t_name = (evt.get("tool_name") or "").strip().lower()
    if not t_name:
        return None

    status = evt.get("status", "running")
    # Only render when tool starts running; NEVER emit redundant "Complete" status lines
    if status not in ("running", "started"):
        return None

    args = evt.get("args") or evt.get("tool_args") or {}
    detail = evt.get("detail") or ""
    summary = evt.get("summary") or ""

    from pathlib import Path

    if t_name in ("execute_cli_command", "terminal", "run_terminal_command"):
        cmd = args.get("command") or detail or summary or ""
        cmd_clean = str(cmd).strip().replace("\r\n", "\n")
        if not cmd_clean:
            return None
        lang = "powershell" if "powershell" in cmd_clean.lower() or "get-" in cmd_clean.lower() else "shell"
        return f"```{lang}\n{cmd_clean}\n```"

    if t_name in ("read_local_file", "read_file"):
        fp = args.get("file_path") or args.get("path") or detail or ""
        fp = str(fp).replace("\\", "/").strip()
        fname = Path(fp).name if fp else "file"
        offset = args.get("offset")
        limit = args.get("limit")
        if offset and limit:
            line_range = f" L{offset}-{int(offset) + int(limit) - 1}"
        elif offset:
            line_range = f" L{offset}"
        else:
            line_range = ""
        return f"📖 Reading {fname}{line_range}"

    if t_name in ("grep_search_code", "search_files"):
        pat = args.get("pattern") or args.get("query") or ""
        p = args.get("path") or detail or ""
        p_clean = str(p).replace("\\", "/").strip()
        p_str = f" in {Path(p_clean).name}" if p_clean and p_clean not in (".", "") else ""
        return f"🔍 Searching files for {pat}{p_str}".strip()

    if t_name in ("glob_find_files", "list_directory"):
        pat = args.get("pattern") or ""
        p = args.get("path") or args.get("directory_path") or detail or ""
        p_clean = str(p).replace("\\", "/").strip()
        p_name = Path(p_clean).name if p_clean and p_clean != "." else p_clean
        if pat:
            return f"📂 Finding files matching {pat}".strip()
        return f"📂 Listing {p_name or '.'}".strip()

    if t_name in ("edit_file", "patch", "write_local_file", "write_file"):
        fp = args.get("file_path") or args.get("path") or detail or ""
        fp = str(fp).replace("\\", "/").strip()
        fname = Path(fp).name if fp else "file"
        return f"✏️ Editing {fname}"

    if t_name == "web_search":
        q = args.get("query") or detail or ""
        return f"🌐 Searching web for {q}"

    if t_name == "fetch_webpage":
        u = args.get("url") or detail or ""
        return f"🌐 Extracting {u}"

    if t_name in ("browser_exec", "browser_code"):
        code = args.get("code") or detail or ""
        first_line = code.strip().splitlines()[0] if code.strip() else ""
        if first_line.startswith("#"):
            label = first_line.lstrip("#").strip()
            return f"🌐 {label[:80]}"
        return "🌐 Executing browser automation"

    if t_name in ("browser_navigate", "browser_open", "browser_goto"):
        u = args.get("url") or detail or ""
        return f"🌐 Browsing {u[:80]}"

    if t_name in ("delegate_task", "spawn_subagent", "subagent"):
        tasks = args.get("tasks") or []
        if isinstance(tasks, list) and len(tasks) > 0:
            first_goal = tasks[0].get("goal") or ""
            goal_snippet = f": {first_goal[:60]}..." if len(first_goal) > 60 else (f": {first_goal}" if first_goal else "")
            return f"👥 Delegating {len(tasks)} subtask{'s' if len(tasks) > 1 else ''}{goal_snippet}"
        return "👥 Delegating subagent workflow"

    if t_name in ("todo_list", "task_scratchpad", "todos"):
        return "📋 Updating task checklist"

    if t_name in ("vision_analyze", "image_analyze"):
        return "👁️ Inspecting visual media"

    if t_name in ("text_to_speech", "voice_synthesize"):
        return "🎙️ Generating voice audio"

    if t_name in ("computer_use", "cua_driver"):
        action = args.get("action") or "action"
        return f"🖥️ Desktop {action}"

    # Default fallback
    target = detail or summary or ""
    if isinstance(target, str) and target.strip():
        clean_target = target.strip().replace("\r\n", " ").replace("\n", " ")
        if len(clean_target) > 75:
            clean_target = clean_target[:72] + "..."
        return f"⚙️ {t_name}: {clean_target}"
    return f"⚙️ {t_name}"


def _format_tool_progress_message(evt: Dict[str, Any]) -> str:
    """Formats an informative, user-friendly live status message for tool execution via dynamic introspection."""
    formatted_line = format_omnichannel_tool_progress(evt)
    if formatted_line:
        return formatted_line

    status = evt.get("status", "running")
    if status == "done":
        # Never produce noisy completion lines in omnichannel
        return ""

    t_name = evt.get("tool_name", "")
    detail = evt.get("detail", "")
    summary = evt.get("summary", "")
    step = evt.get("step")

    step_str = f" [Step {step}]" if step else ""

    if t_name == "agent" and status == "thinking":
        return f"⚙️ Reasoning & planning steps...{step_str}"

    clean_name = t_name.replace("_", " ").title() if t_name else "Action"

    if status in ("error", "failed"):
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


def ensure_closed_code_fences(text: str) -> str:
    """
    Append a closing ``` and/or ` if the text has orphaned code markers.
    Output truncated mid-code-block (finish_reason="length") would otherwise render
    everything after the orphan as one code block / inline span; a spurious close is
    far less harmful. Odd ``` count -> fence on its own line; then, with complete
    ```...``` regions stripped, odd ` count -> a backtick.
    """
    if not isinstance(text, str) or not text:
        return text

    if text.count("```") % 2 == 1:
        text = text.rstrip("\n") + "\n```"

    without_fences = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    without_fences = re.sub(r"```[^`]*$", "", without_fences)

    if without_fences.count("`") % 2 == 1:
        text = text + "`"

    return text


def split_message_chunks(
    text: str,
    max_chars: Optional[int] = None,
    add_part_headers: bool = False,
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

    safe_text = ensure_closed_code_fences(text)
    if len(safe_text) <= limit:
        return [safe_text]

    raw_chunks: List[str] = []
    current_text = safe_text
    effective_limit = limit - 40 if add_part_headers else limit

    while len(current_text) > effective_limit:
        candidate = current_text[:effective_limit]

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
        ends_inside_code = (chunk_part.count("```") % 2 == 1)

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
