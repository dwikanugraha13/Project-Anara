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
            "message": "Login gateway berhasil.",
        }
    raise HTTPException(status_code=401, detail="Password gateway salah.")


@router.post("/api/gateway/logout")
async def gateway_logout():
    """Logs out from gateway session."""
    return {"status": "success", "message": "Sesi gateway ditutup."}
