"""
lifecycle.py — Process Lifecycle, PID Tracking & Sentinel Management for Project Anara.
Anara Standard Process Lifecycle and Gateway Supervisor.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from constants import get_anara_run_dir

logger = logging.getLogger("anara.lifecycle")


def is_pid_alive(pid: Optional[int]) -> bool:
    """Checks if a process with the given PID is currently running."""
    if not pid or pid <= 0:
        return False

    if sys.platform == "win32":
        try:
            # OpenProcess query
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            SYNCHRONIZE = 0x00100000
            h_proc = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid
            )
            if h_proc:
                exit_code = ctypes.c_ulong()
                ctypes.windll.kernel32.GetExitCodeProcess(h_proc, ctypes.byref(exit_code))
                ctypes.windll.kernel32.CloseHandle(h_proc)
                STILL_ACTIVE = 259
                return exit_code.value == STILL_ACTIVE
            return False
        except Exception:
            try:
                out = subprocess.check_output(f'tasklist /FI "PID eq {pid}" /NH', shell=True, text=True, errors="replace")
                return str(pid) in out
            except Exception:
                return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def get_process_pid(name: str) -> Optional[int]:
    """Reads PID from run directory."""
    pid_file = get_anara_run_dir() / f"{name}.pid"
    if pid_file.is_file():
        try:
            val = pid_file.read_text(encoding="utf-8").strip()
            if val and val.isdigit():
                return int(val)
        except Exception:
            pass
    return None


def record_process_start(name: str, pid: Optional[int] = None) -> Path:
    """Records process PID and lifecycle metadata."""
    eff_pid = pid or os.getpid()
    run_dir = get_anara_run_dir()
    pid_file = run_dir / f"{name}.pid"
    pid_file.write_text(str(eff_pid), encoding="utf-8")

    meta_file = run_dir / f"{name}.lifecycle.json"
    meta = {
        "process_name": name,
        "pid": eff_pid,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "running",
    }
    meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return pid_file


def record_process_exit(name: str) -> None:
    """Removes PID file and updates lifecycle sentinel."""
    run_dir = get_anara_run_dir()
    pid_file = run_dir / f"{name}.pid"
    pid_file.unlink(missing_ok=True)

    meta_file = run_dir / f"{name}.lifecycle.json"
    if meta_file.is_file():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            meta["status"] = "stopped"
            meta["stopped_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        except Exception:
            pass
