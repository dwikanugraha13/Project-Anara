"""
process_tools.py — Persistent Background Process Management Tool for Project Anara.
Allows the agent and user to manage long-running daemon processes (e.g. dev servers,
background scripts, watchers) with real-time log tailing.
"""

import logging
from typing import Any, Dict, List, Optional

from .events import _emit_agent_event

logger = logging.getLogger(__name__)


async def _tool_process_manage(
    action: str = "list",
    command: Optional[str] = None,
    process_id: Optional[str] = None,
    cwd: Optional[str] = None,
    lines: int = 50
) -> Dict[str, Any]:
    """
    Manages long-running background daemon processes (Anara Standard compatible process_manage).
    action: 'start' (run new background process), 'list' (view all processes), 'logs' (tail stdout), 'stop' (kill process).
    command: shell command to execute in background (for 'start').
    process_id: identifier of the process (e.g. 'vite_dev', 'api_server').
    cwd: directory to run the process in (optional).
    lines: number of recent log lines to retrieve (default 50).
    """
    from core.process_registry import process_registry

    act = (action or "list").strip().lower()

    _emit_agent_event("agent_action_start", {
        "tool_name": "process_manage",
        "action_title": f"Process Manager ({act.upper()})",
        "detail": f"{process_id or command or 'All processes'}",
        "icon": "activity"
    })

    if act == "start":
        if not command:
            return {"status": "error", "message": "Parameter 'command' is required to start a process."}
        return process_registry.start_process(command=command, cwd=cwd, process_id=process_id)

    elif act == "list":
        procs = process_registry.list_processes()
        return {
            "status": "success",
            "total_processes": len(procs),
            "processes": procs
        }

    elif act in ("logs", "tail", "output"):
        if not process_id:
            return {"status": "error", "message": "Parameter 'process_id' is required to inspect process logs."}
        return process_registry.get_logs(process_id=process_id, lines=lines)

    elif act in ("stop", "kill", "terminate"):
        if not process_id:
            return {"status": "error", "message": "Parameter 'process_id' is required to stop a process."}
        return process_registry.stop_process(process_id=process_id)

    return {"status": "error", "message": f"Unknown process action '{act}'. Use: 'start', 'list', 'logs', 'stop'."}
