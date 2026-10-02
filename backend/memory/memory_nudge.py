"""
memory_nudge.py — Anara Autonomous Nudge & Scratchpad Engine.
Anara Standard: Subsystem 4 Working Memory & Proactive Consolidation.
Tracks conversational turns per session and autonomously nudges the model
to persist user preferences, memories, or newly created skills into SQLite,
while maintaining a focused working-memory Scratchpad for multi-turn execution.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionTurnTracker:
    """Tracks conversation turns per session and triggers autonomous nudges."""
    session_id: str
    turn_count: int = 0
    memory_nudge_interval: int = 10     # Every 10 turns: nudge memory consolidation
    skill_nudge_interval: int = 15      # Every 15 turns: nudge reusable skill extraction

    def increment_turn(self) -> Optional[str]:
        """Called every time a user turn is processed in the channel or session."""
        self.turn_count += 1
        nudges: List[str] = []

        # 1. Autonomous Memory Nudge (Anara Standard)
        if self.turn_count % self.memory_nudge_interval == 0:
            nudges.append(
                f"[ANARA AUTONOMOUS MEMORY NUDGE (Turn {self.turn_count})]\n"
                "Review recent conversation turns. If the user shared new preferences, habits, "
                "crucial code corrections, project facts, or profile details, "
                "call the 'memory' tool (target: USER.md or MEMORY.md) silently. "
                "Maintain active conversation language."
            )

        # 2. Autonomous Skill Creation Nudge (Anara Standard)
        if self.turn_count % self.skill_nudge_interval == 0:
            nudges.append(
                f"[ANARA SKILL CREATION NUDGE (Turn {self.turn_count})]\n"
                "Review recently completed technical workflows. "
                "If you identified a novel, reusable solution pattern or setup procedure, "
                "persist it using 'learn_and_save_skill'. Maintain active conversation language."
            )

        if nudges:
            return "\n\n".join(nudges)
        return None


@dataclass
class TaskScratchpad:
    """Working Memory State for multi-step tasks to prevent objective drift (SQLite Persistent & Thread-Safe)."""
    session_id: str = "default"
    objective: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)  # [{"step": str, "status": "todo"|"in_progress"|"done"}]
    findings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    def persist_to_db(self):
        """Persists current scratchpad state snapshot to SQLite anara_brain.db."""
        with self._lock:
            try:
                from memory import memory_engine
                data = {
                    "objective": self.objective,
                    "steps": self.steps,
                    "findings": self.findings,
                    "notes": self.notes,
                }
                memory_engine.set_app_setting(f"session_scratchpad_{self.session_id}", json.dumps(data))
            except Exception as e:
                logger.debug(f"[Scratchpad] Failed to persist state for session {self.session_id}: {e}")

    def load_from_db(self) -> bool:
        """Restores scratchpad state from SQLite anara_brain.db."""
        with self._lock:
            try:
                from memory import memory_engine
                raw = memory_engine.get_app_setting(f"session_scratchpad_{self.session_id}")
                if raw and str(raw).strip():
                    data = json.loads(raw)
                    self.objective = data.get("objective", "")
                    self.steps = data.get("steps", [])
                    self.findings = data.get("findings", [])
                    self.notes = data.get("notes", [])
                    return True
            except Exception as e:
                logger.debug(f"[Scratchpad] Failed to load state for session {self.session_id}: {e}")
            return False

    def set_objective(self, objective: str, steps: Optional[List[str]] = None):
        """Initializes or resets the primary objective and plan steps."""
        with self._lock:
            self.objective = (objective or "").strip()
            self.steps = [{"step": s.strip(), "status": "todo"} for s in (steps or []) if s.strip()]
            self.findings = []
            self.notes = []
            self.persist_to_db()

    def mark_step(self, step_idx_or_name: Any, status: str = "done") -> bool:
        """Updates the status of a step by 0-based index or step substring."""
        with self._lock:
            clean_status = (status or "done").strip().lower()
            if clean_status in ("completed", "finish", "finished", "success"):
                clean_status = "done"
            elif clean_status in ("progress", "working", "active", "doing"):
                clean_status = "in_progress"
            elif clean_status in ("pending", "waiting", "backlog"):
                clean_status = "todo"

            updated = False
            try:
                idx = int(step_idx_or_name)
                if 0 <= idx < len(self.steps):
                    self.steps[idx]["status"] = clean_status
                    updated = True
            except (ValueError, TypeError):
                pass

            if not updated:
                target = str(step_idx_or_name).strip().lower()
                if len(target) >= 3:
                    for s in self.steps:
                        if target in s.get("step", "").lower() or (len(s.get("step", "")) >= 3 and s.get("step", "").lower() in target):
                            s["status"] = clean_status
                            updated = True
                            break

            if updated:
                self.persist_to_db()
            return updated

    def add_step(self, step_text: str, status: str = "todo"):
        with self._lock:
            clean_s = (step_text or "").strip()
            if clean_s:
                self.steps.append({"step": clean_s, "status": status})
                if len(self.steps) > 30:
                    self.steps.pop(0)
                self.persist_to_db()

    def add_finding(self, finding: str):
        with self._lock:
            clean_f = (finding or "").strip()
            if clean_f and clean_f not in self.findings:
                self.findings.append(clean_f)
                if len(self.findings) > 20:
                    self.findings.pop(0)
                self.persist_to_db()

    def clear(self):
        """Clears the scratchpad when a task completes."""
        with self._lock:
            self.objective = ""
            self.steps = []
            self.findings = []
            self.notes = []
            self.persist_to_db()

    def render_to_prompt(self, max_steps: int = 15, max_findings: int = 8, char_limit: int = 1500) -> str:
        """Injected into Tier 3 volatile system prompt during active task turns with strict token budgets."""
        with self._lock:
            if not self.objective:
                return ""

            step_lines = []
            for i, s in enumerate(self.steps[:max_steps]):
                st = s.get("status", "todo")
                icon = "[x]" if st == "done" else ("[-]" if st == "in_progress" else "[ ]")
                step_lines.append(f"  {icon} {i + 1}. {s.get('step', '')[:100]}")
            if len(self.steps) > max_steps:
                step_lines.append(f"  ... (+{len(self.steps) - max_steps} more steps)")

            findings_lines = [f"  • {f[:120]}" for f in self.findings[:max_findings]]
            if len(self.findings) > max_findings:
                findings_lines.append(f"  ... (+{len(self.findings) - max_findings} more findings)")

            res = (
                "\n=== [ANARA ACTIVE SCRATCHPAD & TASK STATE] ===\n"
                f"🎯 PRIMARY TARGET: {self.objective[:150]}\n"
                f"📋 CHECKLIST PROGRESS:\n" + ("\n".join(step_lines) if step_lines else "  (No steps registered yet)") + "\n"
                f"🔍 KEY FINDINGS:\n" + ("\n".join(findings_lines) if findings_lines else "  (No special notes yet)") + "\n"
                "===============================================\n"
            )
            return res[:char_limit]

    def to_checklist_payload(self) -> Dict[str, Any]:
        """Formats the scratchpad for WebSocket event broadcasting to DockPlanChecklist UI."""
        with self._lock:
            completed = sum(1 for s in self.steps if s.get("status") == "done")
            items = []
            for s in self.steps:
                st = s.get("status", "todo")
                items.append({
                    "title": s.get("step", ""),
                    "isCompleted": st == "done",
                    "isInProgress": st == "in_progress",
                })
            return {
                "title": self.objective or "Task Plan Checklist",
                "completedCount": completed,
                "total": len(self.steps),
                "items": items,
            }


class MemoryNudgeManager:
    """Singleton managing turn tracking and working scratchpads per session."""

    def __init__(self):
        self._lock = threading.RLock()
        self._trackers: Dict[str, SessionTurnTracker] = {}
        self._scratchpads: Dict[str, TaskScratchpad] = {}

    def _canonical_key(self, session_id: Any) -> str:
        """Resolves hybrid session keys (int id or canonical key string) to a consistent string key."""
        if not session_id:
            return "default"
        try:
            from memory import memory_engine
            sid = memory_engine._resolve_session_id(session_id)
            if sid is not None:
                return str(sid)
        except Exception:
            pass
        return str(session_id)

    def get_tracker(self, session_id: Any) -> SessionTurnTracker:
        s_key = self._canonical_key(session_id)
        with self._lock:
            if s_key not in self._trackers:
                self._trackers[s_key] = SessionTurnTracker(session_id=s_key)
            return self._trackers[s_key]

    def get_scratchpad(self, session_id: Any) -> TaskScratchpad:
        s_key = self._canonical_key(session_id)
        with self._lock:
            if s_key not in self._scratchpads:
                pad = TaskScratchpad(session_id=s_key)
                pad.load_from_db()
                self._scratchpads[s_key] = pad
            return self._scratchpads[s_key]

    def increment_and_get_nudge(self, session_id: Any) -> Optional[str]:
        tracker = self.get_tracker(session_id)
        return tracker.increment_turn()

    def evict_session(self, session_id: Any) -> None:
        """Evicts in-memory tracker and scratchpad caches for a deleted session."""
        s_key = self._canonical_key(session_id)
        raw_key = str(session_id)
        with self._lock:
            self._trackers.pop(s_key, None)
            self._trackers.pop(raw_key, None)
            self._scratchpads.pop(s_key, None)
            self._scratchpads.pop(raw_key, None)


# Global singleton instance
memory_nudge_manager = MemoryNudgeManager()
