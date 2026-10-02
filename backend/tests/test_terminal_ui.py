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
    ThinkingPreviewRenderer,
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


def test_activity_feed_canonical_parity(capsys):
    spinner = ToolActivitySpinner()
    # Read tool
    spinner.start_tool("read_local_file", "backend/integrations/platforms/terminal_ui.py")
    spinner.finish_tool(success=True)
    # Edit tool with diff stats
    spinner.start_tool("edit_file", "cli.py")
    spinner.finish_tool(success=True, summary="+12 -3 lines modified")
    # Bash tool
    spinner.start_tool("execute_cli_command", "git status --short")
    spinner.finish_tool(success=True)

    out = capsys.readouterr().out
    assert "● Read(backend/integrations/platforms/terminal_ui.py)" in out
    assert "● Edit(cli.py)" in out
    assert "+12" in out
    assert "-3" in out
    assert "● Bash(git status --short)" in out


def test_stream_token_renderer_unboxed(capsys):
    streamer = StreamTokenRenderer()
    streamer.start(speaker_name="Anara")
    streamer.feed("Direct streaming token test.")
    streamer.finish()
    out = capsys.readouterr().out
    assert "Direct streaming token test." in out
    # Verify eradication of box-itis
    assert "╭─" not in out
    assert "╰─" not in out


def test_eradicate_box_itis_unboxed_markdown(capsys):
    ui = AnaraTerminalUI()
    ui.print_response("# Header\nUnboxed markdown response content.")
    out = capsys.readouterr().out
    assert "Unboxed markdown response content." in out
    # Verify no cyan Panel box borders around response
    assert "╭─" not in out
    assert "╰─" not in out
    assert "│" not in out


def test_thinking_preview_renderer(capsys):
    thinking = ThinkingPreviewRenderer(max_lines=5)
    thinking.start("Analyzing request")
    for i in range(10):
        thinking.feed(f"Reasoning step {i}: inspecting requirements")
    # Test preview truncation helper
    preview = thinking._get_preview_lines()
    assert len(preview) <= 5
    assert any("earlier lines" in line for line in preview)
    thinking.finish(summary="Reasoning complete")
    out = capsys.readouterr().out
    assert "Thought for" in out


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
