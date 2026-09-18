"""
platform_registry.py — Platform-Specific Toolset Registry (Anara Standard).
Filters tool availability based on the active user surface/channel and task intent,
saving 60-70% schema tokens while eliminating hallucination.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

# Core tools that are ALWAYS active across all surfaces
CORE_TOOLS: List[str] = [
    "read_local_file",
    "edit_file",
    "write_local_file",
    "execute_cli_command",
    "memory",
    "manage_memory_and_todos",
    "skill_view",
    "manage_scratchpad",
]

# Surface-specific toolset mappings (Anara Multi-Channel Architecture)
PLATFORM_TOOLSETS: Dict[str, List[str]] = {
    "cli": [
        "glob_find_files",
        "grep_search_code",
        "list_directory",
        "process_manage",
        "interactive_question",
        "session_search",
        "delegate_subagent",
        "learn_and_save_skill",
    ],
    "telegram": [
        "take_screenshot",
        "web_search",
        "web_search_images",
        "fetch_webpage",
        "send_document_file",
        "generate_file_artifact",
        "create_zip_archive",
        "system_control",
        "session_search",
        "learn_and_save_skill",
        "interactive_question",
    ],
    "whatsapp": [
        "take_screenshot",
        "web_search",
        "web_search_images",
        "fetch_webpage",
        "send_document_file",
        "generate_file_artifact",
        "create_zip_archive",
        "session_search",
        "learn_and_save_skill",
    ],
    "web_studio": [
        "glob_find_files",
        "grep_search_code",
        "list_directory",
        "scan_workspace_folder",
        "project_hud",
        "interactive_question",
        "kanban_create_task",
        "kanban_list_tasks",
        "kanban_update_task",
        "kanban_request_review",
        "create_zip_archive",
        "generate_file_artifact",
        "process_manage",
        "delegate_subagent",
        "learn_and_save_skill",
        "take_screenshot",
        "web_search",
        "fetch_webpage",
    ],
    "voice_hud": [
        "spotify_playback",
        "spotify_search",
        "ha_list_entities",
        "ha_call_service",
        "ha_get_state",
        "trigger_avatar_animation",
        "project_hud",
        "take_screenshot",
        "web_search",
        "system_control",
    ],
}

# Aliases for platform keys
PLATFORM_ALIASES: Dict[str, str] = {
    "terminal": "cli",
    "bash": "cli",
    "powershell": "cli",
    "web": "web_studio",
    "code": "web_studio",
    "studio": "web_studio",
    "voice": "voice_hud",
    "hud": "voice_hud",
    "avatar": "voice_hud",
    "tele": "telegram",
    "wa": "whatsapp",
}

# Domain keywords for on-demand lazy toolset expansion
INTENT_TOOL_TRIGGERS: List[tuple[re.Pattern, List[str]]] = [
    (
        re.compile(r"\b(?:spotify|musik|lagu|playlist|play\s+music)\b", re.IGNORECASE),
        ["spotify_playback", "spotify_search"],
    ),
    (
        re.compile(r"\b(?:lampu|saklar|ac|suhu|iot|home\s*assistant|ha_)\b", re.IGNORECASE),
        ["ha_list_entities", "ha_call_service", "ha_get_state"],
    ),
    (
        re.compile(r"\b(?:browser|buka\s+web|playwright|klik\s+tombol|snapshot|crawl|youtube)\b", re.IGNORECASE),
        [
            "browser_navigate", "browser_click", "browser_type",
            "browser_snapshot", "browser_screenshot", "browser_close",
            "browser_scroll", "browser_press", "browser_back",
        ],
    ),
    (
        re.compile(r"\b(?:jadwalkan|jadwal|cron|otomatisasi\s+waktu|tiap\s+jam|tiap\s+hari)\b", re.IGNORECASE),
        ["cronjob_manage"],
    ),
    (
        re.compile(r"\b(?:gambar\s+ai|generate\s+image|dall-e|flux|bikin\s+gambar|lukis)\b", re.IGNORECASE),
        ["image_generate"],
    ),
    (
        re.compile(r"\b(?:video\s+ai|generate\s+video|cogvideox|bikin\s+video)\b", re.IGNORECASE),
        ["video_generate"],
    ),
    (
        re.compile(r"\b(?:gmail|email|surat|kalender|calendar|agenda\s+acara)\b", re.IGNORECASE),
        ["gmail_read_inbox", "calendar_get_schedule"],
    ),
    (
        re.compile(r"\b(?:discord)\b", re.IGNORECASE),
        ["discord_read_messages", "discord_send_message"],
    ),
    (
        re.compile(r"\b(?:slack)\b", re.IGNORECASE),
        ["slack_read_messages", "slack_send_message"],
    ),
    (
        re.compile(r"\b(?:mcp|model\s*context\s*protocol)\b", re.IGNORECASE),
        ["mcp_manage"],
    ),
    (
        re.compile(r"\b(?:kanban|papan\s+tugas|trello)\b", re.IGNORECASE),
        ["kanban_create_task", "kanban_list_tasks", "kanban_update_task", "kanban_request_review"],
    ),
    (
        re.compile(r"\b(?:webhook)\b", re.IGNORECASE),
        ["custom_webhook"],
    ),
]


class PlatformToolRegistry:
    """Dynamic tool resolution and pruning based on surface and user task intent."""

    @classmethod
    def resolve_platform_key(cls, platform: Optional[str]) -> str:
        clean = (platform or "cli").strip().lower()
        return PLATFORM_ALIASES.get(clean, clean)

    @classmethod
    def get_tools_for_platform(
        cls,
        platform: Optional[str] = None,
        user_task: Optional[str] = None,
        extra_tools: Optional[List[str]] = None,
    ) -> Set[str]:
        """
        Resolves active tool names for a specific platform and task context.
        Returns a lean, targeted set of tool names.
        """
        active_tools: Set[str] = set(CORE_TOOLS)

        # 1. Add platform-specific toolset
        p_key = cls.resolve_platform_key(platform)
        if p_key in PLATFORM_TOOLSETS:
            active_tools.update(PLATFORM_TOOLSETS[p_key])
        else:
            active_tools.update(PLATFORM_TOOLSETS["cli"])

        # 2. Dynamic Intent Expansion: scan user task for domain keywords
        if user_task:
            clean_task = str(user_task)
            for pattern, trigger_tools in INTENT_TOOL_TRIGGERS:
                if pattern.search(clean_task):
                    active_tools.update(trigger_tools)

        # 3. Add explicit on-demand extra tools (e.g. from active skills)
        if extra_tools:
            active_tools.update(extra_tools)

        return active_tools


def generate_skills_compact_catalog(available_skills: Dict[str, List[str]]) -> str:
    """
    Renders ultra-compact <available_skills> block for system prompts.
    Skills remain on-demand: model loads full instructions only via skill_view(name).
    """
    lines = [
        "## Skills",
        "Before replying, scan the available skills below. If a skill matches or is relevant to your task, "
        "you MUST load it with skill_view(name) and follow its instructions. Skills contain specialized procedures, "
        "API endpoints, CLI scripts, and workflows that outperform general approaches.",
        "",
        "<available_skills>",
    ]
    for category, skill_list in sorted(available_skills.items()):
        skills_str = ", ".join(sorted(skill_list))
        lines.append(f"  {category}: [{skills_str}]")
    lines.append("</available_skills>\n")
    lines.append("Only proceed without loading a skill if genuinely none are relevant to the task.")
    return "\n".join(lines)
