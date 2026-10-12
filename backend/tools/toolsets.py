"""
toolsets.py — Anara Standard 25 Desktop Toolsets Matrix & Modular Governance for Project Anara.
Groups Anara's tools into 25 cohesive, togglable standard desktop toolsets with persistent status in SQLite and full legacy alias backward-compatibility.
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional, Set

logger = logging.getLogger(__name__)

# Complete 25 Standard Desktop Toolsets Matrix for Project Anara
ANARA_TOOLSETS: Dict[str, Dict[str, Any]] = {
    "web": {
        "id": "web",
        "title": "Web Search & Scraping",
        "description": "Web research and content extraction tools (search and scraping).",
        "icon": "globe",
        "category": "exploration",
        "default_enabled": True,
        "tools": ["web_search", "web_extract"],
    },
    "browser": {
        "id": "browser",
        "title": "Browser Automation",
        "description": "Browser automation for web interaction (navigate, click, type, scroll, exec).",
        "icon": "compass",
        "category": "exploration",
        "default_enabled": True,
        "tools": [
            "browser_navigate",
            "browser_click",
            "browser_type",
            "browser_scroll",
            "browser_exec",
        ],
    },
    "terminal": {
        "id": "terminal",
        "title": "Terminal & Processes",
        "description": "Terminal/command execution and persistent process management tools.",
        "icon": "terminal",
        "category": "system",
        "default_enabled": True,
        "tools": ["terminal", "process_manage"],
    },
    "file": {
        "id": "file",
        "title": "File Operations",
        "description": "File manipulation tools: read, write, patch (with fuzzy matching), and search.",
        "icon": "folder",
        "category": "coding",
        "default_enabled": True,
        "tools": ["read_file", "write_file", "patch", "search_files"],
    },
    "code_execution": {
        "id": "code_execution",
        "title": "Code Execution (REPL)",
        "description": "Run Python scripts and code snippets that call tools programmatically.",
        "icon": "play",
        "category": "coding",
        "default_enabled": True,
        "tools": ["execute_code"],
    },
    "vision": {
        "id": "vision",
        "title": "Vision / Image Analysis",
        "description": "Image analysis and visual understanding tools.",
        "icon": "eye",
        "category": "multimedia",
        "default_enabled": True,
        "tools": ["vision_analyze"],
    },
    "video": {
        "id": "video",
        "title": "Video Analysis",
        "description": "Video analysis and understanding tools (requires video-capable model).",
        "icon": "video",
        "category": "multimedia",
        "default_enabled": False,
        "tools": ["video_analyze"],
    },
    "image_gen": {
        "id": "image_gen",
        "title": "Image Generation",
        "description": "Creative generation tools (AI image generation).",
        "icon": "image",
        "category": "multimedia",
        "default_enabled": True,
        "tools": ["image_generate"],
    },
    "video_gen": {
        "id": "video_gen",
        "title": "Video Generation",
        "description": "AI video generation (text/image/reference) and editing tools.",
        "icon": "film",
        "category": "multimedia",
        "default_enabled": False,
        "tools": ["video_generate", "xai_video_edit", "xai_video_extend"],
    },
    "x_search": {
        "id": "x_search",
        "title": "X (Twitter) Search",
        "description": "Search X (Twitter) posts and threads via xAI built-in search tool.",
        "icon": "twitter",
        "category": "exploration",
        "default_enabled": False,
        "tools": ["x_search"],
    },
    "tts": {
        "id": "tts",
        "title": "Text-to-Speech",
        "description": "Text-to-speech audio synthesis (Edge TTS, ElevenLabs, OpenAI, xAI).",
        "icon": "volume-2",
        "category": "multimedia",
        "default_enabled": True,
        "tools": ["text_to_speech"],
    },
    "stt": {
        "id": "stt",
        "title": "Speech-to-Text",
        "description": "Voice transcription (gateway voice messages + voice mode).",
        "icon": "mic",
        "category": "multimedia",
        "default_enabled": True,
        "tools": ["voice_transcribe"],
    },
    "skills": {
        "id": "skills",
        "title": "Skills Engine",
        "description": "Access, create, edit, and manage skill documents with specialized instructions.",
        "icon": "book-open",
        "category": "intelligence",
        "default_enabled": True,
        "tools": ["skills_list", "skill_view", "skill_manage"],
    },
    "todo": {
        "id": "todo",
        "title": "Task Planning",
        "description": "Task planning and tracking for multi-step work.",
        "icon": "check-square",
        "category": "system",
        "default_enabled": True,
        "tools": ["todo_list"],
    },
    "kanban": {
        "id": "kanban",
        "title": "Kanban Board",
        "description": "Kanban task board coordination and multi-agent workflow cards.",
        "icon": "clipboard",
        "category": "system",
        "default_enabled": False,
        "tools": ["kanban_board", "kanban_card"],
    },
    "memory": {
        "id": "memory",
        "title": "Memory Engine",
        "description": "Persistent memory across sessions (personal notes + user profile).",
        "icon": "cpu",
        "category": "memory",
        "default_enabled": True,
        "tools": ["memory"],
    },
    "session_search": {
        "id": "session_search",
        "title": "Session Search",
        "description": "Search and recall past conversations with summarization.",
        "icon": "history",
        "category": "memory",
        "default_enabled": True,
        "tools": ["session_search"],
    },
    "connections": {
        "id": "connections",
        "title": "Remote Connections",
        "description": "Remote connector discovery, execution, and account authorization.",
        "icon": "link",
        "category": "connectivity",
        "default_enabled": True,
        "tools": ["manage_connections"],
    },
    "clarify": {
        "id": "clarify",
        "title": "Clarifying Questions",
        "description": "Ask the user clarifying questions (multiple-choice or open-ended).",
        "icon": "help-circle",
        "category": "intelligence",
        "default_enabled": True,
        "tools": ["clarify"],
    },
    "delegation": {
        "id": "delegation",
        "title": "Task Delegation",
        "description": "Spawn subagents with isolated context for complex subtasks.",
        "icon": "users",
        "category": "system",
        "default_enabled": True,
        "tools": ["delegate_task"],
    },
    "cronjob": {
        "id": "cronjob",
        "title": "Cron Jobs",
        "description": "Cronjob management tool - create, list, update, pause, resume, run scheduled tasks.",
        "icon": "clock",
        "category": "system",
        "default_enabled": True,
        "tools": ["cronjob_manage"],
    },
    "spotify": {
        "id": "spotify",
        "title": "Spotify",
        "description": "Native Spotify playback, search, playlist, and library controls.",
        "icon": "music",
        "category": "multimedia",
        "default_enabled": True,
        "tools": ["spotify_playback", "spotify_search"],
    },
    "computer_use": {
        "id": "computer_use",
        "title": "Computer Use (Desktop)",
        "description": "Background desktop control via OS automation (screenshots, mouse, keyboard).",
        "icon": "monitor",
        "category": "system",
        "default_enabled": True,
        "tools": ["computer_use"],
    },
    "context_engine": {
        "id": "context_engine",
        "title": "Context Engine",
        "description": "Runtime tools exposed by the active context engine.",
        "icon": "cpu",
        "category": "intelligence",
        "default_enabled": True,
        "tools": [],
    },
    "yuanbao": {
        "id": "yuanbao",
        "title": "Yuanbao",
        "description": "Yuanbao platform tools - group info, member queries, DM, stickers.",
        "icon": "message-square",
        "category": "communication",
        "default_enabled": False,
        "tools": [
            "yb_query_group_info",
            "yb_query_group_members",
            "yb_send_dm",
            "yb_search_sticker",
            "yb_send_sticker",
        ],
    },
}

# ── Legacy Aliases Matrix for Backward Compatibility ──────────────────────────
LEGACY_TOOLSET_ALIASES: Dict[str, str] = {
    # Core legacy names
    "file_operations": "file",
    "terminal_processes": "terminal",
    "web_search_scraping": "web",
    "image_generation": "image_gen",
    "video_generation": "video_gen",
    "text_to_speech": "tts",
    "speech_to_text": "stt",
    "memory_hot": "memory",
    "skills_engine": "skills",
    "clarifying_questions": "clarify",
    "task_delegation": "delegation",
    # Legacy taxonomy aliases
    "browser_automation": "browser",
    "spotify_music": "spotify",
    "cron_scheduler": "cronjob",
    "kanban_management": "kanban",
    "search": "web",
    "web_search": "web",
    "video_analysis": "video",
    "vision_analysis": "vision",
    "computer_use_desktop": "computer_use",
    "os_desktop": "computer_use",
    "desktop_control": "computer_use",
}


def resolve_toolset_name(name: str) -> str:
    """Resolves any toolset name or legacy alias to its canonical Anara toolset identifier."""
    clean = (name or "").strip().lower()
    return LEGACY_TOOLSET_ALIASES.get(clean, clean)


def get_toolset(toolset_id: str) -> Optional[Dict[str, Any]]:
    """Returns toolset specification by ID or legacy alias."""
    canonical_id = resolve_toolset_name(toolset_id)
    return ANARA_TOOLSETS.get(canonical_id)


def is_toolset_enabled(toolset_id: str) -> bool:
    """Returns whether a specific toolset is enabled (supports legacy aliases)."""
    from memory import memory_engine

    clean_id = (toolset_id or "").strip().lower()
    canonical_id = resolve_toolset_name(clean_id)
    if canonical_id not in ANARA_TOOLSETS:
        return False

    setting_val = memory_engine.get_app_setting("toolsets_enabled_map")
    saved_map = {}
    if setting_val:
        try:
            saved_map = json.loads(setting_val)
        except Exception:
            saved_map = {}

    is_enabled = saved_map.get(canonical_id)
    if is_enabled is None and clean_id != canonical_id:
        is_enabled = saved_map.get(clean_id)
    if is_enabled is None:
        for alias, canon in LEGACY_TOOLSET_ALIASES.items():
            if canon == canonical_id and alias in saved_map:
                is_enabled = saved_map[alias]
                break
    if is_enabled is None:
        is_enabled = ANARA_TOOLSETS[canonical_id].get("default_enabled", True)

    return bool(is_enabled)


def get_toolsets_status() -> List[Dict[str, Any]]:
    """Returns all 25 standard desktop toolsets with their live enabled/disabled toggle states."""
    from memory import memory_engine

    setting_val = memory_engine.get_app_setting("toolsets_enabled_map")
    saved_map = {}
    if setting_val:
        try:
            saved_map = json.loads(setting_val)
        except Exception:
            saved_map = {}

    try:
        from tools.registry import registry
        mapping = registry.get_toolsets_mapping()
    except Exception:
        mapping = {}

    result = []
    for ts_id, ts in ANARA_TOOLSETS.items():
        is_enabled = saved_map.get(ts_id)
        if is_enabled is None:
            for alias, canon in LEGACY_TOOLSET_ALIASES.items():
                if canon == ts_id and alias in saved_map:
                    is_enabled = saved_map[alias]
                    break
        if is_enabled is None:
            is_enabled = ts.get("default_enabled", True)

        item = dict(ts)
        tools = list(ts.get("tools", []))

        # Merge dynamic tools only if toolset has no predefined canonical tools
        if not tools:
            candidate_keys = [ts_id] + [a for a, c in LEGACY_TOOLSET_ALIASES.items() if c == ts_id]
            for ck in candidate_keys:
                if ck in mapping:
                    for t in mapping[ck]:
                        if t not in tools:
                            tools.append(t)

        item["tools"] = tools
        item["enabled"] = bool(is_enabled)
        item["tool_count"] = len(tools)
        result.append(item)

    return result


def toggle_toolset(toolset_id: str, enabled: Optional[bool] = None) -> bool:
    """Toggles or sets the enabled state of a specific toolset, supporting legacy aliases."""
    from memory import memory_engine

    clean_id = (toolset_id or "").strip().lower()
    canonical_id = resolve_toolset_name(clean_id)
    if canonical_id not in ANARA_TOOLSETS:
        return False

    setting_val = memory_engine.get_app_setting("toolsets_enabled_map")
    saved_map = {}
    if setting_val:
        try:
            saved_map = json.loads(setting_val)
        except Exception:
            saved_map = {}

    current_state = saved_map.get(canonical_id)
    if current_state is None and clean_id != canonical_id:
        current_state = saved_map.get(clean_id)
    if current_state is None:
        for alias, canon in LEGACY_TOOLSET_ALIASES.items():
            if canon == canonical_id and alias in saved_map:
                current_state = saved_map[alias]
                break
    if current_state is None:
        current_state = ANARA_TOOLSETS[canonical_id].get("default_enabled", True)

    new_state = (not current_state) if enabled is None else bool(enabled)
    saved_map[canonical_id] = new_state
    if clean_id != canonical_id:
        saved_map[clean_id] = new_state

    memory_engine.set_app_setting("toolsets_enabled_map", json.dumps(saved_map))
    logger.info(f"[Toolsets] Toggled toolset '{canonical_id}' (via '{clean_id}') -> {'ENABLED' if new_state else 'DISABLED'}")
    return True


def get_enabled_tool_names() -> Set[str]:
    """Returns the set of tool names whose toolsets are currently enabled (Anara Standard)."""
    from memory import memory_engine

    setting_val = memory_engine.get_app_setting("toolsets_enabled_map")
    saved_map = {}
    if setting_val:
        try:
            saved_map = json.loads(setting_val)
        except Exception:
            saved_map = {}

    try:
        from tools.registry import registry
        mapping = registry.get_toolsets_mapping()
        alias_resolver = getattr(registry, "resolve_name", lambda n: n)
        tool_aliases = getattr(registry, "_aliases", {})
    except Exception:
        mapping = {}
        alias_resolver = lambda n: n
        tool_aliases = {}

    enabled_tools: Set[str] = set()
    for ts_id, ts in ANARA_TOOLSETS.items():
        is_enabled = saved_map.get(ts_id)
        if is_enabled is None:
            for alias, canon in LEGACY_TOOLSET_ALIASES.items():
                if canon == ts_id and alias in saved_map:
                    is_enabled = saved_map[alias]
                    break
        if is_enabled is None:
            is_enabled = ts.get("default_enabled", True)

        if is_enabled:
            tools = list(ts.get("tools", []))
            candidate_keys = [ts_id] + [a for a, c in LEGACY_TOOLSET_ALIASES.items() if c == ts_id]
            for ck in candidate_keys:
                if ck in mapping:
                    for t in mapping[ck]:
                        if t not in tools:
                            tools.append(t)

            for t in tools:
                enabled_tools.add(t)
                resolved = alias_resolver(t)
                if resolved:
                    enabled_tools.add(resolved)

    for alias_name, target_name in tool_aliases.items():
        if target_name in enabled_tools:
            enabled_tools.add(alias_name)
        elif alias_name in enabled_tools:
            enabled_tools.add(target_name)

    return enabled_tools


# ── Anara Coding Posture & Surface Toolsets (Core Tools Parity) ──
# Universal toolset: file I/O, terminal, search, memory, agent primitives, and OS desktop control (CUA).
CODING_TOOLS: Set[str] = {
    "read_local_file",
    "edit_file",
    "write_local_file",
    "delete_local_file",
    "glob_find_files",
    "grep_search_code",
    "list_directory",
    "switch_workspace",
    "execute_cli_command",
    "process_manage",
    "execute_code",
    "web_search",
    "fetch_webpage",
    "memory",
    "manage_memory_and_todos",
    "interactive_question",
    "delegate_subagent",
    "computer_use",
    "take_screenshot",
    "skill_view",
    "learn_and_save_skill",
}
ESSENTIAL_CODING_TOOLS = CODING_TOOLS

CORE_TOOLS: List[str] = [
    "read_local_file",
    "edit_file",
    "write_local_file",
    "delete_local_file",
    "glob_find_files",
    "grep_search_code",
    "list_directory",
    "switch_workspace",
    "execute_cli_command",
    "process_manage",
    "computer_use",
    "take_screenshot",
    "vision_analyze",
    "system_control",
    "web_search",
    "web_search_images",
    "fetch_webpage",
    "send_document_file",
    "generate_file_artifact",
    "create_zip_archive",
    "memory",
    "manage_memory_and_todos",
    "skill_view",
    "learn_and_save_skill",
    "interactive_question",
    "session_search",
    "delegate_subagent",
]

# ── Platform Aliases (Anara Standard: Externalized YAML) ──
def _load_platform_aliases() -> Dict[str, str]:
    try:
        from core.prompt_loader import load_config_yaml
        cfg = load_config_yaml("config/toolset_config.yaml", default={})
        return dict(cfg.get("platform_aliases") or {
            "terminal": "cli", "bash": "cli", "powershell": "cli", "web": "web_studio",
            "code": "web_studio", "studio": "web_studio", "voice": "voice_hud",
            "hud": "voice_hud", "avatar": "voice_hud", "tele": "telegram", "wa": "whatsapp",
        })
    except Exception:
        return {
            "terminal": "cli", "bash": "cli", "powershell": "cli", "web": "web_studio",
            "code": "web_studio", "studio": "web_studio", "voice": "voice_hud",
            "hud": "voice_hud", "avatar": "voice_hud", "tele": "telegram", "wa": "whatsapp"
        }

PLATFORM_ALIASES = _load_platform_aliases()


class PlatformToolRegistry:
    """Dynamic tool resolution (Anara Standard: all platforms share the universal core tool bundle)."""

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
        Resolves active tool names for a specific platform surface and user context.
        All messaging platforms and CLI share the unified core tool suite.
        Specialized developer affordances (Kanban, HUD) and smart-home controls expand on-demand.
        """
        p_key = cls.resolve_platform_key(platform)

        # Anara Standard: Base shared suite across all platforms
        active_tools: Set[str] = set(CORE_TOOLS)

        # Web Studio / Code Station: Developer workspace affordances
        if p_key in ("web_studio", "code", "studio"):
            active_tools.update([
                "scan_workspace_folder",
                "project_hud",
                "kanban_create_task",
                "kanban_list_tasks",
                "kanban_update_task",
                "kanban_request_review",
            ])

        # Voice HUD / 3D Avatar: Voice-first media controls
        if p_key in ("voice_hud", "voice", "audio"):
            active_tools.update([
                "spotify_playback",
                "spotify_search",
                "ha_list_entities",
                "ha_call_service",
                "ha_get_state",
                "trigger_avatar_animation",
                "project_hud",
            ])

        # Dynamic Toolset Domain Activation (Anara Standard: Task-domain intent activation without brittle exclusions)
        if user_task:
            try:
                clean_task = str(user_task).lower()
                GENERIC_NOISE = {"task", "code", "file", "system", "document", "session", "memory"}
                for ts_id, ts_def in ANARA_TOOLSETS.items():
                    ts_name = ts_id.replace("_", " ").lower()
                    parts = ts_id.lower().split("_")
                    is_match = False
                    if ts_name in clean_task:
                        is_match = True
                    else:
                        for p in parts:
                            if len(p) >= 4 and p not in GENERIC_NOISE and re.search(rf"\b{re.escape(p)}\b", clean_task):
                                is_match = True
                                break

                    if is_match:
                        for t in ts_def.get("tools", []):
                            active_tools.add(t)
                        try:
                            from tools.registry import registry
                            mapping = registry.get_toolsets_mapping()
                            candidate_keys = [ts_id] + [a for a, c in LEGACY_TOOLSET_ALIASES.items() if c == ts_id]
                            for ck in candidate_keys:
                                if ck in mapping:
                                    for t in mapping[ck]:
                                        active_tools.add(t)
                        except Exception:
                            pass
            except Exception:
                pass

        # Anara Standard: Inject active Native MCP tools across all platform toolsets
        try:
            from integrations.mcp import mcp_manager
            mcp_tools = mcp_manager.get_registered_mcp_tool_names()
            if mcp_tools:
                active_tools.update(mcp_tools)
        except Exception:
            pass

        if extra_tools:
            active_tools.update(extra_tools)

        return active_tools

    @classmethod
    def get_pruned_tools_for_execution(
        cls,
        platform: Optional[str] = None,
        user_task: Optional[str] = None,
        read_only: bool = False,
        extra_tools: Optional[List[str]] = None,
    ) -> Set[str]:
        """
        Anara Enterprise Architecture: Posture-Based Dynamic Toolset Pruning.
        Zero hardcoded keyword dictionaries. Adopts Anara Coding Posture in software
        workspaces, while dynamically discovering domain tools from ToolRegistry
        when specific domain identifiers are referenced.
        """
        clean_task = (user_task or "").strip().lower()
        p_key = cls.resolve_platform_key(platform)

        # Anara Standard: Text-only and review evaluation platforms require zero tools
        if p_key in ("review", "none", "text_only", "no_tools"):
            return set()

        # 1. Start with the high-signal Anara Coding Posture
        active_tools: Set[str] = set(CODING_TOOLS)

        # 2. Platform-specific egress requirements
        if p_key in ("telegram", "whatsapp"):
            active_tools.add("send_document_file")
            active_tools.add("create_zip_archive")

        if p_key in ("voice_hud", "voice", "audio"):
            active_tools.update([
                "trigger_avatar_animation",
                "project_hud",
                "spotify_playback",
                "spotify_search",
            ])

        # 3. Dynamic Toolset Domain Activation (Anara Standard: Explicit Domain Posture Extension)
        # Dynamic Toolset Domain Activation (Anara Standard: Task-domain intent activation without brittle exclusions)
        if user_task:
            try:
                clean_task = str(user_task).lower()
                GENERIC_NOISE = {"task", "code", "file", "system", "document", "session", "memory"}
                for ts_id, ts_def in ANARA_TOOLSETS.items():
                    ts_name = ts_id.replace("_", " ").lower()
                    parts = ts_id.lower().split("_")
                    is_match = False
                    if ts_name in clean_task:
                        is_match = True
                    else:
                        for p in parts:
                            if len(p) >= 4 and p not in GENERIC_NOISE and re.search(rf"\b{re.escape(p)}\b", clean_task):
                                is_match = True
                                break

                    if is_match:
                        for t in ts_def.get("tools", []):
                            active_tools.add(t)
                        try:
                            from tools.registry import registry
                            mapping = registry.get_toolsets_mapping()
                            candidate_keys = [ts_id] + [a for a, c in LEGACY_TOOLSET_ALIASES.items() if c == ts_id]
                            for ck in candidate_keys:
                                if ck in mapping:
                                    for t in mapping[ck]:
                                        active_tools.add(t)
                        except Exception:
                            pass
            except Exception:
                pass

        if extra_tools:
            active_tools.update(extra_tools)

        # 4. Respect user's explicit toolset toggles in SQLite
        enabled_in_db = get_enabled_tool_names()
        if enabled_in_db:
            active_tools = active_tools & enabled_in_db

        # 5. Read-only gate: prune mutating tools if in read_only mode
        if read_only:
            from tools.catalog import READ_ONLY_TOOL_NAMES
            active_tools = {t for t in active_tools if t in READ_ONLY_TOOL_NAMES}

        # 6. Anara Child Safety Barrier: Subagents cannot access blocked tools
        try:
            from core.subagent import is_delegated_child_context, is_tool_blocked_for_child
            if p_key == "subagent" or is_delegated_child_context():
                active_tools = {t for t in active_tools if not is_tool_blocked_for_child(t)}
        except Exception:
            pass

        logger.info(
            f"[Toolsets] Anara Posture active ({p_key}): {len(active_tools)} tools loaded "
            f"(pruned from full catalog of {len(CORE_TOOLS)})"
        )
        return active_tools


# Alias for backward compatibility
PlatformToolFilter = PlatformToolRegistry
