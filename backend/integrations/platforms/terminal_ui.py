"""
terminal_ui.py — Rich Terminal Rendering Engine & Interactive UX for Project Anara.
Anara Enterprise Architecture:
Provides Claude Code & Hermes parity for terminal interactions:
1. Live token streaming with responsive framing.
2. In-place animated tool spinners with per-action stopwatch timers.
3. Syntax-highlighted unified diffs for file edits.
4. Beautiful action plan approval cards.
5. Rich markdown formatting for code blocks, tables, and lists.
6. Diagnostic status HUD and slash command tables.
"""

from __future__ import annotations

import difflib
import os
import sys
import time
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

console = Console(highlight=False)


class ToolActivitySpinner:
    """
    In-place terminal spinner with live stopwatch for tool execution.
    Prevents scroll-buffer pollution by overwriting the status line in-place.
    """

    def __init__(self, console_ref: Console = console):
        self.console = console_ref
        self._status = None
        self._start_time = 0.0
        self._current_label = ""

    def start_tool(self, tool_name: str, detail: str = ""):
        self._start_time = time.time()
        clean_detail = detail.strip().replace("\n", " ")
        if len(clean_detail) > 65:
            clean_detail = clean_detail[:62] + "..."

        self._current_label = f"[bold cyan]⚡ {tool_name}[/bold cyan]"
        if clean_detail:
            self._current_label += f": [dim]{clean_detail}[/dim]"

        if self._status is not None:
            try:
                self._status.stop()
            except Exception:
                pass

        self._status = self.console.status(self._current_label, spinner="dots")
        self._status.start()

    def update_detail(self, detail: str):
        if self._status:
            clean = detail.strip().replace("\n", " ")
            if len(clean) > 65:
                clean = clean[:62] + "..."
            self._status.update(f"{self._current_label} [dim]({clean})[/dim]")

    def finish_tool(self, success: bool = True, summary: str = ""):
        elapsed = time.time() - self._start_time if self._start_time > 0 else 0.0
        if self._status:
            try:
                self._status.stop()
            except Exception:
                pass
            self._status = None

        mark = "[bold green]✓[/bold green]" if success else "[bold red]✗[/bold red]"
        time_tag = f"[dim]({elapsed:.2f}s)[/dim]"
        msg = f"  {mark} {self._current_label} {time_tag}"
        if summary:
            clean_sum = summary.strip().replace("\n", " ")
            if len(clean_sum) > 55:
                clean_sum = clean_sum[:52] + "..."
            msg += f" → [dim]{clean_sum}[/dim]"
        self.console.print(msg)


class StreamTokenRenderer:
    """
    Renders live streaming tokens with visual framing.
    Preserves raw streaming speed while providing formatted box closures.
    """

    def __init__(self, console_ref: Console = console):
        self.console = console_ref
        self._is_active = False
        self._buffer: List[str] = []
        self._header_printed = False

    def start(self, speaker_name: str = "Anara"):
        self._is_active = True
        self._buffer = []
        self._header_printed = False
        self.console.print(f"\n[bold cyan]╭─ {speaker_name} ─╮[/bold cyan]")

    def feed(self, token: str):
        if not self._is_active:
            self.start()
        self._buffer.append(token)
        sys.stdout.write(token)
        sys.stdout.flush()

    def finish(self):
        if self._is_active:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self.console.print("[bold cyan]╰─────────────╯[/bold cyan]\n")
            self._is_active = False

    def get_full_text(self) -> str:
        return "".join(self._buffer)


