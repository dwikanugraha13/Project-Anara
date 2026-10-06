"""Resolve ANARA_HOME for standalone skill scripts.

Skill scripts may run outside the Anara process (e.g. system Python,
nix env, CI) where ``constants`` is not importable.  This module
provides the same ``get_anara_home()`` and ``display_anara_home()``
contracts as ``constants`` without requiring it on ``sys.path``.

When ``constants`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``constants.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``ANARA_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from constants import display_anara_home as display_anara_home
    from constants import get_anara_home as get_anara_home
except (ModuleNotFoundError, ImportError):

    def get_anara_home() -> Path:
        """Return the Anara home directory (default: ~/.anara).

        Mirrors ``constants.get_anara_home()``."""
        val = os.environ.get("ANARA_HOME", "").strip()
        return Path(val) if val else Path.home() / ".anara"

    def display_anara_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``constants.display_anara_home()``."""
        home = get_anara_home()
        try:
            return "~/" + home.relative_to(Path.home()).as_posix()
        except ValueError:
            return str(home)
