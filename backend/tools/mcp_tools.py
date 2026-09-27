"""
mcp_tools.py — Model Context Protocol Tool Declarations & Dispatch for Project Anara.
"""

from typing import Any, Dict, List, Optional
from .events import _emit_agent_event


async def _tool_mcp_manage(
    action: str,
    server_name: Optional[str] = None,
    command: Optional[str] = None,
    args: Optional[List[str]] = None,
    url: Optional[str] = None
) -> Dict[str, Any]:
    """Manages Model Context Protocol (MCP) servers."""
    from integrations.mcp.manager import mcp_manager

    act = (action or "list").strip().lower()

    _emit_agent_event("agent_action_start", {
        "tool_name": "mcp_manage",
        "action_title": f"MCP Protocol ({act.upper()})",
        "detail": f"Server: {server_name or 'N/A'}",
        "icon": "cpu"
    })

    if act in ("list", "status"):
        return {"status": "success", "servers": mcp_manager.get_status()}

    elif act in ("add", "connect"):
        if not server_name:
            return {"status": "error", "message": "Parameter 'server_name' is required."}
        cfg = {}
        if command:
            cfg["command"] = command
            if args:
                cfg["args"] = args
        elif url:
            cfg["url"] = url
        count = await mcp_manager.connect_all_servers({server_name: cfg})
        return {"status": "success", "connected_count": count, "server": server_name}

    elif act in ("remove", "delete", "disconnect"):
        if not server_name:
            return {"status": "error", "message": "Parameter 'server_name' is required."}
        with mcp_manager._lock:
            session = mcp_manager._servers.pop(server_name, None)
        if session:
            await session.close()
            return {"status": "success", "message": f"Server '{server_name}' disconnected and removed successfully."}
        return {"status": "error", "message": f"Server '{server_name}' not found."}

    return {"status": "error", "message": f"Unknown action '{act}'. Supported: 'list', 'add', 'remove'."}
