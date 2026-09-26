"""
Soul Loader for Project Anara.
Dynamically reads soul.md (Anara multi-tools + OpenCode plan/build philosophy)
with mtime-based hot-reloading and atomic writing (Anara Standard),
ensuring Anara's core identity is always up to date without backend restart.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

_SOUL_LOCK = threading.RLock()
_SOUL_CACHE: Optional[str] = None
_SOUL_MTIME: float = 0.0


def _find_soul_file() -> Optional[str]:
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(cur_dir))
    candidates = [
        os.path.join(root_dir, "soul.md"),
        os.path.join(cur_dir, "soul.md"),
        os.path.join(os.path.dirname(cur_dir), "soul.md"),
    ]
    for p in candidates:
        if os.path.exists(p) and os.path.isfile(p):
            return p
    return None


def _extract_voice_soul(text: str) -> str:
    """Anara Enterprise Architecture: Adapts soul prompt for real-time voice synthesis."""
    if not text:
        return ""
    lines = []
    for line in text.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("|") or "```" in trimmed:
            continue
        if any(h in trimmed.lower() for h in ("git diff", "terminal command", "sql schema", "file structure")):
            continue
        lines.append(line)
    result = "\n".join(lines).strip()
    return result or text


def get_soul_prompt(mode: str = "chat") -> str:
    """
    Returns the core system prompt loaded from soul.md.
    Hot-reloads if the file has been edited on disk.
    Supports mode-specific specialization ('voice' vs 'chat').
    """
    global _SOUL_CACHE, _SOUL_MTIME
    soul_path = _find_soul_file()

    with _SOUL_LOCK:
        if soul_path:
            try:
                mtime = os.path.getmtime(soul_path)
                if _SOUL_CACHE is None or mtime != _SOUL_MTIME:
                    with open(soul_path, "r", encoding="utf-8") as f:
                        _SOUL_CACHE = f.read().strip()
                    _SOUL_MTIME = mtime
                    logger.info(f"[Soul] Loaded soul.md from {soul_path} (mtime={mtime})")
                
                content = _SOUL_CACHE or ""
                if mode == "voice":
                    return _extract_voice_soul(content)
                return content
            except Exception as e:
                logger.warning(f"[Soul] Error reading soul.md: {e}")

        if _SOUL_CACHE:
            content = _SOUL_CACHE
            if mode == "voice":
                return _extract_voice_soul(content)
            return content

    # Fallback if soul.md cannot be read (Anara Standard: externalized template)
    from core.prompt_loader import load_prompt
    fallback = load_prompt("soul_fallback").strip()
    if mode == "voice":
        return _extract_voice_soul(fallback)
    return fallback


def get_soul_raw() -> str:
    """Returns the raw unparsed soul.md content directly from disk."""
    soul_path = _find_soul_file()
    if soul_path and os.path.exists(soul_path):
        try:
            with open(soul_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"[Soul] Error reading raw soul.md: {e}")
    return get_soul_prompt()


def _atomic_write_soul(target_path: str, content: str) -> bool:
    """Atomically writes content to disk via temporary file rename (Anara Standard)."""
    dir_name = os.path.dirname(target_path)
    tmp_path = os.path.join(dir_name, f".soul_{os.getpid()}_{int(time.time() * 1000)}.tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target_path)
        return True
    except Exception as e:
        logger.warning(f"[Soul] Atomic write failed for {target_path}: {e}")
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return False


def save_soul_raw(content: str) -> bool:
    """
    Saves new content into soul.md on disk atomically and updates the hot-reload cache.
    Protects against 0-byte truncation and ghost file sprawl.
    """
    global _SOUL_CACHE, _SOUL_MTIME
    clean_content = (content or "").replace("\x00", "").strip() + "\n"
    if len(clean_content) > 200_000:
        raise ValueError("Soul content exceeds 200KB limit.")

    cur_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(cur_dir))
    target_path = _find_soul_file() or os.path.join(root_dir, "soul.md")

    with _SOUL_LOCK:
        saved = _atomic_write_soul(target_path, clean_content)
        # Keep sibling copy in sync if exists
        sibling_path = os.path.join(cur_dir, "soul.md")
        if sibling_path != target_path and os.path.exists(sibling_path):
            _atomic_write_soul(sibling_path, clean_content)

        if saved:
            _SOUL_CACHE = clean_content.strip()
            _SOUL_MTIME = os.path.getmtime(target_path) if os.path.exists(target_path) else time.time()
            logger.info(f"[Soul] Successfully atomically saved soul.md to {target_path}.")
        return saved


