"""
Chat Sessions, Message Threads, and Project Plans Routes for Project Anara.
"""
import logging
import os
import shutil
import time as _time
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from memory import memory_engine
from core import anara_agent
from shared_state import broadcast_agent_event

logger = logging.getLogger("anara.routers.sessions")

router = APIRouter(tags=["Chat Sessions"])

class SessionCreateRequest(BaseModel):
    title: Optional[str] = "New Chat"
    speaker_name: Optional[str] = None
    session_type: Optional[str] = "chat"

class SessionPatchRequest(BaseModel):
    title: Optional[str] = None
    is_pinned: Optional[bool] = None
    is_archived: Optional[bool] = None

class PlanProposalRequest(BaseModel):
    title: str
    summary: str
    steps: List[str]
    tech_stack: Optional[List[str]] = []
    estimated_effort: Optional[str] = "Normal"

@router.get("/api/chat/sessions")
async def list_sessions(speaker: Optional[str] = None, session_type: Optional[str] = None, include_archived: bool = False):
    """Lists conversation threads for the history sidebar, optionally filtered by session_type ('chat' | 'code')."""
    return memory_engine.get_sessions(speaker_name=speaker, session_type=session_type, include_archived=include_archived)

@router.post("/api/chat/sessions")
async def create_session_endpoint(req: SessionCreateRequest):
    """Starts a brand-new conversation thread for either chat or code environment."""
    clean_type = "code" if req.session_type == "code" else "chat"
    default_title = "New Project" if clean_type == "code" else "New Chat"
    session = memory_engine.create_session(
        speaker_name=req.speaker_name,
        title=req.title or default_title,
        session_type=clean_type
    )
    return {"status": "success", "session": session}

@router.get("/api/chat/sessions/{session_id}")
async def get_session_endpoint(session_id: int):
    """Returns one thread plus all of its messages."""
    session = memory_engine.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesi percakapan tidak ditemukan")
    messages = memory_engine.get_session_messages(session_id)
    return {"status": "success", "session": session, "messages": messages}

@router.patch("/api/chat/sessions/{session_id}")
async def patch_session_endpoint(session_id: int, req: SessionPatchRequest):
    """Renames, pins or archives a thread."""
    ok = memory_engine.patch_session(session_id, title=req.title, is_pinned=req.is_pinned, is_archived=req.is_archived)
    if not ok:
        raise HTTPException(status_code=400, detail="Sesi tidak ditemukan atau tidak ada perubahan")
    return {"status": "success", "session": memory_engine.get_session(session_id)}

@router.delete("/api/chat/sessions/{session_id}")
async def delete_session_endpoint(session_id: int):
    """Deletes a thread together with every message and cleans its workspace folder on disk."""
    anara_agent.clear_workspace(session_id=session_id)
    ok = memory_engine.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan")
    return {"status": "success", "session_id": session_id}

@router.delete("/api/chat/sessions/{session_id}/messages")
async def clear_session_messages_endpoint(session_id: int):
    """Empties a thread but keeps it in the list."""
    removed = memory_engine.clear_session_messages(session_id)
    return {"status": "success", "removed": removed, "session_id": session_id}

@router.delete("/api/chat/sessions")
async def bulk_delete_sessions_endpoint(archived_only: bool = True, keep_pinned: bool = True):
    """Bulk cleanup: archived threads only, or everything non-pinned, cleaning disk workspaces."""
    deleted = memory_engine.bulk_delete_sessions(archived_only=archived_only, keep_pinned=keep_pinned)
    try:
        ws = anara_agent.base_workspace_path
        valid_ids = set(s["id"] for s in memory_engine.get_sessions(include_archived=True))
        if os.path.exists(ws):
            for item in os.listdir(ws):
                if item.startswith("session_"):
                    try:
                        s_id = int(item.replace("session_", ""))
                        if s_id not in valid_ids:
                            shutil.rmtree(os.path.join(ws, item), ignore_errors=True)
                    except ValueError:
                        pass
    except Exception as e:
        logger.debug(f"[Workspace Cleanup] {e}")
    return {"status": "success", "deleted_count": deleted}

# ── Project Planning Mode (Plan/Build protocol) Endpoints ──

@router.get("/api/chat/sessions/{session_id}/plan")
async def get_session_plan_endpoint(session_id: int):
    """Returns the current pending plan proposal for a session."""
    plan = memory_engine.get_session_pending_plan(session_id)
    return {"status": "success", "session_id": session_id, "plan": plan}

@router.post("/api/chat/sessions/{session_id}/plan")
async def save_session_plan_endpoint(session_id: int, req: PlanProposalRequest):
    """Saves or updates a project plan proposal awaiting user review."""
    plan_dict = {
        "title": req.title,
        "summary": req.summary,
        "steps": req.steps,
        "tech_stack": req.tech_stack or [],
        "estimated_effort": req.estimated_effort or "Normal",
        "created_at": _time.time(),
    }
    ok = memory_engine.set_session_pending_plan(session_id, plan_dict)
    if not ok:
        raise HTTPException(status_code=400, detail="Gagal menyimpan rencana")
    broadcast_agent_event({
        "type": "agent_hud_project",
        "visual_type": "plan_card",
        "title": req.title,
        "summary": req.summary,
        "planData": plan_dict,
        "session_id": session_id,
        "timestamp": _time.time(),
    })
    return {"status": "success", "plan": plan_dict}

@router.delete("/api/chat/sessions/{session_id}/plan")
async def clear_session_plan_endpoint(session_id: int):
    """Clears the pending plan for a session."""
    memory_engine.clear_session_pending_plan(session_id)
    return {"status": "success", "session_id": session_id}
