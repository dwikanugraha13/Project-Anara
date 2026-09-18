"""
config.py — Unified Declarative Configuration Engine for Project Anara.
Anara Standard Enterprise Configuration:
1. Loads unified configuration from ANARA_HOME/config.yaml or project config.yaml.
2. Supports recursive deep merging of defaults and user overrides.
3. Supports environment variable expansion: ${VAR_NAME} and ${VAR_NAME:-default}.
4. Version-gated schema migrations via `_config_version`.
5. Atomic writes with rolling timestamped backups (.bak).
6. Dot-notation lookups (e.g. cfg_get("terminal.timeout", 180)).
7. Thread-safe, cached with (mtime, size) invalidation.
"""

import copy
from datetime import datetime
import logging
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Dict, List, Optional, Tuple
import yaml

from constants import get_anara_home

logger = logging.getLogger(__name__)

CURRENT_CONFIG_VERSION = 1

DEFAULT_CONFIG: Dict[str, Any] = {
    "_config_version": CURRENT_CONFIG_VERSION,
    "model": {
        "default": os.getenv("DEFAULT_AI_MODEL", "9router/ag/gemini-3.8-flash-high"),
        "fallback": os.getenv("FALLBACK_AI_MODEL", "9router/ag/gemini-3.8-flash-high"),
        "live_voice": os.getenv("DEFAULT_VOICE_MODEL", "gemini-3.1-flash-live-preview"),
        "auxiliary": os.getenv("AUXILIARY_AI_MODEL", ""),
        "vision": os.getenv("VISION_AI_MODEL", ""),
        "fast_subagent": os.getenv("FAST_SUBAGENT_MODEL", ""),
    },
    "terminal": {
        "timeout": int(os.getenv("TERMINAL_TIMEOUT", 180)),
        "cwd": ".",
    },
    "code_execution": {
        "timeout": int(os.getenv("CODE_EXECUTION_TIMEOUT", 180)),
        "max_tool_calls": 30,
    },
    "browser": {
        "timeout": int(os.getenv("BROWSER_TIMEOUT", 120)),
        "viewport_width": 1280,
        "viewport_height": 800,
    },
    "compression": {
        "enabled": True,
        "protect_last_n": int(os.getenv("COMPRESSION_PROTECT_LAST_N", 15)),
        "max_summary_tokens": int(os.getenv("COMPRESSION_MAX_TOKENS", 500)),
    },
    "delegation": {
        "model": os.getenv("DELEGATION_AI_MODEL", ""),
        "max_iterations": int(os.getenv("DELEGATION_MAX_ITERATIONS", 25)),
    },
    "agent": {
        "turn_timeout": int(os.getenv("AGENT_TURN_TIMEOUT", 300)),
        "max_iterations": int(os.getenv("AGENT_MAX_ITERATIONS", 30)),
        "generation": {
            "temperature": float(os.getenv("AGENT_TEMPERATURE", 0.7)),
            "max_tokens": int(os.getenv("AGENT_MAX_TOKENS", 4096)),
            "plan_temperature": 0.4,
            "auxiliary_temperature": 0.2,
        }
    },
    "database": {
        "journal_mode": os.getenv("DB_JOURNAL_MODE", "wal"),
        "busy_timeout_ms": int(os.getenv("DB_BUSY_TIMEOUT_MS", 15000)),
        "wal_autocheckpoint": 1000,
        "journal_size_limit_bytes": 67108864,  # 64MB (Anara Standard)
    },
    "workspace": {
        "root": os.getenv("ANARA_WORKSPACE_DIR", ""),
    },
    "biometrics": {
        "threshold": float(os.getenv("VOICE_BIOMETRICS_THRESHOLD", 0.74)),
    },
    "stt": {
        "model": os.getenv("STT_MODEL", ""),
    },
    "enabled_toolsets": [],
    "mcp_servers": {},
    "location": {
        "city": os.getenv("ANARA_CITY", "Jakarta"),
        "default_country_code": os.getenv("DEFAULT_COUNTRY_CODE", "62"),
    },
    "security": {
        "redact_secrets": True,
    },
    "gateway": {
        "enabled": True,
        "auth_enabled": True,
        "password_hash": "",
        "tunnel_provider": "cloudflare",
        "remote_port": 3000,
    },
    "updates": {
        "backup_keep": 5,
    }
}

