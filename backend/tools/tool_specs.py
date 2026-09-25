"""
tool_specs.py — Declarative Tool Specifications & Auto-Registration for Project Anara.
Anara Standard: decentralized schema declarations with risk taxonomy and handlers.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from .registry import registry

from .fs_tools import (
    _tool_read_local_file,
    _tool_edit_file,
    _tool_write_local_file,
    _tool_delete_local_file,
    _tool_list_directory,
    _tool_scan_workspace_folder,
    _tool_glob_find_files,
    _tool_grep_search_code,
)
from .artifact_tools import (
    _tool_generate_file_artifact,
    _tool_create_zip_archive,
    _tool_extract_zip_archive,
    _tool_read_zip_contents,
    _tool_rezip_archive,
    _tool_send_document_file,
)
from .web_tools import (
    _tool_web_search,
    _tool_web_search_images,
    _tool_fetch_webpage,
    _tool_custom_webhook,
)
from .system_tools import (
    _tool_execute_cli_command,
    _tool_manage_memory_and_todos,
    _tool_anara_memory,
    _tool_session_search,
    _tool_system_control,
    _tool_project_hud,
    _tool_delegate_subagent,
    _tool_trigger_avatar_animation,
    _tool_learn_and_save_skill,
    _tool_skill_view,
    _tool_interactive_question,
)
from .browser_tools import (
    _tool_browser_navigate,
    _tool_browser_click,
    _tool_browser_type,
    _tool_browser_snapshot,
    _tool_browser_screenshot,
    _tool_browser_close,
    _tool_browser_scroll,
    _tool_browser_press,
    _tool_browser_back,
)
from .spotify_tools import (
    _tool_spotify_search,
    _tool_spotify_playback,
)
from .cron_tools import _tool_cronjob_manage
from .image_tools import _tool_image_generate
from .video_tools import _tool_video_generate
from .vision_tools import _tool_vision_analyze, _tool_video_analyze
from .ha_tools import (
    _tool_ha_list_entities,
    _tool_ha_get_state,
    _tool_ha_call_service,
)
from .voice_tools import (
    _tool_voice_biometrics_manage,
    _tool_wake_word_manage,
)
from .code_execution_tools import _tool_execute_code
from .computer_use_tool import _tool_computer_use
from .mcp_tools import _tool_mcp_manage
from .process_tools import _tool_process_manage
from .kanban_tools import (
    _tool_kanban_create_task,
    _tool_kanban_list_tasks,
    _tool_kanban_update_task,
    _tool_kanban_request_review,
)
from .messaging_tools import (
    _tool_discord_send_message,
    _tool_discord_read_messages,
    _tool_slack_send_message,
    _tool_slack_read_messages,
    _tool_whatsapp_read_messages,
    _tool_whatsapp_send_message,
    _tool_telegram_read_messages,
    _tool_telegram_send_message,
)

logger = logging.getLogger(__name__)


async def _tool_gmail_read_inbox(limit: int = 5) -> Dict[str, Any]:
    from integrations import get_unread_emails, get_google_status
    st = await get_google_status()
    if st.get("status") != "connected":
        return {"status": "error", "message": "Google Workspace account not linked."}
    emails = await get_unread_emails(limit=limit)
    return {"status": "success", "emails": emails}


async def _tool_calendar_get_schedule(days: int = 3) -> Dict[str, Any]:
    from integrations import get_upcoming_events, get_google_status
    st = await get_google_status()
    if st.get("status") != "connected":
        return {"status": "error", "message": "Google Workspace account not linked."}
    events = await get_upcoming_events(days=days)
    return {"status": "success", "events": events}


# All 66 Tool Specifications (Anara Standard)
async def _tool_take_screenshot(title: Optional[str] = None, text: Optional[str] = None, **kw: Any) -> Dict[str, Any]:
    return await _tool_computer_use(action="screenshot", text=title or text)


ALL_TOOL_SPECS: List[Dict[str, Any]] = [
    # ── Digital Artifacts ──
    {
        "name": "generate_file_artifact",
        "description": "Generates a digital document artifact in official formats (DOCX, PDF, CSV, Excel, TXT, MD, Python, JS, JSON).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "filename": {"type": "STRING", "description": "Full filename with extension, e.g. 'proposal.docx', 'report.pdf'."},
                "content": {"type": "STRING", "description": "Complete text or code content for the document."},
                "title": {"type": "STRING", "description": "Official document title header."},
                "destination_folder": {"type": "STRING", "description": "Local destination folder path (optional)."}
            },
            "required": ["filename", "content"]
        },
        "handler": _tool_generate_file_artifact,
        "risk": "mutating",
        "toolset": "digital_artifacts",
        "category": "coding",
        "icon": "file-archive",
    },
    {
        "name": "create_zip_archive",
        "description": "Compresses files or directories into a ZIP archive.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "archive_name": {"type": "STRING", "description": "Target zip archive name, e.g. 'project.zip'."},
                "folder_path": {"type": "STRING", "description": "Project folder path to compress."},
                "files": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of specific files to include in zip."}
            }
        },
        "handler": _tool_create_zip_archive,
        "risk": "mutating",
        "toolset": "digital_artifacts",
        "category": "coding",
        "icon": "file-archive",
    },
    {
        "name": "extract_zip_archive",
        "description": "Extracts files from a ZIP archive to a destination directory.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "zip_path": {"type": "STRING", "description": "Path to the ZIP file to extract."},
                "destination_folder": {"type": "STRING", "description": "Destination directory for extracted files."}
            },
            "required": ["zip_path"]
        },
        "handler": _tool_extract_zip_archive,
        "risk": "mutating",
        "toolset": "digital_artifacts",
        "category": "coding",
        "icon": "file-archive",
    },
    {
        "name": "rezip_archive",
        "description": "Adds, overwrites, or removes files in an existing ZIP archive without fully unpacking.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "zip_path": {"type": "STRING", "description": "Target ZIP file path to update."},
                "files_to_add": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of local file paths to add or overwrite."},
                "files_to_remove": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of file names inside the ZIP to remove."},
                "output_path": {"type": "STRING", "description": "Output path for the updated ZIP file."}
            },
            "required": ["zip_path", "files_to_add"]
        },
        "handler": _tool_rezip_archive,
        "risk": "mutating",
        "toolset": "digital_artifacts",
        "category": "coding",
        "icon": "file-archive",
    },
    {
        "name": "read_zip_contents",
        "description": "Inspects and lists files inside a ZIP archive with compressed/uncompressed sizes (read-only).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "zip_path": {"type": "STRING", "description": "Path to the ZIP file to inspect."}
            },
            "required": ["zip_path"]
        },
        "handler": _tool_read_zip_contents,
        "risk": "read_only",
        "toolset": "digital_artifacts",
        "category": "coding",
        "icon": "file-archive",
    },
    {
        "name": "send_document_file",
        "description": "Dispatches a local document, photo, video, or file directly to Telegram or WhatsApp chat.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Local file path or URL to send."},
                "channel": {"type": "STRING", "description": "Target channel ('telegram' or 'whatsapp')."},
                "recipient": {"type": "STRING", "description": "Target chat ID or phone number."},
                "caption": {"type": "STRING", "description": "Optional message caption."}
            },
            "required": ["file_path"]
        },
        "handler": _tool_send_document_file,
        "risk": "action",
        "toolset": "document_delivery",
        "category": "communication",
        "icon": "share-2",
    },

    # ── Web Search & Scraping ──
    {
        "name": "web_search",
        "description": "Searches the live web for real-time information, documentation, news, and facts.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"query": {"type": "STRING", "description": "Specific search query."}},
            "required": ["query"]
        },
        "handler": _tool_web_search,
        "risk": "read_only",
        "toolset": "web_search_scraping",
        "category": "exploration",
        "icon": "globe",
    },
    {
        "name": "web_search_images",
        "description": "Searches the web for relevant images and photos.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Image search keywords."},
                "limit": {"type": "INTEGER", "description": "Maximum number of images (default 4)."}
            },
            "required": ["query"]
        },
        "handler": _tool_web_search_images,
        "risk": "read_only",
        "toolset": "web_search_scraping",
        "category": "exploration",
        "icon": "globe",
    },
    {
        "name": "fetch_webpage",
        "description": "Fetches and parses readable Markdown content from a web URL.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"url": {"type": "STRING", "description": "Web URL to fetch."}},
            "required": ["url"]
        },
        "handler": _tool_fetch_webpage,
        "risk": "read_only",
        "toolset": "web_search_scraping",
        "category": "exploration",
        "icon": "globe",
    },

    # ── File Operations ──
    {
        "name": "read_local_file",
        "description": "Reads file content from workspace with line numbers and pagination offset/limit.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Workspace file path."},
                "offset": {"type": "INTEGER", "description": "Starting line number (1-indexed)."},
                "limit": {"type": "INTEGER", "description": "Maximum lines to read."}
            },
            "required": ["file_path"]
        },
        "handler": _tool_read_local_file,
        "risk": "read_only",
        "toolset": "file_operations",
        "category": "coding",
        "icon": "folder",
    },
    {
        "name": "edit_file",
        "description": "Performs exact string replacements in workspace files.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Relative file path to edit."},
                "old_string": {"type": "STRING", "description": "Exact text to replace."},
                "new_string": {"type": "STRING", "description": "New replacement text."},
                "replace_all": {"type": "BOOLEAN", "description": "Replace all occurrences if true."}
            },
            "required": ["file_path", "old_string", "new_string"]
        },
        "handler": _tool_edit_file,
        "risk": "mutating",
        "toolset": "file_operations",
        "category": "coding",
        "icon": "folder",
    },
    {
        "name": "glob_find_files",
        "description": "Fast file pattern matching across project files (e.g. '**/*.tsx').",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "pattern": {"type": "STRING", "description": "Glob pattern to match."},
                "path": {"type": "STRING", "description": "Starting search directory."}
            },
            "required": ["pattern"]
        },
        "handler": _tool_glob_find_files,
        "risk": "read_only",
        "toolset": "file_operations",
        "category": "coding",
        "icon": "folder",
    },
    {
        "name": "grep_search_code",
        "description": "Fast regex content search across project source files.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "pattern": {"type": "STRING", "description": "Regex pattern or keywords."},
                "path": {"type": "STRING", "description": "Starting directory."},
                "include": {"type": "STRING", "description": "File pattern to include (e.g. '*.ts')."}
            },
            "required": ["pattern"]
        },
        "handler": _tool_grep_search_code,
        "risk": "read_only",
        "toolset": "file_operations",
        "category": "coding",
        "icon": "folder",
    },
    {
        "name": "write_local_file",
        "description": "Writes or overwrites a file in the workspace.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Relative path and file name to write."},
                "content": {"type": "STRING", "description": "Complete file content to write."}
            },
            "required": ["file_path", "content"]
        },
        "handler": _tool_write_local_file,
        "risk": "mutating",
        "toolset": "file_operations",
        "category": "coding",
        "icon": "folder",
    },
    {
        "name": "delete_local_file",
        "description": "Deletes a targeted individual file in the workspace. Mass wildcards (*) and directory deletions are restricted.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Specific file path to delete (e.g. 'temp.txt' or 'src/old.py')."}
            },
            "required": ["file_path"]
        },
        "handler": _tool_delete_local_file,
        "risk": "mutating",
        "toolset": "file_operations",
        "category": "coding",
        "icon": "trash",
    },
    {
        "name": "list_directory",
        "description": "Lists files and subdirectories in a directory path (read-only).",
        "parameters": {
            "type": "OBJECT",
            "properties": {"directory_path": {"type": "STRING", "description": "Directory path (optional)."}}
        },
        "handler": _tool_list_directory,
        "risk": "read_only",
        "toolset": "file_operations",
        "category": "coding",
        "icon": "folder",
    },
    {
        "name": "scan_workspace_folder",
        "description": "Scans and indexes the hierarchy of a workspace folder (file tree).",
        "parameters": {
            "type": "OBJECT",
            "properties": {"folder_path": {"type": "STRING", "description": "Project folder path."}},
            "required": ["folder_path"]
        },
        "handler": _tool_scan_workspace_folder,
        "risk": "read_only",
        "toolset": "file_operations",
        "category": "coding",
        "icon": "folder",
    },

    # ── Terminal & Processes ──
    {
        "name": "execute_cli_command",
        "description": "Executes shell commands in the host workspace terminal (git, npm, dir, python, curl).",
        "parameters": {
            "type": "OBJECT",
            "properties": {"command": {"type": "STRING", "description": "Terminal command to execute."}},
            "required": ["command"]
        },
        "handler": _tool_execute_cli_command,
        "risk": "mutating",
        "toolset": "terminal_processes",
        "category": "system",
        "icon": "terminal",
    },
    {
        "name": "process_manage",
        "description": "Supervises background processes and daemons with real-time log tailing.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Action: 'start', 'list', 'logs', 'stop'."},
                "command": {"type": "STRING", "description": "CLI command to run in background."},
                "process_id": {"type": "STRING", "description": "Process identifier."},
                "cwd": {"type": "STRING", "description": "Working directory."},
                "lines": {"type": "INTEGER", "description": "Number of recent log lines to tail."}
            },
            "required": ["action"]
        },
        "handler": _tool_process_manage,
        "risk": "mutating",
        "toolset": "terminal_processes",
        "category": "system",
        "icon": "terminal",
    },

    # ── Memory & Context ──
    {
        "name": "manage_memory_and_todos",
        "description": "Manages personal to-do list items and working tasks (add, list, toggle, delete).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Action: 'add', 'list', 'toggle', 'delete'."},
                "title": {"type": "STRING", "description": "Task or note title."},
                "content": {"type": "STRING", "description": "Task or note description."},
                "category": {"type": "STRING", "description": "Category ('todo', 'note', 'reminder')."},
                "item_id": {"type": "INTEGER", "description": "Item ID for toggle/delete."}
            },
            "required": ["action"]
        },
        "handler": _tool_manage_memory_and_todos,
        "risk": "action",
        "toolset": "memory_hot",
        "category": "memory",
        "icon": "cpu",
    },
    {
        "name": "memory",
        "description": "Curated persistent memory manager: Adds, replaces, or removes entries in MEMORY.md and USER.md.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Action: 'add', 'replace', 'remove'."},
                "target": {"type": "STRING", "description": "Target: 'memory' (agent notes) or 'user' (user profile)."},
                "content": {"type": "STRING", "description": "New memory content."},
                "old_text": {"type": "STRING", "description": "Old text substring to replace or remove."}
            },
            "required": ["action"]
        },
        "handler": _tool_anara_memory,
        "risk": "action",
        "toolset": "memory_hot",
        "category": "memory",
        "icon": "cpu",
    },
    {
        "name": "session_search",
        "description": "Full-text search across past conversations and sessions stored in SQLite database.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Keywords or search topic."},
                "limit": {"type": "INTEGER", "description": "Maximum sessions to return."}
            },
            "required": ["query"]
        },
        "handler": _tool_session_search,
        "risk": "read_only",
        "toolset": "session_search",
        "category": "memory",
        "icon": "history",
    },

    # ── System Control & Desktop ──
    {
        "name": "system_control",
        "description": "Launches local desktop applications (Spotify, VS Code, Browser, Notepad, Calculator) or web URLs.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Action ('open')."},
                "target": {"type": "STRING", "description": "Application name or executable path to launch."},
                "arguments": {"type": "STRING", "description": "Optional CLI arguments or web URL."},
                "url": {"type": "STRING", "description": "Destination URL."}
            },
            "required": ["action"]
        },
        "handler": _tool_system_control,
        "risk": "ask",
        "toolset": "system_desktop",
        "category": "system",
        "icon": "monitor",
    },
    {
        "name": "custom_webhook",
        "description": "Dispatches automated HTTP request payloads to external webhook endpoints (Discord, Zapier, n8n, Slack).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING", "description": "Target webhook URL."},
                "method": {"type": "STRING", "description": "HTTP method ('POST', 'GET', 'PUT')."},
                "payload_json": {"type": "STRING", "description": "JSON payload string."}
            },
            "required": ["url"]
        },
        "handler": _tool_custom_webhook,
        "risk": "action",
        "toolset": "custom_webhooks",
        "category": "system",
        "icon": "webhook",
    },
    {
        "name": "project_hud",
        "description": "Projects interactive visualizations, knowledge cards, and code terminals to user HUD.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "visual_type": {"type": "STRING", "description": "Visual card type ('knowledge_card', 'code_box', 'system_hud')."},
                "title": {"type": "STRING", "description": "Visual title."},
                "summary": {"type": "STRING", "description": "Visual summary text."},
                "specs_json": {"type": "STRING", "description": "Supplementary JSON specs data."}
            },
            "required": ["visual_type", "title", "summary"]
        },
        "handler": _tool_project_hud,
        "risk": "read_only",
        "toolset": "visual_hud",
        "category": "multimedia",
        "icon": "layout",
    },

    # ── Messaging Platforms ──
    {
        "name": "whatsapp_read_messages",
        "description": "Reads incoming chat messages from the connected WhatsApp Web bridge.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"unread_only": {"type": "BOOLEAN", "description": "Fetch unread messages only."}}
        },
        "handler": _tool_whatsapp_read_messages,
        "risk": "read_only",
        "toolset": "messaging_whatsapp",
        "category": "communication",
        "icon": "message-circle",
    },
    {
        "name": "whatsapp_send_message",
        "description": "Sends a chat message to a specific contact or phone number via WhatsApp Web.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "recipient": {"type": "STRING", "description": "Target contact name or phone number."},
                "message": {"type": "STRING", "description": "Text message content to send."}
            },
            "required": ["recipient", "message"]
        },
        "handler": _tool_whatsapp_send_message,
        "risk": "action",
        "toolset": "messaging_whatsapp",
        "category": "communication",
        "icon": "message-circle",
    },
    {
        "name": "telegram_read_messages",
        "description": "Reads recent incoming messages from Telegram bot channel.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"limit": {"type": "INTEGER", "description": "Maximum number of messages."}}
        },
        "handler": _tool_telegram_read_messages,
        "risk": "read_only",
        "toolset": "messaging_telegram",
        "category": "communication",
        "icon": "send",
    },
    {
        "name": "telegram_send_message",
        "description": "Sends a message to user or group via Telegram bot.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "message": {"type": "STRING", "description": "Text message content to send."},
                "chat_id": {"type": "STRING", "description": "Target chat/group ID (optional)."}
            },
            "required": ["message"]
        },
        "handler": _tool_telegram_send_message,
        "risk": "action",
        "toolset": "messaging_telegram",
        "category": "communication",
        "icon": "send",
    },
    {
        "name": "discord_read_messages",
        "description": "Reads recent incoming messages from a Discord channel.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "channel_id": {"type": "STRING", "description": "Discord channel ID."},
                "limit": {"type": "INTEGER", "description": "Maximum messages to retrieve (default 10)."}
            }
        },
        "handler": _tool_discord_read_messages,
        "risk": "read_only",
        "toolset": "messaging_discord",
        "category": "communication",
        "icon": "message-square",
    },
    {
        "name": "discord_send_message",
        "description": "Sends a text message to a Discord channel.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "text": {"type": "STRING", "description": "Text message content to send."},
                "channel_id": {"type": "STRING", "description": "Target Discord channel ID."}
            },
            "required": ["text"]
        },
        "handler": _tool_discord_send_message,
        "risk": "action",
        "toolset": "messaging_discord",
        "category": "communication",
        "icon": "message-square",
    },
    {
        "name": "slack_read_messages",
        "description": "Reads recent message history from a Slack channel.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "channel": {"type": "STRING", "description": "Slack channel ID."},
                "limit": {"type": "INTEGER", "description": "Maximum messages to retrieve (default 10)."}
            }
        },
        "handler": _tool_slack_read_messages,
        "risk": "read_only",
        "toolset": "messaging_slack",
        "category": "communication",
        "icon": "hash",
    },
    {
        "name": "slack_send_message",
        "description": "Sends a text message to a Slack channel.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "text": {"type": "STRING", "description": "Text message content to send."},
                "channel": {"type": "STRING", "description": "Target Slack channel ID."}
            },
            "required": ["text"]
        },
        "handler": _tool_slack_send_message,
        "risk": "action",
        "toolset": "messaging_slack",
        "category": "communication",
        "icon": "hash",
    },

    # ── Google Workspace ──
    {
        "name": "gmail_read_inbox",
        "description": "Reads recent emails from user's Gmail inbox.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"limit": {"type": "INTEGER", "description": "Maximum number of emails to retrieve."}}
        },
        "handler": _tool_gmail_read_inbox,
        "risk": "read_only",
        "toolset": "google_workspace",
        "category": "communication",
        "icon": "mail",
    },
    {
        "name": "calendar_get_schedule",
        "description": "Retrieves upcoming events and schedule from Google Calendar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"days": {"type": "INTEGER", "description": "Number of upcoming days to inspect (default 3)."}}
        },
        "handler": _tool_calendar_get_schedule,
        "risk": "read_only",
        "toolset": "google_workspace",
        "category": "communication",
        "icon": "mail",
    },

    # ── Avatar & Gestures ──
    {
        "name": "trigger_avatar_animation",
        "description": "Controls physical gestures, facial expressions, or 3D avatar animations on screen.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "animation_name": {"type": "STRING", "description": "Name of animation/gesture ('dance', 'greeting', 'salute', 'thinking', 'laughing')."},
                "emotion": {"type": "STRING", "description": "Supplementary emotional expression ('happy', 'curious', 'joy', 'neutral', 'empathy')."}
            },
            "required": ["animation_name"]
        },
        "handler": _tool_trigger_avatar_animation,
        "risk": "read_only",
        "toolset": "avatar_3d",
        "category": "multimedia",
        "icon": "smile",
    },

    # ── Skills Engine ──
    {
        "name": "learn_and_save_skill",
        "description": "Anara Lifelong Learning Engine: Learns and permanently saves a new procedural workflow into SQLite database for future reuse.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "description": "Skill name."},
                "category": {"type": "STRING", "description": "Skill category: 'coding', 'architecture', 'research', 'devops', 'system'."},
                "description": {"type": "STRING", "description": "Summary of capabilities."},
                "trigger_keywords": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Keywords or concept triggers."},
                "procedure_steps": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Procedural steps."}
            },
            "required": ["name", "description", "procedure_steps"]
        },
        "handler": _tool_learn_and_save_skill,
        "risk": "read_only",
        "toolset": "skills_engine",
        "category": "intelligence",
        "icon": "book-open",
    },
    {
        "name": "skill_view",
        "description": "Anara Skill Inspector: Reads and loads complete skill guidelines (SKILL.md) from the skill library.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "description": "Skill name or slug to load."}
            },
            "required": ["name"]
        },
        "handler": _tool_skill_view,
        "risk": "read_only",
        "toolset": "skills_engine",
        "category": "intelligence",
        "icon": "book-open",
    },

    # ── Delegation ──
    {
        "name": "delegate_subagent",
        "description": "Delegates investigation or autonomous research tasks to a background worker subagent (supports single mission or parallel batch tasks).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Short background mission title."},
                "mission_prompt": {"type": "STRING", "description": "Complete task instructions."},
                "goal": {"type": "STRING", "description": "Specific task goal the subagent must achieve."},
                "context": {"type": "STRING", "description": "Technical background or relevant files for this task."},
                "tasks": {
                    "type": "ARRAY",
                    "items": {"type": "OBJECT"},
                    "description": "Batch task list [{'goal': '...', 'context': '...'}] for parallel execution."
                },
                "background": {"type": "BOOLEAN", "description": "Run in background (default true)."}
            }
        },
        "handler": _tool_delegate_subagent,
        "risk": "mutating",
        "toolset": "task_delegation",
        "category": "system",
        "icon": "users",
    },

    # ── Clarifying Questions ──
    {
        "name": "interactive_question",
        "description": "Displays a step-by-step interactive questionnaire card (Wizard Card) on the user's screen to clarify ambiguous instructions.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "questions": {
                    "type": "ARRAY",
                    "description": "List of step-by-step interactive questions.",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "header": {"type": "STRING", "description": "Short question label."},
                            "question": {"type": "STRING", "description": "Full question text."},
                            "options": {
                                "type": "ARRAY",
                                "description": "List of choice options.",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "label": {"type": "STRING", "description": "Option label."},
                                        "description": {"type": "STRING", "description": "Option explanation."}
                                    },
                                    "required": ["label", "description"]
                                }
                            },
                            "multiple": {"type": "BOOLEAN", "description": "Allow selecting more than one option."}
                        },
                        "required": ["header", "question", "options"]
                    }
                }
            },
            "required": ["questions"]
        },
        "handler": _tool_interactive_question,
        "risk": "read_only",
        "toolset": "clarifying_questions",
        "category": "intelligence",
        "icon": "help-circle",
    },

    # ── Browser Automation ──
    {
        "name": "browser_navigate",
        "description": "Navigates to a web URL using Playwright Chromium/Brave browser.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING", "description": "Web address URL to visit."},
                "headed": {"type": "BOOLEAN", "description": "Launch browser in visible window mode."},
                "use_brave": {"type": "BOOLEAN", "description": "Use local Brave Browser."}
            },
            "required": ["url"]
        },
        "handler": _tool_browser_navigate,
        "risk": "action",
        "toolset": "browser_automation",
        "category": "exploration",
        "icon": "compass",
    },
    {
        "name": "browser_click",
        "description": "Clicks an interactive element on the active web page.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "selector_or_text": {"type": "STRING", "description": "Button text or CSS selector."}
            },
            "required": ["selector_or_text"]
        },
        "handler": _tool_browser_click,
        "risk": "action",
        "toolset": "browser_automation",
        "category": "exploration",
        "icon": "compass",
    },
    {
        "name": "browser_type",
        "description": "Types text into an input field on the active web page.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "selector": {"type": "STRING", "description": "CSS selector of input field."},
                "text": {"type": "STRING", "description": "Text to type."},
                "press_enter": {"type": "BOOLEAN", "description": "Press Enter after typing."}
            },
            "required": ["selector", "text"]
        },
        "handler": _tool_browser_type,
        "risk": "action",
        "toolset": "browser_automation",
        "category": "exploration",
        "icon": "compass",
    },
    {
        "name": "browser_snapshot",
        "description": "Takes a structured snapshot of the active web page DOM structure.",
        "parameters": {"type": "OBJECT", "properties": {}},
        "handler": _tool_browser_snapshot,
        "risk": "read_only",
        "toolset": "browser_automation",
        "category": "exploration",
        "icon": "compass",
    },
    {
        "name": "browser_screenshot",
        "description": "Captures a visual screenshot of the active web page and saves to disk.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"filename": {"type": "STRING", "description": "Output screenshot filename."}}
        },
        "handler": _tool_browser_screenshot,
        "risk": "read_only",
        "toolset": "browser_automation",
        "category": "exploration",
        "icon": "compass",
    },
    {
        "name": "browser_close",
        "description": "Closes the active browser window and automation session.",
        "parameters": {"type": "OBJECT", "properties": {}},
        "handler": _tool_browser_close,
        "risk": "action",
        "toolset": "browser_automation",
        "category": "exploration",
        "icon": "compass",
    },
    {
        "name": "browser_scroll",
        "description": "Scrolls the browser web page up, down, to top, or to bottom.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "direction": {"type": "STRING", "description": "Scroll direction: 'down', 'up', 'top', 'bottom'."},
                "amount": {"type": "INTEGER", "description": "Scroll distance in pixels."}
            }
        },
        "handler": _tool_browser_scroll,
        "risk": "action",
        "toolset": "browser_automation",
        "category": "exploration",
        "icon": "compass",
    },
    {
        "name": "browser_press",
        "description": "Presses a keyboard key on the active browser (e.g. 'Enter', 'Escape', 'Tab').",
        "parameters": {
            "type": "OBJECT",
            "properties": {"key": {"type": "STRING", "description": "Keyboard key name."}},
            "required": ["key"]
        },
        "handler": _tool_browser_press,
        "risk": "action",
        "toolset": "browser_automation",
        "category": "exploration",
        "icon": "compass",
    },
    {
        "name": "browser_back",
        "description": "Navigates back to the previous page in browser history.",
        "parameters": {"type": "OBJECT", "properties": {}},
        "handler": _tool_browser_back,
        "risk": "action",
        "toolset": "browser_automation",
        "category": "exploration",
        "icon": "compass",
    },

    # ── Spotify ──
    {
        "name": "spotify_search",
        "description": "Searches Spotify for tracks, artists, albums, or playlists.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Track title, artist, or album query."},
                "search_type": {"type": "STRING", "description": "Search type ('track', 'artist', 'album', 'playlist')."}
            },
            "required": ["query"]
        },
        "handler": _tool_spotify_search,
        "risk": "read_only",
        "toolset": "spotify_music",
        "category": "multimedia",
        "icon": "music",
    },
    {
        "name": "spotify_playback",
        "description": "Controls Spotify playback ('play', 'pause', 'next', 'previous', 'resume').",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Playback action ('play', 'pause', 'next', 'previous')."},
                "query": {"type": "STRING", "description": "Optional track, album, or playlist search query."}
            }
        },
        "handler": _tool_spotify_playback,
        "risk": "action",
        "toolset": "spotify_music",
        "category": "multimedia",
        "icon": "music",
    },

    # ── Cron Scheduler ──
    {
        "name": "cronjob_manage",
        "description": "Manages autonomous scheduled background tasks (Hermes Parity cron). Actions: 'create', 'list', 'pause', 'resume', 'run', 'remove'.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Cron action: 'create', 'list', 'pause', 'resume', 'run', 'remove'."},
                "name": {"type": "STRING", "description": "Descriptive task name."},
                "schedule": {"type": "STRING", "description": "Execution schedule. Specify as standard cron expression (e.g. '0 9 * * *', '*/15 * * * *'), standard interval shorthand ('30s', '15m', '2h', '1d', '1w'), or interval in seconds (e.g. 3600). The model translates natural language schedule instructions into this format."},
                "prompt": {"type": "STRING", "description": "Prompt instructions to execute when triggered."},
                "task_id": {"type": "STRING", "description": "Task identifier."},
                "trust_level": {"type": "STRING", "description": "Autonomy level: 'supervised', 'semi_autonomous', 'full_autonomous'."},
                "target_channel": {"type": "STRING", "description": "Notification channel: 'telegram', 'whatsapp', 'cli', 'web'."}
            },
            "required": ["action"]
        },
        "handler": _tool_cronjob_manage,
        "risk": "action",
        "toolset": "cron_scheduler",
        "category": "system",
        "icon": "clock",
    },

    # ── Image & Video AI ──
    {
        "name": "image_generate",
        "description": "Generates high-resolution creative AI images from descriptive prompts.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt": {"type": "STRING", "description": "Detailed visual description of image to generate."},
                "aspect_ratio": {"type": "STRING", "description": "Aspect ratio: '1:1', '16:9', '9:16'."},
                "style": {"type": "STRING", "description": "Artistic style: 'photorealistic', 'anime', 'digital-art', 'cyberpunk'."}
            },
            "required": ["prompt"]
        },
        "handler": _tool_image_generate,
        "risk": "action",
        "toolset": "image_generation",
        "category": "multimedia",
        "icon": "image",
    },
    {
        "name": "video_generate",
        "description": "Generates short AI video clips from text prompts or reference images.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt": {"type": "STRING", "description": "Motion and scene description for the video."},
                "duration": {"type": "INTEGER", "description": "Duration in seconds (default 4)."},
                "aspect_ratio": {"type": "STRING", "description": "Aspect ratio: '16:9', '9:16', '1:1'."},
                "image_url": {"type": "STRING", "description": "Reference image URL for image-to-video."}
            },
            "required": ["prompt"]
        },
        "handler": _tool_video_generate,
        "risk": "action",
        "toolset": "video_generation",
        "category": "multimedia",
        "icon": "video",
    },
    {
        "name": "vision_analyze",
        "description": "Thoroughly analyzes images from local files or web URLs (OCR, screenshot errors, diagrams, objects).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "image_path": {"type": "STRING", "description": "Local image file path or web URL."},
                "question": {"type": "STRING", "description": "Specific question or focus for the visual analysis."}
            },
            "required": ["image_path"]
        },
        "handler": _tool_vision_analyze,
        "risk": "read_only",
        "toolset": "vision",
        "category": "multimedia",
        "icon": "eye",
    },
    {
        "name": "video_analyze",
        "description": "Analyzes local video files (.mp4, .webm, .mov) to extract visual details and scene chronology.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "video_path": {"type": "STRING", "description": "Local video file path on host machine."},
                "question": {"type": "STRING", "description": "Specific question or analysis instructions."}
            },
            "required": ["video_path"]
        },
        "handler": _tool_video_analyze,
        "risk": "read_only",
        "toolset": "video",
        "category": "multimedia",
        "icon": "video",
    },

    # ── Home Assistant ──
    {
        "name": "ha_list_entities",
        "description": "Lists smart home IoT entities connected to Home Assistant.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"domain": {"type": "STRING", "description": "Domain category filter ('light', 'switch', 'sensor', 'climate')."}}
        },
        "handler": _tool_ha_list_entities,
        "risk": "read_only",
        "toolset": "home_assistant",
        "category": "system",
        "icon": "home",
    },
    {
        "name": "ha_get_state",
        "description": "Reads current status and attributes of a specific Home Assistant entity.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"entity_id": {"type": "STRING", "description": "Entity ID (e.g. 'light.living_room')."}},
            "required": ["entity_id"]
        },
        "handler": _tool_ha_get_state,
        "risk": "read_only",
        "toolset": "home_assistant",
        "category": "system",
        "icon": "home",
    },
    {
        "name": "ha_call_service",
        "description": "Controls or invokes a Home Assistant service on smart devices (toggle lights, adjust climate, etc.).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "domain": {"type": "STRING", "description": "Service domain ('light', 'switch', 'climate')."},
                "service": {"type": "STRING", "description": "Service action ('turn_on', 'turn_off', 'toggle')."},
                "entity_id": {"type": "STRING", "description": "Target entity ID."},
                "service_data": {"type": "OBJECT", "description": "Supplementary parameters."}
            },
            "required": ["domain", "service"]
        },
        "handler": _tool_ha_call_service,
        "risk": "action",
        "toolset": "home_assistant",
        "category": "system",
        "icon": "home",
    },

    # ── Voice Biometrics & Wake Word ──
    {
        "name": "voice_biometrics_manage",
        "description": "Manages voiceprint biometric profiles and user identification based on voice samples.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Action: 'list', 'identify', 'enroll'."},
                "speaker_name": {"type": "STRING", "description": "User or speaker name."},
                "audio_file_path": {"type": "STRING", "description": "Local WAV audio file path."},
                "audio_base64": {"type": "STRING", "description": "Base64 encoded audio data."}
            },
            "required": ["action"]
        },
        "handler": _tool_voice_biometrics_manage,
        "risk": "read_only",
        "toolset": "voice_biometrics",
        "category": "intelligence",
        "icon": "mic",
    },
    {
        "name": "wake_word_manage",
        "description": "Controls offline hands-free wake word listener ('Hey Anara').",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Action: 'status', 'start', 'stop', 'set_phrase'."},
                "phrase": {"type": "STRING", "description": "Custom wake phrase."}
            }
        },
        "handler": _tool_wake_word_manage,
        "risk": "action",
        "toolset": "voice_biometrics",
        "category": "intelligence",
        "icon": "mic",
    },

    # ── Code Execution ──
    {
        "name": "execute_code",
        "description": "Evaluates Python or Node.js code snippets in an isolated sandboxed REPL.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "code": {"type": "STRING", "description": "Source code to execute."},
                "language": {"type": "STRING", "description": "Programming language: 'python' or 'javascript'."},
                "timeout": {"type": "INTEGER", "description": "Execution timeout in seconds."}
            },
            "required": ["code"]
        },
        "handler": _tool_execute_code,
        "risk": "mutating",
        "toolset": "code_execution",
        "category": "coding",
        "icon": "play",
    },

    # ── Computer Use ──
    {
        "name": "computer_use",
        "description": "OS-level desktop automation (CUA primitives): send_text (RECOMMENDED universal 1-step focus/launch, input targeting, type text, and submit with Enter in ANY app), launch_app (open unopened applications), list_windows, focus_app, type, key, hotkey, click, screenshot.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "OS action: 'send_text' (RECOMMENDED for typing and submitting text/commands to any active or target desktop app), 'launch_app' (launch an application by name if not running), 'list_windows', 'focus_app', 'type', 'key', 'hotkey', 'click', 'double_click', 'right_click', 'scroll', 'screenshot', 'wait', 'screen_info'."},
                "app": {"type": "STRING", "description": "Target window name or application title to focus or interact with (e.g. 'Notepad', 'Chrome', 'Telegram', 'OpenCode', 'Terminal'). If omitted, interacts with the active foreground window."},
                "text": {"type": "STRING", "description": "Text to type or send into focused window or app."},
                "enter": {"type": "BOOLEAN", "description": "Whether to press Enter/Return key immediately after typing (default true for send_text, false for type)."},
                "submit": {"type": "BOOLEAN", "description": "Whether to submit with Enter key (default true for send_text)."},
                "key": {"type": "STRING", "description": "Key name or hotkey combo to press (e.g. 'enter', 'tab', 'ctrl+c', 'ctrl+v', 'p', 'escape')."},
                "x": {"type": "INTEGER", "description": "Screen horizontal pixel coordinate to click or click-to-focus before typing (optional)."},
                "y": {"type": "INTEGER", "description": "Screen vertical pixel coordinate to click or click-to-focus before typing (optional)."},
                "coordinate": {"type": "ARRAY", "items": {"type": "INTEGER"}, "description": "[x, y] coordinates for mouse click or focus (optional)."},
                "button": {"type": "STRING", "description": "Mouse button: 'left', 'right', 'double'."},
                "amount": {"type": "INTEGER", "description": "Scroll wheel amount."},
                "duration": {"type": "NUMBER", "description": "Wait duration in seconds."},
                "window_id": {"type": "INTEGER", "description": "Optional window handle (HWND)."}
            },
            "required": ["action"]
        },
        "handler": _tool_computer_use,
        "risk": "mutating",
        "toolset": "computer_use",
        "category": "system",
        "icon": "monitor",
    },
    {
        "name": "take_screenshot",
        "description": "Takes a full-screen desktop capture of the active display.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Optional title for the snapshot."}
            }
        },
        "handler": _tool_take_screenshot,
        "risk": "read_only",
        "toolset": "computer_use",
        "category": "system",
        "icon": "camera",
    },

    # ── MCP Protocol ──
    {
        "name": "mcp_manage",
        "description": "Manages external Model Context Protocol (MCP) server connections.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "MCP action: 'list', 'add', 'remove'."},
                "server_name": {"type": "STRING", "description": "MCP server name."},
                "command": {"type": "STRING", "description": "CLI command for stdio server."},
                "args": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Server command arguments."},
                "url": {"type": "STRING", "description": "HTTP/SSE server endpoint URL."}
            },
            "required": ["action"]
        },
        "handler": _tool_mcp_manage,
        "risk": "action",
        "toolset": "mcp_protocol",
        "category": "intelligence",
        "icon": "cpu",
    },

    # ── Kanban Subsystem ──
    {
        "name": "kanban_create_task",
        "description": "Creates a new task card on the project Kanban board.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Short task title."},
                "description": {"type": "STRING", "description": "Detailed task specification."},
                "priority": {"type": "INTEGER", "description": "Priority: 1 (normal), 2 (high), 3 (urgent)."},
                "assignee": {"type": "STRING", "description": "Assignee name (default 'agent')."}
            },
            "required": ["title"]
        },
        "handler": _tool_kanban_create_task,
        "risk": "action",
        "toolset": "kanban_management",
        "category": "system",
        "icon": "clipboard",
    },
    {
        "name": "kanban_list_tasks",
        "description": "Inspects and lists all task cards on the project Kanban board.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "status": {"type": "STRING", "description": "Column filter: 'todo', 'in_progress', 'review', 'blocked', 'done'."}
            }
        },
        "handler": _tool_kanban_list_tasks,
        "risk": "read_only",
        "toolset": "kanban_management",
        "category": "system",
        "icon": "clipboard",
    },
    {
        "name": "kanban_update_task",
        "description": "Updates a Kanban task card status ('todo', 'in_progress', 'review', 'blocked', 'done').",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task_id": {"type": "INTEGER", "description": "Task card ID."},
                "status": {"type": "STRING", "description": "New column status."},
                "notes": {"type": "STRING", "description": "Progress notes or verification summary."}
            },
            "required": ["task_id", "status"]
        },
        "handler": _tool_kanban_update_task,
        "risk": "action",
        "toolset": "kanban_management",
        "category": "system",
        "icon": "clipboard",
    },
    {
        "name": "kanban_request_review",
        "description": "Requests human review for a completed Kanban task with verification evidence.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task_id": {"type": "INTEGER", "description": "Task card ID."},
                "review_summary": {"type": "STRING", "description": "Summary of what was completed and verified."}
            },
            "required": ["task_id", "review_summary"]
        },
        "handler": _tool_kanban_request_review,
        "risk": "action",
        "toolset": "kanban_management",
        "category": "system",
        "icon": "clipboard",
    },
]

# Auto-register all 66 tool specifications into ToolRegistry (Anara Parity)
for spec in ALL_TOOL_SPECS:
    registry.register_tool(
        name=spec["name"],
        description=spec["description"],
        parameters=spec["parameters"],
        handler=spec["handler"],
        risk=spec["risk"],
        toolset=spec["toolset"],
        category=spec["category"],
        icon=spec["icon"],
    )

UNIVERSAL_TOOL_ALIASES = {
    "terminal": "execute_cli_command",
    "read_file": "read_local_file",
    "write_file": "write_local_file",
    "patch": "edit_file",
    "search_files": "glob_find_files",
    "clarify": "interactive_question",
    "delegate_task": "delegate_subagent",
    "web_extract": "fetch_webpage",
    "todo_list": "manage_memory_and_todos",
    "file_search": "glob_find_files",
    "dir_list": "list_directory",
    "analyze_image": "vision_analyze",
    "image_analyze": "vision_analyze",
    "analyze_video": "video_analyze",
}

for alias, target in UNIVERSAL_TOOL_ALIASES.items():
    registry.register_alias(alias, target)

logger.info(f"[ToolSpecs] Initialized & registered {len(ALL_TOOL_SPECS)} tools ({len(UNIVERSAL_TOOL_ALIASES)} aliases) into ToolRegistry.")
