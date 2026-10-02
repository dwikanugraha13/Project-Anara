"""
terminal_ui.py — Rich Terminal Rendering Engine & Interactive UX for Project Anara.
Anara Enterprise Architecture:
Provides Anara CLI & Anara parity for terminal interactions:
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
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

console = Console(highlight=False)


def _canonical_tool_call(tool_name: str, detail: str = "") -> Tuple[str, str]:
    """
    Normalizes arbitrary internal tool names and raw argument strings into
    Canonical activity signatures (e.g. Read, Edit, Write, Bash, Grep, Glob).
    """
    t_lower = tool_name.lower().replace("-", "_").strip()
    arg = detail.strip().replace("\r", " ").replace("\n", " ")

    # Normalize path separators and relative paths
    if "/" in arg or "\\" in arg:
        arg = arg.replace("\\", "/")
        try:
            cwd_norm = os.getcwd().replace("\\", "/").rstrip("/") + "/"
            if arg.startswith(cwd_norm):
                arg = arg[len(cwd_norm):]
        except Exception:
            pass

    # Canonical tool mapping
    name_map = {
        "read_local_file": "Read",
        "read_file": "Read",
        "read": "Read",
        "view_file": "Read",
        "edit_file": "Edit",
        "patch": "Edit",
        "fuzzy_replace": "Edit",
        "write_local_file": "Write",
        "write_file": "Write",
        "delete_local_file": "Delete",
        "delete_file": "Delete",
        "execute_cli_command": "Bash",
        "run_shell_command": "Bash",
        "terminal": "Bash",
        "bash": "Bash",
        "sh": "Bash",
        "cmd": "Bash",
        "grep_search_code": "Grep",
        "search_files": "Search",
        "grep": "Grep",
        "glob_find_files": "Glob",
        "find_files": "Glob",
        "glob": "Glob",
        "list_directory": "ListDir",
        "list_dir": "ListDir",
        "ls": "ListDir",
        "web_search": "WebSearch",
        "search": "WebSearch",
        "fetch_webpage": "Fetch",
        "web_extract": "Fetch",
        "execute_code": "Python",
        "computer_use": "Computer",
        "delegate_subagent": "Agent",
        "extract_code_outline": "Outline",
    }

    canonical = name_map.get(t_lower)
    if not canonical:
        # Fallback substring heuristic
        if "read" in t_lower:
            canonical = "Read"
        elif "edit" in t_lower or "patch" in t_lower:
            canonical = "Edit"
        elif "write" in t_lower:
            canonical = "Write"
        elif any(k in t_lower for k in ("cli", "bash", "shell", "terminal", "command")):
            canonical = "Bash"
        elif "grep" in t_lower:
            canonical = "Grep"
        elif "find" in t_lower or "glob" in t_lower:
            canonical = "Glob"
        elif "search" in t_lower:
            canonical = "Search"
        elif "fetch" in t_lower or "scrape" in t_lower:
            canonical = "Fetch"
        else:
            # Preserve original tool name cleanly (e.g. test_action)
            canonical = tool_name.strip()

    if len(arg) > 55:
        arg = arg[:52] + "..."

    return canonical, arg


class ToolActivitySpinner:
    """
    Terminal-first activity feed renderer.
    Single-line tool progression with live timer, symbol prefixes, and diff stats:
      ● Read(backend/terminal_ui.py) 0.1s
      ● Edit(cli.py) +12 -3 0.2s
      ● Bash(git status) 1.2s
    """

    def __init__(self, console_ref: Console = console):
        self.console = console_ref
        self._status = None
        self._start_time = 0.0
        self._current_tool = ""
        self._current_arg = ""
        self._current_label = ""

    def start_tool(self, tool_name: str, detail: str = ""):
        # If another tool was already active, complete it cleanly before starting new tool
        if self._status is not None and self._current_tool:
            self.finish_tool(success=True)

        self._start_time = time.time()
        canonical, clean_arg = _canonical_tool_call(tool_name, detail)
        self._current_tool = canonical
        self._current_arg = clean_arg

        self._current_label = f"[bold cyan]●[/bold cyan] [bold]{escape(canonical)}[/bold]"
        if clean_arg:
            self._current_label += f"([white]{escape(clean_arg)}[/white])"
        else:
            self._current_label += "()"

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
            if len(clean) > 55:
                clean = clean[:52] + "..."
            self._status.update(f"{self._current_label} [dim]({escape(clean)})[/dim]")

    def finish_tool(self, success: bool = True, summary: str = "", diff_stat: str = ""):
        if not self._current_tool and self._status is None:
            return
        elapsed = time.time() - self._start_time if self._start_time > 0 else 0.0
        if self._status:
            try:
                self._status.stop()
            except Exception:
                pass
            self._status = None

        time_tag = f"[dim]{elapsed:.1f}s[/dim]"

        # Parse or format diff stats (+12 -3)
        diff_display = ""
        stat_candidate = diff_stat or summary
        if stat_candidate:
            import re
            diff_match = re.search(r"(\+\d+)\s+(-\d+)", stat_candidate)
            if diff_match:
                adds, dels = diff_match.group(1), diff_match.group(2)
                diff_display = f"[bold green]{adds}[/bold green] [bold red]{dels}[/bold red] "
            else:
                add_match = re.search(r"\+\d+", stat_candidate)
                if add_match and not diff_display:
                    diff_display = f"[bold green]{add_match.group(0)}[/bold green] "

        # Format single-line output
        if success:
            mark = "[bold green]●[/bold green]"
            msg = f"  {mark} {self._current_tool}"
            if self._current_arg:
                msg += f"({escape(self._current_arg)})"
            else:
                msg += "()"
            if diff_display:
                msg += f" {diff_display}"
            # Checkmark included for clear state & backward compatibility with tests
            msg += f" [green]✓[/green] {time_tag}"
            if summary and not diff_display:
                clean_sum = summary.strip().replace("\n", " ")
                if len(clean_sum) > 50:
                    clean_sum = clean_sum[:47] + "..."
                msg += f" → [dim]{escape(clean_sum)}[/dim]"
        else:
            mark = "[bold red]●[/bold red]"
            msg = f"  {mark} {self._current_tool}"
            if self._current_arg:
                msg += f"({escape(self._current_arg)})"
            else:
                msg += "()"
            msg += f" [bold red]✗ failed[/bold red] [dim]({elapsed:.1f}s)[/dim]"
            if summary:
                clean_sum = summary.strip().replace("\n", " ")
                if len(clean_sum) > 50:
                    clean_sum = clean_sum[:47] + "..."
                msg += f" → [red]{escape(clean_sum)}[/red]"

        self.console.print(msg)
        self._current_tool = ""
        self._current_arg = ""
        self._current_label = ""
        self._start_time = 0.0


class ThinkingPreviewRenderer:
    """
    Subtle dimmed preview renderer for model internal reasoning / thinking.
    Truncates display to at most 5 lines so terminal scrollback isn't overwhelmed.
    Smoothly collapses to a single concise status line on completion.
    """

    def __init__(self, console_ref: Console = console, max_lines: int = 5):
        self.console = console_ref
        self.max_lines = max_lines
        self._is_active = False
        self._start_time = 0.0
        self._buffer: List[str] = []
        self._status = None

    def start(self, initial_thought: str = ""):
        if self._is_active:
            return
        self._is_active = True
        self._start_time = time.time()
        self._buffer = []
        if initial_thought:
            self.feed(initial_thought)

    def feed(self, text: str):
        if not self._is_active:
            self.start()
        clean = text.strip()
        if not clean:
            return
        lines = [line.strip() for line in clean.splitlines() if line.strip()]
        self._buffer.extend(lines)

        preview_lines = self._get_preview_lines()
        preview_text = " ".join(preview_lines)
        if len(preview_text) > 80:
            preview_text = preview_text[:77] + "..."

        label = f"[dim][thinking] {escape(preview_text)}[/dim]"
        if self._status is None:
            self._status = self.console.status(label, spinner="dots")
            self._status.start()
        else:
            self._status.update(label)

    def _get_preview_lines(self) -> List[str]:
        if len(self._buffer) <= self.max_lines:
            return self._buffer
        omitted = len(self._buffer) - (self.max_lines - 1)
        return [f"... ({omitted} earlier lines)"] + self._buffer[-(self.max_lines - 1):]

    def finish(self, summary: str = ""):
        if not self._is_active:
            return
        elapsed = time.time() - self._start_time if self._start_time > 0 else 0.0
        if self._status:
            try:
                self._status.stop()
            except Exception:
                pass
            self._status = None

        time_tag = f"{elapsed:.1f}s"
        msg = f"  [dim]● Thought for {time_tag}[/dim]"
        if summary:
            clean_s = summary.strip().replace("\n", " ")
            if len(clean_s) > 40:
                clean_s = clean_s[:37] + "..."
            msg += f" [dim]({escape(clean_s)})[/dim]"
        self.console.print(msg)

        self._is_active = False
        self._buffer = []
        self._start_time = 0.0

    def reset(self):
        if self._status:
            try:
                self._status.stop()
            except Exception:
                pass
            self._status = None
        self._is_active = False
        self._buffer = []
        self._start_time = 0.0


class StreamTokenRenderer:
    """
    Renders live streaming tokens directly to stdout without box enclosures.
    Eradicates 'Box-itis': no ╭─ Anara ─╮ or ╰─────────╯ borders.
    Preserves raw streaming speed and terminal copy-paste fidelity.
    """

    def __init__(self, console_ref: Console = console):
        self.console = console_ref
        self._is_active = False
        self._buffer: List[str] = []

    def start(self, speaker_name: str = "Anara"):
        if self._is_active:
            return
        self._is_active = True
        self._buffer = []
        # Ensure clean line start without box frame headers
        sys.stdout.write("\n")
        sys.stdout.flush()

    def feed(self, token: str):
        if not self._is_active:
            self.start()
        self._buffer.append(token)
        sys.stdout.write(token)
        sys.stdout.flush()

    def finish(self):
        if self._is_active:
            sys.stdout.write("\n\n")
            sys.stdout.flush()
            self._is_active = False

    def reset(self):
        self._is_active = False
        self._buffer = []

    def get_full_text(self) -> str:
        return "".join(self._buffer)


class AnaraTerminalUI:
    """Central interactive terminal presenter for Project Anara CLI."""

    def __init__(self):
        self.console = console
        self.spinner = ToolActivitySpinner(self.console)
        self.streamer = StreamTokenRenderer(self.console)
        self.thinking = ThinkingPreviewRenderer(self.console)

    def print_banner(self, session_mode: str = "conversational", model_id: str = ""):
        model_tag = f" [dim]•[/dim] Model: [bold cyan]{model_id}[/bold cyan]" if model_id else ""
        banner_text = Text()
        banner_text.append("  ◆ PROJECT ANARA", style="bold cyan")
        banner_text.append(" • Autonomous AI Companion & Full-Stack Engineer\n", style="dim")
        self.console.print()
        self.console.print(banner_text)
        self.console.print(f"  [dim]Mode: [bold green]{session_mode}[/bold green]{model_tag} • Type [bold cyan]/help[/bold cyan] for commands[/dim]\n")

    def print_response(self, text: str, speaker_name: str = "Anara"):
        """
        Renders a complete formatted response with clean unboxed Rich Markdown.
        Eradicates 'Box-itis': no enclosing Panel borders.
        """
        if not text or not text.strip():
            return
        md = Markdown(text.strip(), code_theme="monokai", inline_code_theme="monokai")
        self.console.print()
        self.console.print(md)
        self.console.print()

    def render_diff(self, file_path: str, old_content: str = "", new_content: str = "", raw_diff: Optional[str] = None):
        """Displays a syntax-highlighted unified diff for file edits or raw git diffs."""
        if raw_diff is not None:
            diff_text = raw_diff.strip()
        elif not old_content and (new_content.startswith("diff --git") or new_content.startswith("index ") or new_content.startswith("--- ")):
            diff_text = new_content.strip()
        else:
            old_lines = old_content.splitlines(keepends=True)
            new_lines = new_content.splitlines(keepends=True)
            diff_lines = list(difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                n=3
            ))
            diff_text = "".join(diff_lines).strip()

        if not diff_text:
            self.console.print(f"  [dim]No textual differences for {file_path}[/dim]")
            return

        syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
        self.console.print(f"\n[bold yellow]Diff: {escape(file_path)}[/bold yellow]")
        self.console.print(syntax)
        self.console.print()

    def render_plan_approval_card(self, plan_text: str) -> str:
        """Renders the composed action plan card with interactive prompt options."""
        md = Markdown(plan_text.strip())
        panel = Panel(
            md,
            title="[bold yellow]📋 ACTION PLAN COMPOSED (Plan Gate)[/bold yellow]",
            title_align="left",
            border_style="yellow",
            padding=(0, 1)
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
    Provides Anara CLI & Anara parity tab-completion in the CLI.
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
                sub = ""
                if "/" in prefix or "\\" in prefix:
                    norm_p = prefix.replace("\\", "/")
                    if norm_p.endswith("/"):
                        sub = norm_p.rstrip("/")
                        target_prefix = ""
                    else:
                        sub, target_prefix = norm_p.rsplit("/", 1)
                    base_dir = os.path.join(base_dir, sub)

                if os.path.isdir(base_dir):
                    for item in sorted(os.listdir(base_dir)):
                        if item.startswith(".") or item in ("node_modules", "venv", "__pycache__"):
                            continue
                        if not target_prefix or item.lower().startswith(target_prefix.lower()):
                            is_dir = os.path.isdir(os.path.join(base_dir, item))
                            clean_sub = sub.replace("\\", "/")
                            full_rel = f"{clean_sub}/{item}" if clean_sub else item
                            if is_dir:
                                full_rel += "/"
                            yield Completion(
                                full_rel,
                                start_position=-len(prefix),
                                display=item + ("/" if is_dir else ""),
                                display_meta="dir" if is_dir else "file"
                            )
            except Exception:
                pass


terminal_ui = AnaraTerminalUI()
