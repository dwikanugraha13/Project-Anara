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
    Parses machine-standard schedule expressions into interval seconds (Hermes Parity).
    Accepts:
    - Pure integer seconds: "3600", "1800"
    - Standard cron expressions: "0 9 * * *", "*/15 * * * *"
    - Standard interval shorthand: "30s", "15m", "2h", "1d", "1w"
    
    Natural language translation is handled by the model prior to tool invocation.
    """
    s = (schedule or "").strip().lower()
    if not s:
        return 3600

    # 1. Direct integer seconds
    if s.isdigit():
        return max(10, int(s))

    # 2. Standard 5-part cron expression via croniter
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

    # 3. Cron step pattern e.g. "*/15 * * * *"
    m_cron_step = re.match(r"^\*/(\d+)\s+\*\s+\*\s+\*\s+\*$", s)
    if m_cron_step:
        return max(60, int(m_cron_step.group(1)) * 60)

    # 4. Standard machine interval shorthand: e.g. "30s", "15m", "2h", "1d", "1w"
    m_short = re.match(r"^(\d+)\s*([smhdw])$", s)
    if m_short:
        val = int(m_short.group(1))
        unit = m_short.group(2)
        multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
        return max(10, val * multipliers.get(unit, 1))

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
        "detail": f"{name or task_id or 'Task List'}",
        "icon": "clock"
    })

    if act in ("create", "add"):
        if not prompt or not prompt.strip():
            return {
                "status": "error",
                "message": "Parameter 'prompt' (task instruction) is required to schedule a background task."
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
            "message": f"Scheduled task '{task_name}' created successfully [ID: {res['id']}]. Runs every {interval}s to channel {target_channel}.",
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
            return {"status": "error", "message": "Parameter 'task_id' is required to pause a task."}
        ok = autonomous_engine.pause_task(task_id.strip())
        return {
            "status": "success" if ok else "error",
            "message": f"Task '{task_id}' {'paused successfully.' if ok else 'failed to pause or not found.'}"
        }

    elif act in ("resume", "start"):
        if not task_id:
            return {"status": "error", "message": "Parameter 'task_id' is required to resume a task."}
        ok = autonomous_engine.resume_task(task_id.strip())
        return {
            "status": "success" if ok else "error",
            "message": f"Task '{task_id}' {'resumed successfully.' if ok else 'failed to resume or not found.'}"
        }

    elif act in ("run", "trigger"):
        if not task_id:
            return {"status": "error", "message": "Parameter 'task_id' is required to run a task immediately."}
        run_res = await autonomous_engine.trigger_task_now(task_id.strip())
        return {
            "status": "success",
            "message": f"Task '{task_id}' execution triggered immediately.",
            "execution_result": run_res
        }

    elif act in ("remove", "delete"):
        if not task_id:
            return {"status": "error", "message": "Parameter 'task_id' is required to delete a task."}
        ok = autonomous_engine.delete_task(task_id.strip())
        return {
            "status": "success" if ok else "error",
            "message": f"Task '{task_id}' {'deleted successfully.' if ok else 'failed to delete or not found.'}"
        }

    else:
        return {
            "status": "error",
            "message": f"Unknown action '{act}'. Supported actions: 'create', 'list', 'pause', 'resume', 'run', 'remove'."
        }
