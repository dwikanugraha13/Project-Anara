"""
prompt_loader.py — Hot-Reloading Externalized Prompt & Template Engine for Project Anara.
Claude Code & Hermes Agent Parity:
1. Zero hardcoded prompt strings or behavioral rules embedded inside Python files.
2. In-memory caching with mtime-based hot-reloading (updates take effect immediately without restart).
3. Clean separation of agent constitution, system reminders, and operational guidance from executable logic.
"""

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
_CACHE_LOCK = threading.Lock()


def _safe_format(template: str, **kwargs: Any) -> str:
    """
    Safely substitutes {key} placeholders without crashing on unescaped JSON, CSS, or Bash braces.
    Hermes & Claude Code Parity: template safety for arbitrary markdown code blocks.
    """
    if not kwargs or not template:
        return template
    pattern = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

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

    return candidate


def load_prompt(relative_name: str, default: str = "", **format_kwargs: Any) -> str:
    """
    Loads a markdown prompt template from backend/prompts/ with mtime hot-reloading.
    If format_kwargs are provided, formats the prompt template safely.
    """
    clean_name = relative_name.strip().replace("\\", "/")
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

    try:
        current_mtime = os.path.getmtime(file_path)
        with _CACHE_LOCK:
            cached_entry = _PROMPT_CACHE.get(str(file_path))
            if cached_entry and cached_entry[0] == current_mtime:
                raw_text = cached_entry[1]
            else:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    raw_text = f.read()
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
    """
    clean_name = relative_name.strip().replace("\\", "/")
    if not clean_name.endswith(".yaml") and not clean_name.endswith(".yml"):
        clean_name = f"{clean_name}.yaml"

    prompts_dir = _get_prompts_dir()
    file_path = prompts_dir / clean_name

    if not file_path.is_file():
        return default

    try:
        current_mtime = os.path.getmtime(file_path)
        with _CACHE_LOCK:
            cached_entry = _YAML_CACHE.get(str(file_path))
            if cached_entry and cached_entry[0] == current_mtime:
                return cached_entry[1]

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                data = yaml.safe_load(f)
            _YAML_CACHE[str(file_path)] = (current_mtime, data)
            logger.debug(f"[PromptLoader] Loaded/reloaded YAML config '{clean_name}' (mtime: {current_mtime})")
            return data
    except Exception as e:
        logger.warning(f"[PromptLoader] Error reading YAML config '{clean_name}': {e}")
        return default
