"""
toolsets.py — Anara Standard 31 Toolsets Matrix & Modular Governance for Project Anara.
Groups Anara's tools into 31 cohesive, togglable toolsets with persistent status in SQLite.
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional, Set

logger = logging.getLogger(__name__)

# Complete 31-Toolset Taxonomy for Project Anara
ANARA_TOOLSETS: Dict[str, Dict[str, Any]] = {
    "clarifying_questions": {
        "id": "clarifying_questions",
        "title": "Clarifying Questions",
        "description": "Interactive multi-step questionnaire cards (Wizard) for clarifying ambiguous user tasks.",
        "icon": "help-circle",
        "category": "intelligence",
        "default_enabled": True,
        "tools": ["interactive_question"]
    },
    "web_search_scraping": {
        "id": "web_search_scraping",
        "title": "Web Search & Scraping",
        "description": "Real-time web search (DuckDuckGo/Brave) and clean Markdown content extraction.",
        "icon": "globe",
        "category": "exploration",
        "default_enabled": True,
        "tools": ["web_search", "fetch_webpage"]
    },
    "file_operations": {
        "id": "file_operations",
        "title": "File Operations",
        "description": "Workspace file operations (read, write, edit, search, glob, scan).",
        "icon": "folder",
        "category": "coding",
        "default_enabled": True,
        "tools": [
            "read_local_file",
            "write_local_file",
            "edit_file",
            "glob_find_files",
            "grep_search_code",
            "list_directory",
            "scan_workspace_folder"
        ]
    },
    "terminal_processes": {
        "id": "terminal_processes",
        "title": "Terminal & Processes",
        "description": "Sandboxed terminal command execution (PowerShell/Bash) and persistent background daemon management.",
        "icon": "terminal",
        "category": "system",
        "default_enabled": True,
        "tools": [
            "execute_cli_command",
            "process_manage"
        ]
    },
    "memory_hot": {
        "id": "memory_hot",
        "title": "Memory (Working RAM)",
        "description": "Short and mid-term working memory management (MEMORY.md and USER.md) with add, replace, and remove operations.",
        "icon": "cpu",
        "category": "memory",
        "default_enabled": True,
        "tools": ["memory", "manage_memory_and_todos"]
    },
    "session_search": {
        "id": "session_search",
        "title": "Session Search",
        "description": "Full-text search across past conversations and sessions stored in SQLite database.",
        "icon": "history",
        "category": "memory",
        "default_enabled": True,
        "tools": ["session_search"]
    },
    "skills_engine": {
        "id": "skills_engine",
        "title": "Skills Engine",
        "description": "Learn, inspect, and load technical procedures from the skill repository (agentskills.io format).",
        "icon": "book-open",
        "category": "intelligence",
        "default_enabled": True,
        "tools": [
            "learn_and_save_skill",
            "skill_view"
        ]
    },
    "task_delegation": {
        "id": "task_delegation",
        "title": "Task Delegation",
        "description": "Autonomous task delegation to independent worker subagents.",
        "icon": "users",
        "category": "system",
        "default_enabled": True,
        "tools": ["delegate_subagent"]
    },
    "digital_artifacts": {
        "id": "digital_artifacts",
        "title": "Digital Artifacts & ZIP",
        "description": "Generate downloadable documents (DOCX, PDF, CSV, Excel, TXT, MD) and manage ZIP archives.",
        "icon": "file-archive",
        "category": "coding",
        "default_enabled": True,
        "tools": [
            "generate_file_artifact",
            "create_zip_archive",
            "extract_zip_archive",
            "rezip_archive",
            "read_zip_contents"
        ]
    },
    "messaging_telegram": {
        "id": "messaging_telegram",
        "title": "Messaging: Telegram",
        "description": "Read and send messages, notifications, and status updates via Telegram bot.",
        "icon": "send",
        "category": "communication",
        "default_enabled": True,
        "tools": ["telegram_read_messages", "telegram_send_message"]
    },
    "messaging_whatsapp": {
        "id": "messaging_whatsapp",
        "title": "Messaging: WhatsApp",
        "description": "Read and send messages via local WhatsApp Web Baileys bridge.",
        "icon": "message-circle",
        "category": "communication",
        "default_enabled": True,
        "tools": ["whatsapp_read_messages", "whatsapp_send_message"]
    },
    "messaging_discord": {
        "id": "messaging_discord",
        "title": "Messaging: Discord",
        "description": "Read and send messages to Discord server channels.",
        "icon": "message-square",
        "category": "communication",
        "default_enabled": True,
        "tools": ["discord_read_messages", "discord_send_message"]
    },
    "messaging_slack": {
        "id": "messaging_slack",
        "title": "Messaging: Slack",
        "description": "Read and send messages to Slack workspace channels.",
        "icon": "hash",
        "category": "communication",
        "default_enabled": True,
        "tools": ["slack_read_messages", "slack_send_message"]
    },
    "document_delivery": {
        "id": "document_delivery",
        "title": "Document Delivery",
        "description": "Auto-dispatch digital documents (PDF, DOCX, ZIP, code) directly to WhatsApp or Telegram chats.",
        "icon": "share-2",
        "category": "communication",
        "default_enabled": True,
        "tools": ["send_document_file"]
    },
    "google_workspace": {
        "id": "google_workspace",
        "title": "Google Workspace",
        "description": "Read incoming Gmail messages and inspect Google Calendar schedules.",
        "icon": "mail",
        "category": "communication",
        "default_enabled": True,
        "tools": ["gmail_read_inbox", "calendar_get_schedule"]
    },
    "system_desktop": {
        "id": "system_desktop",
        "title": "System & Desktop",
        "description": "Launch and control desktop applications and system functions.",
        "icon": "monitor",
        "category": "system",
        "default_enabled": True,
        "tools": ["system_control"]
    },
    "visual_hud": {
        "id": "visual_hud",
        "title": "Visual HUD Projection",
        "description": "Project interactive visualizations, knowledge schematic cards, and code terminals to user HUD.",
        "icon": "layout",
        "category": "multimedia",
        "default_enabled": True,
        "tools": ["project_hud"]
    },
    "avatar_3d": {
        "id": "avatar_3d",
        "title": "Avatar 3D & Gestures",
        "description": "Drive 3D avatar animations, gestures, and expressions on screen.",
        "icon": "smile",
        "category": "multimedia",
        "default_enabled": True,
        "tools": ["trigger_avatar_animation"]
    },
    "custom_webhooks": {
        "id": "custom_webhooks",
        "title": "Custom Webhooks",
        "description": "Dispatch automated HTTP payloads to external webhooks (Discord, Zapier, n8n).",
        "icon": "webhook",
        "category": "system",
        "default_enabled": True,
        "tools": ["custom_webhook"]
    },
    "code_execution": {
        "id": "code_execution",
        "title": "Code Execution (REPL)",
        "description": "Evaluate Python and Node.js code snippets in an isolated sandboxed REPL.",
        "icon": "play",
        "category": "coding",
        "default_enabled": True,
        "tools": ["execute_code"]
    },
    "browser_automation": {
        "id": "browser_automation",
        "title": "Browser Automation",
        "description": "Automate web navigation, interaction, clicks, typing, and screenshots via Playwright.",
        "icon": "compass",
        "category": "exploration",
        "default_enabled": True,
        "tools": [
            "browser_navigate",
            "browser_click",
            "browser_type",
            "browser_snapshot",
            "browser_screenshot",
            "browser_close",
            "browser_scroll",
            "browser_press",
            "browser_back"
        ]
    },
    "spotify_music": {
        "id": "spotify_music",
        "title": "Spotify & Audio Player",
        "description": "Search and control Spotify audio and background playlist playback.",
        "icon": "music",
        "category": "multimedia",
        "default_enabled": True,
        "tools": [
            "spotify_search",
            "spotify_playback"
        ]
    },
    "home_assistant": {
        "id": "home_assistant",
        "title": "Home Assistant & IoT",
        "description": "Smart home automation and IoT device control via Home Assistant.",
        "icon": "home",
        "category": "system",
        "default_enabled": True,
        "tools": [
            "ha_list_entities",
            "ha_get_state",
            "ha_call_service"
        ]
    },
    "image_generation": {
        "id": "image_generation",
        "title": "Image Generation",
        "description": "Creative AI image generation via Pollinations Flux and DALL-E.",
        "icon": "image",
        "category": "multimedia",
        "default_enabled": True,
        "tools": ["image_generate"]
    },
    "video_generation": {
        "id": "video_generation",
        "title": "Video Generation",
        "description": "AI video generation from descriptive prompts or reference images.",
        "icon": "video",
        "category": "multimedia",
        "default_enabled": True,
        "tools": ["video_generate"]
    },
    "voice_biometrics": {
        "id": "voice_biometrics",
        "title": "Voice Biometrics & Wake Word",
        "description": "Voiceprint biometrics identification and hands-free wake word detection.",
        "icon": "mic",
        "category": "intelligence",
        "default_enabled": True,
        "tools": [
            "voice_biometrics_manage",
            "wake_word_manage"
        ]
    },
    "cron_scheduler": {
        "id": "cron_scheduler",
        "title": "Cron Scheduler",
        "description": "Schedule autonomous background tasks by time interval or cron expressions.",
        "icon": "clock",
        "category": "system",
        "default_enabled": True,
        "tools": ["cronjob_manage"]
    },
    "kanban_management": {
        "id": "kanban_management",
        "title": "Kanban Multi-Agent Board",
        "description": "Multi-agent Kanban task board coordination (To Do, In Progress, Review, Blocked, Done).",
        "icon": "clipboard",
        "category": "system",
        "default_enabled": True,
        "tools": [
            "kanban_create_task",
            "kanban_list_tasks",
            "kanban_update_task",
            "kanban_request_review"
        ]
    },
    "mcp_protocol": {
        "id": "mcp_protocol",
        "title": "Model Context Protocol (MCP)",
        "description": "External Model Context Protocol (MCP) server connection management (stdio and HTTP/SSE).",
        "icon": "cpu",
        "category": "intelligence",
        "default_enabled": True,
        "tools": ["mcp_manage"]
    },
    "computer_use": {
        "id": "computer_use",
        "title": "Computer Use (OS Desktop)",
        "description": "OS-level desktop automation (screenshots, mouse click, drag, keyboard typing and hotkeys).",
        "icon": "monitor",
        "category": "system",
        "default_enabled": True,
        "tools": ["computer_use", "take_screenshot"]
    },
    "vision": {
        "id": "vision",
        "title": "Vision & Video Analysis",
        "description": "Deep image OCR, diagram inspection, and video analysis tools.",
        "icon": "eye",
        "category": "multimedia",
        "default_enabled": True,
        "tools": ["vision_analyze", "video_analyze"]
    }
}


def get_toolsets_status() -> List[Dict[str, Any]]:
    """Returns all 31 toolsets with their live enabled/disabled toggle states."""
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
        is_enabled = saved_map.get(ts_id, ts.get("default_enabled", True))
        item = dict(ts)
        dyn_tools = mapping.get(ts_id) or ts.get("tools", [])
        item["tools"] = dyn_tools
        item["enabled"] = bool(is_enabled)
        item["tool_count"] = len(dyn_tools)
        result.append(item)

    return result


def toggle_toolset(toolset_id: str, enabled: Optional[bool] = None) -> bool:
    """Toggles or sets the enabled state of a specific toolset."""
    from memory import memory_engine

    clean_id = (toolset_id or "").strip().lower()
    if clean_id not in ANARA_TOOLSETS:
        return False

    setting_val = memory_engine.get_app_setting("toolsets_enabled_map")
    saved_map = {}
    if setting_val:
        try:
            saved_map = json.loads(setting_val)
        except Exception:
            saved_map = {}

    current_state = saved_map.get(clean_id, ANARA_TOOLSETS[clean_id].get("default_enabled", True))
    new_state = (not current_state) if enabled is None else bool(enabled)
    saved_map[clean_id] = new_state

    memory_engine.set_app_setting("toolsets_enabled_map", json.dumps(saved_map))
    logger.info(f"[Toolsets] Toggled toolset '{clean_id}' -> {'ENABLED' if new_state else 'DISABLED'}")
    return True


def get_enabled_tool_names() -> Set[str]:
    """Returns the set of tool names whose toolsets are currently enabled (Hermes Parity)."""
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

    enabled_tools: Set[str] = set()
    for ts_id, ts in ANARA_TOOLSETS.items():
        is_enabled = saved_map.get(ts_id, ts.get("default_enabled", True))
        if is_enabled:
            dyn_tools = mapping.get(ts_id) or ts.get("tools", [])
            for t in dyn_tools:
                enabled_tools.add(t)

    return enabled_tools


# ── Hermes Coding Posture & Surface Toolsets (_HERMES_CORE_TOOLS Parity) ──
# Universal toolset: file I/O, terminal, search, memory, agent primitives, and OS desktop control (CUA).
CODING_TOOLS: Set[str] = {
    "read_local_file",
    "edit_file",
    "write_local_file",
    "delete_local_file",
    "glob_find_files",
    "grep_search_code",
    "list_directory",
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

# ── Platform Aliases (Hermes Parity: Externalized YAML) ──
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
    """Dynamic tool resolution (Hermes Parity: all platforms share the universal core tool bundle)."""

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

        # Hermes Parity: Base shared suite across all platforms
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

        # Dynamic Toolset Domain Activation (Hermes Parity: Explicit Domain Posture Extension)
        if user_task:
            try:
                clean_task = str(user_task).lower()
                GENERIC_DOMAIN_ROOTS = {"task", "home", "code", "file", "system", "document", "session", "memory"}
                for ts_id, ts_def in ANARA_TOOLSETS.items():
                    ts_name = ts_id.replace("_", " ").lower()
                    domain_root = ts_id.split("_")[0].lower()
                    is_match = False
                    if domain_root not in GENERIC_DOMAIN_ROOTS and len(domain_root) >= 4 and re.search(rf"\b{re.escape(domain_root)}\b", clean_task):
                        is_match = True
                    elif re.search(rf"\b{re.escape(ts_name)}\b", clean_task):
                        is_match = True

                    if is_match:
                        for t in ts_def.get("tools", []):
                            active_tools.add(t)
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
        Hermes & Claude Code Parity: Posture-Based Dynamic Toolset Pruning.
        Zero hardcoded keyword dictionaries. Adopts Hermes Coding Posture in software
        workspaces, while dynamically discovering domain tools from ToolRegistry
        when specific domain identifiers are referenced.
        """
        clean_task = (user_task or "").strip().lower()
        p_key = cls.resolve_platform_key(platform)

        # 1. Start with the high-signal Hermes Coding Posture
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

        # 3. Dynamic Toolset Domain Activation (Hermes Parity: Explicit Domain Posture Extension)
        if user_task:
            try:
                GENERIC_DOMAIN_ROOTS = {"task", "home", "code", "file", "system", "document", "session", "memory"}
                for ts_id, ts_def in ANARA_TOOLSETS.items():
                    ts_name = ts_id.replace("_", " ").lower()
                    domain_root = ts_id.split("_")[0].lower()
                    is_match = False
                    if domain_root not in GENERIC_DOMAIN_ROOTS and len(domain_root) >= 4 and re.search(rf"\b{re.escape(domain_root)}\b", clean_task):
                        is_match = True
                    elif re.search(rf"\b{re.escape(ts_name)}\b", clean_task):
                        is_match = True

                    if is_match:
                        for t in ts_def.get("tools", []):
                            active_tools.add(t)
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

        logger.info(
            f"[Toolsets] Hermes Posture active ({p_key}): {len(active_tools)} tools loaded "
            f"(pruned from full catalog of {len(CORE_TOOLS)})"
        )
        return active_tools


# Alias for backward compatibility
PlatformToolFilter = PlatformToolRegistry
