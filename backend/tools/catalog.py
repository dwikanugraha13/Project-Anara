import asyncio
import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional
from google.genai import types

from .events import _emit_agent_event
from .web_tools import _tool_web_search, _tool_fetch_webpage, _tool_custom_webhook
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
from .system_tools import (
    _tool_execute_cli_command,
    _tool_manage_memory_and_todos,
    _tool_system_control,
    _tool_project_hud,
    _tool_delegate_subagent,
    _tool_trigger_avatar_animation,
    _tool_learn_and_save_skill,
    _tool_interactive_question,
)

logger = logging.getLogger(__name__)

ANARA_FUNCTION_DECLARATIONS = [
    types.FunctionDeclaration(
        name="generate_file_artifact",
        description=(
            "Membuat dokumen berkas digital baru dalam berbagai format resmi (DOCX Microsoft Word, PDF, CSV, Excel, TXT, MD, Python, JS, HTML, CSS, JSON). "
            "PENTING: Jika pengguna TIDAK menyebutkan nama folder spesifik, JANGAN isi destination_folder agar berkas tampil di HUD dan bisa diunduh langsung. "
            "Hanya isi destination_folder jika pengguna meminta secara eksplisit untuk menyimpan ke folder lokal tertentu."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "filename": {"type": "STRING", "description": "Nama file lengkap dengan ekstensi, misal 'proposal.docx', 'laporan.pdf', 'index.html', 'data.csv', 'script.py'."},
                "content": {"type": "STRING", "description": "Isi teks lengkap dokumen atau kode yang dibuat."},
                "title": {"type": "STRING", "description": "Judul dokumen resmi untuk header."},
                "destination_folder": {"type": "STRING", "description": "Path folder tujuan fisik lokal (OPSIONAL, hanya jika diminta simpan ke folder tertentu)."}
            },
            "required": ["filename", "content"]
        }
    ),
    types.FunctionDeclaration(
        name="create_zip_archive",
        description="Mengompresi dan membuat berkas arsip ZIP dari seluruh proyek di workspace atau daftar berkas tertentu, lalu memproyeksikan kartu tombol unduh ke layar HUD pengguna.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "archive_name": {"type": "STRING", "description": "Nama berkas zip tujuan, misalnya 'dashboard-project.zip'."},
                "folder_path": {"type": "STRING", "description": "Folder proyek yang ingin dikompresi (opsional, default workspace proyek aktif)."},
                "files": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Daftar berkas tertentu yang ingin dimasukkan ke dalam zip (opsional)."}
            }
        }
    ),
    types.FunctionDeclaration(
        name="extract_zip_archive",
        description="Mengekstrak (unzip) seluruh berkas dari file arsip ZIP ke folder tujuan secara instan dalam hitungan milidetik.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "zip_path": {"type": "STRING", "description": "Nama atau path berkas ZIP yang ingin diekstrak, misal 'project.zip'."},
                "destination_folder": {"type": "STRING", "description": "Folder tujuan ekstraksi (opsional, default ke folder aktif)."}
            },
            "required": ["zip_path"]
        }
    ),
    types.FunctionDeclaration(
        name="rezip_archive",
        description="Menambah, menimpa, atau memperbarui berkas di dalam arsip ZIP yang sudah ada secara cepat tanpa mengekstrak seluruh isi arsip (Fast in-memory Re-zip).",
        parameters={
            "type": "OBJECT",
            "properties": {
                "zip_path": {"type": "STRING", "description": "Nama atau path berkas ZIP yang ingin diperbarui."},
                "files_to_add": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Daftar path berkas lokal yang ingin ditambahkan atau ditimpa ke dalam ZIP."
                },
                "files_to_remove": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Daftar nama berkas di dalam ZIP yang ingin dihapus (opsional)."
                },
                "output_path": {"type": "STRING", "description": "Path keluaran berkas ZIP baru (opsional, jika kosong menimpa ZIP asal)."}
            },
            "required": ["zip_path", "files_to_add"]
        }
    ),
    types.FunctionDeclaration(
        name="read_zip_contents",
        description="Membaca dan memeriksa daftar berkas di dalam file ZIP beserta ukuran asli dan ukuran kompresinya secara cepat tanpa mengekstrak ke disk (100% read-only).",
        parameters={
            "type": "OBJECT",
            "properties": {
                "zip_path": {"type": "STRING", "description": "Nama atau path berkas ZIP yang ingin diperiksa, misal 'project.zip'."}
            },
            "required": ["zip_path"]
        }
    ),
    types.FunctionDeclaration(
        name="send_document_file",
        description="Mengirimkan berkas dokumen lokal fisik (.pdf, .docx, .zip, .csv, dll.) langsung ke chat Telegram atau WhatsApp pengguna agar bisa diunduh langsung di ponsel.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Path atau nama file lokal yang ingin dikirimkan."},
                "channel": {"type": "STRING", "description": "Channel tujuan ('telegram' atau 'whatsapp', default 'telegram')."},
                "caption": {"type": "STRING", "description": "Teks pengantar atau judul dokumen yang dikirimkan."}
            },
            "required": ["file_path"]
        }
    ),
    types.FunctionDeclaration(
        name="web_search",
        description="Mencari informasi real-time dan peristiwa terkini di internet (berita, fakta, skor, harga, cuaca).",
        parameters={
            "type": "OBJECT",
            "properties": {"query": {"type": "STRING", "description": "Kata kunci pencarian spesifik."}},
            "required": ["query"]
        }
    ),
    types.FunctionDeclaration(
        name="fetch_webpage",
        description="Membaca dan menganalisis isi artikel atau halaman website lengkap dari URL.",
        parameters={
            "type": "OBJECT",
            "properties": {"url": {"type": "STRING", "description": "Tautan URL web yang ingin dibaca."}},
            "required": ["url"]
        }
    ),
    types.FunctionDeclaration(
        name="read_local_file",
        description="Membaca isi file dokumen atau kode lokal (.pdf, .docx, .txt, .md, .py, .js, .ts, .tsx, .json, .css) dengan nomor baris dan opsi paginasi offset/limit.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Path atau nama file lokal."},
                "offset": {"type": "INTEGER", "description": "Nomor baris awal (1-indexed) untuk membaca bagian tertentu dari berkas besar (opsional)."},
                "limit": {"type": "INTEGER", "description": "Jumlah baris maksimal yang ingin dibaca (opsional, default 500)."}
            },
            "required": ["file_path"]
        }
    ),
    types.FunctionDeclaration(
        name="edit_file",
        description="Menyunting berkas kode atau dokumen teks secara in-place dengan mengganti blok old_string menjadi new_string secara presisi (OpenCode / Claude Code standard).",
        parameters={
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Path relatif atau nama berkas yang ingin disunting."},
                "old_string": {"type": "STRING", "description": "Teks atau blok kode lama yang persis ada di dalam berkas yang ingin diganti."},
                "new_string": {"type": "STRING", "description": "Teks atau blok kode baru penggantinya."},
                "replace_all": {"type": "BOOLEAN", "description": "Setel true jika ingin mengganti seluruh kemunculan old_string (default false)."}
            },
            "required": ["file_path", "old_string", "new_string"]
        }
    ),
    types.FunctionDeclaration(
        name="glob_find_files",
        description="Mencari berkas dengan cepat di proyek berdasarkan pola glob pattern nama berkas (misal '**/*.tsx', 'src/**/*.py', '*.json'). Otomatis mengabaikan node_modules, .git, venv.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "pattern": {"type": "STRING", "description": "Pola pencarian glob (misal '**/*.ts', 'src/**/*.py')."},
                "path": {"type": "STRING", "description": "Direktori awal pencarian (opsional, default workspace)."}
            },
            "required": ["pattern"]
        }
    ),
    types.FunctionDeclaration(
        name="grep_search_code",
        description="Mencari teks atau pola regex di seluruh berkas proyek kode (seperti ripgrep / grep). Mengembalikan file path, nomor baris, dan teks yang cocok.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "pattern": {"type": "STRING", "description": "Pola regex atau kata kunci teks yang dicari."},
                "path": {"type": "STRING", "description": "Direktori pencarian (opsional, default workspace)."},
                "include": {"type": "STRING", "description": "Filter ekstensi berkas, misal '*.ts' atau '*.py' (opsional)."}
            },
            "required": ["pattern"]
        }
    ),
    types.FunctionDeclaration(
        name="delegate_subagent",
        description="Mendelegasikan tugas berat atau riset mendalam ke pekerja subagent latar belakang otonom tanpa memblokir thread utama.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "title": {"type": "STRING", "description": "Judul misi subagent."},
                "mission_prompt": {"type": "STRING", "description": "Instruksi dan konteks lengkap untuk diselesaikan oleh subagent."}
            },
            "required": ["title", "mission_prompt"]
        }
    ),
    types.FunctionDeclaration(
        name="write_local_file",
        description="Membuat atau menulis file lokal baru (misal teks, catatan, script python/code) di komputer pengguna.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "Path atau nama file tujuan (misal 'ringkasan.txt')."},
                "content": {"type": "STRING", "description": "Isi teks file yang ingin ditulis."}
            },
            "required": ["file_path", "content"]
        }
    ),
    types.FunctionDeclaration(
        name="list_directory",
        description="Melihat daftar file dan folder di direktori lokal komputer pengguna.",
        parameters={
            "type": "OBJECT",
            "properties": {"directory_path": {"type": "STRING", "description": "Path direktori (opsional, default Desktop)."}}
        }
    ),
    types.FunctionDeclaration(
        name="scan_workspace_folder",
        description="Memindai dan mengindeks struktur hierarki seluruh folder proyek lokal (file tree).",
        parameters={
            "type": "OBJECT",
            "properties": {"folder_path": {"type": "STRING", "description": "Path direktori folder proyek."}},
            "required": ["folder_path"]
        }
    ),
    types.FunctionDeclaration(
        name="execute_cli_command",
        description="Menjalankan perintah CLI terminal lokal aman (git, npm, dir, python, curl).",
        parameters={
            "type": "OBJECT",
            "properties": {"command": {"type": "STRING", "description": "Perintah terminal shell yang ingin dijalankan."}},
            "required": ["command"]
        }
    ),
    types.FunctionDeclaration(
        name="manage_memory_and_todos",
        description="Mencatat to-do list, catatan penting, atau menandai tugas selesai di memori Anara.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Aksi: 'add' (tambah tugas) atau 'complete' (tandai selesai)."},
                "title": {"type": "STRING", "description": "Judul tugas atau catatan."},
                "content": {"type": "STRING", "description": "Detail catatan (opsional)."},
                "category": {"type": "STRING", "description": "Kategori: 'todo' atau 'note'."}
            },
            "required": ["action", "title"]
        }
    ),
    types.FunctionDeclaration(
        name="system_control",
        description="Mengontrol komputer desktop Windows: membuka aplikasi lokal (Spotify, Notepad, Calculator, VS Code, Browser, dll).",
        parameters={
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Aksi: 'open', 'buka', 'launch'."},
                "target": {"type": "STRING", "description": "Nama aplikasi target."}
            },
            "required": ["action", "target"]
        }
    ),
    types.FunctionDeclaration(
        name="custom_webhook",
        description="Mengirimkan sinyal HTTP Webhook ke sistem automasi eksternal (n8n, Make, Zapier, Home Assistant).",
        parameters={
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING", "description": "URL endpoint webhook tujuan."},
                "method": {"type": "STRING", "description": "Metode HTTP (POST/GET)."},
                "payload_json": {"type": "STRING", "description": "String JSON payload."}
            },
            "required": ["url"]
        }
    ),
    types.FunctionDeclaration(
        name="project_hud",
        description="Memproyeksikan kartu visual holografik langsung ke layar HUD pengguna secara proaktif.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "visual_type": {"type": "STRING", "description": "Tipe visual: 'knowledge_card', 'todo_list', 'code', 'file_tree'."},
                "title": {"type": "STRING", "description": "Judul kartu HUD."},
                "summary": {"type": "STRING", "description": "Ringkasan teks."},
                "specs_json": {"type": "STRING", "description": "JSON detail spesifikasi (opsional)."}
            },
            "required": ["visual_type", "title", "summary"]
        }
    ),
    types.FunctionDeclaration(
        name="whatsapp_read_messages",
        description="Membaca daftar pesan chat masuk yang belum dibaca dari akun WhatsApp Web pengguna.",
        parameters={
            "type": "OBJECT",
            "properties": {"unread_only": {"type": "BOOLEAN", "description": "Hanya ambil pesan belum dibaca."}}
        }
    ),
    types.FunctionDeclaration(
        name="whatsapp_send_message",
        description="Mengirimkan pesan chat ke kontak atau nomor telepon tertentu melalui WhatsApp Web.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "recipient": {"type": "STRING", "description": "Nama kontak atau nomor telepon tujuan."},
                "message": {"type": "STRING", "description": "Isi pesan teks yang ingin dikirimkan."}
            },
            "required": ["recipient", "message"]
        }
    ),
    types.FunctionDeclaration(
        name="telegram_read_messages",
        description="Membaca pesan masuk terbaru dari Bot Telegram Anara.",
        parameters={
            "type": "OBJECT",
            "properties": {"limit": {"type": "INTEGER", "description": "Jumlah pesan maksimal."}}
        }
    ),
    types.FunctionDeclaration(
        name="telegram_send_message",
        description="Mengirimkan pesan ke chat pengguna atau grup Telegram.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "message": {"type": "STRING", "description": "Isi pesan teks yang ingin dikirimkan."},
                "chat_id": {"type": "STRING", "description": "ID chat/grup tujuan (opsional)."}
            },
            "required": ["message"]
        }
    ),
    types.FunctionDeclaration(
        name="gmail_read_inbox",
        description="Membaca daftar email terbaru yang belum dibaca dari akun Google Gmail.",
        parameters={
            "type": "OBJECT",
            "properties": {"limit": {"type": "INTEGER", "description": "Jumlah email maksimal."}}
        }
    ),
    types.FunctionDeclaration(
        name="calendar_get_schedule",
        description="Melihat agenda jadwal dan acara terdekat dari Google Calendar.",
        parameters={
            "type": "OBJECT",
            "properties": {"days": {"type": "INTEGER", "description": "Rentang hari ke depan."}}
        }
    ),
    types.FunctionDeclaration(
        name="trigger_avatar_animation",
        description="Menggerakkan tubuh atau ekspresi 3D avatar Anara di layar (contoh: 'dance' untuk menari Rumba dengan musik, 'greeting' atau 'wave' untuk melambaikan tangan, 'salute' untuk memberi hormat, 'thinking' untuk pose berpikir, 'laughing' untuk tertawa gembira, 'shy' untuk malu-malu). Panggil tool ini secara alami ketika diminta menari, menyapa, atau mengekspresikan gestur tubuh fisik.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "animation_name": {"type": "STRING", "description": "Nama animasi/gestur ('dance', 'greeting', 'salute', 'thinking', 'laughing', 'shy', dll)."},
                "emotion": {"type": "STRING", "description": "Ekspresi emosi pelengkap ('happy', 'curious', 'joy', 'neutral', 'empathy')."}
            },
            "required": ["animation_name"]
        }
    ),
    types.FunctionDeclaration(
        name="learn_and_save_skill",
        description="Anara Lifelong Learning Engine: Mengingat dan menyimpan prosedur teknis baru, alur kerja arsitektur, atau resep koding ke database SQLite Anara (tabel agent_skills) secara permanen untuk digunakan kembali di masa depan. Panggil tool ini secara otonom setiap kali kamu menemukan atau merancang pola implementasi yang bernilai.",
        parameters={
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "description": "Nama spesifik dari keahlian/skill, misal 'Scaffold Proyek React Vite Tailwind', 'Setup Docker Swarm Traefik', 'Optimasi Query SQLite BM25'."},
                "category": {"type": "STRING", "description": "Kategori keahlian: 'coding', 'architecture', 'research', 'devops', 'system'."},
                "description": {"type": "STRING", "description": "Ringkasan manfaat dan kapan keahlian ini harus digunakan."},
                "trigger_keywords": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Daftar kata kunci pemicu keahlian ini (misal: ['react', 'vite', 'tailwind'])."},
                "procedure_steps": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Langkah-langkah prosedur logis berurutan untuk mengeksekusi keahlian ini."}
            },
            "required": ["name", "description", "procedure_steps"]
        }
    ),
    types.FunctionDeclaration(
        name="interactive_question",
        description=(
            "Menampilkan kartu kuesioner interaktif bertahap (Wizard Card) ke layar pengguna untuk mengumpulkan preferensi, "
            "kebutuhan fitur, pilihan arsitektur, dan mengklarifikasi instruksi yang ambigu SEBELUM menyusun rencana kerja di Plan Mode. "
            "PENTING: Selalu panggil tool ini ketika instruksi pengguna masih umum/luas (misal: 'buatkan website react', 'buatkan aplikasi mobile', 'buatkan sistem backend') "
            "agar rencana kerja yang kamu susun 100% tepat sasaran dan sesuai ekspektasi pengguna."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "questions": {
                    "type": "ARRAY",
                    "description": "Daftar pertanyaan interaktif bertahap yang ingin diajukan ke pengguna.",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "header": {"type": "STRING", "description": "Label singkat kategori pertanyaan (maksimal 30 karakter, misal 'Jenis Website', 'Pilihan Stack', 'Lokasi Proyek')."},
                            "question": {"type": "STRING", "description": "Pertanyaan lengkap yang diajukan ke pengguna."},
                            "multiple": {"type": "BOOLEAN", "description": "Apakah pengguna boleh memilih lebih dari satu jawaban (default false)."},
                            "options": {
                                "type": "ARRAY",
                                "description": "Daftar pilihan jawaban.",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "label": {"type": "STRING", "description": "Teks judul pilihan (misal: 'E-Commerce / Toko Online (Recommended)')."},
                                        "description": {"type": "STRING", "description": "Penjelasan detail mengenai opsi ini."}
                                    },
                                    "required": ["label", "description"]
                                }
                            }
                        },
                        "required": ["header", "question", "options"]
                    }
                }
            },
            "required": ["questions"]
        }
    ),
]

