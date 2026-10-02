"""
platforms/terminal.py — Terminal platform adapter alias and rich terminal renderer (Anara Enterprise Architecture).
"""

from .cli import CliPlatformAdapter as TerminalPlatformAdapter
from .cli import CliPlatformAdapter
from .terminal_ui import (
    terminal_ui,
    AnaraTerminalUI,
    ToolActivitySpinner,
    StreamTokenRenderer,
    ThinkingPreviewRenderer,
    AnaraCliCompleter,
)

__all__ = [
    "TerminalPlatformAdapter",
    "CliPlatformAdapter",
    "terminal_ui",
    "AnaraTerminalUI",
    "ToolActivitySpinner",
    "StreamTokenRenderer",
    "ThinkingPreviewRenderer",
    "AnaraCliCompleter",
]
