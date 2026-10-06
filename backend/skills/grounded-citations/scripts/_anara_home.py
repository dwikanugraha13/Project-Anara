"""Resolve ANARA_HOME for standalone skill scripts.

Skill scripts may run outside the Anara process (system Python, nix env,
CI) where ``constants`` is not importable.  This module provides the
same ``get_anara_home()`` contract without requiring it on ``sys.path``.

When ``constants`` IS available it is used directly so profile
resolution and any future enhancements are picked up automatically.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from constants import get_anara_home as get_anara_home
except (ModuleNotFoundError, ImportError):

    def get_anara_home() -> Path:
        """Return the Anara home directory (default: ``~/.anara``)."""
        val = os.environ.get("ANARA_HOME", "").strip()
        return Path(val) if val else Path.home() / ".anara"
