"""
client.py — Native Model Context Protocol (MCP) Client for Project Anara.
Anara Enterprise Architecture:
1. Standards-compliant JSON-RPC 2.0 transport over Stdio & HTTP.
2. Safe environment variable inheritance (prevents secret leakage to MCP subprocesses).
3. Secret-redacted error handling and bounded execution timeouts.
4. Auto-reconnection and graceful session teardown.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("anara.integrations.mcp")

# Baseline safe environment variables for stdio subprocesses (Anara Standard)
SAFE_ENV_KEYS = {
    "PATH",
    "HOME",
    "USER",
    "USERNAME",
    "SYSTEMROOT",
    "COMSPEC",
    "WINDIR",
    "TEMP",
    "TMP",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "TERM",
    "SHELL",
    "PYTHONPATH",
    "NODE_PATH",
}


def _filter_safe_env(extra_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Filters host environment variables to prevent accidental API key leaks to untrusted MCP servers."""
    filtered: Dict[str, str] = {}
    for k, v in os.environ.items():
        if k in SAFE_ENV_KEYS or k.startswith("XDG_") or k.startswith("SYSTEM_"):
            filtered[k] = v

    if extra_env:
        for k, v in extra_env.items():
            if v is not None:
                filtered[str(k)] = str(v)

    return filtered


def _sanitize_mcp_output(text: str) -> str:
    """Redacts API keys and credential strings from MCP tool responses or error traces."""
    if not text:
        return ""
    s = str(text)
    # Redact common key patterns
    s = re.sub(r"\bAIza[0-9A-Za-z-_]{35}\b", "AIza[REDACTED]", s)
    s = re.sub(r"\bsk-ant-[a-zA-Z0-9_-]{20,}\b", "sk-ant-[REDACTED]", s)
    s = re.sub(r"\bsk-[a-zA-Z0-9_-]{20,}\b", "sk-[REDACTED]", s)
    s = re.sub(r"\bgh[pousr]_[a-zA-Z0-9]{30,}\b", "ghp_[REDACTED]", s)
    s = re.sub(r"\bgithub_pat_[a-zA-Z0-9_]{50,}\b", "github_pat_[REDACTED]", s)
    s = re.sub(r"(?:Bearer\s+)[a-zA-Z0-9_\-\.]{20,}", "Bearer [REDACTED]", s, flags=re.IGNORECASE)
    s = re.sub(r"((?:key|token|api_key|secret|password)=)[^\s&]+", r"\1[REDACTED]", s, flags=re.IGNORECASE)
    return s


class McpToolSpec:
    """Represents a discovered tool from an MCP server."""

    def __init__(self, name: str, description: str, input_schema: Dict[str, Any], server_name: str):
        self.server_name = server_name
        self.raw_name = name
        # Hermes canonical tool name pattern: mcp_{server_name}_{tool_name}
        clean_srv = re.sub(r"[^a-zA-Z0-9_]", "_", server_name.lower()).strip("_")
        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower()).strip("_")
        self.canonical_name = f"mcp_{clean_srv}_{clean_name}"
        self.description = f"[MCP: {server_name}] {description or name}"
        self.input_schema = input_schema or {"type": "object", "properties": {}}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.canonical_name,
            "raw_name": self.raw_name,
            "server": self.server_name,
            "description": self.description,
            "parameters": self.input_schema,
        }


