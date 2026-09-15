"""
plan_detector.py ? Unified Plan Detector for Project Anara General Agent.
Implements the 4-tier risk gate specified in prd-general-agent.md & rancangan-general-agent.md.

Principle: Security follows the tool invoked, not the channel or interface.
Zero-hardcoding: Tools are exclusively selected dynamically by the LLM, not by regex heuristics.
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


def detect_tools_from_text(request_text: str) -> List[str]:
    """
    Zero-hardcode policy: No tool is guessed from raw user text via regex heuristics.
    Tools are exclusively selected by the model dynamically at runtime.
    """
    return []


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
    Unified Plan Detector:
    1. If detected_tools are provided (from LLM runtime tool-call selection):
       - 'read_only': False (direct zero-friction answer)
       - 'action': True only if significant side-effects are detected
       - 'mutating' or 'ask': True ALWAYS (mandatory Plan mode)
    2. In 'explicit_plan_build' mode:
       Requires Plan mode for any non-read_only operation.
    3. In 'conversational' mode without detected tools:
       Delegates directly to LLM with runtime tool interception (Zero-hardcoding).
    """
    tools = list(detected_tools) if detected_tools else detect_tools_from_text(request_text)
    risk = get_highest_risk(tools)

    if session_mode == "explicit_plan_build":
        return risk != "read_only"

    if risk == "read_only":
        return False
    if risk == "action":
        return is_significant_action(request_text, tools)
    if risk in ("mutating", "ask"):
        return True

    return False
