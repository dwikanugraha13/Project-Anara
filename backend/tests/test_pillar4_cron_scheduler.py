"""
test_pillar4_cron_scheduler.py — Verification test suite for Pillar 4: Cron & Background Job Scheduler.
Anara Engineering Standards:
1. Persistent cron job registration, listing, and lifecycle (create, list, runs, pause, resume, delete).
2. Execution run history ledger with status, outputs, errors, and timing.
3. Central tool dispatch integration via _tool_cronjob_manage.
"""

import asyncio
import os
import tempfile
import pytest

from core.autonomous_engine import AutonomousEngine
from tools.cron_tools import _tool_cronjob_manage


def test_autonomous_engine_run_ledger():
    """Verifies that AutonomousEngine records task run history and retrieves it."""
    with tempfile.NamedTemporaryFile("w", suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        engine = AutonomousEngine(db_path=db_path)

        # Register dummy task
        task = engine.register_task(
            name="Daily System Check",
            prompt="Check CPU and memory usage",
            trigger_type="interval",
            interval_seconds=3600,
        )
        task_id = task["id"]

        # Record a successful run
        run_id1 = engine.record_task_run(
            task_id=task_id,
            status="success",
            output="CPU at 12%, Memory at 45%",
            execution_time_sec=1.25,
        )
        assert run_id1.startswith("run_")

        # Record a failed run
        run_id2 = engine.record_task_run(
            task_id=task_id,
            status="failed",
            error_message="Network timeout connecting to agent gateway",
            execution_time_sec=5.0,
        )
        assert run_id2.startswith("run_")

        # Retrieve runs
        runs = engine.get_task_runs(task_id=task_id)
        assert len(runs) == 2
        # Most recent first
        assert runs[0]["status"] == "failed"
        assert "Network timeout" in runs[0]["error_message"]
        assert runs[1]["status"] == "success"
        assert "CPU at 12%" in runs[1]["output"]
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_cronjob_manage_tool_lifecycle():
    """Verifies that _tool_cronjob_manage supports create, list, runs, pause, resume, and delete."""
    async def _run():
        # 1. Create
        create_res = await _tool_cronjob_manage(
            action="create",
            name="Backup Job",
            prompt="Backup workspace to zip archive",
            schedule="2h",
        )
        assert create_res["status"] == "success"
        task_id = create_res["task"]["id"]

        # 2. List
        list_res = await _tool_cronjob_manage(action="list")
        assert list_res["status"] == "success"
        assert any(t["id"] == task_id for t in list_res["tasks"])

        # 3. Runs (history)
        runs_res = await _tool_cronjob_manage(action="runs", task_id=task_id)
        assert runs_res["status"] == "success"
        assert "runs" in runs_res

        # 4. Pause & Resume
        pause_res = await _tool_cronjob_manage(action="pause", task_id=task_id)
        assert pause_res["status"] == "success"

        resume_res = await _tool_cronjob_manage(action="resume", task_id=task_id)
        assert resume_res["status"] == "success"

        # 5. Delete
        delete_res = await _tool_cronjob_manage(action="delete", task_id=task_id)
        assert delete_res["status"] == "success"

    asyncio.run(_run())
