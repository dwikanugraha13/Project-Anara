"""
gateway_routes.py — Remote Gateway Authentication, Status & Tunnel Endpoints for Project Anara.
Anara Standard Remote Gateway Endpoints:
1. Validates local vs remote origin requests.
2. Manages Master Password authentication for remote tunnel access.
3. Issues and verifies session tokens.
"""

from __future__ import annotations

import asyncio
import collections
import logging
import re
import threading
import time
from typing import Dict, List, Optional
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

# ── Brute Force Rate Limiting for Remote Login ──
_LOGIN_LOCK = threading.RLock()
_LOGIN_ATTEMPTS: Dict[str, List[float]] = collections.defaultdict(list)
_MAX_LOGIN_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 60.0


def _check_login_rate_limit(client_ip: str):
    """Enforces rate limiting on gateway password login attempts."""
    now = time.time()
    with _LOGIN_LOCK:
        attempts = [t for t in _LOGIN_ATTEMPTS.get(client_ip, []) if (now - t) < _LOGIN_WINDOW_SECONDS]
        _LOGIN_ATTEMPTS[client_ip] = attempts
        if len(attempts) >= _MAX_LOGIN_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail="Too many failed gateway login attempts. Please wait before retrying."
            )


def _record_failed_login(client_ip: str):
    with _LOGIN_LOCK:
        _LOGIN_ATTEMPTS[client_ip].append(time.time())


def _reset_failed_logins(client_ip: str):
    with _LOGIN_LOCK:
        _LOGIN_ATTEMPTS.pop(client_ip, None)


def _require_gateway_access(request: Request) -> bool:
    """
    Enforces that the request is either from local origin or has a valid gateway session token.
    Protects administrative endpoints (tunnel, logout) from unauthenticated remote callers.
    """
    client_host = request.client.host if request.client else None
    headers_dict = dict(request.headers)
    if is_request_local(client_host, headers_dict):
        return True

    auth_enabled = bool(cfg_get("gateway.auth_enabled", True))
    if not auth_enabled:
        return True

    auth_header = request.headers.get("authorization") or ""
    token = ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    elif request.query_params.get("token"):
        token = request.query_params.get("token", "").strip()

    if token and verify_gateway_session_token(token):
        return True

    raise HTTPException(
        status_code=401,
        detail="Unauthorized: Gateway session token required. Login at /api/gateway/login."
    )


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
async def gateway_login(req: GatewayLoginRequest, request: Request):
    """Authenticates a remote client with the master gateway password, protected by rate limiting."""
    client_ip = request.client.host if request.client else "unknown"
    _check_login_rate_limit(client_ip)

    if not req.password or len(req.password) > 256:
        _record_failed_login(client_ip)
        raise HTTPException(status_code=401, detail="Incorrect gateway password.")

    if verify_gateway_password(req.password):
        _reset_failed_logins(client_ip)
        token = generate_gateway_session_token()
        return {
            "status": "success",
            "token": token,
            "message": "Gateway login successful.",
        }

    _record_failed_login(client_ip)
    raise HTTPException(status_code=401, detail="Incorrect gateway password.")


@router.post("/api/gateway/logout")
async def gateway_logout(request: Request):
    """Logs out and revokes the gateway session token via non-blocking worker thread."""
    _require_gateway_access(request)

    auth_header = request.headers.get("authorization") or ""
    token = ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    elif request.query_params.get("token"):
        token = request.query_params.get("token", "").strip()

    if token and re.match(r"^[A-Za-z0-9_\-]{16,128}$", token):
        def _revoke(t: str):
            try:
                from memory import memory_engine
                with memory_engine._get_connection() as conn:
                    conn.execute("DELETE FROM app_settings WHERE key = ?", (f"gateway_session_{t}",))
                    conn.commit()
                logger.info(f"[Gateway] Revoked session token: {t[:8]}...")
            except Exception as e:
                logger.debug(f"[Gateway] Token revocation error: {e}")

        await asyncio.to_thread(_revoke, token)

    return {"status": "success", "message": "Gateway session closed and token revoked."}


# ── Cloudflare Tunnel Management (Authenticated & Non-blocking) ──

@router.get("/api/gateway/tunnel")
async def get_gateway_tunnel_endpoint(request: Request):
    """Returns the live status of the Cloudflare Quick Tunnel (authenticated, non-blocking)."""
    _require_gateway_access(request)
    from core.tunnel_manager import get_tunnel_status
    return await asyncio.to_thread(get_tunnel_status)


@router.post("/api/gateway/tunnel/start")
async def start_gateway_tunnel_endpoint(request: Request, port: int = 3000):
    """Starts a Cloudflare Quick Tunnel forwarding to local port (authenticated)."""
    _require_gateway_access(request)
    if not (1 <= port <= 65535):
        raise HTTPException(status_code=400, detail="Invalid port number. Must be between 1 and 65535.")
    from core.tunnel_manager import start_quick_tunnel
    res = await start_quick_tunnel(port=port)
    return res


@router.post("/api/gateway/tunnel/stop")
async def stop_gateway_tunnel_endpoint(request: Request):
    """Terminates active Cloudflare tunnel (authenticated, non-blocking)."""
    _require_gateway_access(request)
    from core.tunnel_manager import stop_tunnel
    ok = await asyncio.to_thread(stop_tunnel)
    return {"status": "success" if ok else "stopped", "is_running": False}


# ── Approval Mode (Manual / Smart / Off) ─────────────────────────────────────

class ApprovalModeRequest(BaseModel):
    mode: str


@router.get("/api/approvals/mode")
async def get_approval_mode_endpoint():
    """Returns the persistent approval mode (plan, auto, off)."""
    from config import cfg_get
    mode = str(cfg_get("approvals.mode", "auto")).strip().lower()
    if mode in ("smart", "auto"):
        mode = "auto"
    elif mode in ("manual", "plan"):
        mode = "plan"
    elif mode != "off":
        mode = "auto"
    return {"status": "ok", "mode": mode}


@router.post("/api/approvals/mode")
async def set_approval_mode_endpoint(req: ApprovalModeRequest):
    """Sets and persists the approval mode to config.yaml."""
    from config import save_config
    mode = req.mode.strip().lower()
    if mode in ("smart", "auto"):
        normalized = "auto"
    elif mode in ("manual", "plan"):
        normalized = "plan"
    elif mode == "off":
        normalized = "off"
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid approval mode. Must be 'plan', 'auto', or 'off'."
        )
    save_config({"approvals.mode": normalized})
    return {"status": "ok", "mode": normalized}
