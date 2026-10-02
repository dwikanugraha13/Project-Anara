"""
lifecycle.py — Robust Process Lifecycle, PID Tracking & Sentinel Management.
Anara Enterprise Architecture: Win32 WaitForSingleObject, PID recycling
protection, atomic file writes, POSIX zombie filtering, and stale process scavenging.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from constants import get_anara_run_dir

logger = logging.getLogger("anara.lifecycle")

_IS_WINDOWS = sys.platform == "win32"


def _parse_proc_stat_fields(pid: int) -> Optional[List[str]]:
    """Safely extracts space-separated fields after ') ' from Linux /proc/[pid]/stat."""
    try:
        content = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        rparen = content.rfind(")")
        if rparen == -1:
            return None
        # Returns fields starting after ') ' where:
        # fields[0] is state (field 3 of /proc/pid/stat)
        # fields[19] is starttime (field 22 of /proc/pid/stat)
        return content[rparen + 2:].split()
    except Exception:
        return None


def _posix_is_zombie(pid: int) -> bool:
    """Detects if a POSIX process is an unreaped zombie/defunct process."""
    stat_fields = _parse_proc_stat_fields(pid)
    if stat_fields and len(stat_fields) > 0:
        return stat_fields[0] == "Z"
    with contextlib.suppress(Exception):
        import subprocess
        r = subprocess.run(
            ["ps", "-o", "state=", "-p", str(pid)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=2,
        )
        return r.returncode == 0 and r.stdout.strip().startswith("Z")
    return False


def get_process_start_time(pid: Optional[int]) -> Optional[int]:
    """Returns process creation timestamp/ticks to guard against PID recycling (Anara Standard)."""
    if not pid or pid <= 0:
        return None
    if _IS_WINDOWS:
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
            k32.OpenProcess.restype = ctypes.c_void_p
            k32.CloseHandle.argtypes = [ctypes.c_void_p]
            k32.CloseHandle.restype = ctypes.c_int
            k32.GetProcessTimes.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_uint64),
                ctypes.POINTER(ctypes.c_uint64),
                ctypes.POINTER(ctypes.c_uint64),
                ctypes.POINTER(ctypes.c_uint64),
            ]
            k32.GetProcessTimes.restype = ctypes.c_int
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h_proc = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h_proc:
                return None
            try:
                creation = ctypes.c_uint64()
                exit_t = ctypes.c_uint64()
                kernel = ctypes.c_uint64()
                user = ctypes.c_uint64()
                res = k32.GetProcessTimes(
                    h_proc, ctypes.byref(creation), ctypes.byref(exit_t),
                    ctypes.byref(kernel), ctypes.byref(user)
                )
                return creation.value if res else None
            finally:
                k32.CloseHandle(h_proc)
        except Exception:
            return None
    else:
        try:
            stat_fields = _parse_proc_stat_fields(pid)
            if stat_fields and len(stat_fields) > 19:
                return int(stat_fields[19])
            return None
        except Exception:
            return None


def is_pid_alive(pid: Optional[int]) -> bool:
    """
    Checks if a process with the given PID is currently running.
    Fixes the Win32 STILL_ACTIVE (259) bug by using WaitForSingleObject.
    Guarantees handle cleanup and prevents POSIX zombie false positives.
    """
    if not pid or pid <= 0:
        return False

    if _IS_WINDOWS:
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
            k32.OpenProcess.restype = ctypes.c_void_p
            k32.CloseHandle.argtypes = [ctypes.c_void_p]
            k32.CloseHandle.restype = ctypes.c_int
            k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            k32.WaitForSingleObject.restype = ctypes.c_uint32
            k32.GetLastError.restype = ctypes.c_uint32

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            SYNCHRONIZE = 0x00100000
            desired_access = PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE
            h_proc = k32.OpenProcess(desired_access, False, pid)

            if not h_proc:
                # If access denied, process exists but is owned by system or another user
                ERROR_ACCESS_DENIED = 5
                return k32.GetLastError() == ERROR_ACCESS_DENIED

            try:
                # WAIT_TIMEOUT (0x102 / 258) indicates process is still running
                WAIT_TIMEOUT = 0x00000102
                wait_res = k32.WaitForSingleObject(h_proc, 0)
                return wait_res == WAIT_TIMEOUT
            finally:
                k32.CloseHandle(h_proc)
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            # Filter out zombie processes on Linux/macOS
            return not _posix_is_zombie(pid)
        except (OSError, ProcessLookupError):
            return False


def _atomic_write_text(file_path: Path, content: str) -> None:
    """Atomically writes content using temporary file replace (NTFS & POSIX parity)."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = file_path.parent
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=temp_dir, delete=False) as tf:
        tf.write(content)
        tf.flush()
        os.fsync(tf.fileno())
        tmp_name = tf.name

    try:
        os.replace(tmp_name, file_path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


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


def get_process_metadata(name: str) -> Optional[Dict[str, Any]]:
    """Reads lifecycle sentinel metadata for a process name."""
    meta_file = get_anara_run_dir() / f"{name}.lifecycle.json"
    if meta_file.is_file():
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def record_process_start(name: str, pid: Optional[int] = None, command: Optional[str] = None) -> Path:
    """Records process PID, kernel start ticks, and lifecycle metadata atomically."""
    eff_pid = pid or os.getpid()
    run_dir = get_anara_run_dir()
    pid_file = run_dir / f"{name}.pid"
    _atomic_write_text(pid_file, str(eff_pid))

    start_ticks = get_process_start_time(eff_pid)

    meta_file = run_dir / f"{name}.lifecycle.json"
    meta = {
        "process_name": name,
        "pid": eff_pid,
        "start_ticks": start_ticks,
        "command": command or "",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "running",
    }
    _atomic_write_text(meta_file, json.dumps(meta, indent=2))
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
            _atomic_write_text(meta_file, json.dumps(meta, indent=2))
        except Exception:
            pass


def cleanup_stale_processes(prune_dead: bool = True) -> Dict[str, Any]:
    """
    Sweeps ANARA_HOME/run for orphaned or dead process sentinels (Anara Enterprise Architecture).
    Validates process liveness and guards against PID recycling via start ticks.
    Prunes dead .pid files and updates lifecycle sentinels to 'stale'.
    """
    run_dir = get_anara_run_dir()
    active: List[Dict[str, Any]] = []
    reaped: List[Dict[str, Any]] = []

    for pid_path in list(run_dir.glob("*.pid")):
        proc_name = pid_path.stem
        pid: Optional[int] = None
        try:
            val = pid_path.read_text(encoding="utf-8").strip()
            if val.isdigit():
                pid = int(val)
        except Exception:
            continue

        if not pid:
            if prune_dead:
                pid_path.unlink(missing_ok=True)
            continue

        meta = get_process_metadata(proc_name) or {}
        expected_ticks = meta.get("start_ticks")

        alive = is_pid_alive(pid)
        if alive and expected_ticks is not None:
            curr_ticks = get_process_start_time(pid)
            # PID was recycled onto an unrelated application!
            if curr_ticks is not None and curr_ticks != expected_ticks:
                alive = False
                logger.warning(
                    f"[Lifecycle] PID {pid} for '{proc_name}' was recycled by OS onto an unrelated process."
                )

        proc_info = {
            "process_name": proc_name,
            "pid": pid,
            "is_alive": alive,
            "started_at": meta.get("started_at"),
        }

        if alive:
            active.append(proc_info)
        else:
            reaped.append(proc_info)
            if prune_dead:
                pid_path.unlink(missing_ok=True)
                meta_path = run_dir / f"{proc_name}.lifecycle.json"
                if meta_path.is_file():
                    try:
                        meta["status"] = "stale"
                        meta["stale_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                        _atomic_write_text(meta_path, json.dumps(meta, indent=2))
                    except Exception:
                        pass
                logger.info(f"[Lifecycle] Scavenged dead sentinel for '{proc_name}' (PID {pid}).")

    return {
        "active_count": len(active),
        "reaped_count": len(reaped),
        "active": active,
        "reaped": reaped,
    }
