"""
Brain Database, Memory, Notes, Speakers, and System Status Routes for Project Anara.
"""
import base64
import logging
import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from memory import memory_engine, get_current_indonesian_time_str
from core import key_manager
from shared_state import get_shared_http_client, active_sessions

logger = logging.getLogger("anara.routers.brain")

router = APIRouter(tags=["Brain"])

class MemoryCreateRequest(BaseModel):
    speaker_name: str
    key: str
    value: str
    category: str = "general"

class NoteCreateRequest(BaseModel):
    title: str
    content: str = ""
    category: str = "todo"
    due_date: Optional[str] = None
    speaker_name: Optional[str] = None

class SpeakerCreateRequest(BaseModel):
    name: str

class SpeakerCalibrateRequest(BaseModel):
    audio_base64: str

class ActiveSpeakerRequest(BaseModel):
    name: str

class ProjectCreateRequest(BaseModel):
    speaker_name: str
    name: str
    tech_stack: str = ""
    goal: str = ""
    status: str = "active"
    notes: str = ""

class AnimationUpsertRequest(BaseModel):
    name: str
    category: str
    emotion: str = "neutral"
    gesture: str = "idle"
    intensity: float = 0.5
    duration_sec: float = 2.0
    keywords: List[str] = []

@router.get("/api/brain/overview")
async def get_brain_overview():
    """Returns complete summary of speakers, memories, notes, projects, and stats."""
    stats = memory_engine.get_brain_stats()
    speakers = memory_engine.get_all_speakers()
    notes = memory_engine.get_notes_and_todos()
    memories = memory_engine.get_all_memories()
    projects = memory_engine.get_projects_for_speaker()
    conversations = memory_engine.get_recent_conversations(limit=50)
    time_info = get_current_indonesian_time_str()

    return {
        "stats": stats,
        "speakers": speakers,
        "notes": notes,
        "memories": memories,
        "projects": projects,
        "recent_conversations": conversations,
        "time": time_info
    }

@router.get("/api/proxy-image")
async def proxy_image_endpoint(url: str):
    """Proxies real image requests to bypass browser referrer and CORS restrictions."""
    if not url or not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        client = get_shared_http_client()
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            c_type = resp.headers.get("content-type", "image/jpeg")
            if "image" not in c_type:
                c_type = "image/jpeg"
            return Response(content=resp.content, media_type=c_type, headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*"
            })
    except Exception as e:
        logger.warning(f"[ImageProxy] Error fetching image {url[:60]}: {e}")
    raise HTTPException(status_code=404, detail="Image could not be retrieved")

@router.get("/api/brain/memories")
async def get_memories(speaker: Optional[str] = None):
    """Retrieves memories for a specific speaker or all."""
    if speaker:
        return memory_engine.get_memories_for_speaker(speaker)
    return memory_engine.get_all_memories()

@router.post("/api/brain/memories")
async def create_memory(req: MemoryCreateRequest):
    """Manually creates or updates a memory in SQLite."""
    ok = memory_engine.store_memory(req.speaker_name, req.key, req.value, req.category)
    return {"status": "success" if ok else "error"}

@router.delete("/api/brain/memories/{memory_id}")
async def delete_memory_endpoint(memory_id: int):
    """Deletes a memory by ID."""
    ok = memory_engine.delete_memory_by_id(memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "success", "deleted_id": memory_id}

@router.get("/api/brain/notes")
async def get_notes(category: Optional[str] = None, speaker: Optional[str] = None):
    """Retrieves notes and to-do lists."""
    return memory_engine.get_notes_and_todos(category=category, speaker_name=speaker)

@router.post("/api/brain/notes")
async def create_note(req: NoteCreateRequest):
    """Creates a new note or to-do task."""
    nid = memory_engine.create_note_or_todo(
        title=req.title,
        content=req.content,
        category=req.category,
        due_date=req.due_date,
        speaker_name=req.speaker_name
    )
    return {"status": "success", "note_id": nid}

@router.patch("/api/brain/notes/{note_id}/toggle")
async def toggle_note_todo(note_id: int):
    """Toggles to-do item completed state."""
    ok = memory_engine.toggle_note_completion(note_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"status": "success", "note_id": note_id}

@router.delete("/api/brain/notes/{note_id}")
async def delete_note_endpoint(note_id: int):
    """Deletes a note or to-do item."""
    ok = memory_engine.delete_note(note_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"status": "success", "deleted_id": note_id}

@router.get("/api/brain/conversations")
async def get_conversations(limit: int = 25, speaker: Optional[str] = None):
    """Retrieves episodic conversation logs."""
    return memory_engine.get_recent_conversations(limit=limit, speaker_name=speaker)

@router.delete("/api/brain/conversations")
async def clear_conversations_endpoint():
    """Clears all conversation logs."""
    memory_engine.clear_conversations()
    return {"status": "success"}

