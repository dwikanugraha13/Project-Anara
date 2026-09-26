"""
test_terminal_ui.py — Verification test suite for Rich Terminal UI & Interactive CLI UX.
Anara Enterprise Architecture:
1. AnaraTerminalUI rendering integrity (Markdown, status HUD, help table, plan approval).
2. ToolActivitySpinner lifecycle (start_tool, update_detail, finish_tool with timing).
3. StreamTokenRenderer live token buffer and frame closures.
4. AnaraCliCompleter slash command and workspace file path completions (@).
5. Unified diff syntax highlighting renderer.
"""

import pytest
from prompt_toolkit.document import Document
from integrations.platforms.terminal_ui import (
    terminal_ui,
    AnaraTerminalUI,
    ToolActivitySpinner,
    StreamTokenRenderer,
    AnaraCliCompleter,
)


def test_terminal_ui_spinner_lifecycle(capsys):
    spinner = ToolActivitySpinner()
    spinner.start_tool("test_action", "reading test file")
    spinner.update_detail("reading line 50")
    spinner.finish_tool(success=True, summary="done reading")
    out = capsys.readouterr().out
    assert "✓" in out
    assert "test_action" in out


def test_stream_token_renderer():
    streamer = StreamTokenRenderer()
    streamer.start(speaker_name="AnaraTest")
    streamer.feed("Halo ")
    streamer.feed("dunia!")
    assert streamer.get_full_text() == "Halo dunia!"
    streamer.finish()
    assert streamer._is_active is False


def test_cli_completer_slash_commands():
    completer = AnaraCliCompleter()
    doc = Document("/he")
    completions = list(completer.get_completions(doc, None))
    assert len(completions) >= 1
    assert completions[0].text == "/help"

    doc2 = Document("/mod")
    completions2 = [c.text for c in completer.get_completions(doc2, None)]
    assert "/model" in completions2
    assert "/mode" in completions2


def test_cli_completer_file_trigger(tmp_path):
    # Create sample files
    (tmp_path / "hello.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "world.txt").write_text("world", encoding="utf-8")

    completer = AnaraCliCompleter(workspace_root=str(tmp_path))
    doc = Document("check @hel")
    completions = list(completer.get_completions(doc, None))
    assert len(completions) == 1
    assert completions[0].text == "hello.py"


def test_terminal_ui_render_cards_and_diff(capsys):
    ui = AnaraTerminalUI()
    ui.print_banner("conversational")
    ui.render_help()
    ui.render_status_hud({"Channel": "CLI", "Model": "test-model"})
    ui.render_diff("sample.py", "def a(): pass\n", "def a(): return 1\n")

    out = capsys.readouterr().out
    assert "PROJECT ANARA" in out
    assert "Interactive CLI Commands" in out
    assert "sample.py" in out
