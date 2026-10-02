"""
manager.py — Dynamic MCP Server Manager & Tool Registry Bridge for Project Anara.
Anara Enterprise Architecture:
1. Automated discovery from config.yaml (mcp_servers) and .anara/mcp.json.
2. Idempotent background connection and tool registration into ToolRegistry.
3. First-class invocation parity with built-in tools (read_file, terminal).
4. Graceful shutdown and health diagnostics.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from typing import Any, Callable, Dict, List, Optional, Set

from .client import McpSession, McpToolSpec

logger = logging.getLogger("anara.integrations.mcp")


class McpServerManager:
    """Manages active MCP server sessions and dynamically injects tools into the Anara core."""

    def __init__(self):
        self._servers: Dict[str, McpSession] = {}
        self._lock = threading.RLock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._initialized = False

    def load_mcp_server_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Reads MCP server declarations from:
        1. config.yaml (mcp_servers)
        2. .anara/mcp.json or mcp.json in workspace
        """
        configs: Dict[str, Dict[str, Any]] = {}

        # 1. config.yaml
        try:
            from config import cfg_get
            cfg_servers = cfg_get("mcp_servers") or {}
            if isinstance(cfg_servers, dict):
                for s_name, s_conf in cfg_servers.items():
                    if isinstance(s_conf, dict):
                        configs[s_name] = s_conf
        except Exception as e:
            logger.debug(f"[MCP] Config.yaml inspection note: {e}")

        # 2. Local workspace mcp.json fallback (Anara Enterprise Architecture)
        for check_path in [
            os.path.join(os.getcwd(), ".anara", "mcp.json"),
            os.path.join(os.getcwd(), "mcp.json"),
        ]:
            if os.path.isfile(check_path):
                try:
                    with open(check_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    mcp_block = data.get("mcpServers") or data.get("mcp_servers") or data
                    if isinstance(mcp_block, dict):
                        for s_name, s_conf in mcp_block.items():
                            if isinstance(s_conf, dict) and s_name not in configs:
                                configs[s_name] = s_conf
                except Exception as e:
                    logger.debug(f"[MCP] JSON file read note for {check_path}: {e}")

        return configs

    async def connect_all_servers(self, custom_configs: Optional[Dict[str, Dict[str, Any]]] = None) -> int:
        """Connects to all configured MCP servers and registers their tools."""
        configs = custom_configs if custom_configs is not None else self.load_mcp_server_configs()
        if not configs:
            logger.debug("[MCP] No MCP servers configured.")
            return 0

        connected_count = 0
        from tools.registry import registry

        for s_name, s_conf in configs.items():
            if s_name in self._servers and self._servers[s_name].is_connected:
                continue

            session = McpSession(
                server_name=s_name,
                command=s_conf.get("command"),
                args=s_conf.get("args") or [],
                url=s_conf.get("url"),
                env=s_conf.get("env") or {},
                headers=s_conf.get("headers") or {},
                timeout=float(s_conf.get("timeout", 120.0)),
                connect_timeout=float(s_conf.get("connect_timeout", 30.0)),
            )

            ok = await session.connect()
            if ok:
                with self._lock:
                    self._servers[s_name] = session
                connected_count += 1

                # Inject discovered tools into ToolRegistry
                for tool_name, spec in session.tools.items():
                    self._register_mcp_tool_into_core(registry, session, spec)

        return connected_count

    def _register_mcp_tool_into_core(self, registry: Any, session: McpSession, spec: McpToolSpec) -> None:
        """Bridges an individual MCP tool into the Anara ToolRegistry with async execution handler."""
        raw_tool_name = spec.raw_name

        async def _mcp_handler(**kwargs) -> Dict[str, Any]:
            return await session.call_tool(raw_tool_name, kwargs)

        # Risk classification: inspect schema annotations first, fallback to read-only clues, default mutating
        is_read_only = bool(spec.input_schema.get("readOnly")) if isinstance(spec.input_schema, dict) else False
        if not is_read_only:
            is_read_only = any(kw in spec.raw_name.lower() for kw in ("get", "list", "read", "fetch", "describe", "show", "search"))
        risk = "read_only" if is_read_only else "mutating"

        registry.register_tool(
            name=spec.canonical_name,
            description=spec.description,
            parameters=spec.input_schema,
            handler=_mcp_handler,
            risk=risk,
            toolset="mcp",
            category="connectivity",
            icon="plug",
            enabled_by_default=True,
        )
        logger.debug(f"[MCP] Registered tool '{spec.canonical_name}' into central registry.")

    def get_registered_mcp_tool_names(self) -> Set[str]:
        """Returns the set of all active MCP tool names across connected servers."""
        with self._lock:
            tool_names = set()
            for s in self._servers.values():
                if s.is_connected:
                    tool_names.update(s.tools.keys())
            return tool_names

    def get_status(self) -> Dict[str, Any]:
        """Returns diagnostic status snapshot for all configured and active MCP servers."""
        with self._lock:
            status = {}
            for s_name, session in self._servers.items():
                status[s_name] = {
                    "connected": session.is_connected,
                    "transport": "http" if session.url else "stdio",
                    "tools_count": len(session.tools),
                    "tools": list(session.tools.keys()),
                }
            return status

    async def shutdown(self) -> None:
        """Gracefully disconnects, unregisters tools from ToolRegistry, and reaps all MCP server sessions."""
        from tools.registry import registry
        with self._lock:
            sessions = list(self._servers.values())
            self._servers.clear()

        for s in sessions:
            for tool_spec in s.tools.values():
                try:
                    registry.unregister_tool(tool_spec.canonical_name)
                except Exception:
                    pass
            try:
                await s.close()
            except Exception as e:
                logger.debug(f"[MCP] Error closing server '{s.server_name}': {e}")


# Global singleton instance
mcp_manager = McpServerManager()
