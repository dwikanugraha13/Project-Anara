"""
autonomous_engine.py — Autonomous Task Scheduler, Event Trigger & Trust-Level Policy.
Implements FR-11, FR-12, FR-13, FR-21, FR-22, FR-23, FR-24 and NFR-1, NFR-4
from prd-general-agent.md and rancangan-general-agent.md.

Principles:
1. Unified Security: Autonomous runs pass through the exact same Permission Gate as interactive runs.
2. Trust Levels:
   - 'supervised': All plans require manual approval, pauses and notifies user (default).
   - 'semi_autonomous': Low-risk actions auto-approve; mutating/ask pause for user approval.
   - 'full_autonomous': Mutating tools auto-approve; 'ask' tier (destructive) ALWAYS pauses for human approval.
3. Crash-Resilience: Resumes unfinished autonomous tasks from checkpoint on restart.
"""
import asyncio
import json
import logging
import sqlite3
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional

from memory.base import DB_PATH
from tools import get_tool_risk
from core.plan_detector import get_highest_risk, detect_tools_from_text

logger = logging.getLogger(__name__)


def get_scheduler_timezone() -> timezone:
    """Returns dynamic scheduler timezone from configuration, defaulting to UTC+7 (Hermes Parity)."""
    try:
        from config import cfg_get
        offset_hours = float(cfg_get("agent.scheduler.timezone_offset_hours", 7.0))
        return timezone(timedelta(hours=offset_hours))
    except Exception:
        return timezone(timedelta(hours=7))


WIB = get_scheduler_timezone()


def evaluate_trust_approval(trust_level: str, tools: List[str]) -> bool:
    """
    Evaluates whether an autonomous task plan can be auto-approved
    according to its assigned trust_level policy (FR-22, FR-23, NFR-1).

    Rule matrix:
    - 'ask' tier: NEVER auto-approved under ANY trust level (zero exceptions).
    - 'supervised': NEVER auto-approves mutating/ask actions; waits for human.
    - 'semi_autonomous': Auto-approves 'read_only' and benign 'action'; pauses on 'mutating' & 'ask'.
    - 'full_autonomous': Auto-approves 'read_only', 'action', and 'mutating'; pauses ONLY on 'ask'.
    """
    highest_risk = get_highest_risk(tools)
    clean_level = (trust_level or "supervised").lower().strip()

    # Absolute Safety Constraint (NFR-1): 'ask' is NEVER auto-approved
    if highest_risk == "ask":
        logger.warning(f"[TrustPolicy] Action contains 'ask' tier tool. Auto-approval DENIED even under {clean_level}!")
        return False

    if highest_risk == "read_only":
        return True

    if clean_level == "supervised":
        return False

    if clean_level == "semi_autonomous":
        return highest_risk == "action"

    if clean_level == "full_autonomous":
        return highest_risk in ("action", "mutating")

    return False


