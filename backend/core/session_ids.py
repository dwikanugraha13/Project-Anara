"""
session_ids.py — Session Key Minting Engine for Project Anara.
Anara Enterprise Architecture:
Provides collision-free, chronologically verifiable session keys in the canonical
format: ``YYYYMMDD_HHMMSS_<6hex>`` (e.g. ``20260927_054512_a3f89b``).
"""
import re
import uuid
from datetime import datetime
from typing import Optional

SESSION_KEY_PATTERN = re.compile(r"^\d{8}_\d{6}_[a-f0-9]{6}")


def new_session_key(now: Optional[datetime] = None, hex_len: int = 6) -> str:
    """Mints a canonical collision-free session key: <YYYYMMDD>_<HHMMSS>_<hex>."""
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{uuid.uuid4().hex[:hex_len]}"


def is_valid_session_key(key: str) -> bool:
    """Verifies whether a string conforms to the canonical session key format."""
    return bool(SESSION_KEY_PATTERN.match(str(key or "").strip()))
