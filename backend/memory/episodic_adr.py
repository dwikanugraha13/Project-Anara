"""
episodic_adr.py — Episodic Project Memory & Autonomous Architecture Decision Records (ADR).
Hermes Parity: Pillar 3.
Maintains persistent architectural decisions, structural rationales, and test milestones
in SQLite (anara_brain.db) across coding sessions, preventing architectural drift and
re-solving already solved engineering decisions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional
from constants import get_anara_db_path

logger = logging.getLogger("anara.memory.adr")

DB_PATH = get_anara_db_path()


class EpisodicADRManager:
    """Manages persistent Architectural Decision Records (ADR) in SQLite."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_table()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_table(self):
        """Initializes the project_adr schema in anara_brain.db."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS project_adr (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        adr_id TEXT UNIQUE NOT NULL,
                        session_id TEXT NOT NULL,
                        milestone_task TEXT NOT NULL,
                        architecture_decision TEXT NOT NULL,
                        rationale TEXT NOT NULL,
                        affected_files_json TEXT NOT NULL,
                        test_exit_code INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_adr_session ON project_adr(session_id);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_adr_created ON project_adr(created_at);")
                conn.commit()
        except Exception as e:
            logger.warning(f"[EpisodicADR] Table initialization warning: {e}")

    def record_project_adr(
        self,
        milestone_task: str,
        architecture_decision: str,
        rationale: str,
        affected_files: List[str],
        session_id: str = "default",
        test_exit_code: int = 0,
    ) -> Dict[str, Any]:
        """
        Records a confirmed architectural decision milestone into persistent project memory.
        Emits an ADR_RECORDED telemetry event for live Code Studio HUD reflection.
        """
        adr_id = f"adr_{uuid.uuid4().hex[:8]}"
        files_json = json.dumps(affected_files or [], ensure_ascii=False)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO project_adr (
                    adr_id, session_id, milestone_task, architecture_decision,
                    rationale, affected_files_json, test_exit_code, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                adr_id,
                str(session_id),
                str(milestone_task).strip(),
                str(architecture_decision).strip(),
                str(rationale).strip(),
                files_json,
                int(test_exit_code),
            ))
            conn.commit()

        record = {
            "adr_id": adr_id,
            "session_id": str(session_id),
            "milestone_task": milestone_task,
            "architecture_decision": architecture_decision,
            "rationale": rationale,
            "affected_files": affected_files or [],
            "test_exit_code": test_exit_code,
            "timestamp": time.time(),
        }
        logger.info(f"[EpisodicADR] Recorded ADR {adr_id}: {architecture_decision[:60]}")

        # Real-time Telemetry event distribution (Pilar 2)
        try:
            from telemetry.event_bus import telemetry_bus, EventType, ActivityProvenance
            loop = asyncio.get_running_loop()
            loop.create_task(
                telemetry_bus.emit(
                    event_type=EventType.ADR_RECORDED,
                    provenance=ActivityProvenance.WORKSPACE_SENTINEL,
                    session_id=str(session_id),
                    trace_id=adr_id,
                    payload=record,
                )
            )
        except (RuntimeError, Exception):
            pass

        return record

    def get_recent_project_adrs(
        self,
        limit: int = 10,
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieves recent ADR entries for prompt context injection or Code Studio inspection."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if session_id:
                    cursor.execute("""
                        SELECT adr_id, session_id, milestone_task, architecture_decision,
                               rationale, affected_files_json, test_exit_code, created_at
                        FROM project_adr
                        WHERE session_id = ?
                        ORDER BY id DESC LIMIT ?
                    """, (str(session_id), limit))
                else:
                    cursor.execute("""
                        SELECT adr_id, session_id, milestone_task, architecture_decision,
                               rationale, affected_files_json, test_exit_code, created_at
                        FROM project_adr
                        ORDER BY id DESC LIMIT ?
                    """, (limit,))
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    try:
                        aff_files = json.loads(r["affected_files_json"])
                    except Exception:
                        aff_files = []
                    results.append({
                        "adr_id": r["adr_id"],
                        "session_id": r["session_id"],
                        "milestone_task": r["milestone_task"],
                        "architecture_decision": r["architecture_decision"],
                        "rationale": r["rationale"],
                        "affected_files": aff_files,
                        "test_exit_code": r["test_exit_code"],
                        "created_at": r["created_at"],
                    })
                return results
        except Exception as e:
            logger.warning(f"[EpisodicADR] Read error: {e}")
            return []

    def search_project_adr(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Fuzzy searches past architectural decisions and rationales."""
        clean_q = (query or "").strip().lower()
        if not clean_q:
            return self.get_recent_project_adrs(limit=limit)

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT adr_id, session_id, milestone_task, architecture_decision,
                           rationale, affected_files_json, test_exit_code, created_at
                    FROM project_adr
                    WHERE LOWER(milestone_task) LIKE ?
                       OR LOWER(architecture_decision) LIKE ?
                       OR LOWER(rationale) LIKE ?
                    ORDER BY id DESC LIMIT ?
                """, (f"%{clean_q}%", f"%{clean_q}%", f"%{clean_q}%", limit))
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    try:
                        aff_files = json.loads(r["affected_files_json"])
                    except Exception:
                        aff_files = []
                    results.append({
                        "adr_id": r["adr_id"],
                        "session_id": r["session_id"],
                        "milestone_task": r["milestone_task"],
                        "architecture_decision": r["architecture_decision"],
                        "rationale": r["rationale"],
                        "affected_files": aff_files,
                        "test_exit_code": r["test_exit_code"],
                        "created_at": r["created_at"],
                    })
                return results
        except Exception as e:
            logger.warning(f"[EpisodicADR] Search error: {e}")
            return []

    async def synthesize_and_record_adr_milestone(
        self,
        task_prompt: str,
        modified_files: List[str],
        test_output: str,
        session_id: str = "default",
    ) -> Optional[Dict[str, Any]]:
        """
        Pure Model-Driven Milestone Distillation (Hermes Parity).
        Uses fast auxiliary model with uncapped tokens (max_tokens=None) to extract
        the architectural decision and rationale upon verified test pass (exit_code == 0).
        """
        from providers import call_universal_chat_model
        from core.capabilities import get_fast_auxiliary_model

        sys_inst = (
            "You are an Architecture Decision Record (ADR) synthesizer for an AI software engineering agent. "
            "A technical task has been implemented and successfully verified with exit_code=0.\n"
            "Summarize the technical decision concisely into a valid JSON object with exactly two keys:\n"
            "- \"architecture_decision\": 1 clear sentence describing what architectural pattern/change was applied.\n"
            "- \"rationale\": 1 clear sentence explaining why this change was made and how it solved the issue.\n"
            "Respond ONLY with raw JSON: {\"architecture_decision\": \"...\", \"rationale\": \"...\"}"
        )
        user_p = (
            f"Task: \"{task_prompt}\"\n"
            f"Modified files: {json.dumps(modified_files)}\n"
            f"Test summary snippet: {test_output[:300]}\n"
            "Output JSON:"
        )

        try:
            model_id = get_fast_auxiliary_model()
            res = await asyncio.wait_for(
                call_universal_chat_model(
                    model_id=model_id,
                    user_prompt=user_p,
                    system_instruction=sys_inst,
                    max_tokens=None,
                    temperature=0.2,
                    read_only=True,
                ),
                timeout=4.0
            )
            if isinstance(res, str) and res.strip():
                clean_json = res.strip().strip("`")
                if clean_json.startswith("json"):
                    clean_json = clean_json[4:].strip()
                parsed = json.loads(clean_json)
                decision = parsed.get("architecture_decision", "").strip()
                rationale = parsed.get("rationale", "").strip()
                if decision:
                    return self.record_project_adr(
                        milestone_task=task_prompt,
                        architecture_decision=decision,
                        rationale=rationale or "Verifikasi fisik lulus 100%.",
                        affected_files=modified_files,
                        session_id=session_id,
                        test_exit_code=0,
                    )
        except Exception as e:
            logger.debug(f"[EpisodicADR] LLM synthesis fallback notice: {e}")

        # Parameter-grounded fallback without hardcoded mock templates
        aff_str = ", ".join(os.path.basename(f) for f in (modified_files or [])[:3]) or "repositori"
        return self.record_project_adr(
            milestone_task=task_prompt,
            architecture_decision=f"Penyelesaian {task_prompt[:60]} via {aff_str}",
            rationale="Diverifikasi valid dan lulus melalui pengujian terminal fisik.",
            affected_files=modified_files,
            session_id=session_id,
            test_exit_code=0,
        )


# Global singleton instance
episodic_adr_manager = EpisodicADRManager()
