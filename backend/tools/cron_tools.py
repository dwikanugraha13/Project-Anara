"""
cron_tools.py — Autonomous Background Cron & Task Scheduling Tool for Project Anara.
Anara Standard cronjob management: allows the agent to create, list,
run, pause, resume, and remove persistent autonomous background tasks.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from datetime import datetime

from .events import _emit_agent_event

logger = logging.getLogger(__name__)


def _parse_schedule_to_seconds(schedule: str) -> int:
    """
    Parses natural language, cron expressions, or numeric schedule string into interval seconds (Anara Standard).
    Examples:
    - "3600" -> 3600
    - "every 30m", "30 minutes", "30m" -> 1800
    - "every 2 hours", "2h", "2 hours" -> 7200
    - "every 1 day", "1d", "daily" -> 86400
    - "*/10 * * * *" -> 600
    - "0 * * * *" -> 3600
    - "0 9 * * *" -> 86400
    """
    s = (schedule or "").strip().lower()
    if not s:
        return 3600

    # Direct integer
    if s.isdigit():
        return max(10, int(s))

    # Try croniter if available
    try:
        from croniter import croniter
        from datetime import datetime
        if len(s.split()) == 5:
            base_time = datetime.now()
            iter = croniter(s, base_time)
            next_1 = iter.get_next(datetime)
            next_2 = iter.get_next(datetime)
            delta = int((next_2 - next_1).total_seconds())
            if delta > 0:
                return delta
    except Exception:
        pass

    # Cron step pattern e.g. "*/15 * * * *"
    m_cron_step = re.match(r"^\*/(\d+)\s+\*\s+\*\s+\*\s+\*$", s)
    if m_cron_step:
        return max(60, int(m_cron_step.group(1)) * 60)

    # Match duration patterns like "every 30 min", "15m", "2h", "1d"
    m_sec = re.search(r"(\d+)\s*(?:s|sec|detik)", s)
    if m_sec:
        return max(10, int(m_sec.group(1)))

    m_min = re.search(r"(\d+)\s*(?:m|min|menit)", s)
    if m_min:
        return max(60, int(m_min.group(1)) * 60)

    m_hour = re.search(r"(\d+)\s*(?:h|hr|hour|jam)", s)
    if m_hour:
        return max(300, int(m_hour.group(1)) * 3600)

    m_day = re.search(r"(\d+)\s*(?:d|day|hari)", s)
    if m_day:
        return max(3600, int(m_day.group(1)) * 86400)

    if "weekly" in s or "mingguan" in s or "@weekly" in s:
        return 604800
    if "daily" in s or "harian" in s or "@daily" in s or s.startswith("0 0 *"):
        return 86400
    if "hourly" in s or "tiap jam" in s or "@hourly" in s or s.startswith("0 *"):
        return 3600

    # Default fallback
    return 3600


async def _tool_cronjob_manage(
    action: str,
    name: Optional[str] = None,
    schedule: Optional[str] = None,
    prompt: Optional[str] = None,
    task_id: Optional[str] = None,
    trust_level: str = "semi_autonomous",
    target_channel: Optional[str] = None,
    target_channel_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Cron & Scheduled Task Manager for Project Anara (Anara Standard compatible cronjob_manage).
    Actions:
    - 'create' / 'add': Schedule a new autonomous background task.
    - 'list': List all scheduled tasks, their run intervals, next run, and status.
    - 'pause': Pause an active scheduled task.
    - 'resume': Resume a paused task.
    - 'run': Manually trigger an immediate execution of a scheduled task.
    - 'remove' / 'delete': Delete a scheduled task.
    """
    from core.autonomous_engine import autonomous_engine
    from config import cfg_get

    if not target_channel:
        target_channel = cfg_get("agent.default_channel", "web")

    act = (action or "list").strip().lower()

    _emit_agent_event("agent_action_start", {
        "tool_name": "cronjob_manage",
        "action_title": f"Cron Scheduler ({act.upper()})",
        "detail": f"{name or task_id or 'Daftar Tugas'}",
        "icon": "clock"
    })

    if act in ("create", "add"):
        if not prompt or not prompt.strip():
            return {
                "status": "error",
                "message": "Parameter 'prompt' (instruksi tugas) wajib diisi untuk membuat jadwal tugas."
            }
        task_name = (name or prompt[:30]).strip()
        interval = _parse_schedule_to_seconds(schedule or "1h")

        res = autonomous_engine.register_task(
            name=task_name,
            prompt=prompt.strip(),
            trigger_type="interval",
            interval_seconds=interval,
            trust_level=trust_level or "semi_autonomous",
            target_channel=target_channel or "telegram",
            target_channel_id=target_channel_id,
            task_id=task_id
        )
        return {
            "status": "success",
            "message": f"Tugas terjadwal '{task_name}' berhasil dibuat [ID: {res['id']}]. Berjalan setiap {interval} detik ke channel {target_channel}.",
            "task": res
        }

    elif act == "list":
        tasks = autonomous_engine.list_tasks()
        return {
            "status": "success",
            "total_tasks": len(tasks),
            "tasks": tasks
        }

    elif act in ("pause", "stop"):
        if not task_id:
            return {"status": "error", "message": "Parameter 'task_id' wajib diisi untuk menjeda tugas."}
        ok = autonomous_engine.pause_task(task_id.strip())
        return {
            "status": "success" if ok else "error",
            "message": f"Tugas {task_id} {'berhasil dijeda.' if ok else 'gagal dijeda atau tidak ditemukan.'}"
        }

    elif act in ("resume", "start"):
        if not task_id:
            return {"status": "error", "message": "Parameter 'task_id' wajib diisi untuk mengaktifkan kembali tugas."}
        ok = autonomous_engine.resume_task(task_id.strip())
        return {
            "status": "success" if ok else "error",
            "message": f"Tugas {task_id} {'berhasil diaktifkan kembali.' if ok else 'gagal diaktifkan atau tidak ditemukan.'}"
        }

    elif act in ("run", "trigger"):
        if not task_id:
            return {"status": "error", "message": "Parameter 'task_id' wajib diisi untuk menjalankan tugas sekarang."}
        run_res = await autonomous_engine.trigger_task_now(task_id.strip())
        return {
            "status": "success",
            "message": f"Tugas {task_id} telah dipicu eksekusinya segera.",
            "execution_result": run_res
        }

    elif act in ("remove", "delete"):
        if not task_id:
            return {"status": "error", "message": "Parameter 'task_id' wajib diisi untuk menghapus tugas."}
        ok = autonomous_engine.delete_task(task_id.strip())
        return {
            "status": "success" if ok else "error",
            "message": f"Tugas {task_id} {'berhasil dihapus.' if ok else 'gagal dihapus atau tidak ditemukan.'}"
        }

    else:
        return {
            "status": "error",
            "message": f"Aksi '{act}' tidak dikenal. Pilih dari: 'create', 'list', 'pause', 'resume', 'run', 'remove'."
        }
