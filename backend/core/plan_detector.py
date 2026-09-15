"""
plan_detector.py — Unified Plan Detector for Project Anara General Agent.
Implements the 4-tier risk gate specified in prd-general-agent.md & rancangan-general-agent.md.

Principle: Security follows the tool invoked, not the channel or interface.
"""
import re
import logging
from typing import List, Optional, Dict, Any
from tools import get_tool_risk, TOOL_RISK_CLASSIFICATION

logger = logging.getLogger(__name__)

# Severity hierarchy for tool risk
RISK_ORDER: Dict[str, int] = {
    "read_only": 0,
    "action": 1,
    "mutating": 2,
    "ask": 3,
}

# Explicit approval keywords (Case-insensitive)
EXPLICIT_APPROVAL_PATTERNS = [
    r"\b(?:setujui|setuju|approve|approved)\s+(?:rencana|plan)?\b",
    r"\b(?:eksekusi|jalankan|laksanakan)\s+(?:rencana|plan|sekarang)?\b",
    r"\b(?:sikat|gas|gaspol)\s+(?:rencana|eksekusi|aja|sekarang)?\b",
    r"\b(?:lanjutkan|lanjut|proceed)\b",
    r"\bbuild\s+mode\s*(?:sekarang)?\b",
    r"\bok(?:e)?\s*,?\s*(?:jalankan|eksekusi|sikat|lakukan)\b",
    r"\bya\s*,?\s*(?:jalankan|eksekusi|sikat|lakukan)\b",
]

# Heuristic keyword-to-tool mapper for early pre-flight request inspection (Mutating & Action tools only)
KEYWORD_TOOL_HEURISTICS = [
    (
        r"\b(?:terminal|cmd|powershell|shell|bash)\s+(?:jalankan|eksekusi|run|exec)\b|"
        r"\b(?:npm\s+|pip\s+|cargo\s+|yarn\s+|pnpm\s+|docker\s+|git\s+(?:commit|push|merge|rebase|pull))\b|"
        r"\b(?:install|deploy|build\s+project|compile)\b",
        "execute_cli_command"
    ),
    (r"\b(?:edit|ubah|ganti|modifikasi|refactor)\s+(?:file|berkas|kode|script)\b", "edit_file"),
    (r"\b(?:tulis|buat\s+file|simpan\s+file|create\s+file)\b", "write_local_file"),
    (r"\b(?:hapus|delete|drop|format|shutdown|matikan)\b", "system_control"),
    (r"\b(?:kirim\s+wa|kirim\s+whatsapp|wa\s+ke)\b", "whatsapp_send_message"),
    (r"\b(?:kirim\s+telegram|tele\s+ke)\b", "telegram_send_message"),
    (r"\b(?:webhook|kirim\s+payload)\b", "custom_webhook"),
    (r"\b(?:buka\s+aplikasi|launch|jalankan\s+program)\b", "system_control"),
]


def detect_tools_from_text(request_text: str) -> List[str]:
    """Inspects raw user request text to detect anticipated tool invocations."""
    text = (request_text or "").lower()
    tools: List[str] = []
    for pattern, tool_name in KEYWORD_TOOL_HEURISTICS:
        if re.search(pattern, text):
            if tool_name not in tools:
                tools.append(tool_name)
    return tools


def get_highest_risk(tools: List[str]) -> str:
    """Returns the highest risk tier ('read_only', 'action', 'mutating', 'ask') from a list of tools."""
    if not tools:
        return "read_only"
    highest = "read_only"
    highest_val = 0
    for t in tools:
        risk = get_tool_risk(t)
        val = RISK_ORDER.get(risk, 2)
        if val > highest_val:
            highest_val = val
            highest = risk
    return highest


def is_significant_action(request_text: str, tools: List[str]) -> bool:
    """
    Evaluates if an 'action' tier tool has significant side effects
    (e.g., messaging multiple recipients, destructive todo clears, production webhooks).
    """
    text = (request_text or "").lower()
    significant_patterns = [
        r"\b(?:semua|all|broadcast|group|grup|banyak)\b",
        r"\b(?:penting|urgent|darurat|kritis)\b",
        r"\b(?:hapus\s+semua|reset|clear)\b",
    ]
    return any(re.search(pat, text) for pat in significant_patterns)


def is_explicit_plan_approval(user_text: str) -> bool:
    """Returns True if the user text explicitly approves a pending plan for execution."""
    text = (user_text or "").strip().lower()
    if not text:
        return False
    return any(re.search(pat, text) for pat in EXPLICIT_APPROVAL_PATTERNS)


def needs_plan(
    request_text: str,
    detected_tools: Optional[List[str]] = None,
    session_mode: str = "conversational",
) -> bool:
    """
    Unified Plan Detector as specified in rancangan-general-agent.md (Bab 3):

    1. In 'explicit_plan_build' (Anara Code / Project Workstation):
       Always requires Plan mode for ANY tool other than 'read_only'.
    2. In 'conversational' (Default: Anara AI Companion / Telegram / WhatsApp / General Chat):
       - 'read_only': False (direct zero-friction answer)
       - 'action': True only if significant side-effects are detected
       - 'mutating' or 'ask': True ALWAYS (mandatory Plan mode, cannot be bypassed)
    """
    tools = list(detected_tools) if detected_tools else detect_tools_from_text(request_text)
    risk = get_highest_risk(tools)

    # Mode 1: Explicit Plan/Build (Workstation / Project Codebase)
    if session_mode == "explicit_plan_build":
        return risk != "read_only"

    # Mode 2: Conversational (General Assistant / Daily Chat)
    if risk == "read_only":
        return False
    if risk == "action":
        return is_significant_action(request_text, tools)
    if risk in ("mutating", "ask"):
        # Mandatory Plan Gate — cannot be turned off by user preference
        return True

    return False
