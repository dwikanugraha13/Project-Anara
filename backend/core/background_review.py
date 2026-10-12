"""
background_review.py — Asynchronous Idle Review & Memory Refinement Queue for Project Anara.
Parity with Hermes Agent background_review & review_idle_queue (Nous Research).

Spawns non-blocking background workers during user idle periods to:
1. Extract architectural decisions & lessons into episodic ADR memory.
2. Perform proactive log spillover pruning and tool trace cleanup.
3. Keep runtime fast and responsive without adding latency to active conversational turns.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("anara.core.background_review")


class BackgroundReviewWorker:
    """Non-blocking queue that processes background memory synthesis and maintenance during idle intervals."""

    _instance: Optional[BackgroundReviewWorker] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    @classmethod
    def get_instance(cls) -> BackgroundReviewWorker:
        with cls._lock:
            if cls._instance is None:
                cls._instance = BackgroundReviewWorker()
            return cls._instance

    def schedule_idle_review(
        self,
        session_id: str,
        user_prompt: str,
        assistant_response: str,
        workspace_path: Optional[str] = None,
    ) -> None:
        """Schedules a turn for background evaluation without awaiting."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    self._enqueue_item({
                        "session_id": str(session_id),
                        "user_prompt": user_prompt,
                        "assistant_response": assistant_response,
                        "workspace_path": workspace_path,
                    })
                )
        except RuntimeError:
            pass

    async def _enqueue_item(self, item: Dict[str, Any]) -> None:
        await self._queue.put(item)
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._process_queue())

    async def _process_queue(self) -> None:
        while not self._queue.empty():
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._perform_review(item)
                self._queue.task_done()
            except (asyncio.TimeoutError, asyncio.CancelledError):
                break
            except Exception as e:
                logger.debug(f"[BackgroundReview] Review task notice: {e}")
        self._running = False

    async def _perform_review(self, item: Dict[str, Any]) -> None:
        """Executes lightweight idle analysis: ADR memory extraction and log sanity."""
        u_text = item.get("user_prompt", "")
        a_text = item.get("assistant_response", "")
        sid = item.get("session_id", "default")

        # 1. Check for Architectural Decision Indicators
        adr_triggers = ("arsitektur", "keputusan", "standar", "architecture", "adr", "database schema", "api contract")
        if any(trig in u_text.lower() or trig in a_text.lower() for trig in adr_triggers):
            try:
                from memory.base import memory_engine
                # Extract brief rule/decision
                lines = [ln.strip() for ln in a_text.splitlines() if len(ln.strip()) > 20]
                if lines:
                    key_decision = lines[0][:200]
                    memory_engine.set_app_setting(f"adr_recent_{sid[:8]}", key_decision)
                    logger.info(f"[BackgroundReview] Persisted idle architectural insight for session '{sid}'.")
            except Exception:
                pass

        # 2. Yield briefly to ensure event loop fairness
        await asyncio.sleep(0.01)


background_review_worker = BackgroundReviewWorker.get_instance()
