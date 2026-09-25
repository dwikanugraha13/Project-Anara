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
    from core.mcp_client import mcp_client

    act = (action or "list").strip().lower()

    _emit_agent_event("agent_action_start", {
        "tool_name": "mcp_manage",
        "action_title": f"MCP Protocol ({act.upper()})",
        "detail": f"Server: {server_name or 'N/A'}",
        "icon": "cpu"
    })

    if act == "list":
        return mcp_client.list_servers()

    elif act == "add":
        if not server_name:
            return {"status": "error", "message": "Parameter 'server_name' is required."}
        return mcp_client.add_server(
            name=server_name,
            command=command,
            args=args or [],
            url=url
        )

    elif act in ("remove", "delete"):
        if not server_name:
            return {"status": "error", "message": "Parameter 'server_name' is required."}
        ok = mcp_client.remove_server(server_name)
        return {
            "status": "success" if ok else "error",
            "message": f"Server '{server_name}' {'removed successfully.' if ok else 'not found.'}"
        }

    return {"status": "error", "message": f"Unknown action '{act}'. Supported: 'list', 'add', 'remove'."}
