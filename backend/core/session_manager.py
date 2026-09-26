"""
session_manager.py — State Machine Intent & Pending Action Tracker for Project Anara.
Anara Standard multi-channel session state management:
1. Tracks active transaction states (IDLE, AWAITING_APPROVAL, EXECUTING).
2. Holds pending high-risk tool actions with automatic TTL expiration.
3. Decouples conversational approval intent tracking from rigid regex dictionaries.
"""

from __future__ import annotations

import asyncio
from enum import Enum
import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from constants import get_anara_db_path
from core.plan_detector import is_explicit_plan_approval

logger = logging.getLogger(__name__)


class ActionState(str, Enum):
    """Finite State Machine states for a pending action lifecycle (Hermes Parity)."""
    PENDING = "pending"          # Awaiting user decision
    APPROVED = "approved"        # Approved (via button or voice)
    REJECTED = "rejected"        # Rejected/cancelled
    CANCELLED = "cancelled"      # Cancelled by user or interrupted
    EXECUTING = "executing"      # Running in sandbox
    EXECUTED = "executed"        # Completed successfully
    FAILED = "failed"            # Failed/exception during execution
    EXPIRED = "expired"          # Wait timeout (TTL 300s) exhausted


class AsyncReentrantLock:
    """Task-aware reentrant asyncio lock for session turns (Hermes turn_lease parity)."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._owner: Optional[asyncio.Task] = None
        self._count: int = 0

    async def acquire(self) -> bool:
        current_task = asyncio.current_task()
        if self._owner == current_task:
            self._count += 1
            return True
        await self._lock.acquire()
        self._owner = current_task
        self._count = 1
        return True

    def release(self) -> None:
        current_task = asyncio.current_task()
        if self._owner != current_task:
            return
        self._count -= 1
        if self._count == 0:
            self._owner = None
            self._lock.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release()


@dataclass
class PendingAction:
    """Represents a paused mutating action waiting for user confirmation (Hermes Parity)."""
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    session_id: int = 0
    channel: str = "cli"
    channel_id: str = "default"
    tool_name: str = ""
    tool_args: Dict[str, Any] = field(default_factory=dict)
    original_prompt: str = ""
    plan_text: str = ""
    lead_narration: str = ""
    risk_level: str = "mutating"
    state: ActionState = ActionState.PENDING
    status: Optional[str] = None
    user_id: str = "default_user"
    pending_tool_call: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = 300.0  # 5 minutes auto-expiration

    def __post_init__(self):
        if self.status is not None:
            if isinstance(self.status, ActionState):
                self.state = self.status
            else:
                try:
                    self.state = ActionState(str(self.status).lower())
                except ValueError:
                    self.state = ActionState.PENDING
        elif isinstance(self.state, str):
            try:
                self.state = ActionState(self.state.lower())
            except ValueError:
                self.state = ActionState.PENDING
        self.status = self.state.value

        if not self.lead_narration and self.plan_text:
            self.lead_narration = self.plan_text
        elif not self.plan_text and self.lead_narration:
            self.plan_text = self.lead_narration

    @property
    def action_id(self) -> str:
        return self.plan_id

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "action_id": self.plan_id,
            "session_id": self.session_id,
            "channel": self.channel,
            "channel_id": self.channel_id,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "original_prompt": self.original_prompt,
            "plan_text": self.plan_text,
            "lead_narration": self.lead_narration,
            "risk_level": self.risk_level,
            "state": self.state.value,
            "status": self.state.value,
            "user_id": self.user_id,
            "pending_tool_call": self.pending_tool_call,
            "created_at": self.created_at,
            "ttl_seconds": self.ttl_seconds,
        }


class SessionStateManager:
    """
    Multi-channel state machine tracking pending action states, active turn tasks,
    and process lifecycles per chat channel (Hermes Parity).
    Includes SQLite crash resilience for pending actions and audit trail tracking.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_anara_db_path()
        self._pending: Dict[str, PendingAction] = {}
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._active_processes: Dict[str, set[int]] = {}
        self._interrupted_sessions: set[str] = set()
        self._recently_expired: Dict[str, tuple[PendingAction, float]] = {}
        self._session_locks: Dict[str, asyncio.Lock] = {}

        # Initialize SQLite persistence & rehydrate unexpired actions on startup
        self._init_db()
        self._load_from_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes the persistent pending_actions table and indexes in SQLite."""
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS pending_actions (
                        plan_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        channel TEXT NOT NULL,
                        channel_id TEXT NOT NULL,
                        tool_name TEXT NOT NULL,
                        tool_args_json TEXT NOT NULL,
                        original_prompt TEXT,
                        plan_text TEXT,
                        lead_narration TEXT,
                        risk_level TEXT DEFAULT 'mutating',
                        state TEXT NOT NULL,
                        user_id TEXT DEFAULT 'default_user',
                        pending_tool_call_json TEXT,
                        created_at REAL NOT NULL,
                        ttl_seconds REAL DEFAULT 300.0,
                        updated_at REAL NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_pending_channel_state
                    ON pending_actions(channel, channel_id, state);
                """)
                conn.commit()
        except Exception as e:
            logger.warning(f"[SessionManager] DB init error: {e}")

    def _load_from_db(self) -> int:
        """
        Reloads unexpired pending actions from SQLite on startup (Crash Resilience).
        Sweeps any stale actions that expired while the server was down.
        """
        loaded = 0
        now = time.time()
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM pending_actions
                    WHERE state IN ('pending', 'executing')
                """)
                rows = cursor.fetchall()
                for r in rows:
                    created_at = float(r["created_at"])
                    ttl = float(r["ttl_seconds"])
                    plan_id = r["plan_id"]
                    ch = r["channel"]
                    cid = r["channel_id"]

                    if (now - created_at) > ttl:
                        # Expired while server was down
                        cursor.execute("""
                            UPDATE pending_actions
                            SET state = 'expired', updated_at = ?
                            WHERE plan_id = ?
                        """, (now, plan_id))
                        continue

                    # Unexpired action: rehydrate into memory
                    try:
                        args = json.loads(r["tool_args_json"] or "{}")
                    except Exception:
                        args = {}
                    try:
                        ptc = json.loads(r["pending_tool_call_json"]) if r["pending_tool_call_json"] else None
                    except Exception:
                        ptc = None

                    act = PendingAction(
                        plan_id=plan_id,
                        session_id=r["session_id"],
                        channel=ch,
                        channel_id=cid,
                        tool_name=r["tool_name"],
                        tool_args=args,
                        original_prompt=r["original_prompt"] or "",
                        plan_text=r["plan_text"] or "",
                        lead_narration=r["lead_narration"] or "",
                        risk_level=r["risk_level"] or "mutating",
                        state=ActionState(r["state"]),
                        user_id=r["user_id"] or "default_user",
                        pending_tool_call=ptc,
                        created_at=created_at,
                        ttl_seconds=ttl,
                    )
                    key = self._make_key(ch, cid)
                    self._pending[key] = act
                    loaded += 1

                conn.commit()
            if loaded > 0:
                logger.info(f"[SessionManager] Crash-resumed {loaded} active pending action(s) from SQLite.")
        except Exception as e:
            logger.warning(f"[SessionManager] Error loading pending actions from DB: {e}")
        return loaded

    def _persist_action(self, action: PendingAction) -> None:
        """Upserts a PendingAction record to SQLite."""
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO pending_actions (
                        plan_id, session_id, channel, channel_id,
                        tool_name, tool_args_json, original_prompt, plan_text,
                        lead_narration, risk_level, state, user_id,
                        pending_tool_call_json, created_at, ttl_seconds, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(plan_id) DO UPDATE SET
                        state = excluded.state,
                        updated_at = excluded.updated_at,
                        tool_args_json = excluded.tool_args_json,
                        plan_text = excluded.plan_text,
                        lead_narration = excluded.lead_narration;
                """, (
                    action.plan_id,
                    str(action.session_id),
                    action.channel,
                    action.channel_id,
                    action.tool_name,
                    json.dumps(action.tool_args, ensure_ascii=False),
                    action.original_prompt,
                    action.plan_text,
                    action.lead_narration,
                    action.risk_level,
                    action.state.value,
                    action.user_id,
                    json.dumps(action.pending_tool_call, ensure_ascii=False) if action.pending_tool_call else None,
                    action.created_at,
                    action.ttl_seconds,
                    time.time(),
                ))
                conn.commit()
        except Exception as e:
            logger.warning(f"[SessionManager] Failed to persist action #{action.plan_id}: {e}")

    def _update_action_state_in_db(self, plan_id: str, state: ActionState) -> None:
        """Updates the status of an action in SQLite."""
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    UPDATE pending_actions
                    SET state = ?, updated_at = ?
                    WHERE plan_id = ?
                """, (state.value, time.time(), plan_id))
                conn.commit()
        except Exception as e:
            logger.warning(f"[SessionManager] Failed to update action #{plan_id} state in DB: {e}")

    def get_action_history(
        self,
        channel: Optional[str] = None,
        channel_id: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Retrieves audit history of pending/resolved actions from SQLite."""
        results = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                if channel and channel_id:
                    cursor.execute("""
                        SELECT * FROM pending_actions
                        WHERE channel = ? AND channel_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (channel, str(channel_id), limit))
                elif channel:
                    cursor.execute("""
                        SELECT * FROM pending_actions
                        WHERE channel = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (channel, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM pending_actions
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (limit,))
                for r in cursor.fetchall():
                    results.append(dict(r))
        except Exception as e:
            logger.warning(f"[SessionManager] Error fetching action history: {e}")
        return results

    def _make_key(self, channel: str, channel_id: str) -> str:
        return f"{str(channel).strip().lower()}_{str(channel_id).strip()}"

    def store_pending(self, action: PendingAction) -> None:
        key = self._make_key(action.channel, action.channel_id)
        self._pending[key] = action
        self._persist_action(action)
        logger.info(f"[SessionManager] Stored pending action #{action.plan_id} ({action.tool_name}) for key: {key}")

    def set_pending_action(self, channel: str, channel_id: str, action: PendingAction) -> None:
        """Stores a pending action under the channel and channel_id key (Hermes Lifecycle)."""
        action.channel = channel
        action.channel_id = channel_id
        self.store_pending(action)

    def get_pending(self, channel: str, channel_id: str) -> Optional[PendingAction]:
        key = self._make_key(channel, channel_id)
        action = self._pending.get(key)
        if not action:
            return None

        if action.is_expired:
            logger.info(f"[SessionManager] Pending action #{action.plan_id} has expired.")
            action.state = ActionState.EXPIRED
            self._update_action_state_in_db(action.plan_id, ActionState.EXPIRED)
            self._recently_expired[key] = (action, time.time())
            self._pending.pop(key, None)
            return None

        return action

    def pop_recently_expired(self, channel: str, channel_id: str, max_age_seconds: float = 300.0) -> Optional[PendingAction]:
        key = self._make_key(channel, channel_id)
        entry = self._recently_expired.get(key)
        if entry:
            act, ts = entry
            if (time.time() - ts) <= max_age_seconds:
                self._recently_expired.pop(key, None)
                return act
            self._recently_expired.pop(key, None)
        return None

    def get_pending_action(self, channel: str, channel_id: str) -> Optional[PendingAction]:
        """Retrieves active pending action if not expired (Hermes Lifecycle)."""
        return self.get_pending(channel, channel_id)

    def resolve_action(
        self,
        channel: str,
        channel_id: str,
        action_id: str,
        state: ActionState
    ) -> Optional[PendingAction]:
        """
        Transitions the state of an action (e.g. APPROVED, REJECTED, EXECUTED, FAILED) deterministically.
        Hermes Parity: terminal states clear active pending queues immediately.
        """
        key = self._make_key(channel, channel_id)
        action = self._pending.get(key)
        if not action or action.plan_id != action_id:
            action = self.get_pending_by_id(action_id)
            if not action:
                return None
            key = self._make_key(action.channel, action.channel_id)

        action.state = state
        self._update_action_state_in_db(action.plan_id, state)
        logger.info(f"[SessionManager] Resolved action #{action.plan_id} -> {state.value} for {key}")

        if state in (ActionState.APPROVED, ActionState.EXECUTING):
            return action
        else:
            self._pending.pop(key, None)
            return action

    def clear_expired_actions(self) -> int:
        """Sweeps all active pending actions and evicts any exceeding 300s TTL."""
        expired_count = 0
        now = time.time()
        for key, action in list(self._pending.items()):
            if (now - action.created_at) > action.ttl_seconds:
                action.state = ActionState.EXPIRED
                self._update_action_state_in_db(action.plan_id, ActionState.EXPIRED)
                self._pending.pop(key, None)
                expired_count += 1
                logger.info(f"[SessionManager] Swept expired pending action #{action.plan_id} for {key}")
        return expired_count

    def get_pending_by_id(self, action_id: str) -> Optional[PendingAction]:
        """Finds active pending action across any channel by its unique plan_id/action_id."""
        for key, action in list(self._pending.items()):
            if action.plan_id == action_id:
                if action.is_expired:
                    action.status = "expired"
                    self._update_action_state_in_db(action.plan_id, ActionState.EXPIRED)
                    del self._pending[key]
                    return None
                return action
        return None

    def clear_pending(self, channel: str, channel_id: str) -> Optional[PendingAction]:
        key = self._make_key(channel, channel_id)
        act = self._pending.pop(key, None)
        if act:
            self._update_action_state_in_db(act.plan_id, ActionState.REJECTED)
        return act

    def clear_pending_by_id(self, action_id: str) -> Optional[PendingAction]:
        """Removes pending action across any channel by its unique plan_id/action_id."""
        for key, action in list(self._pending.items()):
            if action.plan_id == action_id:
                act = self._pending.pop(key, None)
                if act:
                    self._update_action_state_in_db(act.plan_id, ActionState.REJECTED)
                return act
        return None

    # ── TASK & SUBPROCESS SUPERVISOR (Hermes Parity) ──

    def register_active_task(self, channel: str, channel_id: str, task: asyncio.Task) -> None:
        key = self._make_key(channel, channel_id)
        self._active_tasks[key] = task
        self._interrupted_sessions.discard(key)
        logger.debug(f"[SessionManager] Registered active task {task} for {key}")

    def get_active_task(self, channel: str, channel_id: str) -> Optional[asyncio.Task]:
        key = self._make_key(channel, channel_id)
        task = self._active_tasks.get(key)
        if task and task.done():
            self._active_tasks.pop(key, None)
            return None
        return task

    def unregister_active_task(self, channel: str, channel_id: str, task: Optional[asyncio.Task] = None) -> None:
        key = self._make_key(channel, channel_id)
        cur = self._active_tasks.get(key)
        if cur and (task is None or cur is task):
            self._active_tasks.pop(key, None)

    def register_process_pid(self, channel: str, channel_id: str, pid: int) -> None:
        if not pid or pid <= 0:
            return
        key = self._make_key(channel, channel_id)
        if key not in self._active_processes:
            self._active_processes[key] = set()
        self._active_processes[key].add(pid)
        logger.debug(f"[SessionManager] Registered OS process PID {pid} for {key}")

    def unregister_process_pid(self, channel: str, channel_id: str, pid: int) -> None:
        key = self._make_key(channel, channel_id)
        if key in self._active_processes:
            self._active_processes[key].discard(pid)
            if not self._active_processes[key]:
                self._active_processes.pop(key, None)

    def get_active_pids(self, channel: str, channel_id: str) -> set[int]:
        key = self._make_key(channel, channel_id)
        return set(self._active_processes.get(key, set()))

    def is_interrupted(self, channel: str, channel_id: str) -> bool:
        key = self._make_key(channel, channel_id)
        return key in self._interrupted_sessions

    def clear_interrupted(self, channel: str, channel_id: str) -> None:
        key = self._make_key(channel, channel_id)
        self._interrupted_sessions.discard(key)

    def get_session_lock(self, session_key: str) -> AsyncReentrantLock:
        """Returns or creates a cooperative reentrant lock for the session (Hermes turn_lease parity)."""
        clean_key = str(session_key).strip().lower()
        if clean_key not in self._session_locks:
            self._session_locks[clean_key] = AsyncReentrantLock()
        return self._session_locks[clean_key]

    async def request_hard_interrupt(self, channel: str, channel_id: str, reason: str = "stop_command") -> Dict[str, Any]:
        """
        Hermes Hard Interrupt & Process Reaper:
        1. Cancels active asyncio turn task.
        2. Kills entire OS child process tree (PID reaper) spawned during this turn.
        3. Clears pending approval state.
        4. Sets interrupted session flag.
        """
        key = self._make_key(channel, channel_id)
        self._interrupted_sessions.add(key)
        logger.warning(f"[SessionManager] HARD INTERRUPT requested for {key} (reason: {reason})")

        task_cancelled = False
        active_task = self._active_tasks.pop(key, None)
        if active_task and not active_task.done():
            active_task.cancel()
            task_cancelled = True
            logger.info(f"[SessionManager] Cancelled in-flight task for {key}")

        # 2. Reap and kill all spawned OS child processes
        processes_killed = 0
        pids = self._active_processes.pop(key, set())
        if pids:
            from core.sandbox import CommandSandbox
            for pid in list(pids):
                try:
                    CommandSandbox._kill_process_tree(pid)
                    processes_killed += 1
                    logger.info(f"[SessionManager] Reaped/killed OS process PID {pid} for {key}")
                except Exception as e_k:
                    logger.debug(f"[SessionManager] Error killing PID {pid}: {e_k}")

        # 3. Clear pending action
        pending_cleared = self.clear_pending(channel, channel_id) is not None

        return {
            "task_cancelled": task_cancelled,
            "processes_killed": processes_killed,
            "pending_cleared": pending_cleared,
            "channel": channel,
            "channel_id": channel_id,
        }

    def evaluate_intent(self, text: str, channel: str, channel_id: str) -> Dict[str, Any]:
        """
        Evaluates incoming user message against session state.
        Returns {'has_pending': bool, 'is_approval': bool, 'pending': Optional[PendingAction]}
        Only intercepts when an action is strictly in PENDING state awaiting user decision.
        """
        pending = self.get_pending(channel, channel_id)
        if not pending or pending.state != ActionState.PENDING:
            return {"has_pending": False, "is_approval": False, "pending": None}

        # User sent a message while an action is pending
        is_app = is_explicit_plan_approval(text)
        return {
            "has_pending": True,
            "is_approval": is_app,
            "pending": pending
        }


# Global singleton session manager
session_state_manager = SessionStateManager()