class McpSession:
    """Manages connection, JSON-RPC 2.0 handshake, and tool execution with an MCP server."""

    def __init__(
        self,
        server_name: str,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        url: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 120.0,
        connect_timeout: float = 30.0,
    ):
        self.server_name = server_name
        self.command = command
        self.args = args or []
        self.url = url
        self.env = env or {}
        self.headers = headers or {}
        self.timeout = float(timeout)
        self.connect_timeout = float(connect_timeout)

        self._process: Optional[asyncio.subprocess.Process] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._tools: Dict[str, McpToolSpec] = {}
        self._request_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._read_task: Optional[asyncio.Task] = None
        self._connected = False
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def tools(self) -> Dict[str, McpToolSpec]:
        return self._tools

    async def connect(self) -> bool:
        """Establishes connection and performs MCP initialize handshake."""
        async with self._lock:
            if self._connected:
                return True

            try:
                if self.url:
                    await self._connect_http()
                elif self.command:
                    await self._connect_stdio()
                else:
                    raise ValueError(f"MCP server '{self.server_name}' must specify either 'command' or 'url'")

                # Handshake
                await self._initialize_handshake()
                await self._discover_tools()
                self._connected = True
                logger.info(f"[MCP] Successfully connected to '{self.server_name}' ({len(self._tools)} tools discovered)")
                return True
            except Exception as e:
                logger.warning(f"[MCP] Failed to connect to server '{self.server_name}': {_sanitize_mcp_output(str(e))}")
                await self.close()
                return False

    async def _connect_stdio(self) -> None:
        """Spawns MCP server subprocess over stdio transport."""
        cmd_path = shutil.which(self.command) or self.command
        full_args = [cmd_path] + self.args
        safe_env = _filter_safe_env(self.env)

        # On Windows, wrap node / npx cmd if necessary
        creationflags = 0
        if sys.platform == "win32":
            creationflags = 0x08000000  # CREATE_NO_WINDOW

        self._process = await asyncio.create_subprocess_exec(
            *full_args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=safe_env,
            creationflags=creationflags,
        )

        self._read_task = asyncio.create_task(self._stdio_read_loop())

        # Background stderr drain prevents 64KB buffer deadlock on Windows/POSIX
        async def _drain_stderr():
            if self._process and self._process.stderr:
                try:
                    while True:
                        err_line = await self._process.stderr.readline()
                        if not err_line:
                            break
                except Exception:
                    pass
        self._stderr_task = asyncio.create_task(_drain_stderr())

    async def _connect_http(self) -> None:
        """Initializes HTTP client for remote MCP server."""
        self._http_client = httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
        )

    async def _stdio_read_loop(self) -> None:
        """Reads JSON-RPC 2.0 messages line-by-line from subprocess stdout."""
        if not self._process or not self._process.stdout:
            return

        while True:
            try:
                line = await self._process.stdout.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue

                try:
                    msg = json.loads(line_str)
                except Exception:
                    continue

                # Match pending request
                msg_id = msg.get("id")
                if msg_id is not None and msg_id in self._pending_requests:
                    fut = self._pending_requests.pop(msg_id)
                    if not fut.done():
                        fut.set_result(msg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[MCP:{self.server_name}] Read loop note: {e}")
                break

    async def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dispatches a JSON-RPC 2.0 request and awaits the corresponding response."""
        self._request_id += 1
        req_id = self._request_id
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }

        if self._http_client and self.url:
            res = await self._http_client.post(self.url, json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"HTTP {res.status_code}: {_sanitize_mcp_output(res.text)}")
            return res.json()

        if self._process and self._process.stdin:
            fut: asyncio.Future = asyncio.get_running_loop().create_future()
            self._pending_requests[req_id] = fut
            try:
                line_bytes = (json.dumps(payload) + "\n").encode("utf-8")
                self._process.stdin.write(line_bytes)
                await self._process.stdin.drain()
                resp = await asyncio.wait_for(fut, timeout=self.timeout)
                return resp
            finally:
                self._pending_requests.pop(req_id, None)

        raise RuntimeError(f"Server '{self.server_name}' transport is not available")

    async def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Sends a JSON-RPC 2.0 notification without waiting for a response."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        if self._http_client and self.url:
            await self._http_client.post(self.url, json=payload)
        elif self._process and self._process.stdin:
            line_bytes = (json.dumps(payload) + "\n").encode("utf-8")
            self._process.stdin.write(line_bytes)
            await self._process.stdin.drain()

    async def _initialize_handshake(self) -> None:
        """Executes standard MCP protocol initialization handshake."""
        init_params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": True},
            },
            "clientInfo": {
                "name": "ProjectAnara",
                "version": "1.0.0",
            },
        }
        res = await asyncio.wait_for(self._send_request("initialize", init_params), timeout=self.connect_timeout)
        if "error" in res:
            raise RuntimeError(f"Initialize error: {res['error']}")

        # Confirm initialization notification
        await self._send_notification("notifications/initialized")

    async def _discover_tools(self) -> None:
        """Queries tools/list and caches discovered tools."""
        res = await asyncio.wait_for(self._send_request("tools/list", {}), timeout=self.connect_timeout)
        if "error" in res:
            raise RuntimeError(f"tools/list error: {res['error']}")

        raw_tools = res.get("result", {}).get("tools", [])
        self._tools.clear()
        for t in raw_tools:
            name = t.get("name")
            desc = t.get("description", "")
            schema = t.get("inputSchema", {})
            if name:
                spec = McpToolSpec(name, desc, schema, self.server_name)
                self._tools[spec.canonical_name] = spec

    async def call_tool(self, tool_raw_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a tool on the MCP server and returns the formatted result."""
        if not self._connected:
            connected = await self.connect()
            if not connected:
                return {"status": "error", "message": f"MCP server '{self.server_name}' is offline"}

        try:
            params = {
                "name": tool_raw_name,
                "arguments": arguments or {},
            }
            res = await asyncio.wait_for(self._send_request("tools/call", params), timeout=self.timeout)
            if "error" in res:
                return {
                    "status": "error",
                    "error": _sanitize_mcp_output(str(res["error"].get("message") or res["error"])),
                }

            result_data = res.get("result", {})
            # Standard MCP tool response content blocks
            content = result_data.get("content", [])
            text_blocks = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_blocks.append(block.get("text", ""))

            output_text = "\n".join(text_blocks) if text_blocks else json.dumps(result_data)
            return {
                "status": "success",
                "result": _sanitize_mcp_output(output_text),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": _sanitize_mcp_output(f"Failed to execute tool on '{self.server_name}': {e}"),
            }

    async def close(self) -> None:
        """Gracefully terminates transport and cleans up background tasks."""
        self._connected = False
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()

        if hasattr(self, "_stderr_task") and self._stderr_task and not self._stderr_task.done():
            self._stderr_task.cancel()

        if self._process:
            try:
                if self._process.stdin:
                    self._process.stdin.close()
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=3.0)
            except Exception:
                try:
                    if sys.platform == "win32":
                        import subprocess
                        subprocess.run(
                            ["taskkill", "/PID", str(self._process.pid), "/F", "/T"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=3
                        )
                    else:
                        self._process.kill()
                except Exception:
                    try:
                        self._process.kill()
                    except Exception:
                        pass
            self._process = None

        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        for fut in self._pending_requests.values():
            if not fut.done():
                fut.cancel()
        self._pending_requests.clear()
