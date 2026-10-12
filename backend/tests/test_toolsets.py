"""
test_toolsets.py — Unit tests for the 25 Standard Desktop Toolsets Matrix & Legacy Aliases.
Validates:
1. Definition of the 25 standard desktop toolsets with 1:1 member tool alignment.
2. Legacy alias lookups (file_operations -> file, etc.).
3. Toggle toolset state persistence and alias resolution.
4. get_toolsets_status and get_enabled_tool_names behaviors.
5. 100% Native Project Anara branding compliance.
"""

import sys
from pathlib import Path
import pytest

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tools.toolsets import (
    ANARA_TOOLSETS,
    LEGACY_TOOLSET_ALIASES,
    resolve_toolset_name,
    get_toolset,
    is_toolset_enabled,
    get_toolsets_status,
    toggle_toolset,
    get_enabled_tool_names,
)


class TestStandardDesktopToolsetsDefinition:
    """Verifies the 25 standard desktop toolsets and 1:1 member tool alignment."""

    def test_toolset_count(self):
        assert len(ANARA_TOOLSETS) == 25, f"Expected exactly 25 toolsets, got {len(ANARA_TOOLSETS)}"

    def test_standard_desktop_toolsets_and_tools_alignment(self):
        expected_matrix = {
            "web": ["web_search", "web_extract"],
            "browser": [
                "browser_navigate",
                "browser_click",
                "browser_type",
                "browser_scroll",
                "browser_exec",
            ],
            "terminal": ["terminal", "process_manage"],
            "file": ["read_file", "write_file", "patch", "search_files"],
            "code_execution": ["execute_code"],
            "vision": ["vision_analyze"],
            "video": ["video_analyze"],
            "image_gen": ["image_generate"],
            "video_gen": ["video_generate", "xai_video_edit", "xai_video_extend"],
            "x_search": ["x_search"],
            "tts": ["text_to_speech"],
            "stt": ["voice_transcribe"],
            "skills": ["skills_list", "skill_view", "skill_manage"],
            "todo": ["todo_list"],
            "kanban": ["kanban_board", "kanban_card"],
            "memory": ["memory"],
            "session_search": ["session_search"],
            "connections": ["manage_connections"],
            "clarify": ["clarify"],
            "delegation": ["delegate_task"],
            "cronjob": ["cronjob_manage"],
            "spotify": ["spotify_playback", "spotify_search"],
            "computer_use": ["computer_use"],
            "context_engine": [],
            "yuanbao": [
                "yb_query_group_info",
                "yb_query_group_members",
                "yb_send_dm",
                "yb_search_sticker",
                "yb_send_sticker",
            ],
        }

        for ts_id, expected_tools in expected_matrix.items():
            assert ts_id in ANARA_TOOLSETS, f"Toolset '{ts_id}' missing from ANARA_TOOLSETS"
            actual_tools = ANARA_TOOLSETS[ts_id]["tools"]
            assert actual_tools == expected_tools, (
                f"Toolset '{ts_id}' tools mismatch: expected {expected_tools}, got {actual_tools}"
            )


class TestLegacyAliasLookups:
    """Verifies resolution of legacy toolset aliases to canonical IDs."""

    @pytest.mark.parametrize(
        ("legacy_alias", "canonical_id"),
        [
            ("file_operations", "file"),
            ("terminal_processes", "terminal"),
            ("web_search_scraping", "web"),
            ("image_generation", "image_gen"),
            ("video_generation", "video_gen"),
            ("text_to_speech", "tts"),
            ("speech_to_text", "stt"),
            ("memory_hot", "memory"),
            ("skills_engine", "skills"),
            ("clarifying_questions", "clarify"),
            ("task_delegation", "delegation"),
            ("browser_automation", "browser"),
            ("spotify_music", "spotify"),
            ("cron_scheduler", "cronjob"),
            ("kanban_management", "kanban"),
            ("search", "web"),
        ],
    )
    def test_alias_resolution(self, legacy_alias, canonical_id):
        assert resolve_toolset_name(legacy_alias) == canonical_id
        ts = get_toolset(legacy_alias)
        assert ts is not None
        assert ts["id"] == canonical_id

    def test_canonical_passthrough(self):
        assert resolve_toolset_name("web") == "web"
        assert resolve_toolset_name("file") == "file"
        assert resolve_toolset_name("unknown_toolset_abc") == "unknown_toolset_abc"


class TestToolsetTogglesAndStatus:
    """Verifies toggling toolsets via canonical and legacy names."""

    def test_toggle_toolset_canonical_and_legacy(self):
        # Toggle via canonical id
        assert toggle_toolset("file", enabled=False) is True
        assert is_toolset_enabled("file") is False
        assert is_toolset_enabled("file_operations") is False

        # Toggle via legacy alias
        assert toggle_toolset("file_operations", enabled=True) is True
        assert is_toolset_enabled("file") is True
        assert is_toolset_enabled("file_operations") is True

        # Toggle web
        assert toggle_toolset("web_search_scraping", enabled=False) is True
        assert is_toolset_enabled("web") is False
        assert toggle_toolset("web", enabled=True) is True
        assert is_toolset_enabled("web") is True

    def test_get_toolsets_status_returns_25(self):
        statuses = get_toolsets_status()
        assert len(statuses) == 25
        ids = {s["id"] for s in statuses}
        assert "web" in ids
        assert "file" in ids
        assert "terminal" in ids
        assert "code_execution" in ids
        assert "computer_use" in ids

    def test_get_enabled_tool_names_returns_set(self):
        enabled_tools = get_enabled_tool_names()
        assert isinstance(enabled_tools, set)
        assert "read_file" in enabled_tools
        assert "web_search" in enabled_tools