TOOL_RISK_CLASSIFICATION: Dict[str, str] = {
    # Tier 1: READ_ONLY (Always allowed in any mode & channel)
    "interactive_question": "read_only",
    "read_local_file": "read_only",
    "grep_search_code": "read_only",
    "glob_find_files": "read_only",
    "list_directory": "read_only",
    "scan_workspace_folder": "read_only",
    "web_search": "read_only",
    "fetch_webpage": "read_only",
    "learn_and_save_skill": "read_only",
    "whatsapp_read_messages": "read_only",
    "telegram_read_messages": "read_only",
    "gmail_read_inbox": "read_only",
    "calendar_get_schedule": "read_only",
    "trigger_avatar_animation": "read_only",
    "project_hud": "read_only",
    "read_zip_contents": "read_only",

    # Tier 2: ACTION (External side-effects, isolated & reversible)
    "whatsapp_send_message": "action",
    "telegram_send_message": "action",
    "send_document_file": "action",
    "custom_webhook": "action",
    "manage_memory_and_todos": "action",

    # Tier 3: MUTATING (Modifies file/system/code/shell — ALWAYS requires Plan Mode first)
    "edit_file": "mutating",
    "write_local_file": "mutating",
    "execute_cli_command": "mutating",
    "generate_file_artifact": "mutating",
    "create_zip_archive": "mutating",
    "extract_zip_archive": "mutating",
    "delegate_subagent": "mutating",

    # Tier 4: ASK (Destructive, irreversible, or host environment takeover — granular approval required)
    "system_control": "ask",
}