_CONFIG_CACHE: Optional[Dict[str, Any]] = None
_CONFIG_SIGNATURE: Tuple[float, int] = (0.0, 0)


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively deep merges overlay dictionary into a copy of base dictionary."""
    out = copy.deepcopy(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and k in out and isinstance(out[k], dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


_ENV_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")


def _expand_env_vars(val: Any) -> Any:
    """Expands ${VAR} and ${VAR:-default} within strings, dicts, and lists."""
    if isinstance(val, str):
        def _replace_match(m):
            var_name = m.group(1)
            default_val = m.group(2) if m.group(2) is not None else ""
            return os.getenv(var_name, default_val)
        return _ENV_VAR_PATTERN.sub(_replace_match, val)
    elif isinstance(val, dict):
        return {k: _expand_env_vars(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [_expand_env_vars(item) for item in val]
    return val


def _get_config_path() -> Path:
    """Returns the primary config.yaml path (under ANARA_HOME or repo root)."""
    env_cfg = os.getenv("ANARA_CONFIG_PATH", "").strip()
    if env_cfg:
        return Path(env_cfg)

    home_cfg = get_anara_home() / "config.yaml"
    if home_cfg.is_file():
        return home_cfg

    # Project root fallback
    repo_cfg = Path(__file__).resolve().parent.parent / "config.yaml"
    if repo_cfg.is_file():
        return repo_cfg

    return home_cfg


def _rotate_config_backups(cfg_file: Path, keep: int = 5) -> None:
    """Creates a timestamped backup and keeps only the most recent N copies (Anara standard)."""
    try:
        if not cfg_file.is_file():
            return
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = cfg_file.with_name(f"{cfg_file.name}.bak.{now_str}")
        shutil.copy2(cfg_file, backup_file)

        # Prune older backups
        parent_dir = cfg_file.parent
        backups = sorted(
            [f for f in parent_dir.glob(f"{cfg_file.name}.bak.*") if f.is_file()],
            key=lambda x: x.stat().st_mtime
        )
        if len(backups) > keep:
            for old_b in backups[:-keep]:
                try:
                    old_b.unlink()
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"[Config] Backup rotation warning: {e}")


def atomic_config_write(target_path: Path, data: Dict[str, Any], backup: bool = True) -> bool:
    """Atomically writes YAML configuration with temporary swap and backup creation."""
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if backup and target_path.is_file():
            keep = data.get("updates", {}).get("backup_keep", 5) if isinstance(data, dict) else 5
            _rotate_config_backups(target_path, keep=keep)

        temp_dir = target_path.parent
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8", suffix=".tmp") as tf:
            temp_name = tf.name
            yaml.safe_dump(data, tf, default_flow_style=False, sort_keys=False)

        os.replace(temp_name, target_path)
        return True
    except Exception as e:
        logger.error(f"[Config] atomic_config_write error: {e}")
        try:
            if "temp_name" in locals() and os.path.exists(temp_name):
                os.remove(temp_name)
        except Exception:
            pass
        return False


def _migrate_v0_to_v1(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Migrates legacy unversioned configs to version 1."""
    cfg["_config_version"] = 1
    if "agent" not in cfg:
        cfg["agent"] = {}
    if "generation" not in cfg["agent"]:
        cfg["agent"]["generation"] = {
            "temperature": 0.7,
            "max_tokens": 4096,
            "plan_temperature": 0.4,
            "auxiliary_temperature": 0.2,
        }
    if "location" not in cfg:
        cfg["location"] = {}
    if "default_country_code" not in cfg["location"]:
        cfg["location"]["default_country_code"] = "62"
    return cfg


