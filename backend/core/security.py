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
