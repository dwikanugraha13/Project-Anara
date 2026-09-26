"""
gateway_manager.py — Compatibility alias forwarding to core.tunnel_manager.
Maintains backward compatibility across all CLI, daemon, and gateway consumers
following Anara Agent and Claude Code process supervision standards.
"""
from core.tunnel_manager import (
    get_cloudflared_path,
    ensure_cloudflared_installed,
    get_tunnel_status,
    stop_tunnel,
    start_quick_tunnel,
    is_local_port_open,
    verify_cloudflared_binary,
    CLOUDFLARE_WINDOWS_URL,
    TUNNEL_LIFECYCLE_FILE,
    TUNNEL_PID_FILE,
)

__all__ = [
    "get_cloudflared_path",
    "ensure_cloudflared_installed",
    "get_tunnel_status",
    "stop_tunnel",
    "start_quick_tunnel",
    "is_local_port_open",
    "verify_cloudflared_binary",
    "CLOUDFLARE_WINDOWS_URL",
    "TUNNEL_LIFECYCLE_FILE",
    "TUNNEL_PID_FILE",
]