READ_ONLY_TOOL_NAMES = {
    name for name, risk in TOOL_RISK_CLASSIFICATION.items() if risk == "read_only"
}
ACTION_TOOL_NAMES = {
    name for name, risk in TOOL_RISK_CLASSIFICATION.items() if risk == "action"
}
MUTATING_TOOL_NAMES = {
    name for name, risk in TOOL_RISK_CLASSIFICATION.items() if risk == "mutating"
}
ASK_TOOL_NAMES = {
    name for name, risk in TOOL_RISK_CLASSIFICATION.items() if risk == "ask"
}


def get_tool_risk(tool_name: str) -> str:
    """Returns the risk tier of a given tool ('read_only', 'action', 'mutating', or 'ask')."""
    if tool_name in TOOL_RISK_CLASSIFICATION:
        return TOOL_RISK_CLASSIFICATION[tool_name]
    try:
        from .registry import registry
        import tools.tool_specs
        if tool_name in registry._tools:
            return registry.get_risk(tool_name)
    except Exception:
        pass
    return "mutating"


import re

def is_safe_read_only_cli_command(command: str) -> bool:
    """
    Validates if a CLI command in Plan Mode is purely for safe host/environment inspection
    using the unified Parameter-Aware AST Dissector in plan_detector.py.
    """
    cmd = (command or "").strip()
    if not cmd:
        return False

    try:
        from core.plan_detector import evaluate_command_safety
        return evaluate_command_safety(cmd) == "read_only"
    except Exception:
        pass

    # Check for actual shell file redirection (> or >>), ignoring arrows (->, =>) and quotes
    cmd_no_quotes = re.sub(r'"[^"]*"|\'[^\']*\'', "", cmd)
    if re.search(r"(?<![-=])>[>]?", cmd_no_quotes):
        return False

    cmd_lower = cmd.lower()
    mutating_tokens = [
        "npm i ", "npm install", "npm run", "npm test", "npm start", "npm exec", "npm build", "npm create", "npx ", "vite create",
        "pip install", "pip uninstall", "yarn add", "yarn test", "yarn run", "yarn start",
        "pnpm add", "pnpm test", "pnpm run", "pnpm start", "cargo add", "cargo build", "cargo test", "cargo run",
        "git commit", "git push", "git merge", "git rebase", "git checkout -b", "git branch -d",
        "rmdir", "del ", "erase ", "mkdir ", "new-item",
        "set-content", "add-content", "out-file", "remove-item", "move-item", "copy-item",
        "stop-process", "taskkill", "kill "
    ]
    for tok in mutating_tokens:
        if tok in cmd_lower:
            return False

    # Short 2-char mutating command aliases MUST use word boundary to avoid false-matching 'cmd /c', 'term', etc.
    for p in [r"\bmd\s+", r"\bni\s+", r"\brm\s+"]:
        if re.search(p, cmd_lower):
            return False

    # Direct fast-match for safe read-only inspection commands
    safe_roots = [
        "win32_battery", "powerstatus", "batteryreport", "estimatedchargeremaining", "batterystatus",
        "get-psdrive", "get-volume", "get-disk", "win32_logicaldisk", "psdrive", "diskfree", "df ", "free ",
        "win32_operatingsystem", "win32_processor", "win32_computersystem", "freeprivatebytes",
        "get-process", "get-service", "get-ciminstance", "get-wmiobject", "wmic",
        "systeminfo", "hostname", "get-uptime", "reg query", "tasklist", "driverquery", "node -v", "npm -v", "python -v", "git status", "git log", "git diff",
        "test-path", "get-childitem", "get-item", "get-command", "get-location", "get-date",
        "shell.application", "namespace(", ".items()", "select-object", "format-table", "format-list",
        "measure-object", "sort-object", "where-object", "out-string", "get-acl", "get-content",
        "recycle.bin", "recyclebin", "get-itemproperty", "findstr", "dir /", "dir ", "ls "
    ]
    if any(k in cmd_lower for k in safe_roots):
        return True

    # Python one-liner inspection (python -c "import ... print(...)")
    if re.search(r"^python(?:\.exe)?\s+-c\b", cmd_lower) or re.search(r"^python3(?:\.exe)?\s+-c\b", cmd_lower):
        py_mutating = [
            "open(", "write(", ".write", "os.remove", "os.unlink", "os.rmdir", "shutil.rmtree",
            "os.rename", "os.replace", "shutil.move", "shutil.copy", "subprocess.", "os.system"
        ]
        if not any(pm in cmd_lower for pm in py_mutating):
            return True

    safe_patterns = [
        r"^node\s+-[vV]", r"^npm\s+-[vV]", r"^pnpm\s+-[vV]", r"^yarn\s+-[vV]", r"^bun\s+-[vV]",
        r"^python\s+--?version", r"^python\s+-V", r"^pip\s+--?version", r"^pip\s+list",
        r"^git\s+--version", r"^git\s+status", r"^git\s+branch", r"^git\s+log", r"^git\s+diff",
        r"^\$env:\w+", r"^test-path\b", r"^get-childitem\b", r"^get-item\b", r"^get-command\b", r"^get-location\b",
        r"^pwd\b", r"^dir\b", r"^ls\b", r"^where(?:\.exe)?\b", r"^which\b", r"^whoami\b",
        r"^wmic\b", r"^get-ciminstance\b", r"^get-wmiobject\b", r"^powercfg\b",
        r"^get-psdrive\b", r"^get-volume\b", r"^get-disk\b", r"^df\b", r"^free\b",
        r"^systeminfo\b", r"^hostname\b", r"^date\b", r"^time\b", r"^get-date\b",
        r"^get-process\b", r"^get-service\b", r"^get-uptime\b",
        r"^ipconfig\b", r"^ping\b", r"^nslookup\b", r"^netstat\b", r"^curl\b",
        r"^cat\b", r"^type\b", r"^head\b", r"^tail\b", r"^echo\b", r"^write-output\b",
        r"^select\b", r"^select-object\b", r"^format-table\b", r"^format-list\b",
        r"^measure-object\b", r"^sort-object\b", r"^where-object\b",
    ]

    first_clean = re.sub(r"^(?:powershell(?:\.exe)?|cmd(?:\.exe)?)\s+(?:-(?:c|command|k)\s+)?", "", cmd, flags=re.IGNORECASE).strip()
    first_clean = first_clean.lstrip("([\"' $").strip()
    return any(re.search(pat, first_clean, re.IGNORECASE) for pat in safe_patterns)

