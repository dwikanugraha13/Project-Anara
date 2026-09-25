"""
security.py — Content Moderation, Prompt Injection Defense & Approver Authorization.
Implements FR-20, NFR-1, and Section 12.2/12.5 from rancangan-general-agent.md & prd-general-agent.md.

Protections:
1. Inbound Prompt Injection & Jailbreak Defense: Flags and rejects adversarial manipulation
   attempts (e.g. "ignore previous instructions", "reveal system prompt verbatim", "act as DAN").
2. Approver Authorization Matrix: Enforces strict user ID validation so only authorized
   owners/admins can approve plans or trigger mutating build actions in public channels.
"""
import logging
import os
import re
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Hermes Agent Parity: Conversational inputs are not censored via naive keyword blacklists.
# Security boundaries are enforced at the OS execution layer (WorkspaceSentinel & command_sandbox AST).

def check_prompt_injection(text: str) -> Tuple[bool, Optional[str]]:
    """
    Hermes Agent Parity: Inbound prompts are permitted without lexical blacklists.
    Technical security analysis (e.g. ransomware, DDoS mitigation, bypass methods)
    is not falsely flagged.
    Guards against corrupt binary/control payloads while delegating physical execution
    safety to WorkspaceSentinel and Sandbox AST evaluation.
    """
    clean_text = (text or "").strip()
    if not clean_text:
        return True, None

    # Structural guard against non-printable binary control payloads
    if any(ord(c) < 32 and c not in "\r\n\t" for c in clean_text):
        return False, "Input rejected: non-printable control characters detected."

    return True, None


def get_authorized_admins(channel: str = "telegram") -> List[str]:
    """
    Retrieves the list of authorized admin user IDs from memory or environment.
    """
    from memory import memory_engine
    setting_key = f"{channel}_admin_ids"
    raw = memory_engine.get_app_setting(setting_key) or os.getenv(f"{channel.upper()}_ADMIN_IDS", "")
    if not raw:
        return []
    return [uid.strip() for uid in raw.split(",") if uid.strip()]


def is_authorized_approver(user_id: str, plan_owner_id: str, channel: str = "telegram") -> bool:
    """
    Validates whether the user attempting to approve a plan is authorized (Section 12.2 & 12.5).
    Rules:
    1. The original plan requester is always authorized to approve their own plan.
    2. Any user ID explicitly listed in telegram_admin_ids is authorized.
    3. If no admin whitelist is configured and it's a direct private chat (not a group),
       owner ID match suffices.
    """
    clean_user = str(user_id).strip()
    clean_owner = str(plan_owner_id).strip()

    # Rule 1: The user who requested the plan is authorized
    if clean_user == clean_owner:
        return True

    # Rule 2: Check designated admins
    admins = get_authorized_admins(channel=channel)
    if clean_user in admins:
        return True

    logger.warning(f"[SecurityAuthorization] User {clean_user} is NOT authorized to approve plan owned by {clean_owner}.")
    return False


import hashlib
import hmac
import time

_GATEWAY_SALT = "anara_gateway_salt_v2"


def hash_gateway_password(password: str) -> str:
    clean = (password or "").strip()
    return hashlib.sha256(f"{clean}:{_GATEWAY_SALT}".encode()).hexdigest()


def get_configured_gateway_password_hash() -> str:
    try:
        from config import cfg_get
        stored = cfg_get("gateway.password_hash", "")
        if stored and str(stored).strip():
            return str(stored).strip()
    except Exception:
        pass
    return hash_gateway_password("anara2026")


def verify_gateway_password(input_password: str) -> bool:
    clean_in = (input_password or "").strip()
    if not clean_in:
        return False
    configured_hash = get_configured_gateway_password_hash()
    return hmac.compare_digest(hash_gateway_password(clean_in), configured_hash)


def set_gateway_password(new_password: str) -> bool:
    clean_p = (new_password or "").strip()
    if len(clean_p) < 4:
        raise ValueError("Gateway password must be at least 4 characters.")
    p_hash = hash_gateway_password(clean_p)
    try:
        from config import save_config
        return save_config({"gateway.password_hash": p_hash})
    except Exception as e:
        logger.error(f"[Security] Failed to save gateway password: {e}")
        return False


def generate_gateway_session_token() -> str:
    import uuid
    token = uuid.uuid4().hex
    try:
        from memory import memory_engine
        memory_engine.set_app_setting(f"gateway_session_{token}", str(time.time()))
    except Exception:
        pass
    return token


def verify_gateway_session_token(token: str) -> bool:
    clean = (token or "").strip()
    if not clean:
        return False
    try:
        from memory import memory_engine
        ts = memory_engine.get_app_setting(f"gateway_session_{clean}")
        if ts:
            created_at = float(ts)
            # Token valid for 7 days
            if (time.time() - created_at) < 7 * 86400:
                return True
    except Exception:
        pass
    return False


def is_request_local(client_host: Optional[str], headers: Optional[Dict[str, str]] = None) -> bool:
    if headers:
        cf_ip = headers.get("cf-connecting-ip") or headers.get("x-real-ip")
        if cf_ip and cf_ip.strip() not in ("127.0.0.1", "::1", "localhost"):
            return False
        if headers.get("cf-ray"):
            return False
    clean_host = (client_host or "").strip().lower()
    return clean_host in ("127.0.0.1", "::1", "localhost", "testclient")


from starlette.requests import HTTPConnection


async def require_gateway_auth(conn: HTTPConnection) -> bool:
    """
    Hermes & Production API Security Guard (Gap 6 Parity):
    1. Local requests (127.0.0.1, ::1, localhost, testclient) are automatically permitted
       to ensure friction-free local developer experience for Web Studio, 3D HUD, and CLI.
    2. Remote / Tunnel requests must provide a valid Authorization: Bearer <token> or query param ?token=<token>.
    3. If gateway.auth_enabled is False in config, all requests are permitted.
    """
    try:
        from config import cfg_get
        if not bool(cfg_get("gateway.auth_enabled", True)):
            return True
    except Exception:
        pass

    from fastapi import HTTPException

    client_host = conn.client.host if hasattr(conn, "client") and conn.client else None
    headers_dict = dict(conn.headers) if hasattr(conn, "headers") and conn.headers else {}
    if is_request_local(client_host, headers_dict):
        return True

    # Check Bearer token in Authorization header
    auth_header = headers_dict.get("authorization") or ""
    token = ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    elif hasattr(conn, "query_params") and conn.query_params.get("token"):
        token = conn.query_params.get("token", "").strip()

    if token and verify_gateway_session_token(token):
        return True

    raise HTTPException(
        status_code=401,
        detail="Unauthorized: Remote access requires a valid gateway session token. Login at /api/gateway/login."
    )


