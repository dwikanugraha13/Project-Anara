"""
tracker.py — Empirical Evaluation Metrics Tracker for Project Anara.
Stores benchmark trial history, token spend, latency, and success rates into SQLite.
"""

from __future__ import annotations

import os
import sqlite3
import time
from typing import Any, Dict, List, Optional


class EvalMetricsTracker:
    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            db_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(db_dir, ".evals_history.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    model_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    edit_mode TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    turns INTEGER NOT NULL,
                    tokens_used INTEGER NOT NULL,
                    latency_ms REAL NOT NULL,
                    details TEXT
                )
            """)
            conn.commit()

    def record_trial(
        self,
        run_id: str,
        model_id: str,
        task_id: str,
        edit_mode: str,
        success: bool,
        turns: int,
        tokens_used: int,
        latency_ms: float,
        details: str = ""
    ):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO benchmark_runs (
                    run_id, timestamp, model_id, task_id, edit_mode, success, turns, tokens_used, latency_ms, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                time.time(),
                model_id,
                task_id,
                edit_mode,
                1 if success else 0,
                turns,
                tokens_used,
                latency_ms,
                details
            ))
            conn.commit()

    def get_summary(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            if run_id:
                cur.execute("""
                    SELECT edit_mode,
                           COUNT(*) as total_tasks,
                           SUM(success) as passed_tasks,
                           AVG(tokens_used) as avg_tokens,
                           AVG(latency_ms) as avg_latency
                    FROM benchmark_runs
                    WHERE run_id = ?
                    GROUP BY edit_mode
                """, (run_id,))
            else:
                cur.execute("""
                    SELECT edit_mode,
                           COUNT(*) as total_tasks,
                           SUM(success) as passed_tasks,
                           AVG(tokens_used) as avg_tokens,
                           AVG(latency_ms) as avg_latency
                    FROM benchmark_runs
                    GROUP BY edit_mode
                """)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
