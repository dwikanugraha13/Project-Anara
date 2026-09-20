"""
constants.py — Shared Paths & Environment Constants for Project Anara.
Anara Standard Constants:
1. Dynamically resolves ANARA_HOME (%LOCALAPPDATA%/anara on Windows, ~/.anara on Linux/macOS).
2. Keeps user runtime data (SQLite, caches, staging, logs) cleanly isolated from source code.
3. Import-safe, stdlib-only — importable from anywhere without circular-import risk.
"""

import os
import shutil
import sys
from pathlib import Path


def get_anara_home() -> Path:
    """
    Returns the platform-native Anara home directory.
    Can be overridden via ANARA_HOME environment variable.
    """
    env_home = os.getenv("ANARA_HOME", "").strip()
    if env_home:
        p = Path(env_home)
        p.mkdir(parents=True, exist_ok=True)
        return p

    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
        base = Path(local_appdata) if local_appdata else Path.home() / "AppData" / "Local"
        p = base / "anara"
    else:
        p = Path.home() / ".anara"

    p.mkdir(parents=True, exist_ok=True)
    return p


def get_anara_db_path() -> str:
    """
    Returns the persistent SQLite database path for Anara Brain.
    Canonical single source of truth is ANARA_HOME / anara_brain.db (Anara Standard).
    Seamlessly migrates any legacy in-tree database if needed.
    """
    override = os.getenv("ANARA_DB_PATH", "").strip()
    if override:
        return override

    home_db = get_anara_home() / "anara_brain.db"
    backend_dir = Path(__file__).resolve().parent
    local_db = backend_dir / "anara_brain.db"

    # Migrate local repo DB to ANARA_HOME if home_db doesn't exist yet
    if not home_db.is_file() and local_db.is_file():
        try:
            home_db.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local_db, home_db)
        except Exception:
            return str(local_db)

    if home_db.is_file():
        return str(home_db)
    if local_db.is_file():
        return str(local_db)
    return str(home_db)


def get_anara_staging_dir(subdir: str = "") -> Path:
    """Returns persistent staging directory under ANARA_HOME."""
    st = get_anara_home() / "staging"
    if subdir:
        st = st / subdir
    st.mkdir(parents=True, exist_ok=True)
    return st


def get_anara_cache_dir(subdir: str = "") -> Path:
    """Returns persistent cache directory under ANARA_HOME."""
    cd = get_anara_home() / "cache"
    if subdir:
        cd = cd / subdir
    cd.mkdir(parents=True, exist_ok=True)
    return cd


def get_anara_logs_dir(subdir: str = "") -> Path:
    """Returns persistent logs directory under ANARA_HOME."""
    ld = get_anara_home() / "logs"
    if subdir:
        ld = ld / subdir
    ld.mkdir(parents=True, exist_ok=True)
    return ld


def get_anara_run_dir(subdir: str = "") -> Path:
    """Returns persistent run/PID directory under ANARA_HOME."""
    rd = get_anara_home() / "run"
    if subdir:
        rd = rd / subdir
    rd.mkdir(parents=True, exist_ok=True)
    return rd


def get_anara_workspace_dir(subdir: str = "") -> Path:
    """Returns persistent workspace root directory under ANARA_HOME."""
    wd = get_anara_home() / "workspace"
    if subdir:
        wd = wd / subdir
    wd.mkdir(parents=True, exist_ok=True)
    return wd


def get_anara_checkpoints_dir(subdir: str = "") -> Path:
    """Returns persistent checkpoints directory under ANARA_HOME."""
    cp = get_anara_home() / "checkpoints"
    if subdir:
        cp = cp / subdir
    cp.mkdir(parents=True, exist_ok=True)
    return cp


def prune_stale_staging_files(max_age_days: int = 7) -> int:
    """
    Cleans up temporary media, screenshots, and zip archives in staging directory
    older than max_age_days (Anara Garbage Collection).
    Returns count of pruned files.
    """
    staging_dir = get_anara_home() / "staging"
    if not staging_dir.is_dir():
        return 0

    import time
    now = time.time()
    max_age_sec = max(1, max_age_days) * 86400.0
    pruned_count = 0

    for item in staging_dir.rglob("*"):
        if item.is_file():
            try:
                mtime = item.stat().st_mtime
                if (now - mtime) > max_age_sec:
                    item.unlink(missing_ok=True)
                    pruned_count += 1
            except Exception:
                pass

    return pruned_count


def get_anara_env_file() -> Optional[Path]:
    """
    Universal .env discovery (Hermes Parity):
    1. User Runtime .env: %LOCALAPPDATA%/anara/.env (or ~/.anara/.env)
    2. In-tree backend/.env
    3. Workspace root .env
    Returns the first existing path, or None.
    """
    candidates = [
        get_anara_home() / ".env",
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def load_universal_env() -> None:
    """
    Loads environment variables from discovered .env locations.
    Loads project default .env first, then overlays with user runtime .env (%LOCALAPPDATA%/anara/.env)
    so user-level overrides always take precedence cleanly and safely.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    # 1. Project level base (backend/.env)
    project_env = Path(__file__).resolve().parent / ".env"
    if project_env.is_file():
        load_dotenv(project_env, override=False)

    # 2. Workspace root level (.env)
    root_env = Path(__file__).resolve().parent.parent / ".env"
    if root_env.is_file():
        load_dotenv(root_env, override=False)

    # 3. User runtime level (%LOCALAPPDATA%/anara/.env or ~/.anara/.env) — highest precedence
    user_env = get_anara_home() / ".env"
    if user_env.is_file():
        load_dotenv(user_env, override=True)
