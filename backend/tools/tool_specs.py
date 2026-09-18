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
from .skills_hub_tools import _tool_skills_hub_manage
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
        return {"status": "error", "message": "Akun Google Workspace belum ditautkan."}
    emails = await get_unread_emails(limit=limit)
    return {"status": "success", "emails": emails}


async def _tool_calendar_get_schedule(days: int = 3) -> Dict[str, Any]:
    from integrations import get_upcoming_events, get_google_status
    st = await get_google_status()
    if st.get("status") != "connected":
        return {"status": "error", "message": "Akun Google Workspace belum ditautkan."}
    events = await get_upcoming_events(days=days)
    return {"status": "success", "events": events}


# All 66 Tool Specifications (Anara Standard)
ALL_TOOL_SPECS: List[Dict[str, Any]] = [
    # ── Digital Artifacts ──
    {
        "name": "generate_file_artifact",
        "description": "Membuat dokumen berkas digital baru dalam berbagai format resmi (DOCX, PDF, CSV, Excel, TXT, MD, Python, JS, JSON).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "filename": {"type": "STRING", "description": "Nama file lengkap dengan ekstensi, misal 'proposal.docx', 'laporan.pdf'."},
                "content": {"type": "STRING", "description": "Isi teks lengkap dokumen atau kode yang dibuat."},
                "title": {"type": "STRING", "description": "Judul dokumen resmi untuk header."},
                "destination_folder": {"type": "STRING", "description": "Path folder tujuan fisik lokal (opsional)."}
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
        "description": "Mengompresi dan membuat berkas arsip ZIP dari seluruh proyek di workspace atau daftar berkas tertentu.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "archive_name": {"type": "STRING", "description": "Nama berkas zip tujuan, misalnya 'dashboard-project.zip'."},
                "folder_path": {"type": "STRING", "description": "Folder proyek yang ingin dikompresi."},
                "files": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Daftar berkas tertentu yang ingin dimasukkan ke dalam zip."}
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
        "description": "Mengekstrak (unzip) seluruh berkas dari file arsip ZIP ke folder tujuan secara instan.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "zip_path": {"type": "STRING", "description": "Nama atau path berkas ZIP yang ingin diekstrak."},
                "destination_folder": {"type": "STRING", "description": "Folder tujuan ekstraksi."}
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
        "description": "Menambah, menimpa, atau memperbarui berkas di dalam arsip ZIP tanpa mengekstrak seluruh isi arsip.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "zip_path": {"type": "STRING", "description": "Nama atau path berkas ZIP yang ingin diperbarui."},
                "files_to_add": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Daftar path berkas lokal yang ingin ditambahkan."},
                "files_to_remove": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Daftar nama berkas di dalam ZIP yang ingin dihapus."},
                "output_path": {"type": "STRING", "description": "Path keluaran berkas ZIP baru."}
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
        "description": "Membaca dan memeriksa daftar berkas di dalam file ZIP beserta ukuran asli dan kompresinya secara read-only.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "zip_path": {"type": "STRING", "description": "Nama atau path berkas ZIP yang ingin diperiksa."}
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
        "description": "Mengirimkan berkas dokumen, foto, video, atau berkas lokal langsung ke obrolan Telegram atau WhatsApp.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Path atau nama file lokal / URL yang ingin dikirimkan."},
                "channel": {"type": "STRING", "description": "Channel tujuan ('telegram' atau 'whatsapp')."},
                "recipient": {"type": "STRING", "description": "Target ID penerima atau nomor telepon."},
                "caption": {"type": "STRING", "description": "Teks pengantar atau judul dokumen."}
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
        "description": "Mencari informasi real-time dan peristiwa terkini di internet (berita, fakta, skor, cuaca).",
        "parameters": {
            "type": "OBJECT",
            "properties": {"query": {"type": "STRING", "description": "Kata kunci pencarian spesifik."}},
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
        "description": "Mencari foto, gambar berita nyata, atau dokumentasi visual terkini di internet dan langsung mengirimkannya ke pengguna.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Kata kunci pencarian foto/gambar."},
                "limit": {"type": "INTEGER", "description": "Jumlah maksimal foto yang dicari (default 4)."}
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
        "description": "Membaca dan menganalisis isi artikel atau halaman website lengkap dari URL.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"url": {"type": "STRING", "description": "Tautan URL web yang ingin dibaca."}},
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
        "description": "Membaca isi file dokumen atau kode lokal dengan nomor baris dan opsi paginasi offset/limit.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Path atau nama file lokal."},
                "offset": {"type": "INTEGER", "description": "Nomor baris awal (1-indexed)."},
                "limit": {"type": "INTEGER", "description": "Jumlah baris maksimal yang ingin dibaca."}
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
        "description": "Menyunting berkas kode atau dokumen teks secara in-place dengan mengganti blok old_string menjadi new_string.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Path relatif atau nama berkas yang ingin disunting."},
                "old_string": {"type": "STRING", "description": "Teks atau blok kode lama yang ingin diganti."},
                "new_string": {"type": "STRING", "description": "Teks atau blok kode baru penggantinya."},
                "replace_all": {"type": "BOOLEAN", "description": "Setel true jika ingin mengganti seluruh kemunculan old_string."}
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
        "description": "Mencari berkas dengan cepat di proyek berdasarkan pola glob pattern nama berkas (misal '**/*.tsx').",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "pattern": {"type": "STRING", "description": "Pola pencarian glob."},
                "path": {"type": "STRING", "description": "Direktori awal pencarian."}
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
        "description": "Mencari teks atau ekspresi reguler (regex) secara cepat di seluruh isi file kode dalam proyek.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "pattern": {"type": "STRING", "description": "Regex atau kata kunci yang dicari."},
                "path": {"type": "STRING", "description": "Direktori awal pencarian."},
                "include": {"type": "STRING", "description": "Filter pola berkas (misal '*.ts')."}
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
        "description": "Menulis atau membuat berkas baru secara langsung di dalam workspace proyek pengguna.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Path relatif dan nama file yang ingin ditulis."},
                "content": {"type": "STRING", "description": "Isi lengkap berkas yang ingin ditulis."}
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
        "name": "list_directory",
        "description": "Melihat daftar berkas dan subfolder dalam sebuah direktori lokal (100% read-only).",
        "parameters": {
            "type": "OBJECT",
            "properties": {"directory_path": {"type": "STRING", "description": "Path direktori (opsional)."}}
        },
        "handler": _tool_list_directory,
        "risk": "read_only",
        "toolset": "file_operations",
        "category": "coding",
        "icon": "folder",
    },
    {
        "name": "scan_workspace_folder",
        "description": "Memindai dan mengindeks struktur hierarki seluruh folder proyek lokal (file tree).",
        "parameters": {
            "type": "OBJECT",
            "properties": {"folder_path": {"type": "STRING", "description": "Path direktori folder proyek."}},
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
        "description": "Menjalankan perintah CLI terminal lokal aman (git, npm, dir, python, curl).",
        "parameters": {
            "type": "OBJECT",
            "properties": {"command": {"type": "STRING", "description": "Perintah terminal shell yang ingin dijalankan."}},
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
        "description": "Mengelola proses latar belakang persisten/daemon (server dev, watcher, daemon script) dengan log streaming real-time.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Aksi: 'start', 'list', 'logs', 'stop'."},
                "command": {"type": "STRING", "description": "Perintah CLI untuk dijalankan di background."},
                "process_id": {"type": "STRING", "description": "ID pengenal proses."},
                "cwd": {"type": "STRING", "description": "Folder kerja eksekusi proses."},
                "lines": {"type": "INTEGER", "description": "Jumlah baris log terbaru yang diambil."}
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
        "description": "Mengelola catatan to-do list harian personal (tambah, lihat, centang, hapus).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Aksi: 'add', 'list', 'toggle', 'delete'."},
                "title": {"type": "STRING", "description": "Judul catatan atau to-do."},
                "content": {"type": "STRING", "description": "Deskripsi catatan."},
                "category": {"type": "STRING", "description": "Kategori ('todo', 'note', 'reminder')."},
                "item_id": {"type": "INTEGER", "description": "ID catatan untuk toggle/delete."}
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
        "description": "Anara Persistent Memory Manager: Menambah, mengganti, atau menghapus catatan pribadi dan preferensi.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Aksi memori: 'add', 'replace', 'remove'."},
                "target": {"type": "STRING", "description": "Target memori: 'memory' (catatan agen) atau 'user' (profil pengguna)."},
                "content": {"type": "STRING", "description": "Teks memori baru."},
                "old_text": {"type": "STRING", "description": "Substring teks lama yang ingin diganti atau dihapus."}
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
        "description": "Mencari riwayat obrolan dan sesi lampau di basis data SQLite.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Kata kunci topik percakapan lampau."},
                "limit": {"type": "INTEGER", "description": "Jumlah maksimal sesi yang dicari."}
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
        "description": "Membuka aplikasi komputer lokal Windows (Spotify, VS Code, Browser, Notepad, Calculator) atau URL web.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Aksi ('open')."},
                "target": {"type": "STRING", "description": "Nama aplikasi atau target yang ingin dibuka."},
                "arguments": {"type": "STRING", "description": "Argumen atau URL web opsional."},
                "url": {"type": "STRING", "description": "URL tujuan."}
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
        "description": "Mengirimkan data HTTP request otomatis ke endpoint webhook luar (Discord, Zapier, n8n, Slack).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING", "description": "URL tujuan webhook."},
                "method": {"type": "STRING", "description": "HTTP method ('POST', 'GET', 'PUT')."},
                "payload_json": {"type": "STRING", "description": "Payload JSON string."}
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
        "description": "Memproyeksikan visualisasi, kartu pengetahuan, dan terminal kode ke layar HUD pengguna.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "visual_type": {"type": "STRING", "description": "Tipe visual ('knowledge_card', 'code_box', 'system_hud')."},
                "title": {"type": "STRING", "description": "Judul visual."},
                "summary": {"type": "STRING", "description": "Ringkasan penjelasan visual."},
                "specs_json": {"type": "STRING", "description": "Spesifikasi data JSON pelengkap."}
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
        "description": "Membaca daftar pesan chat masuk yang belum dibaca dari akun WhatsApp Web pengguna.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"unread_only": {"type": "BOOLEAN", "description": "Hanya ambil pesan belum dibaca."}}
        },
        "handler": _tool_whatsapp_read_messages,
        "risk": "read_only",
        "toolset": "messaging_whatsapp",
        "category": "communication",
        "icon": "message-circle",
    },
    {
        "name": "whatsapp_send_message",
        "description": "Mengirimkan pesan chat ke kontak atau nomor telepon tertentu melalui WhatsApp Web.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "recipient": {"type": "STRING", "description": "Nama kontak atau nomor telepon tujuan."},
                "message": {"type": "STRING", "description": "Isi pesan teks yang ingin dikirimkan."}
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
        "description": "Membaca pesan masuk terbaru dari Bot Telegram Anara.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"limit": {"type": "INTEGER", "description": "Jumlah pesan maksimal."}}
        },
        "handler": _tool_telegram_read_messages,
        "risk": "read_only",
        "toolset": "messaging_telegram",
        "category": "communication",
        "icon": "send",
    },
    {
        "name": "telegram_send_message",
        "description": "Mengirimkan pesan ke chat pengguna atau grup Telegram.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "message": {"type": "STRING", "description": "Isi pesan teks yang ingin dikirimkan."},
                "chat_id": {"type": "STRING", "description": "ID chat/grup tujuan (opsional)."}
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
        "description": "Membaca pesan masuk terbaru dari channel Discord tertentu.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "channel_id": {"type": "STRING", "description": "ID channel Discord."},
                "limit": {"type": "INTEGER", "description": "Jumlah pesan maksimal (default 10)."}
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
        "description": "Mengirimkan pesan teks ke channel Discord.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "text": {"type": "STRING", "description": "Isi pesan teks yang ingin dikirimkan."},
                "channel_id": {"type": "STRING", "description": "ID channel Discord tujuan."}
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
        "description": "Membaca riwayat pesan terbaru dari channel Slack.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "channel": {"type": "STRING", "description": "ID channel Slack."},
                "limit": {"type": "INTEGER", "description": "Jumlah pesan maksimal (default 10)."}
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
        "description": "Mengirimkan pesan teks ke channel Slack.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "text": {"type": "STRING", "description": "Isi pesan teks yang ingin dikirimkan."},
                "channel": {"type": "STRING", "description": "ID channel Slack tujuan."}
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
        "description": "Membaca daftar email masuk terbaru dari kotak masuk Gmail pengguna.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"limit": {"type": "INTEGER", "description": "Jumlah maksimal email yang dibaca."}}
        },
        "handler": _tool_gmail_read_inbox,
        "risk": "read_only",
        "toolset": "google_workspace",
        "category": "communication",
        "icon": "mail",
    },
    {
        "name": "calendar_get_schedule",
        "description": "Melihat jadwal janji temu dan acara mendatang di Google Calendar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"days": {"type": "INTEGER", "description": "Jumlah hari ke depan (default 3 hari)."}}
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
        "description": "Mengendalikan gestur fisik, ekspresi wajah, atau tarian avatar 3D Anara di layar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "animation_name": {"type": "STRING", "description": "Nama animasi/gestur ('dance', 'greeting', 'salute', 'thinking', 'laughing')."},
                "emotion": {"type": "STRING", "description": "Ekspresi emosi pelengkap ('happy', 'curious', 'joy', 'neutral', 'empathy')."}
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
        "description": "Anara Lifelong Learning Engine: Mengingat dan menyimpan prosedur teknis baru ke database SQLite Anara.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "description": "Nama keahlian/skill."},
                "category": {"type": "STRING", "description": "Kategori keahlian: 'coding', 'architecture', 'research', 'devops', 'system'."},
                "description": {"type": "STRING", "description": "Ringkasan manfaat."},
                "trigger_keywords": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Kata kunci pemicu."},
                "procedure_steps": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Langkah-langkah prosedur."}
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
        "description": "Anara Skill Inspector: Membaca dan memuat isi lengkap pedoman keahlian (SKILL.md) dari perpustakaan 90+ skill.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "description": "Nama atau slug keahlian yang ingin dimuat."}
            },
            "required": ["name"]
        },
        "handler": _tool_skill_view,
        "risk": "read_only",
        "toolset": "skills_engine",
        "category": "intelligence",
        "icon": "book-open",
    },
    {
        "name": "skills_hub_manage",
        "description": "Menelusuri, mengunduh, memasang, melihat, dan menghapus keahlian komunitas (Skills Hub) dari GitHub/ClawHub.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Aksi: 'search', 'install', 'list', 'uninstall'."},
                "query": {"type": "STRING", "description": "Kata kunci pencarian."},
                "skill_name": {"type": "STRING", "description": "Nama skill target."},
                "custom_url": {"type": "STRING", "description": "Tautan URL mentah berkas SKILL.md GitHub."}
            },
            "required": ["action"]
        },
        "handler": _tool_skills_hub_manage,
        "risk": "action",
        "toolset": "skills_engine",
        "category": "intelligence",
        "icon": "book-open",
    },

    # ── Delegation ──
    {
        "name": "delegate_subagent",
        "description": "Mendelegasikan tugas investigasi mandiri ke subagent pekerja latar belakang.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Judul singkat misi latar belakang."},
                "mission_prompt": {"type": "STRING", "description": "Instruksi tugas lengkap."},
                "subagent_type": {"type": "STRING", "description": "Tipe sub-agent ('researcher', 'coder', 'analyst')."}
            },
            "required": ["title", "mission_prompt"]
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
        "description": "Menampilkan kartu kuesioner interaktif bertahap (Wizard Card) ke layar pengguna untuk mengklarifikasi instruksi ambigu.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "questions": {
                    "type": "ARRAY",
                    "description": "Daftar pertanyaan interaktif bertahap.",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "header": {"type": "STRING", "description": "Label singkat pertanyaan."},
                            "question": {"type": "STRING", "description": "Teks lengkap pertanyaan."},
                            "options": {
                                "type": "ARRAY",
                                "description": "Daftar opsi pilihan.",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "label": {"type": "STRING", "description": "Label opsi."},
                                        "description": {"type": "STRING", "description": "Penjelasan opsi."}
                                    },
                                    "required": ["label", "description"]
                                }
                            },
                            "multiple": {"type": "BOOLEAN", "description": "Boleh memilih lebih dari satu opsi."}
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
        "description": "Membuka dan menavigasi ke URL web menggunakan browser Playwright Chromium/Brave.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING", "description": "Alamat URL website yang ingin dikunjungi."},
                "headed": {"type": "BOOLEAN", "description": "Buka browser dengan jendela tampak."},
                "use_brave": {"type": "BOOLEAN", "description": "Gunakan Brave Browser lokal."}
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
        "description": "Mengklik elemen interaktif pada halaman web aktif.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "selector_or_text": {"type": "STRING", "description": "Teks tombol atau selector CSS elemen."}
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
        "description": "Mengetikkan teks ke dalam form input pada halaman web aktif.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "selector": {"type": "STRING", "description": "Selector CSS field input."},
                "text": {"type": "STRING", "description": "Teks yang ingin diketikkan."},
                "press_enter": {"type": "BOOLEAN", "description": "Tekan tombol Enter setelah mengetik."}
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
        "description": "Mengambil snapshot struktur DOM halaman web yang sedang aktif secara terstruktur.",
        "parameters": {"type": "OBJECT", "properties": {}},
        "handler": _tool_browser_snapshot,
        "risk": "read_only",
        "toolset": "browser_automation",
        "category": "exploration",
        "icon": "compass",
    },
    {
        "name": "browser_screenshot",
        "description": "Mengambil tangkapan layar visual halaman web aktif dan menyimpannya ke disk.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"filename": {"type": "STRING", "description": "Nama file screenshot output."}}
        },
        "handler": _tool_browser_screenshot,
        "risk": "read_only",
        "toolset": "browser_automation",
        "category": "exploration",
        "icon": "compass",
    },
    {
        "name": "browser_close",
        "description": "Menutup jendela dan sesi browser otomasi yang sedang aktif.",
        "parameters": {"type": "OBJECT", "properties": {}},
        "handler": _tool_browser_close,
        "risk": "action",
        "toolset": "browser_automation",
        "category": "exploration",
        "icon": "compass",
    },
    {
        "name": "browser_scroll",
        "description": "Menggulir halaman web browser ke atas, bawah, paling atas, atau paling bawah.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "direction": {"type": "STRING", "description": "Arah gulir: 'down', 'up', 'top', 'bottom'."},
                "amount": {"type": "INTEGER", "description": "Jarak gulir dalam piksel."}
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
        "description": "Menekan tombol keyboard pada browser aktif (misal 'Enter', 'Escape', 'Tab').",
        "parameters": {
            "type": "OBJECT",
            "properties": {"key": {"type": "STRING", "description": "Nama tombol keyboard."}},
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
        "description": "Navigasi kembali ke halaman sebelumnya pada riwayat browser.",
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
        "description": "Mencari lagu, artis, atau playlist di Spotify.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Judul lagu atau nama artis yang dicari."},
                "search_type": {"type": "STRING", "description": "Tipe pencarian ('track', 'artist', 'album', 'playlist')."}
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
        "description": "Mengontrol pemutaran musik Spotify: 'play', 'pause', 'next', 'previous'.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Aksi playback ('play', 'pause', 'next', 'previous')."},
                "query": {"type": "STRING", "description": "Judul lagu atau album opsional."}
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
        "description": "Mengelola tugas otomatis terjadwal (Anara Standard cron). Aksi: 'create', 'list', 'pause', 'resume', 'run', 'remove'.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Aksi cron: 'create', 'list', 'pause', 'resume', 'run', 'remove'."},
                "name": {"type": "STRING", "description": "Nama deskriptif untuk tugas terjadwal."},
                "schedule": {"type": "STRING", "description": "Jadwal eksekusi: 'every 30m', 'every 2 hours', 'daily', atau detik."},
                "prompt": {"type": "STRING", "description": "Instruksi prompt yang harus dijalankan agen saat jadwal terpicu."},
                "task_id": {"type": "STRING", "description": "ID tugas."},
                "trust_level": {"type": "STRING", "description": "Tingkat otonomi: 'supervised', 'semi_autonomous', 'full_autonomous'."},
                "target_channel": {"type": "STRING", "description": "Channel notifikasi hasil: 'telegram', 'whatsapp', 'cli', 'web'."}
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
        "description": "Membuat gambar digital AI kreatif beresolusi tinggi berdasarkan prompt deskripsi dan memproyeksikannya ke HUD.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt": {"type": "STRING", "description": "Deskripsi detail visual gambar yang ingin dibuat."},
                "aspect_ratio": {"type": "STRING", "description": "Rasio gambar: '1:1', '16:9', '9:16'."},
                "style": {"type": "STRING", "description": "Gaya artistik: 'photorealistic', 'anime', 'digital-art', 'cyberpunk'."}
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
        "description": "Membuat video digital AI pendek dari teks prompt instruksi atau referensi gambar dan memproyeksikannya ke HUD.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt": {"type": "STRING", "description": "Deskripsi detail pergerakan, subjek, dan adegan video."},
                "duration": {"type": "INTEGER", "description": "Durasi video dalam detik (default 4)."},
                "aspect_ratio": {"type": "STRING", "description": "Rasio video: '16:9', '9:16', '1:1'."},
                "image_url": {"type": "STRING", "description": "Tautan URL gambar referensi untuk image-to-video."}
            },
            "required": ["prompt"]
        },
        "handler": _tool_video_generate,
        "risk": "action",
        "toolset": "video_generation",
        "category": "multimedia",
        "icon": "video",
    },

    # ── Home Assistant ──
    {
        "name": "ha_list_entities",
        "description": "Membaca dan memeriksa daftar perangkat pintar IoT yang terhubung ke Home Assistant.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"domain": {"type": "STRING", "description": "Filter kategori domain ('light', 'switch', 'sensor', 'climate')."}}
        },
        "handler": _tool_ha_list_entities,
        "risk": "read_only",
        "toolset": "home_assistant",
        "category": "system",
        "icon": "home",
    },
    {
        "name": "ha_get_state",
        "description": "Membaca status terkini dan atribut sensor perangkat spesifik di Home Assistant.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"entity_id": {"type": "STRING", "description": "ID entitas (misal 'light.living_room')."}},
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
        "description": "Mengontrol atau memanggil service perangkat IoT di Home Assistant (menyalakan/mematikan lampu, atur AC).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "domain": {"type": "STRING", "description": "Domain service ('light', 'switch', 'climate')."},
                "service": {"type": "STRING", "description": "Aksi service ('turn_on', 'turn_off', 'toggle')."},
                "entity_id": {"type": "STRING", "description": "Target ID entitas."},
                "service_data": {"type": "OBJECT", "description": "Parameter tambahan."}
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
        "description": "Mengelola profil biometrik sidik suara dan identifikasi pengguna berdasarkan rekaman audio.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Aksi: 'list', 'identify', 'enroll'."},
                "speaker_name": {"type": "STRING", "description": "Nama pengguna/pembicara."},
                "audio_file_path": {"type": "STRING", "description": "Path berkas audio WAV lokal."},
                "audio_base64": {"type": "STRING", "description": "Data audio base64."}
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
        "description": "Mengontrol listener pendeteksi panggilan suara offline hands-free ('Hey Anara').",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Aksi: 'status', 'start', 'stop', 'set_phrase'."},
                "phrase": {"type": "STRING", "description": "Kata kunci panggilan."}
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
        "description": "Mengevaluasi cuplikan script Python atau JavaScript secara terisolasi dalam REPL sandboxed aman.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "code": {"type": "STRING", "description": "Kode sumber yang ingin dieksekusi."},
                "language": {"type": "STRING", "description": "Bahasa pemrograman: 'python' atau 'javascript'."},
                "timeout": {"type": "INTEGER", "description": "Batas waktu eksekusi dalam detik."}
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
        "description": "Otomasi desktop OS Windows tingkat rendah (tangkapan layar, klik mouse, pergerakan kursor, drag, ketik teks, dan tekan tombol keyboard).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Aksi: 'screenshot', 'mouse_click', 'mouse_move', 'mouse_drag', 'keyboard_type', 'keyboard_press', 'screen_info'."},
                "x": {"type": "INTEGER", "description": "Koordinat horizontal piksel layar."},
                "y": {"type": "INTEGER", "description": "Koordinat vertikal piksel layar."},
                "button": {"type": "STRING", "description": "Tombol mouse: 'left', 'right', 'double'."},
                "text": {"type": "STRING", "description": "Teks yang ingin diketik ke jendela aktif."},
                "key": {"type": "STRING", "description": "Nama tombol keyboard."}
            },
            "required": ["action"]
        },
        "handler": _tool_computer_use,
        "risk": "ask",
        "toolset": "computer_use",
        "category": "system",
        "icon": "monitor",
    },

    # ── MCP Protocol ──
    {
        "name": "mcp_manage",
        "description": "Mengelola koneksi ke server Model Context Protocol (MCP) eksternal (menambah, menghapus, atau melihat daftar server).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Aksi MCP: 'list', 'add', 'remove'."},
                "server_name": {"type": "STRING", "description": "Nama server MCP."},
                "command": {"type": "STRING", "description": "Perintah CLI untuk server stdio."},
                "args": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Argumen perintah server."},
                "url": {"type": "STRING", "description": "URL endpoint untuk server MCP HTTP/SSE."}
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
        "description": "Membuat kartu task baru di papan Kanban proyek Anara.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Judul singkat task."},
                "description": {"type": "STRING", "description": "Rincian spesifikasi tugas."},
                "priority": {"type": "INTEGER", "description": "Prioritas: 1 (normal), 2 (tinggi), 3 (mendesak)."},
                "assignee": {"type": "STRING", "description": "Penanggung jawab (default 'agent')."}
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
        "description": "Melihat dan memeriksa daftar seluruh kartu tugas di papan Kanban proyek.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "status": {"type": "STRING", "description": "Filter kolom: 'todo', 'in_progress', 'review', 'blocked', 'done'."}
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
        "description": "Menggeser status kartu tugas Kanban ke kolom lain ('todo', 'in_progress', 'review', 'blocked', 'done').",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task_id": {"type": "INTEGER", "description": "ID kartu task."},
                "status": {"type": "STRING", "description": "Status kolom baru."},
                "notes": {"type": "STRING", "description": "Catatan progres atau penjelasan hasil kerja."}
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
        "description": "Meminta review terhadap tugas Kanban yang telah selesai dikerjakan beserta bukti verifikasi.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task_id": {"type": "INTEGER", "description": "ID kartu task."},
                "review_summary": {"type": "STRING", "description": "Ringkasan apa yang telah diselesaikan dan diverifikasi."}
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
}

for alias, target in UNIVERSAL_TOOL_ALIASES.items():
    registry.register_alias(alias, target)

logger.info(f"[ToolSpecs] Initialized & registered {len(ALL_TOOL_SPECS)} tools ({len(UNIVERSAL_TOOL_ALIASES)} aliases) into ToolRegistry.")