@router.delete("/api/brain/conversations/{conversation_id}")
async def delete_conversation_endpoint(conversation_id: int):
    """Deletes a single conversation log entry."""
    ok = memory_engine.delete_conversation_by_id(conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation entry not found")
    return {"status": "success", "deleted_id": conversation_id}

@router.get("/api/brain/speakers")
async def get_speakers():
    """Returns registered speakers and voice biometric profiles."""
    return memory_engine.get_all_speakers()

@router.post("/api/brain/speakers")
async def create_speaker_endpoint(req: SpeakerCreateRequest):
    """Creates a new speaker profile in SQLite."""
    ok = memory_engine.enroll_or_update_speaker(req.name)
    return {"status": "success" if ok else "error", "name": req.name}

@router.post("/api/brain/speakers/{speaker_name}/calibrate")
async def calibrate_speaker_endpoint(speaker_name: str, req: SpeakerCalibrateRequest):
    """Calibrates voice biometrics for a speaker profile from base64 audio."""
    try:
        audio_bytes = base64.b64decode(req.audio_base64)
        res = memory_engine.calibrate_speaker_voice(speaker_name, audio_bytes)
        return {"status": "success", "data": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/api/brain/speakers/{speaker_name}")
async def delete_speaker_endpoint(speaker_name: str):
    """Deletes a speaker and all associated data."""
    ok = memory_engine.delete_speaker(speaker_name)
    return {"status": "success" if ok else "error"}

@router.get("/api/brain/projects")
async def get_projects(speaker_name: Optional[str] = None):
    """Retrieves personal projects for a speaker."""
    return memory_engine.get_projects_for_speaker(speaker_name)

@router.post("/api/brain/projects")
async def create_project_endpoint(req: ProjectCreateRequest):
    """Creates or updates a personal project for a speaker."""
    pid = memory_engine.save_project(
        speaker_name=req.speaker_name,
        name=req.name,
        tech_stack=req.tech_stack,
        goal=req.goal,
        status=req.status,
        notes=req.notes
    )
    return {"status": "success", "id": pid}

@router.delete("/api/brain/projects/{project_id}")
async def delete_project_endpoint(project_id: int):
    """Deletes a project by its ID."""
    ok = memory_engine.delete_project(project_id)
    return {"status": "success" if ok else "error"}

@router.get("/api/brain/semantic-search")
async def semantic_search_endpoint(query: str, speaker_name: Optional[str] = None, limit: int = 6):
    """JARVIS 2.0 Semantic Memory RAG search endpoint."""
    return memory_engine.semantic_search_brain(query, speaker_name=speaker_name, top_k=limit)

@router.get("/api/brain/animations")
async def get_animations_endpoint():
    """Returns all registered 3D animation & behavior profiles."""
    return memory_engine.get_all_animations()

@router.post("/api/brain/animations")
async def upsert_animation_endpoint(req: AnimationUpsertRequest):
    """Creates or updates a 3D animation/behavior profile."""
    ok = memory_engine.upsert_animation(
        name=req.name,
        category=req.category,
        emotion=req.emotion,
        gesture=req.gesture,
        intensity=req.intensity,
        duration_sec=req.duration_sec,
        keywords=req.keywords
    )
    return {"status": "success" if ok else "error"}

@router.delete("/api/brain/animations/{animation_name}")
async def delete_animation_endpoint(animation_name: str):
    """Deletes an animation profile from the database."""
    ok = memory_engine.delete_animation(animation_name)
    return {"status": "success" if ok else "error"}

@router.get("/api/brain/system-status")
async def get_system_status():
    """JARVIS Core telemetry stats."""
    db_stat = memory_engine.get_brain_stats()
    k_preview = None
    cur_k = key_manager.get_active_key()
    if cur_k:
        k_preview = cur_k[:8] + "..." + cur_k[-4:]
    return {
        "core_status": "OPTIMAL",
        "ai_model": os.getenv("GEMINI_MODEL", "gemini-3.1-flash-live-preview"),
        "key_pool_total": key_manager.total_keys,
        "active_key_preview": k_preview,
        "memory_nodes": db_stat.get("memories_count", 0),
        "notes_count": db_stat.get("notes_count", 0),
        "conversations_logged": db_stat.get("conversations_count", 0),
        "active_websocket_sessions": len(active_sessions),
        "db_size_kb": round(db_stat.get("db_size_bytes", 0) / 1024, 1),
    }

class FileMemoryUpdateRequest(BaseModel):
    file_type: str  # 'user' or 'memory'
    content: str

@router.get("/api/brain/file-memory")
async def get_file_memory_endpoint():
    """Returns the 4-file persistent memory snapshots (SOUL, USER, MEMORY)."""
    from memory.file_memory import file_memory
    return {
        "soul": file_memory.get_soul_content(),
        "user": file_memory.get_user_profile(),
        "memory": file_memory.get_memory_facts(),
    }

@router.post("/api/brain/file-memory")
async def update_file_memory_endpoint(req: FileMemoryUpdateRequest):
    """Updates USER.md or MEMORY.md with sanitized content."""
    from memory.file_memory import file_memory, filter_sensitive_data, USER_FILE_PATH, MEMORY_FILE_PATH
    clean_content = filter_sensitive_data(req.content)
    if req.file_type == "user":
        ok = file_memory._write_file_safe(USER_FILE_PATH, clean_content)
    elif req.file_type == "memory":
        ok = file_memory._write_file_safe(MEMORY_FILE_PATH, clean_content)
    else:
        raise HTTPException(status_code=400, detail="Invalid file_type (must be 'user' or 'memory')")
    return {"status": "success" if ok else "error"}

@router.get("/api/brain/skills/v2")
async def list_skills_v2_endpoint(status: Optional[str] = None):
    """Returns all folder-based skills in agentskills.io format."""
    from core.skill_library import skill_library
    return skill_library.list_skills(status_filter=status)

@router.post("/api/brain/skills/v2/{slug}/approve")
async def approve_skill_v2_endpoint(slug: str):
    """Approves a pending skill into active status."""
    from core.skill_library import skill_library
    ok = skill_library.approve_skill(slug)
    return {"status": "success" if ok else "error"}

@router.delete("/api/brain/skills/v2/{slug}")
async def delete_skill_v2_endpoint(slug: str):
    """Deletes or rejects a skill folder."""
    from core.skill_library import skill_library
    ok = skill_library.reject_skill(slug, delete_folder=True)
    return {"status": "success" if ok else "error"}
