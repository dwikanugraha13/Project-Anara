"""
anara_tools.py — Loopback Tool Calling Bridge for Code Execution REPL.
Parity with Oh My Pi (in-cell tool calling) and Hermes Agent (hermes_tools).
Allows scripts executed inside `execute_code` to call agent tools programmatically
without leaving the execution cell or causing token context bloat.
"""

import asyncio
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Union


def _run_async(coro):
    """Safely runs an async coroutine from synchronous code."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def read_file(path: str, offset: Optional[int] = None, limit: Optional[int] = None) -> Dict[str, Any]:
    """Reads a file with line numbers and pagination."""
    from tools.fs_tools import _tool_read_local_file
    res = _run_async(_tool_read_local_file(file_path=path, offset=offset, limit=limit))
    return res


def write_file(path: str, content: str, overwrite: bool = True) -> Dict[str, Any]:
    """Overwrites or creates a file directly in the active workspace."""
    from tools.fs_tools import _tool_write_local_file
    res = _run_async(_tool_write_local_file(file_path=path, content=content, overwrite=overwrite))
    return res


def edit_file(path: str, old_string: Optional[str] = None, new_string: Optional[str] = None, replace_all: bool = False, patch: Optional[str] = None) -> Dict[str, Any]:
    """Edits a file via Hashline line-anchored engine or fuzzy replacement."""
    from tools.fs_tools import _tool_edit_file
    res = _run_async(_tool_edit_file(file_path=path, old_string=old_string, new_string=new_string, replace_all=replace_all, patch=patch))
    return res


def search_files(pattern: str, target: str = "content", path: Optional[str] = None, include: Optional[str] = None) -> Dict[str, Any]:
    """Searches file content (regex grep) or finds files by name pattern (glob)."""
    if target == "files":
        from tools.fs_tools import _tool_glob_find_files
        res = _run_async(_tool_glob_find_files(pattern=pattern, path=path))
    else:
        from tools.fs_tools import _tool_grep_search_code
        res = _run_async(_tool_grep_search_code(pattern=pattern, path=path, include=include))
    return res


def terminal(command: str, workdir: Optional[str] = None) -> Dict[str, Any]:
    """Executes a shell command and returns output and exit code."""
    from tools.system_tools import _tool_execute_cli_command
    res = _run_async(_tool_execute_cli_command(command=command, workdir=workdir))
    return res


def web_search(query: str) -> Dict[str, Any]:
    """Searches live web and academic sources (arXiv, OpenAlex, Wikipedia)."""
    from tools.web_tools import _tool_web_search
    res = _run_async(_tool_web_search(query=query))
    return res


def json_parse(text: str) -> Any:
    """Tolerant JSON parser."""
    clean = text.strip()
    if clean.startswith("```"):
        lines = clean.splitlines()
        clean = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(clean)


def delegate_task(
    tasks: Optional[Union[List[Dict[str, Any]], str]] = None,
    goal: Optional[str] = None,
    context: Optional[str] = None,
    action: Optional[str] = None,
    subagent_id: Optional[str] = None,
    message: Optional[str] = None,
    output_schema: Optional[Dict[str, Any]] = None,
    images: Optional[List[str]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Spawns child subagents (or controls them) programmatically from code execution REPL (Anara Standard).
    Enforces child safety barriers: child subagents cannot recursively delegate.
    """
    from core.subagent import is_delegated_child_context, subagent_manager
    if is_delegated_child_context():
        raise PermissionError("Child subagent is prohibited from calling delegate_task (recursive delegation safety barrier).")
    return _run_async(subagent_manager.handle_delegate_call(
        tasks=tasks,
        goal=goal,
        context=context,
        action=action,
        subagent_id=subagent_id,
        message=message,
        output_schema=output_schema,
        images=images,
        **kwargs,
    ))