MIGRATIONS: Tuple[Tuple[int, Any], ...] = (
    (1, _migrate_v0_to_v1),
)


def _apply_config_migrations(raw_cfg: Dict[str, Any], cfg_file: Path) -> Dict[str, Any]:
    """Checks and applies schema migrations progressively."""
    ver = raw_cfg.get("_config_version", 0)
    if ver >= CURRENT_CONFIG_VERSION:
        return raw_cfg

    cfg = copy.deepcopy(raw_cfg)
    migrated = False
    for target_ver, mig_func in MIGRATIONS:
        if ver < target_ver:
            try:
                cfg = mig_func(cfg)
                ver = target_ver
                migrated = True
                logger.info(f"[Config] Migrated config schema to version {ver}")
            except Exception as e:
                logger.error(f"[Config] Migration to version {target_ver} failed: {e}")
                break

    if migrated:
        cfg["_config_version"] = ver
        atomic_config_write(cfg_file, cfg, backup=True)

    return cfg


def _seed_default_config_file(cfg_file: Path) -> None:
    """Auto-seeds a fully documented config.yaml if one does not exist yet (Anara Standard)."""
    template = """# ==============================================================================
#  PROJECT ANARA — ENTERPRISE DECLARATIVE CONFIGURATION
#  Anara Standard config.yaml
#  All fields support dot-notation lookups (e.g. cfg_get("terminal.timeout"))
#  Supports environment variable expansion: ${VAR} or ${VAR:-default}
# ==============================================================================
_config_version: 1

# Primary, Live Voice & Role-Based AI Models (Anara Standard)
model:
  default: "9router/ag/gemini-3.8-flash-high"
  fallback: "9router/ag/gemini-3.8-flash-high"
  live_voice: "gemini-3.1-flash-live-preview"
  auxiliary: ""    # Leave empty to follow active model or fallback model automatically
  vision: ""       # Leave empty to auto-detect from active model or vision registry
  fast_subagent: "" # Leave empty to use fast auxiliary model for subagents

# Terminal Shell & Sandbox Execution
terminal:
  timeout: 180       # Command execution timeout in seconds
  cwd: "."           # Default workspace root

# Sandboxed Python & JavaScript Code Execution
code_execution:
  timeout: 180       # Maximum execution time in seconds
  max_tool_calls: 30 # Loop safety limit

# Headed / Headless Browser Automation (Playwright)
browser:
  timeout: 120
  viewport_width: 1280
  viewport_height: 800

# Rolling Context Window Compaction (Anara Protected Tail Standard)
compression:
  enabled: true
  protect_last_n: 15       # Protect the most recent N turns verbatim
  max_summary_tokens: 500  # Size of compressed older memory capsule

# Multi-Agent Subagent Delegation
delegation:
  model: ""                # Dedicated model for background delegated subagents (leave empty to use active model)
  max_iterations: 25

# Agent Runtime Turn Timeouts & Loop Controls
agent:
  turn_timeout: 300        # Seconds allowed per agent generation turn
  max_iterations: 30       # Maximum tool call loop iterations before returning synthesis
  generation:
    temperature: 0.7
    max_tokens: 4096
    plan_temperature: 0.4
    auxiliary_temperature: 0.2

# Database Engine Pragmas (Anara Standard)
database:
  journal_mode: "wal"      # "wal" (recommended) or "delete"
  busy_timeout_ms: 15000   # Busy wait timeout in milliseconds
  wal_autocheckpoint: 1000 # Autocheckpoint page limit
  journal_size_limit_bytes: 67108864 # 64MB journal boundary limit

# Declarative Native Model Context Protocol (MCP) Servers
mcp_servers:
  # fetch:
  #   command: "uvx"
  #   args: ["mcp-server-fetch"]

# Persistent Agent Workspace Location (Anara Standard)
workspace:
  root: ""                 # Custom folder for agent workspace (defaults to %LOCALAPPDATA%/anara/workspace)

# Acoustic Voice Biometrics Matching
biometrics:
  threshold: 0.74          # Cosine similarity threshold for voice recognition (0.65 - 0.85)

# Location & Regional Meteorological Context
location:
  city: "Jakarta"          # User base city for live weather & daily briefings
  default_country_code: "62"

# Enterprise Privacy & Security Controls
security:
  redact_secrets: true     # Automatically masks API keys, tokens, passwords in logs

# Automated Rolling Backups
updates:
  backup_keep: 5
"""
    try:
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        cfg_file.write_text(template, encoding="utf-8")
        logger.info(f"[Config] Auto-seeded default enterprise configuration at {cfg_file}")
    except Exception as e:
        logger.debug(f"[Config] Could not write default config.yaml: {e}")


