"""
anara_subagent.py

Anara Sub-Agent Background Worker Engine.
Allows delegating heavy tasks (reading 30+ project files, deep web scraping, batch PDF analysis)
to isolated asynchronous worker tasks in the background without blocking the real-time Gemini Live voice thread.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)


class SubAgentTask:
    """Represents a delegated background mission."""
    def __init__(self, task_id: str, title: str, mission_prompt: str):
        self.task_id = task_id
        self.title = title
        self.mission_prompt = mission_prompt
        self.status = "running" # 'running', 'completed', 'failed'
        self.progress_percent = 0
        self.steps_log: List[str] = []
        self.result: Optional[str] = None
        self.created_at = time.time()
        self.completed_at: Optional[float] = None


class SubAgentManager:
    """Manages concurrent background worker tasks."""
    def __init__(self):
        self.tasks: Dict[str, SubAgentTask] = {}
        self._listeners: List[Callable[[Dict[str, Any]], Any]] = []

    def register_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def _emit(self, event_type: str, data: Dict[str, Any]):
        for cb in self._listeners:
            try:
                res = cb({"type": event_type, **data})
                if asyncio.iscoroutine(res):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(res)
                    except RuntimeError:
                        pass
            except Exception as e:
                logger.debug(f"[SubAgent] Event callback error: {e}")

    async def spawn_subagent_task(
        self,
        title: str,
        mission_prompt: str,
        worker_coro_factory: Optional[Callable[..., Any]] = None
    ) -> SubAgentTask:
        """Spawns an asynchronous background task."""
        task_id = str(uuid.uuid4())[:8]
        task = SubAgentTask(task_id, title, mission_prompt)
        self.tasks[task_id] = task

        logger.info(f"[SubAgent] Spawned background mission #{task_id}: '{title}'")
        self._emit("subagent_task_started", {
            "task_id": task_id,
            "title": title,
            "prompt": mission_prompt,
            "status": "running"
        })

        asyncio.create_task(self._run_task_pipeline(task, worker_coro_factory))
        return task

    async def _run_task_pipeline(self, task: SubAgentTask, worker_coro_factory: Optional[Callable]):
        """Executes the sub-agent task pipeline in background."""
        try:
            task.steps_log.append("Memulai eksekusi tugas di latar belakang...")
            task.progress_percent = 15

            if worker_coro_factory:
                res = await worker_coro_factory(task)
                task.result = str(res)
            else:
                # Real autonomous sub-agent execution via LLM reasoning
                from providers import call_universal_chat_model, get_active_model_id
                from cognition import get_soul_prompt
                task.steps_log.append(f"Menganalisis konteks: {task.title}...")
                task.progress_percent = 40
                sub_prompt = (
                    f"Kamu adalah Sub-Agent Anara yang bertugas menyelesaikan misi berikut secara mandiri dan tuntas:\n"
                    f"Judul Misi: {task.title}\n"
                    f"Deskripsi/Konteks: {task.mission_prompt}\n\n"
                    "Berikan hasil pengerjaan atau analisis akhir yang konkret, solutif, dan lengkap."
                )
                active_model = get_active_model_id()
                res = await call_universal_chat_model(
                    model_id=active_model,
                    user_prompt=sub_prompt,
                    system_instruction=get_soul_prompt(mode="chat")
                )
                task.result = res or f"Misi '{task.title}' telah berhasil diproses."
                task.steps_log.append("Analisis dan pengerjaan tuntas.")

            task.status = "completed"
            task.progress_percent = 100
            task.completed_at = time.time()
            task.steps_log.append("Selesai")

            logger.info(f"[SubAgent] Mission #{task.task_id} COMPLETED: '{task.title}'")
            self._emit("subagent_task_completed", {
                "task_id": task.task_id,
                "title": task.title,
                "result": task.result,
                "status": "completed",
                "duration_sec": round(task.completed_at - task.created_at, 1)
            })
        except Exception as e:
            task.status = "failed"
            task.result = f"Error: {str(e)}"
            task.completed_at = time.time()
            logger.error(f"[SubAgent] Mission #{task.task_id} FAILED: {e}", exc_info=True)
            self._emit("subagent_task_failed", {
                "task_id": task.task_id,
                "title": task.title,
                "error": str(e),
                "status": "failed"
            })

    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Returns all running and recent sub-agent tasks."""
        return [
            {
                "task_id": t.task_id,
                "title": t.title,
                "status": t.status,
                "progress_percent": t.progress_percent,
                "steps_log": t.steps_log,
                "result": t.result,
                "created_at": t.created_at,
            }
            for t in self.tasks.values()
        ]


# Global subagent manager instance
subagent_manager = SubAgentManager()
