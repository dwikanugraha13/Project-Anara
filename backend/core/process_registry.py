"""
process_registry.py — Background Daemon Process Supervisor for Project Anara.
Implements persistent background process management (e.g. dev servers, watcher scripts)
with bounded log tailing, PID lifecycle supervision, session isolation, and clean tree
termination with PID-reuse protection (Anara Enterprise Architecture).
"""

import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from constants import get_anara_cache_dir
from core.lifecycle import is_pid_alive, record_process_start, record_process_exit, get_process_start_time

logger = logging.getLogger("anara.core.process_registry")

_IS_WINDOWS = sys.platform == "win32"
MAX_LOG_SIZE_BYTES = 50 * 1024 * 1024  # 50MB disk runaway watchdog (Anara Engineering Standards)


def _tail_file_block_reverse(file_path: str, max_lines: int = 50, block_size: int = 4096) -> List[str]:
    """Reads the last N lines of a file via reverse block seeking (Anara zero-OOM standard)."""
    lines: List[str] = []
    try:
        with open(file_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            remainder = b""
            bytes_to_read = file_size

            while bytes_to_read > 0 and len(lines) < max_lines:
                chunk_size = min(block_size, bytes_to_read)
                bytes_to_read -= chunk_size
                f.seek(bytes_to_read, os.SEEK_SET)
                chunk = f.read(chunk_size) + remainder
                chunk_lines = chunk.split(b"\n")
                remainder = chunk_lines[0]
                for line in reversed(chunk_lines[1:]):
                    lines.append(line.decode("utf-8", errors="replace"))
                    if len(lines) >= max_lines:
                        break

            if len(lines) < max_lines and remainder:
                lines.append(remainder.decode("utf-8", errors="replace"))
    except Exception:
        pass
    return list(reversed(lines))


class ProcessRegistry:
    """Manages long-running background daemon processes with logging and supervisor lifecycle."""

    def __init__(self):
        self._lock = threading.RLock()
        self._processes: Dict[str, Dict[str, Any]] = {}
        self._log_dir = get_anara_cache_dir("process_logs")
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def _generate_id(self, command: str) -> str:
        words = re.sub(r"[^\w\s-]", "", command.lower()).split()
        prefix = "_".join(words[:2]) if words else "proc"
        return f"{prefix}_{uuid.uuid4().hex[:6]}"

    def start_process(
        self,
        command: str,
        cwd: Optional[str] = None,
        process_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Starts a persistent background daemon process with stdout/stderr redirection and session isolation."""
        cmd_clean = (command or "").strip()
        if not cmd_clean:
            return {"status": "error", "message": "Command cannot be empty."}

        proc_id = (process_id or "").strip() or self._generate_id(cmd_clean)

        with self._lock:
            if proc_id in self._processes:
                existing = self._processes[proc_id]
                pid = existing.get("pid")
                if is_pid_alive(pid):
                    return {
                        "status": "warning",
                        "process_id": proc_id,
                        "pid": pid,
                        "message": f"Process '{proc_id}' is already running (PID: {pid})."
                    }

        from core.agent import anara_agent
        from core.sandbox import get_sanitized_environment

        work_dir = os.path.abspath(cwd) if cwd else anara_agent.get_session_dir()
        if not os.path.exists(work_dir):
            work_dir = os.getcwd()

        log_path = self._log_dir / f"{proc_id}.log"
        env = get_sanitized_environment()

        try:
            log_file = open(log_path, "a", encoding="utf-8", errors="replace")
            try:
                creationflags = 0
                start_new_session = False
                if _IS_WINDOWS:
                    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
                else:
                    # Critical Hermes/Anara Standard: Isolate child into its own process session
                    # to prevent os.killpg from killing the backend server process!
                    start_new_session = True

                proc = subprocess.Popen(
                    cmd_clean,
                    cwd=work_dir,
                    env=env,
                    shell=True,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    creationflags=creationflags,
                    start_new_session=start_new_session,
                )
            finally:
                # Parent must close the open file handle to avoid resource/descriptor leak
                log_file.close()

            record_process_start(f"daemon_{proc_id}", proc.pid)
            start_ticks = get_process_start_time(proc.pid)

            proc_meta = {
                "process_id": proc_id,
                "command": cmd_clean,
                "pid": proc.pid,
                "start_ticks": start_ticks,
                "cwd": work_dir,
                "log_file": str(log_path),
                "started_at": time.time(),
                "started_at_str": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

            with self._lock:
                self._processes[proc_id] = proc_meta

            logger.info(f"[ProcessRegistry] Started daemon #{proc_id} (PID {proc.pid}): '{cmd_clean}'")

            return {
                "status": "success",
                "process_id": proc_id,
                "pid": proc.pid,
                "log_file": str(log_path),
                "message": f"Background process '{proc_id}' started (PID: {proc.pid})."
            }
        except Exception as e:
            logger.error(f"[ProcessRegistry] Failed to start '{cmd_clean}': {e}")
            return {"status": "error", "message": f"Failed to start process: {e}"}

    def list_processes(self) -> List[Dict[str, Any]]:
        """Lists all registered background processes and their live health status."""
        active = []
        with self._lock:
            items = list(self._processes.items())

        for proc_id, meta in items:
            pid = meta.get("pid")
            alive = is_pid_alive(pid)
            # Verify PID recycling: if PID is alive but start ticks don't match, it was recycled!
            if alive and meta.get("start_ticks") is not None:
                curr_ticks = get_process_start_time(pid)
                if curr_ticks is not None and curr_ticks != meta.get("start_ticks"):
                    alive = False

            entry = dict(meta)
            entry["is_alive"] = alive
            entry["uptime_seconds"] = round(time.time() - meta["started_at"], 1) if alive else 0
            active.append(entry)
        return active

    def get_logs(self, process_id: str, lines: int = 50) -> Dict[str, Any]:
        """Tails the most recent log lines for a background process using bounded reverse seek (zero OOM)."""
        proc_id = (process_id or "").strip()
        log_path = self._log_dir / f"{proc_id}.log"
        if not log_path.exists():
            return {"status": "error", "message": f"No logs found for process '{proc_id}'."}

        try:
            tail_lines = _tail_file_block_reverse(str(log_path), max_lines=max(1, lines))
            return {
                "status": "success",
                "process_id": proc_id,
                "lines_count": len(tail_lines),
                "logs": "\n".join(tail_lines).strip()
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to read logs: {e}"}

    def stop_process(self, process_id: str) -> Dict[str, Any]:
        """Terminates a background process tree cleanly with PID-recycling and group suicide prevention."""
        proc_id = (process_id or "").strip()
        with self._lock:
            if proc_id not in self._processes:
                return {"status": "error", "message": f"Process '{proc_id}' was not found."}
            meta = self._processes[proc_id]

        pid = meta.get("pid")
        if not pid or not is_pid_alive(pid):
            with self._lock:
                self._processes.pop(proc_id, None)
            record_process_exit(f"daemon_{proc_id}")
            return {"status": "success", "process_id": proc_id, "message": f"Process '{proc_id}' was already terminated."}

        # PID Recycling verification
        if meta.get("start_ticks") is not None:
            curr_ticks = get_process_start_time(pid)
            if curr_ticks is not None and curr_ticks != meta.get("start_ticks"):
                logger.warning(f"[ProcessRegistry] Refusing to kill PID {pid}: start ticks mismatch (PID was recycled by OS).")
                with self._lock:
                    self._processes.pop(proc_id, None)
                record_process_exit(f"daemon_{proc_id}")
                return {"status": "warning", "process_id": proc_id, "message": f"PID {pid} was recycled by host OS."}

        try:
            if _IS_WINDOWS:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    timeout=5,
                    creationflags=0x08000000  # CREATE_NO_WINDOW
                )
            else:
                # Safe POSIX tree termination without committing server suicide
                try:
                    pgid = os.getpgid(pid)
                    if pgid != os.getpgrp():
                        os.killpg(pgid, signal.SIGTERM)
                        time.sleep(0.3)
                        if is_pid_alive(pid):
                            os.killpg(pgid, signal.SIGKILL)
                    else:
                        os.kill(pid, signal.SIGTERM)
                        time.sleep(0.3)
                        if is_pid_alive(pid):
                            os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass

            with self._lock:
                self._processes.pop(proc_id, None)
            record_process_exit(f"daemon_{proc_id}")
            logger.info(f"[ProcessRegistry] Stopped daemon #{proc_id} (PID {pid})")
            return {"status": "success", "process_id": proc_id, "message": f"Process '{proc_id}' (PID {pid}) terminated successfully."}
        except Exception as e:
            logger.warning(f"[ProcessRegistry] Error stopping '{proc_id}': {e}")
            return {"status": "error", "message": f"Failed to stop process: {e}"}


# Global process registry singleton
process_registry = ProcessRegistry()