class AnaraTerminalUI:
    """Central interactive terminal presenter for Project Anara CLI."""

    def __init__(self):
        self.console = console
        self.spinner = ToolActivitySpinner(self.console)
        self.streamer = StreamTokenRenderer(self.console)

    def print_banner(self, session_mode: str = "conversational"):
        banner_text = Text()
        banner_text.append("  ╔══════════════════════════════════════════════════════════╗\n", style="bold cyan")
        banner_text.append("  ║                     PROJECT ANARA                        ║\n", style="bold cyan")
        banner_text.append("  ║       Autonomous AI Companion & Full-Stack Engineer      ║\n", style="cyan")
        banner_text.append("  ╚══════════════════════════════════════════════════════════╝", style="bold cyan")
        self.console.print(banner_text)
        self.console.print(f"  [dim]Type [bold cyan]/help[/bold cyan] for commands • Active Mode: [bold green]{session_mode}[/bold green][/dim]\n")

    def print_response(self, text: str, speaker_name: str = "Anara"):
        """Renders a complete formatted response with Rich Markdown formatting."""
        md = Markdown(text.strip())
        panel = Panel(
            md,
            title=f"[bold cyan] {speaker_name} [/bold cyan]",
            title_align="left",
            border_style="cyan",
            padding=(0, 1),
        )
        self.console.print()
        self.console.print(panel)
        self.console.print()

    def render_diff(self, file_path: str, old_content: str, new_content: str):
        """Displays a syntax-highlighted unified diff for file edits."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff_lines = list(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            n=3
        ))
        if not diff_lines:
            self.console.print(f"  [dim]No textual differences for {file_path}[/dim]")
            return

        diff_text = "".join(diff_lines)
        syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
        panel = Panel(
            syntax,
            title=f"[bold yellow]Diff: {file_path}[/bold yellow]",
            title_align="left",
            border_style="yellow"
        )
        self.console.print(panel)

    def render_plan_approval_card(self, plan_text: str) -> str:
        """Renders the composed action plan card with interactive prompt options."""
        md = Markdown(plan_text.strip())
        panel = Panel(
            md,
            title="[bold yellow]📋 ACTION PLAN COMPOSED (Plan Gate)[/bold yellow]",
            title_align="left",
            border_style="yellow",
            padding=(1, 2)
        )
        self.console.print()
        self.console.print(panel)
        self.console.print()

    def render_status_hud(self, data: Dict[str, Any]):
        """Renders comprehensive runtime diagnostic status card."""
        table = Table(title="[bold cyan]Project Anara — System & Session Status[/bold cyan]", border_style="cyan")
        table.add_column("Parameter", style="bold", width=22)
        table.add_column("Current State", style="green")

        for k, v in data.items():
            table.add_row(str(k), str(v))

        self.console.print(table)
        self.console.print()

    def render_help(self):
        """Renders available slash commands and keyboard shortcuts."""
        table = Table(title="[bold cyan]Project Anara — Interactive CLI Commands[/bold cyan]", border_style="cyan")
        table.add_column("Command / Trigger", style="bold yellow", width=20)
        table.add_column("Description", style="white")

        commands = [
            ("/help", "Show this interactive commands & shortcuts guide"),
            ("/status", "Display active session, model, token usage, and git status"),
            ("/mode [chat|plan|build]", "Switch operational mode (conversational vs plan-build)"),
            ("/model [name]", "View or switch active LLM provider and model"),
            ("/skills [search|list]", "Browse, search, and inspect available autonomous skills"),
            ("/diff", "View unstaged git diff of current workspace"),
            ("/clear", "Clear terminal screen scrollback"),
            ("/memory", "Inspect long-term facts and active user profile"),
            ("/daemon [restart|status|stop]", "Manage background background services"),
            ("/exit or /quit", "Gracefully terminate the CLI session"),
            ("@<path>", "Tab-autocomplete and reference local files into prompt"),
            (r"\ + Enter", "Insert newline for multi-line prompts"),
            ("Ctrl+C", "Interrupt active generation or turn without exiting"),
        ]

        for cmd, desc in commands:
            table.add_row(cmd, desc)

        self.console.print(table)
        self.console.print()


from prompt_toolkit.completion import Completer, Completion


class AnaraCliCompleter(Completer):
    """
    Intelligent fuzzy completer for slash commands and workspace file paths (@).
    Provides Claude Code & Hermes parity tab-completion in the CLI.
    """
    COMMANDS = {
        "/help": "Show interactive commands & shortcuts guide",
        "/status": "Display active session, model, and git status",
        "/mode": "Switch between conversational and build mode",
        "/model": "Switch or inspect active AI model",
        "/skills": "Browse and search autonomous skills library",
        "/diff": "View unstaged git diff in current project",
        "/clear": "Clear terminal screen buffer",
        "/memory": "Inspect long-term facts and user profile",
        "/daemon": "Manage background daemon (restart, status, stop)",
        "/exit": "Quit Anara interactive CLI",
        "/quit": "Quit Anara interactive CLI",
    }

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or os.getcwd()

    def get_completions(self, document, complete_event):
        text_before_cursor = document.text_before_cursor

        # 1. Slash commands completion
        if text_before_cursor.startswith("/"):
            word = text_before_cursor.split()[0].lower()
            for cmd, desc in self.COMMANDS.items():
                if cmd.lower().startswith(word):
                    yield Completion(
                        cmd,
                        start_position=-len(word),
                        display=cmd,
                        display_meta=desc
                    )
            return

        # 2. File reference completion triggered by @
        if "@" in text_before_cursor:
            at_idx = text_before_cursor.rfind("@")
            prefix = text_before_cursor[at_idx + 1:]
            try:
                base_dir = self.workspace_root
                target_prefix = prefix
                if "/" in prefix or "\\" in prefix:
                    sub, target_prefix = os.path.split(prefix)
                    base_dir = os.path.join(base_dir, sub)

                if os.path.isdir(base_dir):
                    for item in os.listdir(base_dir):
                        if item.startswith(".") or item in ("node_modules", "venv", "__pycache__"):
                            continue
                        if item.lower().startswith(target_prefix.lower()):
                            full_rel = os.path.join(prefix[:-len(target_prefix)], item) if target_prefix else item
                            yield Completion(
                                full_rel,
                                start_position=-len(prefix),
                                display=item,
                                display_meta="file" if not os.path.isdir(os.path.join(base_dir, item)) else "dir"
                            )
            except Exception:
                pass


terminal_ui = AnaraTerminalUI()