def check_tool_permission(tool_name: str, mode: str = "plan", args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Anara Standard Permission Gate:
    Enforces 3-tier risk boundary (read_only, mutating, ask) programmatically at code level.
    """
    risk = get_tool_risk(tool_name)

    # Plan Mode Gate: strictly block mutating tools, permit safe read-only CLI inspection
    if mode == "plan":
        if tool_name == "execute_cli_command":
            cmd = (args or {}).get("command", "")
            if is_safe_read_only_cli_command(cmd):
                return {"allowed": True, "risk": "read_only"}
            return {
                "allowed": False,
                "risk": "mutating",
                "message": (
                    f"DITOLAK PERMISSION GATE: Perintah terminal '{cmd}' tidak diizinkan di Plan Mode. "
                    "Hanya perintah inspeksi lingkungan read-only (seperti node -v, Test-Path, Get-ChildItem, $env:USERPROFILE) yang diizinkan."
                )
            }
        if risk != "read_only":
            return {
                "allowed": False,
                "risk": risk,
                "message": (
                    f"DITOLAK PERMISSION GATE: Tool '{tool_name}' (risk={risk}) diblokir di Plan Mode. "
                    "Mode ini beroperasi dalam status Read-Only untuk eksplorasi dan perancangan arsitektur. "
                    "Usulkan perubahan ini sebagai tahapan rencana kerja yang dapat dieksekusi di Build Mode."
                )
            }

    # Granular Risk Gate for 'ask' category tools (destructive commands, etc.)
    if risk == "ask" and tool_name == "execute_cli_command":
        cmd = (args or {}).get("command", "").lower()
        dangerous_patterns = [
            r"\brm\s+-[rf]{1,2}\s+[/~]",
            r"\bformat\s+[a-z]:",
            r"\bdiskpart\b",
            r"\bdrop\s+database\b",
            r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;",
            r"\bshutdown\b",
            r"\breboot\b",
        ]
        for dp in dangerous_patterns:
            if re.search(dp, cmd):
                return {
                    "allowed": False,
                    "risk": "ask",
                    "message": f"DITOLAK SISTEM KEAMANAN: Perintah '{cmd}' terdeteksi berisiko tinggi terhadap integritas sistem operasi dan diblokir."
                }

    return {"allowed": True, "risk": risk}


def get_agent_tools(read_only: bool = False, enabled_set: Optional[Set[str]] = None) -> List[types.Tool]:
    """Returns the Tool object wrapping function declarations. In Plan Mode, write tools are physically stripped."""
    seen_names = set()
    decls = []

    # 1. Base catalog function declarations
    for fn in ANARA_FUNCTION_DECLARATIONS:
        name = fn.name
        if enabled_set is not None and name not in enabled_set:
            continue
        if read_only and name not in READ_ONLY_TOOL_NAMES:
            continue
        if name not in seen_names:
            seen_names.add(name)
            decls.append(fn)

    # 2. Decentralized dynamic registry declarations
    try:
        from .registry import registry
        import tools.tool_specs
        for name, t in registry._tools.items():
            if enabled_set is not None and name not in enabled_set:
                continue
            if read_only and t.risk != "read_only":
                continue
            if name not in seen_names and t.declaration:
                seen_names.add(name)
                decls.append(t.declaration)
    except Exception as e:
        logger.debug(f"[AgentTools] Error merging registry tools: {e}")

    return [types.Tool(function_declarations=decls)]


def get_tools_catalog(enabled_set: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
    """Returns a structured JSON catalog of all registered agent tools for UI inspection."""
    catalog = []
    seen = set()

    for fn in ANARA_FUNCTION_DECLARATIONS:
        name = fn.name
        seen.add(name)
        desc = fn.description or ""
        risk = get_tool_risk(name)
        is_ro = risk == "read_only"

        if name in ["edit_file", "write_local_file", "generate_file_artifact", "create_zip_archive", "rezip_archive"]:
            cat = "coding"
            icon = "code"
        elif name in ["read_local_file", "glob_find_files", "grep_search_code", "scan_workspace_folder", "list_directory"]:
            cat = "exploration"
            icon = "search"
        elif name in ["execute_cli_command", "system_control", "custom_webhook"]:
            cat = "system"
            icon = "terminal"
        elif name in ["web_search", "fetch_webpage", "delegate_subagent", "manage_memory_and_todos", "learn_and_save_skill"]:
            cat = "intelligence"
            icon = "brain"
        else:
            cat = "connectivity"
            icon = "link"

        params = fn.parameters
        if hasattr(params, "to_dict"):
            p_dict = params.to_dict()
        elif hasattr(params, "__dict__"):
            p_dict = {k: v for k, v in params.__dict__.items() if not k.startswith("_")}
        elif isinstance(params, dict):
            p_dict = params
        else:
            p_dict = {}

        catalog.append({
            "name": name,
            "description": desc,
            "category": cat,
            "icon": icon,
            "risk": risk,
            "is_read_only": is_ro,
            "mode_label": "Plan & Build" if is_ro else "Build Only",
            "is_enabled": name in enabled_set if enabled_set else True,
            "parameters": p_dict
        })

    # Merge additional tools from registry
    try:
        from .registry import registry
        import tools.tool_specs
        for name, t in registry._tools.items():
            if name in seen:
                continue
            seen.add(name)
            is_ro = (t.risk == "read_only")
            catalog.append({
                "name": name,
                "description": t.description,
                "category": t.category,
                "icon": t.icon,
                "risk": t.risk,
                "is_read_only": is_ro,
                "mode_label": "Plan & Build" if is_ro else "Build Only",
                "toolset_id": t.toolset,
                "toolset_title": t.toolset.replace("_", " ").title(),
                "is_enabled": name in enabled_set if enabled_set else True,
                "parameters": t.parameters
            })
    except Exception as e:
        logger.debug(f"[AgentTools] Error merging registry catalog: {e}")

    return catalog


async def dispatch_tool_call(
    name: str,
    args: Dict[str, Any],
    read_only: bool = False,
    mode: Optional[str] = None
) -> Dict[str, Any]:
    """Routes an incoming function_call from Gemini Live or ReAct loop to its Python executor."""
    effective_mode = mode if mode else ("plan" if read_only else "build")
    logger.info(f"[AnaraAgent] Dispatching tool '{name}' with args: {args} (mode={effective_mode})")

    # ── Permission Gate 3-Tier Enforcement ──
    perm = check_tool_permission(name, mode=effective_mode, args=args)
    if not perm["allowed"]:
        logger.warning(f"[PermissionGate] Blocked execution of '{name}': {perm['message']}")
        return {
            "status": "error",
            "error_type": "permission_denied",
            "risk": perm.get("risk"),
            "message": perm["message"]
        }
    try:
        if name == "generate_file_artifact":
            return await _tool_generate_file_artifact(
                filename=args.get("filename", "document.txt"),
                content=args.get("content", ""),
                title=args.get("title"),
                destination_folder=args.get("destination_folder")
            )
        elif name == "create_zip_archive":
            return await _tool_create_zip_archive(
                archive_name=args.get("archive_name"),
                folder_path=args.get("folder_path"),
                files=args.get("files")
            )
        elif name == "extract_zip_archive":
            return await _tool_extract_zip_archive(
                zip_path=args.get("zip_path", ""),
                destination_folder=args.get("destination_folder")
            )
        elif name == "rezip_archive":
            return await _tool_rezip_archive(
                zip_path=args.get("zip_path", ""),
                files_to_add=args.get("files_to_add", []),
                files_to_remove=args.get("files_to_remove"),
                output_path=args.get("output_path")
            )
        elif name == "read_zip_contents":
            return await _tool_read_zip_contents(
                zip_path=args.get("zip_path", "")
            )
        elif name == "send_document_file":
            return await _tool_send_document_file(
                file_path=args.get("file_path", ""),
                channel=args.get("channel"),
                recipient=args.get("recipient"),
                caption=args.get("caption")
            )
        elif name == "web_search":
            return await _tool_web_search(args.get("query", ""))
        elif name == "fetch_webpage":
            return await _tool_fetch_webpage(args.get("url", ""))
        elif name == "read_local_file":
            return await _tool_read_local_file(
                file_path=args.get("file_path", ""),
                offset=args.get("offset"),
                limit=args.get("limit")
            )
        elif name == "edit_file":
            return await _tool_edit_file(
                file_path=args.get("file_path", ""),
                old_string=args.get("old_string", ""),
                new_string=args.get("new_string", ""),
                replace_all=bool(args.get("replace_all", False))
            )
        elif name == "glob_find_files":
            return await _tool_glob_find_files(
                pattern=args.get("pattern", ""),
                path=args.get("path")
            )
        elif name == "grep_search_code":
            return await _tool_grep_search_code(
                pattern=args.get("pattern", ""),
                path=args.get("path"),
                include=args.get("include")
            )
        elif name == "delegate_subagent":
            return await _tool_delegate_subagent(
                title=args.get("title", ""),
                mission_prompt=args.get("mission_prompt", "")
            )
        elif name == "write_local_file":
            return await _tool_write_local_file(args.get("file_path", ""), args.get("content", ""))
        elif name == "list_directory":
            return await _tool_list_directory(args.get("directory_path"))
        elif name == "scan_workspace_folder":
            return await _tool_scan_workspace_folder(args.get("folder_path", ""))
        elif name == "execute_cli_command":
            return await _tool_execute_cli_command(args.get("command", ""))
        elif name == "interactive_question":
            return await _tool_interactive_question(args.get("questions", []))
        elif name == "manage_memory_and_todos":
            return await _tool_manage_memory_and_todos(
                action=args.get("action", "add"),
                title=args.get("title", ""),
                content=args.get("content"),
                category=args.get("category", "todo")
            )
        elif name == "system_control":
            return await _tool_system_control(
                action=args.get("action", "open"),
                target=args.get("target")
            )
        elif name == "custom_webhook":
            return await _tool_custom_webhook(
                url=args.get("url", ""),
                method=args.get("method", "POST"),
                payload_json=args.get("payload_json")
            )
        elif name == "project_hud":
            return await _tool_project_hud(
                visual_type=args.get("visual_type", "knowledge_card"),
                title=args.get("title", ""),
                summary=args.get("summary", ""),
                specs_json=args.get("specs_json")
            )
        elif name == "whatsapp_read_messages":
            from integrations import get_unread_whatsapp_messages, is_whatsapp_connected
            if not is_whatsapp_connected():
                return {"status": "error", "message": "WhatsApp belum terhubung. Silakan scan QR code terlebih dahulu."}
            unread = await get_unread_whatsapp_messages()
            return {"status": "success", "unread_count": len(unread), "messages": unread}
        elif name == "whatsapp_send_message":
            from integrations import send_whatsapp_message, is_whatsapp_connected
            if not is_whatsapp_connected():
                return {"status": "error", "message": "WhatsApp belum terhubung."}
            phone = args.get("recipient", "").strip()
            msg = args.get("message", "").strip()
            ok = await send_whatsapp_message(phone, msg)
            return {"status": "success" if ok else "error", "sent_to": phone}
        elif name == "telegram_read_messages":
            from integrations import get_recent_telegram_updates, get_telegram_status
            st = await get_telegram_status()
            if st.get("status") != "connected":
                return {"status": "error", "message": "Bot Telegram belum terhubung."}
            msgs = await get_recent_telegram_updates(limit=args.get("limit", 5))
            return {"status": "success", "messages": msgs}
        elif name == "telegram_send_message":
            from integrations import send_telegram_message, get_telegram_status
            st = await get_telegram_status()
            if st.get("status") != "connected":
                return {"status": "error", "message": "Bot Telegram belum diatur."}
            return await send_telegram_message(str(args.get("message", "")), chat_id=args.get("chat_id"))
        elif name == "gmail_read_inbox":
            from integrations import get_unread_emails, get_google_status
            st = await get_google_status()
            if st.get("status") != "connected":
                return {"status": "error", "message": "Akun Google Workspace belum ditautkan."}
            emails = await get_unread_emails(limit=args.get("limit", 5))
            return {"status": "success", "emails": emails}
        elif name == "calendar_get_schedule":
            from integrations import get_upcoming_events, get_google_status
            st = await get_google_status()
            if st.get("status") != "connected":
                return {"status": "error", "message": "Akun Google Workspace belum ditautkan."}
            events = await get_upcoming_events(days=args.get("days", 3))
            return {"status": "success", "events": events}
        elif name == "trigger_avatar_animation":
            return await _tool_trigger_avatar_animation(
                animation_name=str(args.get("animation_name", "dance")),
                emotion=args.get("emotion")
            )
        elif name == "learn_and_save_skill":
            return await _tool_learn_and_save_skill(
                name=str(args.get("name", "")),
                category=str(args.get("category", "general")),
                description=str(args.get("description", "")),
                trigger_keywords=args.get("trigger_keywords"),
                procedure_steps=args.get("procedure_steps"),
            )
        else:
            try:
                from .registry import registry
                import tools.tool_specs
                handler = registry.get_handler(name)
                if handler:
                    return await registry.dispatch(name, args)
            except Exception as reg_err:
                logger.error(f"[AgentTools] Registry dispatch error for {name}: {reg_err}")

            logger.warning(f"[AgentTools] Unrecognized tool '{name}'")
            return {"status": "error", "message": f"Alat '{name}' tidak terdaftar."}
    except Exception as e:
        logger.error(f"[AgentTools] Tool error in '{name}': {e}", exc_info=True)
        return {"status": "error", "message": f"Kesalahan pada tool {name}: {str(e)}"}


async def generate_text_response_with_tools(
    client: Any,
    model: str,
    user_prompt: str,
    system_instruction: str,
    max_tokens: Optional[int] = None,
    temperature: float = 0.7,
    read_only: bool = False,
    progress_cb: Optional[Callable[[Dict[str, Any]], Any]] = None,
    token_cb: Optional[Callable[[str], Any]] = None,
    intercept_mutating_tools: bool = False,
) -> Any:
    """Executes a multi-step ReAct turn using Gemini model with native tool chaining (uncapped tokens by default)."""
    tools = get_agent_tools(read_only=read_only)
    cfg_kwargs: Dict[str, Any] = {
        "temperature": temperature,
        "tools": tools,
    }
    if max_tokens is not None and max_tokens > 0:
        cfg_kwargs["max_output_tokens"] = max_tokens
    if system_instruction and system_instruction.strip():
        cfg_kwargs["system_instruction"] = system_instruction.strip()
    config = types.GenerateContentConfig(**cfg_kwargs)
    
    contents = [user_prompt]
    last_tool_summary = ""
    for step in range(25):
        try:
            res = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
        except Exception as step_err:
            err_str = str(step_err).lower()
            if "thought_signature" in err_str or "function_call" in err_str:
                logger.warning(f"[AnaraAgent Step {step+1}] Model {model} hit thought_signature requirement — breaking to synthesis: {step_err}")
                break
            raise step_err

        if not res:
            break

        function_calls = getattr(res, "function_calls", None)
        if not function_calls and res.candidates:
            for part in (res.candidates[0].content.parts or []):
                if getattr(part, "function_call", None):
                    if not function_calls:
                        function_calls = []
                    function_calls.append(part.function_call)

        if not function_calls:
            if res.text and res.text.strip():
                try:
                    from memory import memory_engine
                    u_meta = getattr(res, "usage_metadata", None)
                    p_tok = getattr(u_meta, "prompt_token_count", 0) if u_meta else 0
                    c_tok = getattr(u_meta, "candidates_token_count", 0) if u_meta else 0
                    if p_tok or c_tok:
                        memory_engine.record_token_usage(
                            model_id=model,
                            provider="gemini",
                            prompt_tokens=p_tok,
                            completion_tokens=c_tok
                        )
                except Exception:
                    pass
                return res.text.strip()
            break

        contents.append(res.candidates[0].content)

        fn_parts = []
        for fc in function_calls:
            fn_name = getattr(fc, "name", "")
            clean_fn_name = fn_name.split(":")[-1]
            fn_args = getattr(fc, "args", {}) or {}
            fn_id = getattr(fc, "id", None)
            logger.info(f"[AnaraAgent Step {step+1}] Invoked: {fn_name!r} (clean={clean_fn_name!r}, id={fn_id}) with args {fn_args}")

            risk = get_tool_risk(clean_fn_name)
            if clean_fn_name in ("execute_cli_command", "terminal", "run_terminal_command"):
                from core.plan_detector import evaluate_command_safety
                risk = evaluate_command_safety(fn_args.get("command", ""))

            if intercept_mutating_tools and risk in ("mutating", "ask"):
                logger.info(f"[ToolInterceptor Native] Intercepted mutating tool '{clean_fn_name}' for Plan approval.")
                cmd_preview = fn_args.get("command") or fn_args.get("file_path") or fn_args.get("title") or ""
                return {
                    "intercepted": True,
                    "tool_name": clean_fn_name,
                    "tool_args": fn_args,
                    "tool_risk": risk,
                    "cmd_preview": cmd_preview,
                    "raw_call": {"tool": clean_fn_name, "arguments": fn_args},
                }

            if progress_cb:
                try:
                    res_cb = progress_cb({"tool_name": fn_name, "status": "running"})
                    if asyncio.iscoroutine(res_cb):
                        await res_cb
                except Exception:
                    pass

            tool_res = await dispatch_tool_call(fn_name, fn_args, read_only=read_only)

            if fn_name == "interactive_question" and isinstance(tool_res, dict) and tool_res.get("dismissed"):
                dismiss_notice = "Pertanyaan ditutup."
                if token_cb:
                    try:
                        res = token_cb(dismiss_notice)
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception:
                        pass
                return dismiss_notice
            
            if progress_cb:
                try:
                    res_cb = progress_cb({
                        "tool_name": fn_name,
                        "status": "done",
                        "summary": (tool_res.get("message") or tool_res.get("summary") or "")[:160] if isinstance(tool_res, dict) else str(tool_res)[:160]
                    })
                    if asyncio.iscoroutine(res_cb):
                        await res_cb
                except Exception:
                    pass

            if isinstance(tool_res, dict) and tool_res.get("message"):
                last_tool_summary = tool_res.get("message")

            fn_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fn_name,
                        id=fn_id,
                        response={"result": tool_res}
                    )
                )
            )

        contents.append(types.Content(parts=fn_parts))

    if last_tool_summary or len(contents) > 1:
        if progress_cb:
            try:
                res_cb = progress_cb({
                    "tool_name": "agent",
                    "status": "thinking",
                    "summary": "Merumuskan cetak biru arsitektur & spesifikasi..." if read_only else "Menyusun perubahan kode & ringkasan hasil..."
                })
                if asyncio.iscoroutine(res_cb):
                    await res_cb
            except Exception:
                pass
        try:
            synth_kwargs: Dict[str, Any] = {
                "temperature": temperature,
            }
            if max_tokens is not None and max_tokens > 0:
                synth_kwargs["max_output_tokens"] = max_tokens
            if system_instruction and system_instruction.strip():
                synth_kwargs["system_instruction"] = system_instruction.strip()
            synth_config = types.GenerateContentConfig(**synth_kwargs)
            prompt_with_summary = (
                f"{user_prompt}\n\n"
                f"[LAPORAN HASIL EKSEKUSI ALAT]:\n{last_tool_summary or 'Aksi alat selesai dieksekusi.'}\n\n"
                "Instruksi: Sebagai AI Agent, jelaskan secara cerdas, tuntas, dan alami apa yang telah kamu kerjakan, "
                "struktur atau perubahan berkas yang terjadi, dan rekomendasi langkah berikutnya. "
                "Dilarang menggunakan kalimat template kaku."
            )
            synth_res = await client.aio.models.generate_content(
                model=model,
                contents=[prompt_with_summary],
                config=synth_config
            )
            if synth_res and synth_res.text and synth_res.text.strip():
                if token_cb:
                    try:
                        res = token_cb(synth_res.text.strip())
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception:
                        pass
                try:
                    from memory import memory_engine
                    u_meta = getattr(synth_res, "usage_metadata", None)
                    p_tok = getattr(u_meta, "prompt_token_count", 0) if u_meta else 0
                    c_tok = getattr(u_meta, "candidates_token_count", 0) if u_meta else 0
                    if p_tok or c_tok:
                        memory_engine.record_token_usage(
                            model_id=model,
                            provider="gemini",
                            prompt_tokens=p_tok,
                            completion_tokens=c_tok
                        )
                except Exception:
                    pass
                return synth_res.text.strip()
        except Exception as e:
            logger.warning(f"[AnaraAgent] Synthesis step error: {e}")
            if last_tool_summary:
                return str(last_tool_summary)
            raise e

    if last_tool_summary:
        return str(last_tool_summary)
    return ""