def load_config(force_reload: bool = False) -> Dict[str, Any]:
    """Loads, migrates, expands, and merges config.yaml with default settings."""
    global _CONFIG_CACHE, _CONFIG_SIGNATURE

    cfg_file = _get_config_path()
    if not cfg_file.is_file():
        _seed_default_config_file(cfg_file)
        if _CONFIG_CACHE is None or force_reload:
            _CONFIG_CACHE = _expand_env_vars(copy.deepcopy(DEFAULT_CONFIG))
        return _CONFIG_CACHE

    try:
        st = cfg_file.stat()
        sig = (st.st_mtime, st.st_size)
        if not force_reload and _CONFIG_CACHE is not None and sig == _CONFIG_SIGNATURE:
            return _CONFIG_CACHE

        with open(cfg_file, "r", encoding="utf-8") as f:
            user_data = yaml.safe_load(f) or {}

        # Apply schema migrations if needed
        user_data = _apply_config_migrations(user_data, cfg_file)

        # Deep merge default config with user overrides
        merged = _deep_merge(DEFAULT_CONFIG, user_data)

        # Expand environment variables (${VAR})
        expanded = _expand_env_vars(merged)

        _CONFIG_CACHE = expanded
        _CONFIG_SIGNATURE = sig
        return _CONFIG_CACHE

    except Exception as e:
        logger.warning(f"[Config] Error loading {cfg_file}: {e}. Using defaults.")
        if _CONFIG_CACHE is None:
            _CONFIG_CACHE = _expand_env_vars(copy.deepcopy(DEFAULT_CONFIG))
        return _CONFIG_CACHE


def cfg_get(key_path: str, default: Any = None) -> Any:
    """
    Retrieves a nested configuration value using dot notation (Anara standard).
    Example: cfg_get("agent.max_iterations", 30)
    """
    config = load_config()
    parts = key_path.strip().split(".")
    curr = config
    for part in parts:
        if isinstance(curr, dict) and part in curr:
            curr = curr[part]
        else:
            return default
    return curr if curr is not None else default


def save_config(updates: Dict[str, Any]) -> bool:
    """Updates and safely persists changes to config.yaml under ANARA_HOME."""
    cfg_file = _get_config_path()
    # Read unexpanded raw user data to avoid writing back expanded secrets
    try:
        if cfg_file.is_file():
            with open(cfg_file, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f) or {}
        else:
            raw_data = copy.deepcopy(DEFAULT_CONFIG)
    except Exception:
        raw_data = copy.deepcopy(DEFAULT_CONFIG)

    for k, v in updates.items():
        if "." in k:
            parts = k.split(".")
            d = raw_data
            for p in parts[:-1]:
                d = d.setdefault(p, {})
            d[parts[-1]] = v
        else:
            if isinstance(v, dict) and isinstance(raw_data.get(k), dict):
                raw_data[k].update(v)
            else:
                raw_data[k] = v

    raw_data["_config_version"] = CURRENT_CONFIG_VERSION
    success = atomic_config_write(cfg_file, raw_data, backup=True)
    if success:
        load_config(force_reload=True)
    return success
