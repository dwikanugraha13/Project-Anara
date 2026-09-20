"""
kanban_tools.py — Multi-Agent Kanban Task Orchestration Tools for Project Anara.
Anara Standard kanban toolset (kanban_create, kanban_list,
kanban_complete, kanban_request_review, kanban_block).
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from memory import memory_engine
from .events import _emit_agent_event

logger = logging.getLogger(__name__)


def _init_kanban_table():
    """Initializes the kanban_tasks table in anara_brain.db safely."""
    try:
        with memory_engine._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kanban_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'todo', -- 'todo', 'in_progress', 'review', 'blocked', 'done'
                    priority INTEGER DEFAULT 1, -- 1=normal, 2=high, 3=urgent
                    assignee TEXT DEFAULT 'agent',
                    review_notes TEXT DEFAULT '',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_kanban_status ON kanban_tasks(status);")
            conn.commit()
    except Exception as e:
        logger.debug(f"[KanbanTools] Table init warning: {e}")


_init_kanban_table()


async def _tool_kanban_create_task(
    title: str,
    description: str = "",
    priority: int = 1,
    assignee: str = "agent"
) -> Dict[str, Any]:
    """Creates a new task card on the Kanban project board."""
    clean_title = (title or "").strip()
    if not clean_title:
        return {"status": "error", "message": "Task title cannot be empty."}

    _emit_agent_event("agent_action_start", {
        "tool_name": "kanban_create_task",
        "action_title": "Kanban: Create Task",
        "detail": f"[{priority}] {clean_title}",
        "icon": "clipboard"
    })

    try:
        with memory_engine._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO kanban_tasks (title, description, status, priority, assignee, updated_at)
                VALUES (?, ?, 'todo', ?, ?, CURRENT_TIMESTAMP)
            """, (clean_title, (description or "").strip(), int(priority or 1), (assignee or "agent").strip()))
            conn.commit()
            task_id = cursor.lastrowid

        # Emit HUD projection event
        _emit_agent_event("hud_project", {
            "type": "kanban_card",
            "action": "created",
            "task": {"id": task_id, "title": clean_title, "status": "todo", "priority": priority}
        })

        return {
            "status": "success",
            "task_id": task_id,
            "title": clean_title,
            "column": "todo",
            "message": f"Task #{task_id} '{clean_title}' created successfully in 'todo' column."
        }
    except Exception as e:
        logger.error(f"[KanbanTools] Create task error: {e}")
        return {"status": "error", "message": f"Failed to create task: {e}"}


async def _tool_kanban_list_tasks(status: Optional[str] = None) -> Dict[str, Any]:
    """Lists all Kanban tasks, optionally filtered by status ('todo', 'in_progress', 'review', 'blocked', 'done')."""
    try:
        with memory_engine._get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT * FROM kanban_tasks WHERE status = ? ORDER BY priority DESC, id ASC", (status.strip().lower(),))
            else:
                cursor.execute("SELECT * FROM kanban_tasks ORDER BY status ASC, priority DESC, id ASC")
            rows = [dict(r) for r in cursor.fetchall()]

        # Group by column
        columns = {"todo": [], "in_progress": [], "review": [], "blocked": [], "done": []}
        for r in rows:
            col = r.get("status", "todo")
            if col in columns:
                columns[col].append(r)
            else:
                columns["todo"].append(r)

        return {
            "status": "success",
            "total_tasks": len(rows),
            "columns": columns,
            "tasks": rows
        }
    except Exception as e:
        logger.error(f"[KanbanTools] List tasks error: {e}")
        return {"status": "error", "message": f"Failed to list tasks: {e}"}


async def _tool_kanban_update_task(
    task_id: int,
    status: str,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Updates the status of a Kanban task card.
    status: 'todo', 'in_progress', 'review', 'blocked', 'done'
    """
    clean_status = (status or "").strip().lower()
    valid_statuses = {"todo", "in_progress", "review", "blocked", "done"}
    if clean_status not in valid_statuses:
        return {
            "status": "error",
            "message": f"Status '{status}' is invalid. Choose from: {', '.join(valid_statuses)}"
        }

    _emit_agent_event("agent_action_start", {
        "tool_name": "kanban_update_task",
        "action_title": f"Kanban: Move #{task_id} -> {clean_status.upper()}",
        "detail": notes or "",
        "icon": "check-square"
    })

    try:
        with memory_engine._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE kanban_tasks
                SET status = ?, review_notes = COALESCE(?, review_notes), updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (clean_status, notes, int(task_id)))
            conn.commit()
            updated = cursor.rowcount > 0

        if not updated:
            return {"status": "error", "message": f"Task #{task_id} was not found in Kanban board."}

        _emit_agent_event("hud_project", {
            "type": "kanban_card",
            "action": "moved",
            "task_id": task_id,
            "new_status": clean_status
        })

        return {
            "status": "success",
            "task_id": task_id,
            "new_status": clean_status,
            "message": f"Task #{task_id} moved to '{clean_status}' column successfully."
        }
    except Exception as e:
        logger.error(f"[KanbanTools] Update task error: {e}")
        return {"status": "error", "message": f"Failed to update task: {e}"}


async def _tool_kanban_request_review(task_id: int, review_summary: str) -> Dict[str, Any]:
    """Moves a task to 'review' status with a concise summary of work accomplished and verified."""
    return await _tool_kanban_update_task(task_id=task_id, status="review", notes=review_summary)
