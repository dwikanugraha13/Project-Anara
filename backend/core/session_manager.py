"""
session_manager.py — State Machine Intent & Pending Action Tracker for Project Anara.
Anara Standard multi-channel session state management:
1. Tracks active transaction states (IDLE, AWAITING_APPROVAL, EXECUTING).
2. Holds pending high-risk tool actions with automatic TTL expiration.
3. Decouples conversational approval intent tracking from rigid regex dictionaries.
"""

from __future__ import annotations

from enum import Enum
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from core.plan_detector import is_explicit_plan_approval

logger = logging.getLogger(__name__)


class ActionState(str, Enum):
    """Finite State Machine states for a pending action lifecycle (Hermes Parity)."""
    PENDING = "pending"          # Menunggu keputusan pengguna
    APPROVED = "approved"        # Disetujui (via tombol atau lisan)
    REJECTED = "rejected"        # Ditolak/dibatalkan
    EXECUTING = "executing"      # Sedang berjalan di sandbox
    EXECUTED = "executed"        # Selesai dengan sukses
    FAILED = "failed"            # Gagal/eksepsi saat eksekusi
    EXPIRED = "expired"          # Waktu tunggu (TTL 300s) habis


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
    """

    def __init__(self):
        self._pending: Dict[str, PendingAction] = {}
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._active_processes: Dict[str, set[int]] = {}
        self._interrupted_sessions: set[str] = set()
        self._recently_expired: Dict[str, tuple[PendingAction, float]] = {}

    def _make_key(self, channel: str, channel_id: str) -> str:
        return f"{str(channel).strip().lower()}_{str(channel_id).strip()}"

    def store_pending(self, action: PendingAction) -> None:
        key = self._make_key(action.channel, action.channel_id)
        self._pending[key] = action
        logger.info(f"[SessionManager] Stored pending action #{action.plan_id} ({action.tool_name}) for key: {key}")

    def set_pending_action(self, channel: str, channel_id: str, action: PendingAction) -> None:
        """Stores a pending action under the channel and channel_id key (Hermes Lifecycle)."""
        action.channel = channel
        action.channel_id = channel_id
        self.store_pending(action)

    def get_pending(self, channel: str, channel_id: str) -> Optional[PendingAction]:
        key = self._make_key(channel, channel_id)
        action = self._pending.get(key)
        if action and action.is_expired:
            logger.info(f"[SessionManager] Pending action #{action.plan_id} has expired.")
            action.state = ActionState.EXPIRED
            self._recently_expired[key] = (action, time.time())
            del self._pending[key]
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
                    del self._pending[key]
                    return None
                return action
        return None

    def clear_pending(self, channel: str, channel_id: str) -> Optional[PendingAction]:
        key = self._make_key(channel, channel_id)
        return self._pending.pop(key, None)

    def clear_pending_by_id(self, action_id: str) -> Optional[PendingAction]:
        """Removes pending action across any channel by its unique plan_id/action_id."""
        for key, action in list(self._pending.items()):
            if action.plan_id == action_id:
                return self._pending.pop(key, None)
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
        """
        pending = self.get_pending(channel, channel_id)
        if not pending:
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
