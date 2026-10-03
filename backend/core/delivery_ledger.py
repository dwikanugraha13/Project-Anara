"""
delivery_ledger.py — Durable Outbox Delivery Obligations Ledger for Project Anara Omnichannel Gateway.

Ensures that final conversational responses and notifications destined for messaging platforms
(Telegram, WhatsApp, Discord, Slack) are never lost during host restarts, network drops, or process termination.

Lifecycle States:
- pending: obligation recorded prior to outbound dispatch
- attempting: currently in-flight over network transport
- delivered: confirmed acknowledged by platform API (pruned)
- failed: rejected by transport (retried with exponential backoff)
- abandoned: exceeded maximum retry attempts or expired
"""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("anara.gateway.delivery_ledger")
_DB_LOCK = threading.Lock()

MAX_ATTEMPTS = 3
STALE_AFTER_SECONDS = 24 * 3600
RECOVERED_MARKER = "♻️ [Pesan terpulihkan — server sempat restart saat pengiriman]:\n\n"


def _get_db_path() -> str:
    from memory.base import DB_PATH
    return DB_PATH


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_get_db_path(), timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_delivery_ledger_table() -> None:
    """Creates the persistent delivery obligations table and indexes in SQLite."""
    with _DB_LOCK:
        try:
            with _get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS delivery_obligations (
                        obligation_id TEXT PRIMARY KEY,
                        session_key TEXT NOT NULL,
                        channel TEXT NOT NULL,
                        target_id TEXT NOT NULL,
                        content TEXT NOT NULL,
                        state TEXT NOT NULL, -- pending, attempting, delivered, failed, abandoned
                        attempts INTEGER NOT NULL DEFAULT 0,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        owner_pid INTEGER NOT NULL,
                        last_error TEXT
                    );
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_obligations_state
                    ON delivery_obligations(state, updated_at);
                """)
                conn.commit()
        except Exception as e:
            logger.warning(f"[DeliveryLedger] Init table warning: {e}")


def generate_obligation_id(session_key: str, channel: str, target_id: str, content: str) -> str:
    """Generates deterministic unique obligation ID."""
    raw = f"{session_key}:{channel}:{target_id}:{content[:500]}:{time.time():.4f}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def record_obligation(
    session_key: str,
    channel: str,
    target_id: str,
    content: str,
) -> str:
    """Records an outbound delivery obligation as 'pending' prior to transport dispatch."""
    init_delivery_ledger_table()
    obl_id = generate_obligation_id(session_key, channel, target_id, content)
    now = time.time()
    pid = os.getpid()

    with _DB_LOCK:
        try:
            with _get_conn() as conn:
                conn.cursor().execute("""
                    INSERT OR REPLACE INTO delivery_obligations (
                        obligation_id, session_key, channel, target_id,
                        content, state, attempts, created_at, updated_at,
                        owner_pid, last_error
                    ) VALUES (?, ?, ?, ?, ?, 'pending', 0, ?, ?, ?, NULL);
                """, (obl_id, session_key, channel, str(target_id), content, now, now, pid))
                conn.commit()
        except Exception as e:
            logger.debug(f"[DeliveryLedger] Record obligation error: {e}")
    return obl_id


def mark_attempting(obligation_id: str) -> None:
    """Marks an obligation as actively in-flight over network transport."""
    now = time.time()
    with _DB_LOCK:
        try:
            with _get_conn() as conn:
                conn.cursor().execute("""
                    UPDATE delivery_obligations
                    SET state = 'attempting', attempts = attempts + 1, updated_at = ?
                    WHERE obligation_id = ?;
                """, (now, obligation_id))
                conn.commit()
        except Exception as e:
            logger.debug(f"[DeliveryLedger] Mark attempting error: {e}")


def mark_delivered(obligation_id: str) -> None:
    """Marks obligation as successfully delivered and prunes from durable ledger."""
    with _DB_LOCK:
        try:
            with _get_conn() as conn:
                conn.cursor().execute("""
                    DELETE FROM delivery_obligations WHERE obligation_id = ?;
                """, (obligation_id,))
                conn.commit()
        except Exception as e:
            logger.debug(f"[DeliveryLedger] Mark delivered error: {e}")


def mark_failed(obligation_id: str, error_message: str) -> None:
    """Updates failed status and increments attempt counter."""
    now = time.time()
    with _DB_LOCK:
        try:
            with _get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT attempts FROM delivery_obligations WHERE obligation_id = ?;
                """, (obligation_id,))
                row = cursor.fetchone()
                attempts = row[0] if row else 1
                new_state = "abandoned" if attempts >= MAX_ATTEMPTS else "failed"

                cursor.execute("""
                    UPDATE delivery_obligations
                    SET state = ?, updated_at = ?, last_error = ?
                    WHERE obligation_id = ?;
                """, (new_state, now, str(error_message)[:300], obligation_id))
                conn.commit()
        except Exception as e:
            logger.debug(f"[DeliveryLedger] Mark failed error: {e}")


def sweep_recoverable(max_age_seconds: float = STALE_AFTER_SECONDS) -> List[Dict[str, Any]]:
    """
    Sweeps the delivery ledger on startup or reconnect for orphaned messages from crashed PIDs.
    Returns messages ready for replay with appropriate recovered prefixes.
    """
    init_delivery_ledger_table()
    now = time.time()
    current_pid = os.getpid()
    recoverable: List[Dict[str, Any]] = []

    with _DB_LOCK:
        try:
            with _get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT obligation_id, session_key, channel, target_id, content, state, attempts
                    FROM delivery_obligations
                    WHERE state IN ('pending', 'attempting', 'failed')
                      AND (owner_pid != ? OR (? - updated_at) > 120.0)
                      AND (? - created_at) <= ?
                      AND attempts < ?;
                """, (current_pid, now, now, max_age_seconds, MAX_ATTEMPTS))
                rows = cursor.fetchall()
                for r in rows:
                    rec = dict(r)
                    # Attempting or failed items may already have landed; wrap with recovered marker
                    if rec["state"] in ("attempting", "failed"):
                        rec["display_content"] = f"{RECOVERED_MARKER}{rec['content']}"
                    else:
                        rec["display_content"] = rec["content"]
                    recoverable.append(rec)
        except Exception as e:
            logger.warning(f"[DeliveryLedger] Sweep recoverable error: {e}")

    return recoverable
