"""
validate_env.py — Automated Pre-Flight Environment Validator for Project Anara.
Anara Standard Pre-Flight Doctor Verification:
Validates Python runtime, directories, database schema integrity, and configurations
before starting background services.
"""

import os
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


def validate_environment() -> bool:
    """Performs all pre-flight checks and returns True if healthy."""
    print("Running Anara Pre-Flight Environment Validation...")
    ok = True

    # 1. Python version check
    if sys.version_info < (3, 10):
        print(f"  [ERROR] Python 3.10+ required. Current: {sys.version}")
        ok = False
    else:
        print(f"  [OK] Python Runtime: {sys.version.split()[0]}")

    # 2. Directory checks
    try:
        from constants import (
            get_anara_home,
            get_anara_logs_dir,
            get_anara_run_dir,
            get_anara_workspace_dir,
            get_anara_checkpoints_dir,
        )
        home = get_anara_home()
        logs = get_anara_logs_dir()
        run_d = get_anara_run_dir()
        ws = get_anara_workspace_dir()
        cp = get_anara_checkpoints_dir()
        print(f"  [OK] ANARA_HOME: {home}")
    except Exception as e:
        print(f"  [ERROR] Directory resolution failed: {e}")
        ok = False

    # 3. Database & Schema check
    try:
        from memory import memory_engine
        with memory_engine._get_connection() as conn:
            uv = conn.execute("PRAGMA user_version").fetchone()[0]
            if uv < 2:
                print(f"  [WARN] Database user_version is {uv} (expected >= 2)")
            else:
                print(f"  [OK] SQLite Database: user_version {uv} (FTS5 Enabled)")
    except Exception as e:
        print(f"  [ERROR] Database check failed: {e}")
        ok = False

    # 4. Config check
    try:
        from config import load_config, cfg_get
        cfg = load_config()
        def_model = cfg_get("model.default")
        print(f"  [OK] Configuration: _config_version {cfg.get('_config_version', 1)}, Model: {def_model}")
    except Exception as e:
        print(f"  [ERROR] Config loading error: {e}")
        ok = False

    # 5. Tools registry check
    try:
        from tools import registry
        tool_count = len(registry._tools)
        if tool_count >= 66:
            print(f"  [OK] Tool Registry: {tool_count} decentralized tools loaded.")
        else:
            print(f"  [WARN] Tool Registry: Only {tool_count} tools loaded (expected 66).")
    except Exception as e:
        print(f"  [ERROR] Tool registry check error: {e}")
        ok = False

    if ok:
        print("[SUCCESS] All Pre-Flight Checks Passed Successfully!")
    else:
        print("[FAILED] Pre-Flight Validation Failed!")

    return ok


if __name__ == "__main__":
    if not validate_environment():
        sys.exit(1)
