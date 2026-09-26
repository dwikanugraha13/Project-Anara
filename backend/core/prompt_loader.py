"""
prompt_loader.py — Hot-Reloading Externalized Prompt & Template Engine for Project Anara.
Anara Enterprise Architecture:
1. Zero hardcoded prompt strings or behavioral rules embedded inside Python files.
2. In-memory caching with mtime-based hot-reloading (updates take effect immediately without restart).
3. Clean separation of agent constitution, system reminders, and operational guidance from executable logic.
"""

import copy
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

logger = logging.getLogger(__name__)

_PROMPTS_DIR: Optional[Path] = None
_PROMPT_CACHE: Dict[str, Tuple[float, str]] = {}
_YAML_CACHE: Dict[str, Tuple[float, Any]] = {}
_MAX_CACHE_ENTRIES = 64
_CACHE_LOCK = threading.Lock()


def _safe_format(template: str, **kwargs: Any) -> str:
    """
    Safely substitutes {key} placeholders without crashing on unescaped JSON, CSS, or Bash braces.
    Double braces like {{name}} are preserved intact as escaped braces (Anara Standard).
    """
    if not kwargs or not template:
        return template
    # Match {key} but not {{key}} or {key}}
    pattern = re.compile(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})")

    def replacer(match: re.Match) -> str:
        k = match.group(1)
        if k in kwargs:
            val = kwargs[k]
            return str(val) if val is not None else ""
        return match.group(0)

    return pattern.sub(replacer, template)


def _get_prompts_dir() -> Path:
    global _PROMPTS_DIR
    if _PROMPTS_DIR and _PROMPTS_DIR.is_dir():
        return _PROMPTS_DIR

    with _CACHE_LOCK:
        if _PROMPTS_DIR and _PROMPTS_DIR.is_dir():
            return _PROMPTS_DIR

        # Try backend/prompts
        candidate = Path(__file__).resolve().parent.parent / "prompts"
        if candidate.is_dir():
            _PROMPTS_DIR = candidate
            return candidate

        # Try project root prompts
        root_candidate = Path(__file__).resolve().parent.parent.parent / "prompts"
        if root_candidate.is_dir():
            _PROMPTS_DIR = root_candidate
            return root_candidate

        _PROMPTS_DIR = candidate
        return candidate


def load_prompt(relative_name: str, default: str = "", **format_kwargs: Any) -> str:
    """
    Loads a markdown prompt template from backend/prompts/ with mtime hot-reloading.
    If format_kwargs are provided, formats the prompt template safely.
    Strictly prevents path traversal outside the prompts directory.
    """
    clean_name = relative_name.strip().replace("\\", "/")
    if clean_name.startswith("/") or ".." in clean_name.split("/"):
        logger.warning(f"[PromptLoader] Blocked path traversal attempt: {relative_name}")
        return _safe_format(default, **format_kwargs) if format_kwargs else default

    if clean_name.endswith(".md"):
        clean_name = clean_name[:-3]
    prompts_dir = _get_prompts_dir()
    file_path = prompts_dir / f"{clean_name}.md"

    if not file_path.is_file():
        # Check without .md extension
        alt_path = prompts_dir / clean_name
        if alt_path.is_file():
            file_path = alt_path
        else:
            logger.debug(f"[PromptLoader] Prompt file not found: {file_path}. Using fallback.")
            return _safe_format(default, **format_kwargs) if format_kwargs else default

    # Verify path confinement
    try:
        if not file_path.resolve().is_relative_to(prompts_dir.resolve()):
            logger.warning(f"[PromptLoader] Path escaped prompts root: {file_path}")
            return _safe_format(default, **format_kwargs) if format_kwargs else default
    except Exception:
        pass

    try:
        current_mtime = os.path.getmtime(file_path)
        with _CACHE_LOCK:
            cached_entry = _PROMPT_CACHE.get(str(file_path))
            if cached_entry and cached_entry[0] == current_mtime:
                raw_text = cached_entry[1]
            else:
                with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
                    raw_text = f.read()
                if len(_PROMPT_CACHE) >= _MAX_CACHE_ENTRIES:
                    _PROMPT_CACHE.pop(next(iter(_PROMPT_CACHE)), None)
                _PROMPT_CACHE[str(file_path)] = (current_mtime, raw_text)
                logger.debug(f"[PromptLoader] Loaded/reloaded prompt '{clean_name}' (mtime: {current_mtime})")

        if format_kwargs:
            return _safe_format(raw_text, **format_kwargs)

        return raw_text
    except Exception as e:
        logger.warning(f"[PromptLoader] Error reading prompt '{clean_name}': {e}")
        return _safe_format(default, **format_kwargs) if format_kwargs else default


def load_config_yaml(relative_name: str, default: Any = None) -> Any:
    """
    Loads and parses a YAML configuration from backend/prompts/ with mtime caching.
    Returns a deep copy of parsed data to prevent callers from mutating the shared cache.
    """
    clean_name = relative_name.strip().replace("\\", "/")
    if clean_name.startswith("/") or ".." in clean_name.split("/"):
        logger.warning(f"[PromptLoader] Blocked path traversal attempt in YAML load: {relative_name}")
        return default

    if not clean_name.endswith(".yaml") and not clean_name.endswith(".yml"):
        clean_name = f"{clean_name}.yaml"

    prompts_dir = _get_prompts_dir()
    file_path = prompts_dir / clean_name

    if not file_path.is_file():
        return default

    try:
        if not file_path.resolve().is_relative_to(prompts_dir.resolve()):
            logger.warning(f"[PromptLoader] Path escaped prompts root: {file_path}")
            return default
    except Exception:
        pass

    try:
        current_mtime = os.path.getmtime(file_path)
        with _CACHE_LOCK:
            cached_entry = _YAML_CACHE.get(str(file_path))
            if cached_entry and cached_entry[0] == current_mtime:
                return copy.deepcopy(cached_entry[1])

            with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
                data = yaml.safe_load(f)
            if len(_YAML_CACHE) >= _MAX_CACHE_ENTRIES:
                _YAML_CACHE.pop(next(iter(_YAML_CACHE)), None)
            _YAML_CACHE[str(file_path)] = (current_mtime, data)
            logger.debug(f"[PromptLoader] Loaded/reloaded YAML config '{clean_name}' (mtime: {current_mtime})")
            return copy.deepcopy(data)
    except Exception as e:
        logger.warning(f"[PromptLoader] Error reading YAML config '{clean_name}': {e}")
        return default
