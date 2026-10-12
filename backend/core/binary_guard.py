"""
binary_guard.py — Binary File Context Pollution Guard for Project Anara.
Parity with Hermes Agent tools/binary_extensions.py (Nous Research).

Prevents tools like read_local_file from reading raw binary data (.exe, .dll, .so, .zip, .pyc, .sqlite, images, etc.)
as UTF-8 text with unicode replacement characters (\\ufffd), which wastes thousands of context tokens
and degrades model reasoning.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Set

BINARY_EXTENSIONS: Set[str] = {
    # Images & Media (Handled by vision tools, not raw text)
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff", ".tif",
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".flv", ".m4v",
    ".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".wma", ".opus",
    # Archives & Compressed formats
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar", ".xz", ".tgz", ".iso",
    # Executables & Compiled binaries
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a", ".obj", ".lib", ".app", ".msi",
    # VM Bytecode & WebAssembly
    ".pyc", ".pyo", ".class", ".jar", ".war", ".ear", ".node", ".wasm",
    # Databases & Indexes
    ".sqlite", ".sqlite3", ".db", ".mdb", ".idx",
    # Fonts
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    # Raw data & blobs
    ".dat", ".data", ".lockb",
}

# Special SQLite journal/wal sidecars
SQLITE_SIDECAR_EXTENSIONS: Set[str] = {".db-wal", ".db-shm", ".sqlite-wal", ".sqlite-shm", ".sqlite3-wal", ".sqlite3-shm"}


OPAQUE_DOCUMENT_EXTENSIONS: Set[str] = {".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"}


def check_binary_write_prohibited(file_path: str, exists: bool) -> tuple[bool, Optional[str]]:
    """
    Checks if writing plain text to file_path is forbidden.
    Returns (is_prohibited, refusal_reason).
    """
    clean = (file_path or "").strip().lower()
    ext = os.path.splitext(clean)[1]

    if ext in OPAQUE_DOCUMENT_EXTENSIONS:
        return True, (
            f"Refusing to write plain text to binary document '{os.path.basename(file_path)}' ({ext}). "
            "A plain text write cannot produce a valid document container and would corrupt the file."
        )

    for sidecar in SQLITE_SIDECAR_EXTENSIONS:
        if clean.endswith(sidecar):
            return True, (
                f"Refusing to write plain text to SQLite sidecar '{os.path.basename(file_path)}'. "
                "Writing text here would corrupt the database."
            )

    if exists and (ext in BINARY_EXTENSIONS or ext == ".pdf"):
        return True, (
            f"Refusing to overwrite existing binary file '{os.path.basename(file_path)}' ({ext}) with plain text. "
            "Writing plain text will destroy the binary asset."
        )

    return False, None


def is_binary_file(file_path: str) -> bool:
    """Checks whether the file has a binary extension unsuitable for UTF-8 reading."""
    clean = (file_path or "").strip().lower()
    if not clean:
        return False

    for sidecar in SQLITE_SIDECAR_EXTENSIONS:
        if clean.endswith(sidecar):
            return True

    ext = os.path.splitext(clean)[1]
    return ext in BINARY_EXTENSIONS


def get_binary_file_notice(file_path: str, size_bytes: Optional[int] = None) -> str:
    """Returns a clean formatted observation suppressing raw binary content."""
    filename = os.path.basename(file_path)
    size_str = f" ({round(size_bytes / 1024, 2)} KB)" if size_bytes is not None else ""
    ext = os.path.splitext(filename)[1].lower()

    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
        hint = "To inspect images, use 'analyze_image' or multimodal vision capabilities."
    elif ext in (".zip", ".tar", ".gz", ".7z", ".rar"):
        hint = "To inspect archive contents, use shell or archive tools rather than text read."
    elif ext in (".sqlite", ".sqlite3", ".db"):
        hint = "To inspect SQLite databases, use database queries or sqlite3 cli."
    else:
        hint = "Raw text display suppressed to avoid context token waste and corruption."

    return (
        f"[Binary File Notice: '{filename}'{size_str} is a compiled or binary asset. "
        f"{hint}]"
    )
