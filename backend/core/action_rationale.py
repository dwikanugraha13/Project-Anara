"""
action_rationale.py — Model-Driven Action Rationale & Channel Status Synthesizer for Project Anara.
Queries fast auxiliary models to formulate natural, contextual 1-sentence explanations
of tool invocations and channel execution notices with zero canned templates.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("anara.action_rationale")


async def synthesize_action_rationale(tool_name: str, tool_args: Dict[str, Any], prompt: str = "") -> str:
    """
    Pure Model-Driven Rationale Synthesis (Anara Standard).
    Queries the fast auxiliary model (e.g. gemini-3.1-flash / < 400ms) to formulate a natural,
    contextual 1-sentence conversational explanation of WHY this tool is being invoked for this prompt.
    Eliminates hardcoded if-else dictionaries and regexes.
    """
    from providers import call_universal_chat_model
    from core.capabilities import get_fast_auxiliary_model
    from core.prompt_loader import load_prompt

    args_summary = ", ".join(f"{k}={v}" for k, v in list(tool_args.items())[:3])
    sys_instruction = load_prompt("channel/action_rationale")
    user_p = (
        f"User request context: \"{prompt or 'Fulfill user task'}\"\n"
        f"Tool action being invoked: '{tool_name}' ({args_summary})\n"
        "Brief conversational rationale (1 friendly sentence):"
    )

    try:
        model_id = get_fast_auxiliary_model()
        res = await asyncio.wait_for(
            call_universal_chat_model(
                model_id=model_id,
                user_prompt=user_p,
                system_instruction=sys_instruction,
                max_tokens=None,
                temperature=0.3,
                read_only=True,
            ),
            timeout=3.5
        )
        if isinstance(res, str) and res.strip():
            clean = res.strip().strip('"\'`')
            # Anti-leak gate on synthesized output
            if "{" not in clean and "<" not in clean and len(clean) > 8:
                return clean
    except Exception as e:
        logger.debug(f"[RationaleSynthesis] Fast LLM pass notice: {e}")

    # Fallback to dynamic parameter-grounded rationale if LLM is unreachable offline
    return generate_dynamic_action_rationale(tool_name, tool_args, prompt)


def generate_dynamic_action_rationale(tool_name: str, tool_args: Dict[str, Any], prompt: str = "") -> str:
    """
    Factual parameter-grounded action summary (Anara build_tool_preview parity).
    Clean, direct, and zero robotic canned templates.
    """
    t_clean = (tool_name or "tool").strip().lower()
    canonical = t_clean.replace("_", " ")

    # Dynamic target parameter discovery
    target_info = (
        tool_args.get("command")
        or tool_args.get("file_path")
        or tool_args.get("path")
        or tool_args.get("target")
        or tool_args.get("title")
        or tool_args.get("query")
        or tool_args.get("source_dir")
        or tool_args.get("task")
        or ""
    )
    clean_target = str(target_info).strip()

    # For CLI commands: format clean one-liner target
    if t_clean in ("execute_cli_command", "terminal", "run_terminal_command"):
        if "\n" in clean_target:
            clean_target = clean_target.splitlines()[0].strip()
        clean_target = clean_target.strip("`;| ")
        if clean_target:
            return f"Run: {clean_target[:100]}"
        clean_p = (prompt or "").strip()
        if clean_p:
            return f"Run terminal command: {clean_p[:80]}"
        return "Run terminal command"

    # For file, media, search, and other tools: clean parameter preview
    if clean_target:
        if "/" in clean_target or "\\" in clean_target:
            clean_display = clean_target.replace("\\", "/").split("/")[-1]
        else:
            clean_display = clean_target
        return f"{canonical.capitalize()}: {clean_display[:80]}"

    clean_p = (prompt or "").strip()
    return f"{canonical.capitalize()}: {clean_p[:80]}" if clean_p else canonical.capitalize()


async def synthesize_channel_notice(
    notice_type: str,
    channel: str = "telegram",
    task_description: str = "",
    error_detail: str = "",
    user_id: str = "",
) -> str:
    """
    Pure Model-Driven Channel Notice Synthesizer (Anara Standard).
    Generates contextual, platform-tailored, zero-canned conversational notices
    (e.g., expiry, rejection, authorization denial, cancellation, or runtime failure)
    using the fast auxiliary model with graceful dynamic fallbacks.
    """
    from providers import call_universal_chat_model
    from core.capabilities import get_fast_auxiliary_model
    from core.prompt_loader import load_prompt

    sys_inst = load_prompt(
        "channel/channel_notice",
        default=(
            "You are Anara delivering a concise 1-sentence channel status notice to the user.\n"
            "If status is 'rejected' or 'cancelled', clearly state that the action has been cancelled as requested (use words like 'dibatalkan', 'batal', or 'cancelled').\n"
            "If status is 'expired', clearly state that the action has expired (use words like 'kedaluwarsa' or 'expired').\n"
            "Match the language of the task context and keep it to 1 short sentence."
        ),
    )
    user_prompt = (
        f"Channel: {channel}\n"
        f"Status: {notice_type}\n"
        f"Task context: {task_description or 'System task'}\n"
        f"Additional detail: {error_detail or 'None'}\n"
        "Brief friendly notice (1 sentence):"
    )
    try:
        model_id = get_fast_auxiliary_model()
        res = await asyncio.wait_for(
            call_universal_chat_model(
                model_id=model_id,
                user_prompt=user_prompt,
                system_instruction=sys_inst,
                max_tokens=None,
                temperature=0.3,
                read_only=True,
            ),
            timeout=3.0
        )
        if isinstance(res, str) and res.strip():
            clean = res.strip().strip('"\'`')
            if "{" not in clean and "<tool" not in clean and len(clean) > 5:
                return clean
    except Exception as e:
        logger.debug(f"[ChannelNotice] Auxiliary synthesis notice: {e}")

    # Universal fallbacks formatted dynamically based on situation (Anara Standard)
    task_info = f" '{task_description}'" if task_description else ""
    err_info = f": {error_detail}" if error_detail else ""
    if notice_type == "expired":
        return f"Action plan{task_info} expired."
    elif notice_type == "rejected":
        return f"Action{task_info} was cancelled."
    elif notice_type == "unauthorized":
        return f"Authorization required for action{task_info}."
    elif notice_type == "stopped":
        return f"Execution{task_info} has been stopped."
    elif notice_type == "error":
        return f"Execution failed{task_info}{err_info}."
    return f"Status: {notice_type}{task_info}."
