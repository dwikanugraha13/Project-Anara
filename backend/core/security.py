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

# Heuristic patterns for adversarial prompt injection and system hijacking
PROMPT_INJECTION_PATTERNS = [
    r"(?i)\b(?:ignore|forget|disregard|override|bypass)\s+(?:all\s+)?(?:previous|prior|system|core)\s+(?:instructions|prompts|rules|guidelines)\b",
    r"(?i)\b(?:reveal|show|print|display|dump|leak|output)\s+(?:the|your|all|any)?\s*(?:exact\s+)?(?:system\s+prompt|hidden\s+instructions|system\s+instruction|developer\s+mode|prompt)\b",
    r"(?i)\b(?:you\s+are\s+now|enter|switch\s+to|act\s+as)\b.*?\b(?:dan|developer\s+mode|unrestricted|jailbreak|god\s+mode|root\s+mode)\b",
    r"(?i)\b(?:bypass|disable|turn\s+off)\s+(?:all\s+)?(?:safety|security|filters|restrictions|permission\s+gate)\b",
    r"(?i)\bprint\s+the\s+entire\s+text\s+above\b",
    r"(?i)\bwhat\s+(?:are|is)\s+your\s+(?:exact\s+)?(?:initial|original|system)\s+(?:prompt|instructions)\b",
]

# Toxic / destructive payload heuristics
MALICIOUS_INTENT_PATTERNS = [
    r"(?i)\b(?:ransomware|trojan|keylogger|rootkit|ddos|fork\s*bomb)\b",
]


def check_prompt_injection(text: str) -> Tuple[bool, Optional[str]]:
    """
    Scans incoming user prompt for adversarial jailbreak, prompt injection,
    or system prompt exfiltration attempts (FR-20).
    Returns (is_safe, denial_reason).
    """
    clean_text = (text or "").strip()
    if not clean_text:
        return True, None

    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, clean_text):
            logger.warning(f"[SecurityFilter] Blocked prompt injection attempt: {pattern} in '{clean_text[:60]}'")
            return False, "DITOLAK SISTEM KEAMANAN (PROMPT INJECTION): Permintaan terdeteksi mengandung pola manipulasi instruksi sistem atau jailbreak."

    for pattern in MALICIOUS_INTENT_PATTERNS:
        if re.search(pattern, clean_text):
            logger.warning(f"[SecurityFilter] Blocked malicious keyword: {pattern} in '{clean_text[:60]}'")
            return False, "DITOLAK SISTEM KEAMANAN: Permintaan terdeteksi mengandung instruksi berbahaya."

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


# ─────────────────────────────────────────────────────────────────────────────
# Secret Redaction & Gateway Security
# ─────────────────────────────────────────────────────────────────────────────

SECRET_PATTERNS = [
    (re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{32,}"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{30,}"), "[REDACTED_ANTHROPIC_KEY]"),
    (re.compile(r"AIzaSy[A-Za-z0-9_-]{33}"), "[REDACTED_GOOGLE_KEY]"),
    (re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"), "[REDACTED_TELEGRAM_TOKEN]"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"), "[REDACTED_JWT_TOKEN]"),
    (re.compile(r"-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z ]+)?PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
]


def redact_sensitive_text(val: Any) -> Any:
    """Scrubs API keys, passwords, and tokens before sending to LLM or logs."""
    if isinstance(val, str):
        res = val
        for pat, replacement in SECRET_PATTERNS:
            res = pat.sub(replacement, res)
        return res
    if isinstance(val, dict):
        return {k: redact_sensitive_text(v) for k, v in val.items()}
    if isinstance(val, list):
        return [redact_sensitive_text(item) for item in val]
    return val


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
        raise ValueError("Password gateway minimal 4 karakter.")
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

