"""
trajectory.py — Autonomous Trajectory Recording & Dataset Export Engine for Project Anara.
Parity with Hermes Agent trajectory (Nous Research).

Persists completed or interrupted multi-step agent trajectories into ShareGPT/JSONL format
in `.anara/trajectories/` for post-run analysis, offline replay, and local model distillation/fine-tuning.
Includes cross-platform thread & file locking (Windows msvcrt / POSIX fcntl).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("anara.core.trajectory")

_MEM_LOCK = threading.Lock()


def _get_trajectories_dir() -> Path:
    from constants import get_anara_cache_dir
    base_dir = get_anara_cache_dir("trajectories")
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def _lock_file(f, acquire: bool) -> None:
    """Exclusive whole-file lock for append writes (cross-platform Windows & POSIX)."""
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK if acquire else msvcrt.LK_UNLCK, 1)
            f.seek(0, os.SEEK_END)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX if acquire else fcntl.LOCK_UN)
    except Exception:
        pass


class TrajectoryRecorder:
    """Records multi-turn conversational trajectories with step metadata and ShareGPT formatting."""

    @classmethod
    def save_trajectory(
        cls,
        session_id: str,
        messages: List[Dict[str, Any]],
        model: str,
        completed: bool = True,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> Optional[Path]:
        """
        Appends an execution trajectory in JSONL format.
        Saved to `.anara/trajectories/trajectories_completed.jsonl` or `trajectories_failed.jsonl`.
        """
        if not messages:
            return None

        traj_dir = _get_trajectories_dir()
        filename = "trajectories_completed.jsonl" if completed else "trajectories_failed.jsonl"
        target_path = traj_dir / filename

        # Format into ShareGPT conversational standard
        conversations: List[Dict[str, Any]] = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if isinstance(content, list):
                # Flatten text pieces
                text_parts = [
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                content = "\n".join(text_parts) if text_parts else str(content)
            
            from_role = "gpt" if role in ("assistant", "model") else ("human" if role == "user" else "system")
            conversations.append({
                "from": from_role,
                "value": str(content)
            })

        entry = {
            "session_id": str(session_id),
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "completed": completed,
            "conversations": conversations,
            "metrics": metrics or {},
        }

        serialized = json.dumps(entry, ensure_ascii=False) + "\n"

        with _MEM_LOCK:
            try:
                with open(target_path, "a", encoding="utf-8") as f:
                    _lock_file(f, True)
                    try:
                        f.write(serialized)
                        f.flush()
                    finally:
                        _lock_file(f, False)
                logger.info(f"[Trajectory] Successfully recorded session '{session_id}' to {target_path.name}")
                return target_path
            except Exception as e:
                logger.warning(f"[Trajectory] Failed to record trajectory for session '{session_id}': {e}")
                return None

    @classmethod
    def read_trajectories(cls, completed: bool = True, limit: int = 50) -> List[Dict[str, Any]]:
        """Reads recent recorded trajectories."""
        traj_dir = _get_trajectories_dir()
        filename = "trajectories_completed.jsonl" if completed else "trajectories_failed.jsonl"
        target_path = traj_dir / filename
        if not target_path.exists():
            return []

        entries = []
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
        except Exception as e:
            logger.debug(f"[Trajectory] Error reading trajectories: {e}")
        return entries[-limit:]
