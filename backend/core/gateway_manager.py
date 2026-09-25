"""
gateway_manager.py — Compatibility alias forwarding to core.tunnel_manager.
Maintains backward compatibility across all CLI, daemon, and gateway consumers.
"""
from core.tunnel_manager import (
    get_cloudflared_path,
    ensure_cloudflared_installed,
    get_tunnel_status,
    stop_tunnel,
    start_quick_tunnel,
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
    "CLOUDFLARE_WINDOWS_URL",
    "TUNNEL_LIFECYCLE_FILE",
    "TUNNEL_PID_FILE",
]
