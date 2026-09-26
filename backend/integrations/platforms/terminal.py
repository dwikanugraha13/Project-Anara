"""
platforms/terminal.py — Terminal platform adapter alias and rich terminal renderer (Anara Enterprise Architecture).
"""

from .cli import CliPlatformAdapter as TerminalPlatformAdapter
from .cli import CliPlatformAdapter

__all__ = ["TerminalPlatformAdapter", "CliPlatformAdapter"]
