"""
process_registry.py — Background Daemon Process Supervisor for Project Anara.
Implements persistent background process management (e.g. dev servers, watcher scripts)
with log tailing, PID lifecycle supervision, and clean tree termination (Hermes Parity).
"""

import logging
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from constants import get_anara_cache_dir
from core.lifecycle import is_pid_alive, record_process_start, record_process_exit

logger = logging.getLogger("anara.core.process_registry")


class ProcessRegistry:
    """Manages long-running background daemon processes with logging and supervisor lifecycle."""

    def __init__(self):
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
        """Starts a persistent background daemon process with stdout/stderr redirection to log file."""
        cmd_clean = (command or "").strip()
        if not cmd_clean:
            return {"status": "error", "message": "Command cannot be empty."}

        proc_id = (process_id or "").strip() or self._generate_id(cmd_clean)

        # Check if already running with same ID
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
            # Windows creation flags for fully detached daemon
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

            proc = subprocess.Popen(
                cmd_clean,
                cwd=work_dir,
                env=env,
                shell=True,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=creationflags
            )

            record_process_start(f"daemon_{proc_id}", proc.pid)
            proc_meta = {
                "process_id": proc_id,
                "command": cmd_clean,
                "pid": proc.pid,
                "cwd": work_dir,
                "log_file": str(log_path),
                "started_at": time.time(),
                "started_at_str": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
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
        for proc_id, meta in list(self._processes.items()):
            pid = meta.get("pid")
            alive = is_pid_alive(pid)
            entry = dict(meta)
            entry["is_alive"] = alive
            entry["uptime_seconds"] = round(time.time() - meta["started_at"], 1) if alive else 0
            active.append(entry)
        return active

    def get_logs(self, process_id: str, lines: int = 50) -> Dict[str, Any]:
        """Tails the most recent log lines for a background process."""
        proc_id = (process_id or "").strip()
        log_path = self._log_dir / f"{proc_id}.log"
        if not log_path.exists():
            return {"status": "error", "message": f"No logs found for process '{proc_id}'."}

        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
            tail_lines = all_lines[-max(1, lines):]
            return {
                "status": "success",
                "process_id": proc_id,
                "lines_count": len(tail_lines),
                "logs": "".join(tail_lines).strip()
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to read logs: {e}"}

    def stop_process(self, process_id: str) -> Dict[str, Any]:
        """Terminates a background process tree cleanly."""
        proc_id = (process_id or "").strip()
        if proc_id not in self._processes:
            return {"status": "error", "message": f"Process '{proc_id}' was not found."}

        meta = self._processes[proc_id]
        pid = meta.get("pid")
        if not pid or not is_pid_alive(pid):
            self._processes.pop(proc_id, None)
            record_process_exit(f"daemon_{proc_id}")
            return {"status": "success", "process_id": proc_id, "message": f"Process '{proc_id}' was already terminated."}

        from core.sandbox import CommandSandbox
        try:
            CommandSandbox._kill_process_tree(pid)
            self._processes.pop(proc_id, None)
            record_process_exit(f"daemon_{proc_id}")
            logger.info(f"[ProcessRegistry] Stopped daemon #{proc_id} (PID {pid})")
            return {"status": "success", "process_id": proc_id, "message": f"Process '{proc_id}' (PID {pid}) terminated successfully."}
        except Exception as e:
            logger.warning(f"[ProcessRegistry] Error stopping '{proc_id}': {e}")
            return {"status": "error", "message": f"Failed to stop process: {e}"}


# Global process registry singleton
process_registry = ProcessRegistry()
