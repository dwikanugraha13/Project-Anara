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
                    mcp_block = None
                    if isinstance(data, dict):
                        if "mcpServers" in data and isinstance(data["mcpServers"], dict):
                            mcp_block = data["mcpServers"]
                        elif "mcp_servers" in data and isinstance(data["mcp_servers"], dict):
                            mcp_block = data["mcp_servers"]
                        else:
                            mcp_block = data
                    if isinstance(mcp_block, dict):
                        for s_name, s_conf in mcp_block.items():
                            if s_name in ("mcpServers", "mcp_servers"):
                                continue
                            if isinstance(s_conf, dict) and s_name not in configs:
                                configs[s_name] = s_conf
                except Exception as e:
                    logger.debug(f"[MCP] JSON file read note for {check_path}: {e}")

        # 3. SQLite app_settings custom servers
        try:
            from memory import memory_engine
            raw = memory_engine.get_app_setting("mcp_servers_custom")
            if raw:
                custom_configs = json.loads(raw)
                if isinstance(custom_configs, dict):
                    if "mcpServers" in custom_configs and isinstance(custom_configs["mcpServers"], dict):
                        custom_configs = custom_configs["mcpServers"]
                    elif "mcp_servers" in custom_configs and isinstance(custom_configs["mcp_servers"], dict):
                        custom_configs = custom_configs["mcp_servers"]
                    for s_name, s_conf in custom_configs.items():
                        if s_name in ("mcpServers", "mcp_servers"):
                            continue
                        if isinstance(s_conf, dict) and s_name not in configs:
                            configs[s_name] = s_conf
        except Exception as e:
            logger.debug(f"[MCP] SQLite custom configs read note: {e}")

        return configs

    def get_disabled_servers(self) -> Set[str]:
        """Returns set of servers explicitly disabled by the user."""
        try:
            from memory import memory_engine
            raw = memory_engine.get_app_setting("mcp_servers_disabled")
            if raw:
                data = json.loads(raw)
                if isinstance(data, list):
                    return set(data)
                elif isinstance(data, dict):
                    return {k for k, v in data.items() if not v}
        except Exception:
            pass
        return set()

    def set_server_enabled(self, name: str, enabled: bool) -> None:
        """Sets server enabled or disabled flag."""
        try:
            from memory import memory_engine
            raw = memory_engine.get_app_setting("mcp_servers_disabled")
            disabled_set: Set[str] = set()
            if raw:
                data = json.loads(raw)
                if isinstance(data, list):
                    disabled_set = set(data)
                elif isinstance(data, dict):
                    disabled_set = {k for k, v in data.items() if not v}
            if enabled:
                disabled_set.discard(name)
            else:
                disabled_set.add(name)
            memory_engine.set_app_setting("mcp_servers_disabled", json.dumps(list(disabled_set)))
        except Exception as e:
            logger.debug(f"[MCP] Error persisting disabled state: {e}")

    def save_mcp_server_config(self, name: str, config: Dict[str, Any]) -> None:
        """Persists custom MCP server configuration to SQLite app_settings and .anara/mcp.json."""
        from memory import memory_engine
        raw = memory_engine.get_app_setting("mcp_servers_custom")
        custom_configs: Dict[str, Any] = {}
        if raw:
            try:
                custom_configs = json.loads(raw)
            except Exception:
                custom_configs = {}
        custom_configs[name] = config
        memory_engine.set_app_setting("mcp_servers_custom", json.dumps(custom_configs))

        try:
            anara_dir = os.path.join(os.getcwd(), ".anara")
            os.makedirs(anara_dir, exist_ok=True)
            mcp_file = os.path.join(anara_dir, "mcp.json")
            existing_data: Dict[str, Any] = {}
            if os.path.isfile(mcp_file):
                try:
                    with open(mcp_file, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)
                except Exception:
                    existing_data = {}
            mcp_block = existing_data.get("mcpServers") or existing_data.get("mcp_servers") or existing_data
            if not isinstance(mcp_block, dict):
                mcp_block = {}
            mcp_block[name] = config
            existing_data["mcpServers"] = mcp_block
            with open(mcp_file, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, indent=2)
        except Exception as e:
            logger.debug(f"[MCP] Error writing .anara/mcp.json: {e}")

    def delete_mcp_server_config(self, name: str) -> None:
        """Deletes custom MCP server configuration from SQLite and .anara/mcp.json."""
        from memory import memory_engine
        raw = memory_engine.get_app_setting("mcp_servers_custom")
        if raw:
            try:
                custom_configs = json.loads(raw)
                if name in custom_configs:
                    del custom_configs[name]
                    memory_engine.set_app_setting("mcp_servers_custom", json.dumps(custom_configs))
            except Exception:
                pass

        try:
            mcp_file = os.path.join(os.getcwd(), ".anara", "mcp.json")
            if os.path.isfile(mcp_file):
                with open(mcp_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                mcp_block = existing_data.get("mcpServers") or existing_data.get("mcp_servers") or existing_data
                if isinstance(mcp_block, dict) and name in mcp_block:
                    del mcp_block[name]
                    existing_data["mcpServers"] = mcp_block
                    with open(mcp_file, "w", encoding="utf-8") as f:
                        json.dump(existing_data, f, indent=2)
        except Exception as e:
            logger.debug(f"[MCP] Error updating .anara/mcp.json: {e}")

    def get_raw_mcp_json(self) -> str:
        """Returns the raw mcp.json string from disk or memory."""
        for check_path in [
            os.path.join(os.getcwd(), ".anara", "mcp.json"),
            os.path.join(os.getcwd(), "mcp.json"),
        ]:
            if os.path.isfile(check_path):
                try:
                    with open(check_path, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception:
                    pass
        # Fallback: construct from existing configs
        configs = self.load_mcp_server_configs()
        return json.dumps({"mcpServers": configs}, indent=2)

    async def save_raw_mcp_json(self, raw_text: str) -> Dict[str, Any]:
        """Validates and persists raw mcp.json content."""
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            raise ValueError("mcp.json root must be a JSON object.")

        mcp_servers = data.get("mcpServers") or data.get("mcp_servers") or data
        if not isinstance(mcp_servers, dict):
            raise ValueError("mcpServers must be an object/dictionary.")

        anara_dir = os.path.join(os.getcwd(), ".anara")
        os.makedirs(anara_dir, exist_ok=True)
        mcp_file = os.path.join(anara_dir, "mcp.json")
        with open(mcp_file, "w", encoding="utf-8") as f:
            f.write(raw_text)

        from memory import memory_engine
        memory_engine.set_app_setting("mcp_servers_custom", json.dumps(mcp_servers))
        return mcp_servers

    async def connect_server(self, s_name: str, custom_config: Optional[Dict[str, Any]] = None) -> bool:
        """Connects a single MCP server by name."""
        if s_name in self._servers and self._servers[s_name].is_connected:
            await self.disconnect_server(s_name)

        configs = self.load_mcp_server_configs()
        s_conf = custom_config or configs.get(s_name)
        if not s_conf:
            logger.warning(f"[MCP] Configuration for server '{s_name}' not found.")
            return False

        from tools.registry import registry
        session = McpSession(
            server_name=s_name,
            command=s_conf.get("command"),
            args=s_conf.get("args") or [],
            url=s_conf.get("url"),
            env=s_conf.get("env") or {},
            headers=s_conf.get("headers") or {},
            cwd=s_conf.get("cwd"),
            timeout=float(s_conf.get("timeout", 120.0)),
            connect_timeout=float(s_conf.get("connect_timeout", 30.0)),
        )

        ok = await session.connect()
        if ok:
            with self._lock:
                self._servers[s_name] = session
            for tool_name, spec in session.tools.items():
                self._register_mcp_tool_into_core(registry, session, spec)
            logger.info(f"[MCP] Successfully connected server '{s_name}' with {len(session.tools)} tools.")
            return True
        else:
            logger.warning(f"[MCP] Failed to connect server '{s_name}'.")
            return False

    async def disconnect_server(self, s_name: str) -> bool:
        """Disconnects a single MCP server and unregisters its tools."""
        from tools.registry import registry
        with self._lock:
            session = self._servers.pop(s_name, None)

        if not session:
            return False

        for tool_spec in session.tools.values():
            try:
                registry.unregister_tool(tool_spec.canonical_name)
            except Exception:
                pass
        try:
            await session.close()
        except Exception as e:
            logger.debug(f"[MCP] Error closing server '{s_name}': {e}")
        return True

    async def add_server(self, name: str, config: Dict[str, Any], auto_connect: bool = True) -> bool:
        """Adds a new MCP server configuration and optionally connects it immediately."""
        self.save_mcp_server_config(name, config)
        self.set_server_enabled(name, True)
        if auto_connect:
            return await self.connect_server(name, config)
        return True

    async def remove_server(self, name: str) -> bool:
        """Removes an MCP server configuration and disconnects it."""
        await self.disconnect_server(name)
        self.delete_mcp_server_config(name)
        self.set_server_enabled(name, True)
        return True

    async def toggle_server(self, name: str, enabled: Optional[bool] = None) -> bool:
        """Toggles server enabled state. Disconnects if disabled, connects if enabled."""
        disabled = self.get_disabled_servers()
        current_enabled = name not in disabled
        new_enabled = (not current_enabled) if enabled is None else bool(enabled)
        self.set_server_enabled(name, new_enabled)
        if new_enabled:
            await self.connect_server(name)
        else:
            await self.disconnect_server(name)
        return new_enabled

    async def connect_all_servers(self, custom_configs: Optional[Dict[str, Dict[str, Any]]] = None) -> int:
        """Connects to all configured MCP servers and registers their tools."""
        configs = custom_configs if custom_configs is not None else self.load_mcp_server_configs()
        if not configs:
            logger.debug("[MCP] No MCP servers configured.")
            return 0

        disabled = self.get_disabled_servers()
        connected_count = 0
        from tools.registry import registry

        for s_name, s_conf in configs.items():
            if s_name in disabled:
                continue
            if s_name in self._servers and self._servers[s_name].is_connected:
                continue

            session = McpSession(
                server_name=s_name,
                command=s_conf.get("command"),
                args=s_conf.get("args") or [],
                url=s_conf.get("url"),
                env=s_conf.get("env") or {},
                headers=s_conf.get("headers") or {},
                cwd=s_conf.get("cwd"),
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
        configs = self.load_mcp_server_configs()
        disabled = self.get_disabled_servers()
        with self._lock:
            status = {}
            for s_name, cfg in configs.items():
                session = self._servers.get(s_name)
                is_connected = session.is_connected if session else False
                status[s_name] = {
                    "connected": is_connected,
                    "enabled": s_name not in disabled,
                    "transport": "http" if cfg.get("url") else "stdio",
                    "tools_count": len(session.tools) if (session and is_connected) else 0,
                    "tools": list(session.tools.keys()) if (session and is_connected) else [],
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