class AutonomousEngine:
    """Manages scheduled background jobs, event triggers, and trust-level execution."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._init_table()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_table(self):
        """Creates the autonomous_tasks SQLite table for persistent task tracking and crash resume."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS autonomous_tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    trigger_type TEXT DEFAULT 'interval', -- 'interval', 'cron', 'event', 'once'
                    interval_seconds INTEGER DEFAULT 3600,
                    trust_level TEXT DEFAULT 'supervised', -- 'supervised', 'semi_autonomous', 'full_autonomous'
                    target_channel TEXT DEFAULT 'telegram', -- 'telegram', 'cli', 'web'
                    target_channel_id TEXT,
                    is_active INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'idle', -- 'idle', 'running', 'waiting_approval', 'paused', 'failed'
                    pending_plan_id TEXT,
                    current_step_index INTEGER DEFAULT 0,
                    last_run DATETIME,
                    next_run DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_auto_tasks_active
                ON autonomous_tasks(is_active, next_run);
            """)
            try:
                cursor.execute("ALTER TABLE autonomous_tasks ADD COLUMN failure_count INTEGER DEFAULT 0;")
            except Exception:
                pass
            conn.commit()

    def register_task(
        self,
        name: str,
        prompt: str,
        trigger_type: str = "interval",
        interval_seconds: int = 3600,
        trust_level: str = "supervised",
        target_channel: str = "telegram",
        target_channel_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Registers a scheduled or event-driven autonomous task."""
        t_id = task_id or f"task_{uuid.uuid4().hex[:8]}"
        now = datetime.now(WIB)
        next_run = now + timedelta(seconds=interval_seconds)

        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO autonomous_tasks (
                    id, name, prompt, trigger_type, interval_seconds,
                    trust_level, target_channel, target_channel_id,
                    is_active, status, next_run, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 'idle', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    prompt=excluded.prompt,
                    interval_seconds=excluded.interval_seconds,
                    trust_level=excluded.trust_level,
                    target_channel=excluded.target_channel,
                    target_channel_id=excluded.target_channel_id,
                    is_active=excluded.is_active,
                    updated_at=CURRENT_TIMESTAMP
            """, (
                t_id, name, prompt, trigger_type, interval_seconds,
                trust_level, target_channel, target_channel_id,
                next_run.isoformat()
            ))
            conn.commit()

        logger.info(f"[AutonomousEngine] Registered task '{name}' [{t_id}] (trust={trust_level}, interval={interval_seconds}s)")
        return {
            "id": t_id,
            "name": name,
            "prompt": prompt,
            "trust_level": trust_level,
            "next_run": next_run.isoformat()
        }

    def list_tasks(self) -> List[Dict[str, Any]]:
        """Returns all registered autonomous background tasks."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM autonomous_tasks ORDER BY updated_at DESC")
            return [dict(r) for r in cursor.fetchall()]

    def delete_task(self, task_id: str) -> bool:
        """Removes a task from the scheduler."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM autonomous_tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0

    def pause_task(self, task_id: str) -> bool:
        """Pauses a scheduled autonomous task."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE autonomous_tasks SET is_active = 0, status = 'paused', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0

    def resume_task(self, task_id: str) -> bool:
        """Resumes a paused autonomous task."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            now = datetime.now(WIB)
            cursor.execute("SELECT interval_seconds FROM autonomous_tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            interval = row[0] if row else 3600
            next_r = now + timedelta(seconds=interval)
            cursor.execute("""
                UPDATE autonomous_tasks SET
                    is_active = 1,
                    status = 'idle',
                    next_run = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (next_r.isoformat(), task_id))
            conn.commit()
            return cursor.rowcount > 0

    async def trigger_task_now(self, task_id: str) -> Dict[str, Any]:
        """Manually triggers execution of an autonomous task immediately."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM autonomous_tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return {"status": "error", "message": f"Task '{task_id}' was not found."}
            task = dict(row)

        return await self._execute_autonomous_task(task)

    async def _execute_autonomous_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes an autonomous task through the unified Channel Adapter and Permission Gate.
        """
        from core.channel_adapter import ChannelRequest, process_channel_request, _execute_build_mode
        from integrations.telegram import send_telegram_message, send_telegram_plan_proposal

        task_id = task["id"]
        name = task["name"]
        prompt = task["prompt"]
        trust_level = task.get("trust_level", "supervised")
        channel = task.get("target_channel", "telegram")
        channel_id = task.get("target_channel_id") or "autonomous_scheduler"

        logger.info(f"[AutonomousEngine] Firing task '{name}' [{task_id}] (trust={trust_level})")

        # Mark task as running
        self._update_task_status(task_id, "running")

        req = ChannelRequest(
            text=prompt,
            channel=channel,
            channel_id=channel_id,
            user_id="scheduler_agent",
            sender_name=f"Autonomous ({name})",
            trigger_type="autonomous",
            metadata={"task_id": task_id, "trust_level": trust_level}
        )

        try:
            # 1. Process via Channel Gateway
            res = await process_channel_request(req)

            # 2. Check if a plan was generated
            if res.plan_pending and res.plan_id:
                from core.session_manager import session_state_manager
                pending_act = session_state_manager.get_pending_by_id(res.plan_id)
                action_tools = [pending_act.tool_name] if (pending_act and pending_act.tool_name) else (res.tools_used or ["mutating"])
                auto_approved = evaluate_trust_approval(trust_level, action_tools)

                if auto_approved:
                    # Policy grants auto-approval for this risk tier
                    logger.info(f"[AutonomousEngine] Plan #{res.plan_id} auto-approved by trust policy ({trust_level}). Executing...")
                    build_res = await _execute_build_mode(
                        session_id=res.session_id,
                        user_prompt=prompt,
                        req=req
                    )
                    self._update_task_status(task_id, "idle", last_run=True)
                    # Notify completion across omnichannel transports (Hermes & Claude Code Parity)
                    if channel == "telegram":
                        try:
                            await send_telegram_message(
                                text=f"🤖 <b>[Autonomous Run Complete: {name}]</b>\n\n{build_res.text}",
                                chat_id=channel_id
                            )
                        except Exception as e_tg:
                            logger.warning(f"[AutonomousEngine] Telegram notify error: {e_tg}")
                    else:
                        try:
                            from integrations import platform_registry
                            await platform_registry.send_message(
                                platform=channel,
                                target_id=channel_id,
                                text=f"🤖 [Autonomous Run Complete: {name}]\n\n{build_res.text}"
                            )
                        except Exception as e_ch:
                            logger.warning(f"[AutonomousEngine] Platform notify error ({channel}): {e_ch}")
                    return {"status": "success", "result": build_res.text, "auto_approved": True}
                else:
                    # Policy demands human review (supervised or high-risk mutating/ask)
                    logger.info(f"[AutonomousEngine] Plan #{res.plan_id} PAUSED for human approval ({trust_level}). Sending proactive notification...")
                    self._update_task_status(task_id, "waiting_approval", plan_id=res.plan_id)

                    # Send proactive plan proposal across omnichannel transports
                    if channel == "telegram":
                        try:
                            await send_telegram_plan_proposal(
                                chat_id=channel_id,
                                plan_text=f"🤖 <b>[Scheduled Task: {name}]</b>\n\n{res.text}",
                                plan_id=res.plan_id
                            )
                        except Exception as e_tg:
                            logger.warning(f"[AutonomousEngine] Telegram plan proposal error: {e_tg}")
                    else:
                        try:
                            from integrations import platform_registry
                            await platform_registry.send_message(
                                platform=channel,
                                target_id=channel_id,
                                text=f"🤖 [Scheduled Task Approval Needed: {name}]\nPlan #{res.plan_id}:\n\n{res.text}"
                            )
                        except Exception as e_ch:
                            logger.warning(f"[AutonomousEngine] Platform plan proposal error ({channel}): {e_ch}")
                    return {"status": "waiting_approval", "plan_id": res.plan_id, "plan_text": res.text}

            # 3. Direct response (read-only / safe)
            self._update_task_status(task_id, "idle", last_run=True)
            if channel == "telegram":
                try:
                    await send_telegram_message(
                        text=f"🤖 <b>[Autonomous Run: {name}]</b>\n\n{res.text}",
                        chat_id=channel_id
                    )
                except Exception as e_tg:
                    logger.warning(f"[AutonomousEngine] Telegram direct response error: {e_tg}")
            else:
                try:
                    from integrations import platform_registry
                    await platform_registry.send_message(
                        platform=channel,
                        target_id=channel_id,
                        text=f"🤖 [Autonomous Run: {name}]\n\n{res.text}"
                    )
                except Exception as e_ch:
                    logger.warning(f"[AutonomousEngine] Platform direct response error ({channel}): {e_ch}")
            return {"status": "success", "result": res.text}

        except Exception as e:
            logger.error(f"[AutonomousEngine] Task '{name}' execution error: {e}")
            self._update_task_status(task_id, "failed", last_run=True)
            return {"status": "error", "message": str(e)}

    def _update_task_status(
        self,
        task_id: str,
        status: str,
        plan_id: Optional[str] = None,
        last_run: bool = False
    ):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            now = datetime.now(get_scheduler_timezone())
            if last_run:
                # Calculate next run or finalize one-shot tasks
                cursor.execute("SELECT interval_seconds, trigger_type, failure_count FROM autonomous_tasks WHERE id = ?", (task_id,))
                row = cursor.fetchone()
                interval = row[0] if row else 3600
                trigger_t = row[1] if row and len(row) > 1 else "interval"
                fail_cnt = row[2] if row and len(row) > 2 and row[2] is not None else 0

                if status == "idle":
                    fail_cnt = 0
                elif status == "failed":
                    fail_cnt += 1

                # Calculate effective interval with exponential backoff on failure (5m, 10m, 20m, 40m, max 1h)
                if status == "failed":
                    backoff = min(3600, 300 * (2 ** min(max(fail_cnt - 1, 0), 4)))
                    effective_interval = max(interval, backoff)
                    if fail_cnt >= 5:
                        status = "paused"
                        logger.warning(f"[AutonomousEngine] Task {task_id} circuit breaker tripped (paused after {fail_cnt} failures).")
                else:
                    effective_interval = interval

                if trigger_t == "once":
                    cursor.execute("""
                        UPDATE autonomous_tasks SET
                            status = 'completed',
                            is_active = 0,
                            pending_plan_id = NULL,
                            failure_count = ?,
                            last_run = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (fail_cnt, now.isoformat(), task_id))
                else:
                    next_r = now + timedelta(seconds=effective_interval)
                    cursor.execute("""
                        UPDATE autonomous_tasks SET
                            status = ?,
                            pending_plan_id = ?,
                            failure_count = ?,
                            last_run = ?,
                            next_run = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (status, plan_id, fail_cnt, now.isoformat(), next_r.isoformat(), task_id))
            else:
                cursor.execute("""
                    UPDATE autonomous_tasks SET
                        status = ?,
                        pending_plan_id = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, plan_id, task_id))
            conn.commit()

    async def _scheduler_loop(self):
        """Continuous scheduler tick inspecting pending & due autonomous tasks."""
        logger.info("[AutonomousEngine] Scheduler loop initiated.")
        while self._running:
            try:
                now_iso = datetime.now(get_scheduler_timezone()).isoformat()
                with self._get_conn() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT * FROM autonomous_tasks
                        WHERE is_active = 1
                          AND status IN ('idle', 'failed')
                          AND next_run <= ?
                    """, (now_iso,))
                    due_tasks = [dict(r) for r in cursor.fetchall()]

                for task in due_tasks:
                    asyncio.create_task(self._execute_autonomous_task(task))

            except Exception as e:
                logger.debug(f"[AutonomousEngine] Scheduler tick error: {e}")

            await asyncio.sleep(30.0)

    def start(self):
        """Starts the autonomous engine worker."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._scheduler_loop())
        logger.info("[AutonomousEngine] Worker started.")

    def stop(self):
        """Stops the autonomous engine worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            self._worker_task = None
        logger.info("[AutonomousEngine] Worker stopped.")


autonomous_engine = AutonomousEngine()
