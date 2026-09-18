"""
Soul Loader for Project Anara.
Dynamically reads soul.md (Anara multi-tools + OpenCode plan/build philosophy)
with mtime-based hot-reloading, ensuring Anara's core identity is always up to date
without requiring a backend restart.
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_SOUL_CACHE: Optional[str] = None
_SOUL_MTIME: float = 0.0

def _find_soul_file() -> Optional[str]:
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(cur_dir, "soul.md"),
        os.path.join(os.path.dirname(cur_dir), "soul.md"),
        os.path.join(os.path.dirname(os.path.dirname(cur_dir)), "soul.md"),
    ]
    for p in candidates:
        if os.path.exists(p) and os.path.isfile(p):
            return p
    return None

def get_soul_prompt(mode: str = "chat") -> str:
    """
    Returns the core system prompt loaded from soul.md.
    Hot-reloads if the file has been edited on disk.
    """
    global _SOUL_CACHE, _SOUL_MTIME
    soul_path = _find_soul_file()

    if soul_path:
        try:
            mtime = os.path.getmtime(soul_path)
            if _SOUL_CACHE is None or mtime != _SOUL_MTIME:
                with open(soul_path, "r", encoding="utf-8") as f:
                    _SOUL_CACHE = f.read().strip()
                _SOUL_MTIME = mtime
                logger.info(f"[Soul] Loaded soul.md from {soul_path} (mtime={mtime})")
            return _SOUL_CACHE
        except Exception as e:
            logger.warning(f"[Soul] Error reading soul.md: {e}")

    if _SOUL_CACHE:
        return _SOUL_CACHE

    # Fallback if soul.md cannot be read
    return (
        "Kamu adalah Anara, asisten AI visual 3D dan autonomous agent yang cerdas, hangat, dan ekspresif. "
        "Memadukan Anara Agent (multi-tools otonom) dan filosofi OpenCode (protokol Plan & Build mode). "
        "Bicaralah secara alami, ramah, dan ringkas. Sesuaikan bahasa responmu secara cerdas dengan bahasa pengguna tanpa kalimat kaku atau template sistem."
    )

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

def save_soul_raw(content: str) -> bool:
    """Saves new content into soul.md on disk and resets the hot-reload cache."""
    global _SOUL_CACHE, _SOUL_MTIME
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(cur_dir, "soul.md"),
        os.path.join(os.path.dirname(cur_dir), "soul.md"),
    ]
    saved = False
    for p in candidates:
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(content.strip() + "\n")
            saved = True
        except Exception as e:
            logger.warning(f"[Soul] Could not write to {p}: {e}")

    if saved:
        _SOUL_CACHE = content.strip()
        _SOUL_MTIME = os.path.getmtime(candidates[0]) if os.path.exists(candidates[0]) else 0.0
        logger.info("[Soul] Successfully saved new soul.md to disk.")
    return saved

