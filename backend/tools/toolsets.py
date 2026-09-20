"""
toolsets.py — Anara Standard 24 Toolsets Matrix & Modular Governance for Project Anara.
Groups Anara's tools into 24 cohesive, togglable toolsets with persistent status in SQLite.
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional, Set

logger = logging.getLogger(__name__)

# Complete 24-Toolset Taxonomy for Project Anara
ANARA_TOOLSETS: Dict[str, Dict[str, Any]] = {
    "clarifying_questions": {
        "id": "clarifying_questions",
        "title": "Clarifying Questions",
        "description": "Kuesioner bertahap (Interactive Wizard Card) untuk memperjelas tujuan pengguna jika perintah ambigu.",
        "icon": "help-circle",
        "category": "intelligence",
        "default_enabled": True,
        "tools": ["interactive_question"]
    },
    "web_search_scraping": {
        "id": "web_search_scraping",
        "title": "Web Search & Scraping",
        "description": "Pencarian web real-time (DuckDuckGo/Brave) dan ekstraksi konten laman bersih dalam format Markdown.",
        "icon": "globe",
        "category": "exploration",
        "default_enabled": True,
        "tools": ["web_search", "fetch_webpage"]
    },
    "file_operations": {
        "id": "file_operations",
        "title": "File Operations",
        "description": "Membaca, menulis, menyunting, mencari, dan menelusuri berkas maupun folder di dalam workspace proyek.",
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
        "description": "Eksekusi perintah terminal shell aman (PowerShell/Bash) serta pengelolaan daemon/proses background persisten.",
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
        "description": "Manajemen memori jangka pendek & menengah (MEMORY.md dan USER.md) dengan operasi add, replace, remove.",
        "icon": "cpu",
        "category": "memory",
        "default_enabled": True,
        "tools": ["memory", "manage_memory_and_todos"]
    },
    "session_search": {
        "id": "session_search",
        "title": "Session Search",
        "description": "Mencari seluruh riwayat percakapan dan sesi lampau di database SQLite (long-term conversational recall).",
        "icon": "history",
        "category": "memory",
        "default_enabled": True,
        "tools": ["session_search"]
    },
    "skills_engine": {
        "id": "skills_engine",
        "title": "Skills Engine",
        "description": "Mempelajari, memeriksa, dan memuat prosedur teknis lengkap dari repositori 90+ keahlian (agentskills.io format).",
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
        "description": "Pendelegasian tugas eksplorasi atau riset mandiri ke sub-agent pekerja independen.",
        "icon": "users",
        "category": "system",
        "default_enabled": True,
        "tools": ["delegate_subagent"]
    },
    "digital_artifacts": {
        "id": "digital_artifacts",
        "title": "Digital Artifacts & ZIP",
        "description": "Membuat dokumen berkas (DOCX Word, PDF, CSV, Excel, TXT, MD) dan pembuatan/ekstraksi arsip ZIP.",
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
        "description": "Membaca dan mengirimkan pesan teks, perintah, atau update status melalui bot Telegram resmi.",
        "icon": "send",
        "category": "communication",
        "default_enabled": True,
        "tools": ["telegram_read_messages", "telegram_send_message"]
    },
    "messaging_whatsapp": {
        "id": "messaging_whatsapp",
        "title": "Messaging: WhatsApp",
        "description": "Membaca dan mengirimkan pesan percakapan melalui WhatsApp Web Baileys Bridge lokal.",
        "icon": "message-circle",
        "category": "communication",
        "default_enabled": True,
        "tools": ["whatsapp_read_messages", "whatsapp_send_message"]
    },
    "messaging_discord": {
        "id": "messaging_discord",
        "title": "Messaging: Discord",
        "description": "Membaca dan mengirimkan pesan ke channel server Discord resmi.",
        "icon": "message-square",
        "category": "communication",
        "default_enabled": True,
        "tools": ["discord_read_messages", "discord_send_message"]
    },
    "messaging_slack": {
        "id": "messaging_slack",
        "title": "Messaging: Slack",
        "description": "Membaca dan mengirimkan pesan ke channel workspace Slack.",
        "icon": "hash",
        "category": "communication",
        "default_enabled": True,
        "tools": ["slack_read_messages", "slack_send_message"]
    },
    "document_delivery": {
        "id": "document_delivery",
        "title": "Document Delivery",
        "description": "Mengirimkan berkas dokumen digital (PDF, DOCX, ZIP, Code) langsung ke chat WhatsApp atau Telegram.",
        "icon": "share-2",
        "category": "communication",
        "default_enabled": True,
        "tools": ["send_document_file"]
    },
    "google_workspace": {
        "id": "google_workspace",
        "title": "Google Workspace",
        "description": "Membaca pesan email masuk Gmail dan memeriksa jadwal acara di Google Calendar.",
        "icon": "mail",
        "category": "communication",
        "default_enabled": True,
        "tools": ["gmail_read_inbox", "calendar_get_schedule"]
    },
    "system_desktop": {
        "id": "system_desktop",
        "title": "System & Desktop",
        "description": "Membuka aplikasi komputer lokal Windows (Spotify, VS Code, Browser, Notepad, Calculator).",
        "icon": "monitor",
        "category": "system",
        "default_enabled": True,
        "tools": ["system_control"]
    },
    "visual_hud": {
        "id": "visual_hud",
        "title": "Visual HUD Projection",
        "description": "Memproyeksikan visualisasi interaktif, kartu pengetahuan, dan terminal kode ke layar HUD pengguna.",
        "icon": "layout",
        "category": "multimedia",
        "default_enabled": True,
        "tools": ["project_hud"]
    },
    "avatar_3d": {
        "id": "avatar_3d",
        "title": "Avatar 3D & Gestures",
        "description": "Menggerakkan ekspresi wajah, tarian (Rumba), salam, dan gestur avatar 3D Anara di layar.",
        "icon": "smile",
        "category": "multimedia",
        "default_enabled": True,
        "tools": ["trigger_avatar_animation"]
    },
    "custom_webhooks": {
        "id": "custom_webhooks",
        "title": "Custom Webhooks",
        "description": "Mengirimkan payload HTTP request otomatis ke URL webhook luar (Discord, Zapier, n8n).",
        "icon": "webhook",
        "category": "system",
        "default_enabled": True,
        "tools": ["custom_webhook"]
    },
    "code_execution": {
        "id": "code_execution",
        "title": "Code Execution (REPL)",
        "description": "Mengevaluasi cuplikan kode Python, Node.js, atau skrip secara terisolasi.",
        "icon": "play",
        "category": "coding",
        "default_enabled": True,
        "tools": ["execute_code"]
    },
    "browser_automation": {
        "id": "browser_automation",
        "title": "Browser Automation",
        "description": "Otomasi navigasi web, pencarian/pemutaran video YouTube, pengambilan screenshot, scroll, dan interaksi browser via Playwright.",
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
        "description": "Pemutaran musik, pencarian lagu, dan kontrol playlist pemutar audio latar belakang Anara.",
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
        "description": "Kontrol perangkat pintar rumah tangga, lampu, dan sensor IoT melalui gateway Home Assistant.",
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
        "description": "Pembuatan gambar digital kreatif berbasis AI menggunakan Pollinations Flux dan DALL-E.",
        "icon": "image",
        "category": "multimedia",
        "default_enabled": True,
        "tools": ["image_generate"]
    },
    "video_generation": {
        "id": "video_generation",
        "title": "Video Generation",
        "description": "Pembuatan video digital AI pendek berbasis teks atau gambar referensi menggunakan CogVideoX.",
        "icon": "video",
        "category": "multimedia",
        "default_enabled": True,
        "tools": ["video_generate"]
    },
    "voice_biometrics": {
        "id": "voice_biometrics",
        "title": "Voice Biometrics & Wake Word",
        "description": "Pengenalan identitas pengguna berdasarkan pola sidik suara dan deteksi panggilan suara hands-free ('Hey Anara').",
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
        "description": "Penjadwalan tugas otonom berkala di latar belakang berdasarkan interval waktu atau cron.",
        "icon": "clock",
        "category": "system",
        "default_enabled": True,
        "tools": ["cronjob_manage"]
    },
    "kanban_management": {
        "id": "kanban_management",
        "title": "Kanban Multi-Agent Board",
        "description": "Koordinasi papan tugas multi-agen (To Do, In Progress, Review, Blocked, Done).",
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
        "description": "Integrasi dan manajemen koneksi server MCP eksternal (stdio dan HTTP/SSE).",
        "icon": "cpu",
        "category": "intelligence",
        "default_enabled": True,
        "tools": ["mcp_manage"]
    },
    "computer_use": {
        "id": "computer_use",
        "title": "Computer Use (OS Desktop)",
        "description": "Otomasi layar desktop tingkat OS Windows (tangkapan layar, mouse click, drag, keyboard type & press).",
        "icon": "monitor",
        "category": "system",
        "default_enabled": True,
        "tools": ["computer_use"]
    }
}


def get_toolsets_status() -> List[Dict[str, Any]]:
    """Returns all 24 toolsets with their live enabled/disabled toggle states."""
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


# ── Surface-specific toolset filtering (Hermes Parity: _HERMES_CORE_TOOLS) ──
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
    "manage_scratchpad",
]

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

        # Dynamic On-Demand Tool Expansion (Hermes Parity: zero static keyword regexes)
        if user_task:
            try:
                from tools.registry import registry
                task_tokens = set(re.findall(r"\w+", str(user_task).lower()))
                for name, tool_def in registry._tools.items():
                    name_segments = set(name.lower().split("_"))
                    cat_segments = set(tool_def.category.lower().split("_")) if getattr(tool_def, "category", None) else set()
                    ts_segments = set(tool_def.toolset.lower().split("_")) if getattr(tool_def, "toolset", None) else set()
                    if (name_segments | cat_segments | ts_segments) & task_tokens:
                        active_tools.add(name)
            except Exception:
                pass

        if extra_tools:
            active_tools.update(extra_tools)

        return active_tools


# Alias for backward compatibility
PlatformToolFilter = PlatformToolRegistry
