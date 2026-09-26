"""
test_pillar1_native_mcp.py — Comprehensive verification test suite for Pillar 1: Native MCP Client.
Anara Engineering Standards:
1. Environment isolation & credential scrubbing.
2. JSON-RPC 2.0 protocol handshake (initialize, tools/list, tools/call).
3. Canonical tool naming convention: mcp_{server}_{tool}.
4. Dynamic registration into ToolRegistry and automatic injection into PlatformToolRegistry.
5. End-to-end execution dispatch.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch

from integrations.mcp.client import (
    McpSession,
    McpToolSpec,
    _filter_safe_env,
    _sanitize_mcp_output,
)
from integrations.mcp.manager import McpServerManager
from tools.registry import registry
from tools.toolsets import PlatformToolRegistry


def test_mcp_safe_env_filtering():
    """Verifies that host secrets are stripped from subprocess env unless explicitly declared."""
    dummy_key = "s" + "k-test-proj-000000000000"
    dummy_gh = "g" + "hp_test_pat_token_0000000000"
    with patch.dict("os.environ", {
        "PATH": "/usr/bin;C:\\Windows",
        "SECRET_API_KEY": dummy_key,
        "GITHUB_TOKEN": dummy_gh,
        "USER": "TestUser",
    }):
        # Without explicit env
        safe = _filter_safe_env()
        assert "PATH" in safe
        assert "USER" in safe
        assert "SECRET_API_KEY" not in safe
        assert "GITHUB_TOKEN" not in safe

        # With explicit server env (opt-in)
        safe_with_explicit = _filter_safe_env({"TARGET_DB_URL": "postgres://localhost/db"})
        assert safe_with_explicit.get("TARGET_DB_URL") == "postgres://localhost/db"
        assert "SECRET_API_KEY" not in safe_with_explicit


def test_mcp_output_sanitization():
    """Verifies that API keys and credential strings are redacted from MCP output."""
    raw_key = "s" + "k-" + "proj-1234567890abcdef"
    raw_gh = "g" + "hp_" + "1234567890abcdef1234567890abcdef"
    raw = f"Connected using {raw_key} and {raw_gh}."
    clean = _sanitize_mcp_output(raw)
    assert "sk-[REDACTED]" in clean
    assert "ghp_[REDACTED]" in clean
    assert raw_key not in clean
    assert raw_gh not in clean


def test_mcp_tool_spec_canonical_naming():
    """Verifies standard canonical naming convention: mcp_{server}_{tool}."""
    spec1 = McpToolSpec("read_file", "Reads file from disk", {"type": "object"}, "filesystem")
    assert spec1.canonical_name == "mcp_filesystem_read_file"
    assert "[MCP: filesystem]" in spec1.description

    spec2 = McpToolSpec("list-issues", "Lists github issues", {}, "github-server")
    assert spec2.canonical_name == "mcp_github_server_list_issues"


def test_mcp_session_handshake_and_dispatch():
    """Simulates JSON-RPC 2.0 handshake and verifies end-to-end tool execution."""
    async def _run():
        session = McpSession(server_name="test_time", url="http://mock-mcp-server/v1")

        # Mock JSON-RPC responses for initialize, tools/list, and tools/call
        async def mock_post(url, json=None, **kwargs):
            method = json.get("method")
            req_id = json.get("id")

            class MockResponse:
                status_code = 200
                def __init__(self, d):
                    self._d = d
                    self.text = ""
                def json(self):
                    return self._d

            if method == "initialize":
                return MockResponse({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "mock-time-server", "version": "1.0.0"}
                    }
                })
            elif method == "notifications/initialized":
                return MockResponse({"jsonrpc": "2.0"})
            elif method == "tools/list":
                return MockResponse({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": [
                            {
                                "name": "get_current_time",
                                "description": "Returns current UTC timestamp",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"timezone": {"type": "string"}},
                                }
                            }
                        ]
                    }
                })
            elif method == "tools/call":
                return MockResponse({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": "2026-09-27T04:45:00Z"}
                        ]
                    }
                })
            return MockResponse({"jsonrpc": "2.0", "id": req_id, "error": {"message": "Unknown method"}})

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            # 1. Connect and initialize
            ok = await session.connect()
            assert ok is True
            assert session.is_connected is True
            assert "mcp_test_time_get_current_time" in session.tools

            # 2. Call tool directly
            res = await session.call_tool("get_current_time", {"timezone": "UTC"})
            assert res["status"] == "success"
            assert "2026-09-27T04:45:00Z" in res["result"]

            await session.close()

    asyncio.run(_run())


def test_mcp_manager_integration_with_tool_registry():
    """Verifies that McpServerManager registers MCP tools into Anara's ToolRegistry and PlatformToolRegistry."""
    async def _run():
        mgr = McpServerManager()

        custom_configs = {
            "mock_db": {
                "url": "http://mock-db-server/mcp",
                "timeout": 10.0,
            }
        }

        async def mock_post(url, json=None, **kwargs):
            method = json.get("method")
            req_id = json.get("id")

            class MockResponse:
                status_code = 200
                def __init__(self, d):
                    self._d = d
                    self.text = ""
                def json(self):
                    return self._d

            if method == "initialize":
                return MockResponse({"jsonrpc": "2.0", "id": req_id, "result": {}})
            elif method == "notifications/initialized":
                return MockResponse({"jsonrpc": "2.0"})
            elif method == "tools/list":
                return MockResponse({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": [
                            {
                                "name": "query_records",
                                "description": "Executes SQL query on database",
                                "inputSchema": {"type": "object", "properties": {"sql": {"type": "string"}}},
                            }
                        ]
                    }
                })
            elif method == "tools/call":
                return MockResponse({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": "Row count: 42"}]}
                })
            return MockResponse({})

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            count = await mgr.connect_all_servers(custom_configs=custom_configs)
            assert count == 1

            canonical_name = "mcp_mock_db_query_records"
            assert canonical_name in mgr.get_registered_mcp_tool_names()

            # Check ToolRegistry has it
            tool_def = registry.get_tool(canonical_name)
            assert tool_def is not None
            assert "[MCP: mock_db]" in tool_def.description

            # Check PlatformToolRegistry auto-injects it
            with patch("integrations.mcp.mcp_manager", mgr):
                platform_tools = PlatformToolRegistry.get_tools_for_platform("telegram")
                assert canonical_name in platform_tools

                # Dispatch execution through central ToolRegistry
                res = await registry.dispatch(canonical_name, {"sql": "SELECT COUNT(*) FROM users;"})
                assert res.get("status") == "success"
                assert "Row count: 42" in res.get("result", "")

            await mgr.shutdown()

    asyncio.run(_run())
