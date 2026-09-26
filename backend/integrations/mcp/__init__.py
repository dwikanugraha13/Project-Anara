"""
MCP Package initialization for Project Anara.
Provides native Model Context Protocol (MCP) server management,
discovery, and tool execution parity with Anara Agent and Claude Code.
"""

from .client import McpSession, McpToolSpec
from .manager import McpServerManager, mcp_manager

__all__ = [
    "McpSession",
    "McpToolSpec",
    "McpServerManager",
    "mcp_manager",
]
