"""
sharpshooter.py — Friction-Gated Project Memory Engine for Project Anara.
Parity with Oh My Pi (packages/coding-agent/src/sharpshooter/types.ts).

Admits and persists decisions into project memory ONLY when user dialogue shows friction:
- Corrective: The user is explicitly correcting or forbidding an agent behavior (e.g., 'jangan pakai...').
- Regression: The user reports that previously working behavior broke or drifted.
- Architectural Decision: The user declares a definitive engineering or UI invariant.

Guarantees prefix-cache invariance and prevents memory pollution by ignoring routine chatter.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("anara.core.sharpshooter")

_CORRECTIVE_PATTERNS = [
    r"\b(?:jangan|dilarang|stop|hindari|bukan\s+gitu|salah|keliru)\s+([^\n.,;]+)",
    r"\b(?:don't|never|stop|do\s+not)\s+([^\n.,;]+)",
    r"\b(?:hapus\s+saja|buang\s+saja|hilangkan)\s+([^\n.,;]+)",
]

_REGRESSION_PATTERNS = [
    r"\b(?:kemarin\s+(?:bisa|jalan)|sebelumnya\s+(?:bisa|jalan)).*?(?:sekarang\s+error|rusak|pecah|bug)",
    r"\b(?:kok\s+(?:balik\s+lagi|error\s+lagi|rusak\s+lagi))",
    r"\b(?:broke\s+again|regressed|stopped\s+working\s+again)\b",
]

_DECISION_PATTERNS = [
    r"\b(?:kita\s+sepakat|kesepakatan|aturan|standar\s+kita|invarian(?:t)?)\s*[:\-]?\s*([^\n.,;]+)",
    r"\b(?:wajib\s+gunakan|harus\s+pakai|selalu\s+gunakan)\s+([^\n.,;]+)",
    r"\b(?:we\s+decided|always\s+use|must\s+use|architecture\s+rule)\s*[:\-]?\s*([^\n.,;]+)",
]


def detect_friction(prompt: str) -> Optional[Dict[str, Any]]:
    """
    Inspects user prompt for friction signals.
    Returns friction metadata dictionary if friction is admitted, else None.
    """
    clean = (prompt or "").strip()
    if not clean or len(clean) < 5:
        return None

    # 1. Check for corrective signals
    for pat in _CORRECTIVE_PATTERNS:
        m = re.search(pat, clean, re.IGNORECASE)
        if m:
            extracted = m.group(1).strip() if m.groups() else clean
            return {
                "kind": "correction",
                "statement": f"Rule: Hindari {extracted}",
                "evidence": clean[:180],
                "friction": {"corrective": True, "regression": False, "subtle": True},
            }

    # 2. Check for regression signals
    for pat in _REGRESSION_PATTERNS:
        if re.search(pat, clean, re.IGNORECASE):
            return {
                "kind": "regression",
                "statement": f"Regression Guard: Perbaiki dan jaga stabilitas ({clean[:80]})",
                "evidence": clean[:180],
                "friction": {"corrective": False, "regression": True, "subtle": True},
            }

    # 3. Check for architectural decision signals
    for pat in _DECISION_PATTERNS:
        m = re.search(pat, clean, re.IGNORECASE)
        if m:
            extracted = m.group(1).strip() if m.groups() else clean
            return {
                "kind": "architecture_decision",
                "statement": f"Standard: {extracted}",
                "evidence": clean[:180],
                "friction": {"corrective": False, "regression": False, "subtle": False},
            }

    return None


def maybe_record_friction_decision(prompt: str, session_id: str = "default") -> Optional[Dict[str, Any]]:
    """
    If friction is detected, registers an ADR in episodic project memory.
    Returns the recorded record if admitted, None if rejected by friction gate.
    """
    friction_meta = detect_friction(prompt)
    if not friction_meta:
        return None

    try:
        from memory.episodic_adr import episodic_adr_manager
        adr_rec = episodic_adr_manager.record_project_adr(
            milestone_task=f"Friction Gate [{friction_meta['kind']}]",
            architecture_decision=friction_meta["statement"],
            rationale=f"Triggered by user feedback: \"{friction_meta['evidence']}\"",
            affected_files=[],
            session_id=str(session_id),
            test_exit_code=0,
        )
        logger.info(f"[Sharpshooter] Friction gate admitted decision ({friction_meta['kind']}): {friction_meta['statement']}")
        return {
            "admitted": True,
            "kind": friction_meta["kind"],
            "statement": friction_meta["statement"],
            "adr_id": adr_rec.get("adr_id"),
        }
    except Exception as e:
        logger.warning(f"[Sharpshooter] Failed to record friction decision: {e}")
        return None
