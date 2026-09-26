"""
gateway_routes.py — Remote Gateway Authentication, Status & Tunnel Endpoints for Project Anara.
Anara Standard Remote Gateway Endpoints:
1. Validates local vs remote origin requests.
2. Manages Master Password authentication for remote tunnel access.
3. Issues and verifies session tokens.
"""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Request, Response, HTTPException
from pydantic import BaseModel

from core.security import (
    verify_gateway_password,
    generate_gateway_session_token,
    verify_gateway_session_token,
    is_request_local,
)
from config import cfg_get

logger = logging.getLogger("anara.routers.gateway")

router = APIRouter(tags=["gateway"])


class GatewayLoginRequest(BaseModel):
    password: str


@router.get("/api/gateway/status")
async def get_gateway_status(request: Request):
    """Returns the gateway state for client authentication decisions."""
    is_local = is_request_local(request.client.host if request.client else None, dict(request.headers))
    auth_enabled = bool(cfg_get("gateway.auth_enabled", True))

    authenticated = False
    if is_local:
        authenticated = True
    else:
        auth_header = request.headers.get("authorization") or ""
        token = ""
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
        elif request.query_params.get("token"):
            token = request.query_params.get("token", "").strip()

        if token and verify_gateway_session_token(token):
            authenticated = True

    return {
        "status": "ok",
        "is_local": is_local,
        "auth_required": not is_local and auth_enabled,
        "authenticated": authenticated,
        "client_ip": request.client.host if request.client else "unknown",
    }


@router.post("/api/gateway/login")
async def gateway_login(req: GatewayLoginRequest):
    """Authenticates a remote client with the master gateway password."""
    if verify_gateway_password(req.password):
        token = generate_gateway_session_token()
        return {
            "status": "success",
            "token": token,
            "message": "Gateway login successful.",
        }
    raise HTTPException(status_code=401, detail="Incorrect gateway password.")


@router.post("/api/gateway/logout")
async def gateway_logout(request: Request):
    """Logs out and revokes the gateway session token."""
    auth_header = request.headers.get("authorization") or ""
    token = ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    elif request.query_params.get("token"):
        token = request.query_params.get("token", "").strip()

    if token:
        try:
            from memory import memory_engine
            with memory_engine._get_connection() as conn:
                conn.execute("DELETE FROM app_settings WHERE key = ?", (f"gateway_session_{token}",))
                conn.commit()
            logger.info(f"[Gateway] Revoked session token: {token[:8]}...")
        except Exception as e:
            logger.debug(f"[Gateway] Token revocation error: {e}")

    return {"status": "success", "message": "Gateway session closed and token revoked."}


# ── Cloudflare Tunnel Management ──

@router.get("/api/gateway/tunnel")
async def get_gateway_tunnel_endpoint():
    """Returns the live status of the Cloudflare Quick Tunnel."""
    from core.tunnel_manager import get_tunnel_status
    return get_tunnel_status()


@router.post("/api/gateway/tunnel/start")
async def start_gateway_tunnel_endpoint(port: int = 3000):
    """Starts a Cloudflare Quick Tunnel forwarding to local port."""
    from core.tunnel_manager import start_quick_tunnel
    res = await start_quick_tunnel(port=port)
    return res


@router.post("/api/gateway/tunnel/stop")
async def stop_gateway_tunnel_endpoint():
    """Terminates active Cloudflare tunnel."""
    from core.tunnel_manager import stop_tunnel
    ok = stop_tunnel()
    return {"status": "success" if ok else "stopped", "is_running": False}
