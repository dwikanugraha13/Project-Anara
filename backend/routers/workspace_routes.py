"""
Agent Workspace, File Management, Terminal Shell, Git, Skills, and Soul Routes for Project Anara.
"""
import asyncio
import json
import logging
import os
import re
import subprocess
import tempfile
import time as _time
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from memory import memory_engine
from core import anara_agent, subagent_manager
from cognition import get_soul_raw, save_soul_raw, _find_soul_file
from tools import get_tools_catalog
from shared_state import broadcast_agent_event

logger = logging.getLogger("anara.routers.workspace")

router = APIRouter(tags=["Agent Workspace"])

class FolderImportRequest(BaseModel):
    folder_path: str
    session_id: Optional[int] = None

class InitEmptyWorkspaceRequest(BaseModel):
    folder_name: str
    session_id: Optional[int] = None

class SaveWorkspaceFileRequest(BaseModel):
    path: str
    content: str
    session_id: Optional[int] = None

class TerminalExecRequest(BaseModel):
    command: str
    session_id: Optional[int] = None
    workdir: Optional[str] = None

class CheckpointRevertRequest(BaseModel):
    checkpoint_id: str
    session_id: Optional[int] = None

class SkillAddRequest(BaseModel):
    name: str
    category: str
    description: str
    trigger_keywords: List[str] = []
    procedure_steps: List[str] = []

class SoulUpdateRequest(BaseModel):
    content: str

# ── File & Folder Imports ──

@router.post("/api/agent/pick-local-folder")
async def pick_local_folder_endpoint(req: FolderImportRequest):
    """Opens the native Windows folder picker and attaches the selected real folder to a chat session."""
    import tkinter as tk
    from tkinter import filedialog

    folder_path = req.folder_path
    if not folder_path:
        try:
            root = tk.Tk()
            root.withdraw()
            root.wm_attributes("-topmost", 1)
            folder_path = filedialog.askdirectory(title="Pilih Folder Project untuk Anara Agent")
            root.destroy()
        except Exception as e:
            logger.warning(f"[Workspace Folder Picker] Tkinter dialog error: {e}")

    if not folder_path:
        return {"status": "cancelled"}
    try:
        session_id = req.session_id
        if session_id is None:
            session_id = anara_agent.get_active_session_id()
        if session_id is None:
            last_sid = memory_engine.get_last_active_session_id()
            if last_sid:
                session_id = last_sid
            else:
                new_s = memory_engine.create_session(title=os.path.basename(folder_path.rstrip("\\/")) or "Project Workspace")
                session_id = new_s["id"]
        anara_agent.set_active_session_id(session_id)

        tree = anara_agent.attach_local_folder(folder_path, session_id)
        return {"status": "success", "session_id": session_id, "tree": tree}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/api/agent/upload")
async def upload_agent_file(
    file: UploadFile = File(...),
    relative_path: Optional[str] = Form(None),
    session_id: Optional[int] = Form(None)
):
    """Uploads a file into Anara Agent Workspace."""
    content = await file.read()
    res = anara_agent.save_uploaded_file(file.filename, content, relative_path=relative_path, session_id=session_id)
    return res

@router.post("/api/agent/upload-folder")
async def upload_agent_folder(
    files: List[UploadFile] = File(...),
    paths: Optional[str] = Form(None),
    session_id: Optional[int] = Form(None)
):
    """Uploads an entire multi-file project directory into Anara Agent Workspace."""
    path_list = []
    if paths:
        try:
            path_list = json.loads(paths)
        except Exception:
            path_list = []

    root_name = "Project Workspace"
    if path_list and "/" in path_list[0]:
        root_name = path_list[0].split("/")[0]
        anara_agent.set_custom_folder_name(root_name, session_id=session_id)

    for i, file in enumerate(files):
        rel_p = path_list[i] if i < len(path_list) else file.filename
        content = await file.read()
        anara_agent.save_uploaded_file(file.filename, content, relative_path=rel_p, session_id=session_id)

    tree = anara_agent.get_workspace_tree(session_id=session_id)
    if session_id is not None:
        try:
            memory_engine.set_session_workspace_info(session_id, {
                "name": tree.get("workspace_name", root_name),
                "total_files": tree.get("total_files", len(files)),
                "root_path": tree.get("root_path", "")
            })
        except Exception as e:
            logger.warning(f"[Workspace] Failed to persist workspace for session #{session_id}: {e}")

    broadcast_agent_event({
        "type": "workspace_folder_imported",
        "session_id": session_id,
        "folder_name": tree.get("workspace_name", root_name),
        "total_files": tree.get("total_files", len(files)),
        "tree": tree
    })
    return {"status": "success", "tree": tree}

@router.post("/api/agent/init-empty-workspace")
async def init_empty_workspace_endpoint(req: InitEmptyWorkspaceRequest):
    """Initializes an empty project folder workspace."""
    tree = anara_agent.init_empty_workspace(req.folder_name, session_id=req.session_id)
    return {"status": "success", "tree": tree}

# ── Workspace Tree & File Inspection/Saving ──

@router.get("/api/agent/workspace/tree")
async def get_agent_workspace_tree(session_id: Optional[int] = None):
    """Returns the current file tree of the Anara Agent workspace."""
    return anara_agent.get_workspace_tree(session_id=session_id)

@router.get("/api/agent/workspace/file-content")
@router.get("/api/agent/workspace/file")
async def get_agent_workspace_file_content(path: str, session_id: Optional[int] = None):
    """Returns raw file content for integrated IDE editor."""
    target_dir = anara_agent.get_session_dir(session_id)
    clean_p = path.lstrip("/\\")
    full_p = os.path.join(target_dir, clean_p)
    if not os.path.exists(full_p) or not os.path.isfile(full_p):
        candidates = [clean_p, os.path.expanduser(clean_p)]
        for c in candidates:
            if c and os.path.exists(c) and os.path.isfile(c):
                full_p = c
                break

    if not os.path.exists(full_p) or not os.path.isfile(full_p):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    ext = os.path.splitext(full_p)[1].lstrip(".").lower()
    try:
        with open(full_p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {e}")

    return {
        "status": "success",
        "filename": os.path.basename(full_p),
        "path": clean_p,
        "ext": ext,
        "size_kb": round(os.path.getsize(full_p) / 1024, 1),
        "content": content
    }

@router.post("/api/agent/workspace/save-file")
async def save_agent_workspace_file(req: SaveWorkspaceFileRequest):
    """Saves user-edited code directly to disk and broadcasts updates."""
    target_dir = anara_agent.get_session_dir(req.session_id)
    clean_p = req.path.lstrip("/\\")
    full_p = os.path.join(target_dir, clean_p)
    if not os.path.exists(full_p) or not os.path.isfile(full_p):
        candidates = [clean_p, os.path.expanduser(clean_p)]
        for c in candidates:
            if c and os.path.exists(c) and os.path.isfile(c):
                full_p = c
                break

    os.makedirs(os.path.dirname(full_p), exist_ok=True)
    try:
        with open(full_p, "w", encoding="utf-8") as f:
            f.write(req.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error writing file: {e}")

    filename = os.path.basename(full_p)
    ext = os.path.splitext(full_p)[1].lstrip(".").lower()
    size_kb = round(os.path.getsize(full_p) / 1024, 1)

    broadcast_agent_event({
        "type": "workspace_file_created",
        "file_path": full_p,
        "filename": filename,
        "file_ext": ext,
        "content": req.content,
        "size_kb": size_kb
    })

    return {
        "status": "success",
        "filename": filename,
        "path": clean_p,
        "size_kb": size_kb,
        "message": f"Berkas '{filename}' berhasil disimpan."
    }

@router.delete("/api/agent/workspace")
async def clear_agent_workspace(session_id: Optional[int] = None):
    """Resets and clears the active workspace for a specific session."""
    anara_agent.clear_workspace(session_id=session_id)
    broadcast_agent_event({"type": "workspace_updated", "session_id": session_id, "cleared": True})
    return {"status": "success", "message": "Workspace dibersihkan", "session_id": session_id}

# ── Terminal Command Execution ──

@router.post("/api/agent/terminal/execute")
async def execute_terminal_command_endpoint(req: TerminalExecRequest):
    """Executes a real terminal shell command in the active workspace directory."""
    active_f = anara_agent.get_session_dir(req.session_id)
    cwd = os.path.abspath(os.path.expanduser(req.workdir)) if req.workdir else active_f
    if not os.path.exists(cwd):
        cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    cmd = (req.command or "").strip()
    if not cmd:
        return {"status": "error", "message": "Command is empty"}

    try:
        if os.name == "nt":
            ps_cmd = [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-Command",
                f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {cmd}"
            ]
            use_shell = False
        else:
            ps_cmd = cmd
            use_shell = True

        def _run_terminal_sync():
            return subprocess.run(
                ps_cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60.0,
                shell=use_shell
            )

        completed_proc = await asyncio.to_thread(_run_terminal_sync)
        out_text = (completed_proc.stdout or "").strip()
        err_text = (completed_proc.stderr or "").strip()

        return {
            "status": "success" if completed_proc.returncode == 0 else "error",
            "returncode": completed_proc.returncode,
            "stdout": out_text,
            "stderr": err_text,
            "cwd": cwd
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "returncode": -1, "stdout": "", "stderr": "Perintah melampaui batas waktu (60s)."}
    except Exception as e:
        return {"status": "error", "returncode": -1, "stdout": "", "stderr": str(e) or type(e).__name__}

@router.post("/api/agent/terminal/stream")
async def stream_terminal_command_endpoint(req: TerminalExecRequest):
    """Streams terminal command execution line-by-line via Server-Sent Events (SSE)."""
    active_f = anara_agent.get_session_dir(req.session_id)
    cwd = os.path.abspath(os.path.expanduser(req.workdir)) if req.workdir else active_f
    if not os.path.exists(cwd):
        cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    cmd = (req.command or "").strip()
    if not cmd:
        async def empty_stream():
            yield "data: " + json.dumps({"error": "Perintah kosong"}) + "\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    async def sse_runner():
        try:
            if os.name == "nt":
                ps_cmd = [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy", "Bypass",
                    "-Command",
                    f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {cmd}"
                ]
                proc = await asyncio.create_subprocess_exec(
                    *ps_cmd,
                    cwd=cwd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )
            else:
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    cwd=cwd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )
            while True:
                line_bytes = await proc.stdout.readline()
                if not line_bytes:
                    break
                line_str = line_bytes.decode("utf-8", errors="replace").rstrip("\r\n")
                yield f"data: {json.dumps({'line': line_str})}\n\n"

            await proc.wait()
            yield f"data: {json.dumps({'done': True, 'returncode': proc.returncode})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        sse_runner(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# ── Workspace Checkpoints ──

@router.post("/api/agent/checkpoint/revert")
async def revert_checkpoint_endpoint(req: CheckpointRevertRequest):
    """Restores workspace files to a snapshot backup."""
    ok = anara_agent.rollback_checkpoint(req.checkpoint_id, req.session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Checkpoint tidak ditemukan atau gagal dipulihkan.")
    broadcast_agent_event({"type": "workspace_updated", "session_id": req.session_id})
    return {"status": "success", "message": f"Ruang kerja berhasil dipulihkan dari checkpoint {req.checkpoint_id}."}

# ── Git Integration ──

@router.get("/api/agent/git/status")
async def get_agent_git_status(session_id: Optional[int] = None):
    """Returns real git status strictly for the active session project workspace."""
    sid = session_id if session_id is not None else anara_agent.get_active_session_id()
    if sid is None:
        return {"is_git": False, "changed_count": 0, "files": []}

    active_f = anara_agent.get_session_dir(sid)
    repo_dir = active_f

    if not os.path.exists(os.path.join(repo_dir, ".git")):
        return {"is_git": False, "changed_count": 0, "files": []}

    try:
        p_br = await asyncio.create_subprocess_shell("git rev-parse --abbrev-ref HEAD", cwd=repo_dir, stdout=asyncio.subprocess.PIPE)
        out_br, _ = await p_br.communicate()
        branch = out_br.decode().strip() or "main"

        p_st = await asyncio.create_subprocess_shell("git status --porcelain", cwd=repo_dir, stdout=asyncio.subprocess.PIPE)
        out_st, _ = await p_st.communicate()
        status_lines = out_st.decode().strip().splitlines()

        p_diff = await asyncio.create_subprocess_shell("git diff --shortstat", cwd=repo_dir, stdout=asyncio.subprocess.PIPE)
        out_diff, _ = await p_diff.communicate()
        diff_str = out_diff.decode().strip()

        insertions = 0
        deletions = 0
        if diff_str:
            m_ins = re.search(r"(\d+)\s+insertion", diff_str)
            m_del = re.search(r"(\d+)\s+deletion", diff_str)
            if m_ins: insertions = int(m_ins.group(1))
            if m_del: deletions = int(m_del.group(1))

        files = []
        for line in status_lines[:30]:
            if len(line) >= 3:
                code = line[:2].strip()
                fpath = line[3:].strip()
                files.append({"path": fpath, "status": code})

        return {
            "is_git": True,
            "branch": branch,
            "changed_count": len(status_lines),
            "insertions": insertions,
            "deletions": deletions,
            "files": files
        }
    except Exception as e:
        return {"is_git": False, "error": str(e), "changed_count": 0, "files": []}

@router.post("/api/agent/git/init")
async def init_agent_git_repo(session_id: Optional[int] = None):
    """Initializes a git repository strictly within the active workspace folder."""
    ok = anara_agent.ensure_git_repo(session_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Gagal menginisialisasi Git di folder proyek.")
    status = await get_agent_git_status(session_id)
    return {"status": "success", "git": status}

class GitRollbackRequest(BaseModel):
    commit_sha: str
    session_id: Optional[int] = None

@router.post("/api/agent/git/rollback")
async def rollback_agent_git_commit(req: GitRollbackRequest):
    """Rolls back or reverts a specific git commit in the project workspace (FR-18)."""
    ok = anara_agent.rollback_git_commit(req.commit_sha, req.session_id)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Gagal melakukan rollback untuk commit '{req.commit_sha}'.")
    broadcast_agent_event({"type": "workspace_updated", "session_id": req.session_id})
    status = await get_agent_git_status(req.session_id)
    return {"status": "success", "message": f"Rollback commit {req.commit_sha} berhasil.", "git": status}

@router.get("/api/agent/artifacts/download/{filename}")
async def download_artifact_endpoint(filename: str):
    """Allows instant 1-click download of generated artifacts."""
    safe_name = os.path.basename(filename)
    candidates = [
        os.path.join(tempfile.gettempdir(), "anara_agent_artifacts", safe_name),
        os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Temp", "anara_agent_artifacts", safe_name),
    ]
    file_path = None
    for c in candidates:
        if os.path.exists(c) and os.path.isfile(c):
            file_path = c
            break
    if not file_path:
        raise HTTPException(status_code=404, detail="File artifact not found")
    return FileResponse(path=file_path, filename=safe_name, media_type="application/octet-stream")

# ── Autonomous Agent Skills ──

@router.get("/api/agent/skills")
async def get_skills_endpoint():
    """Returns all Hermes-Class autonomous agent skills."""
    return memory_engine.get_all_agent_skills()

@router.post("/api/agent/skills")
async def add_skill_endpoint(req: SkillAddRequest):
    """Registers a new skill manually into Anara Agent's brain."""
    sid = memory_engine.add_agent_skill(
        name=req.name,
        category=req.category,
        description=req.description,
        trigger_keywords=req.trigger_keywords,
        procedure_steps=req.procedure_steps,
        learned_from_experience=False
    )
    return {"status": "success", "skill_id": sid}

@router.patch("/api/agent/skills/{skill_id}/toggle")
async def toggle_skill_endpoint(skill_id: int):
    """Toggles active/inactive status of a skill."""
    ok = memory_engine.toggle_agent_skill(skill_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Skill tidak ditemukan")
    return {"status": "success", "skill_id": skill_id}

@router.delete("/api/agent/skills/{skill_id}")
async def delete_skill_endpoint(skill_id: int):
    """Deletes a skill from Anara Agent's brain."""
    ok = memory_engine.delete_agent_skill(skill_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Skill tidak ditemukan")
    return {"status": "success", "skill_id": skill_id}

# ── Agent Persona & Soul System (soul.md) ──

@router.get("/api/agent/soul")
async def get_agent_soul_endpoint():
    """Returns raw soul.md markdown content for in-console editing."""
    raw = get_soul_raw()
    path = _find_soul_file() or "soul.md"
    return {
        "status": "success",
        "file_path": path,
        "content": raw,
        "length": len(raw)
    }

@router.post("/api/agent/soul")
async def update_agent_soul_endpoint(req: SoulUpdateRequest):
    """Updates soul.md directly on disk and hot-reloads memory."""
    if not req.content or not req.content.strip():
        raise HTTPException(status_code=400, detail="Konten soul.md tidak boleh kosong")
    ok = save_soul_raw(req.content)
    if not ok:
        raise HTTPException(status_code=500, detail="Gagal menyimpan soul.md ke disk")
    return {"status": "success", "message": "Soul of Anara berhasil diperbarui & dimuat ulang."}

# ── Tools Catalog & Subagent Tasks ──

@router.get("/api/agent/tools")
async def get_agent_tools_catalog_endpoint():
    """Returns the comprehensive tools catalog with schema and permission info."""
    tools = get_tools_catalog()
    return {"status": "success", "count": len(tools), "tools": tools}

@router.get("/api/agent/subagent/tasks")
async def get_subagent_tasks_endpoint():
    """Returns background worker subagent tasks."""
    tasks = subagent_manager.get_active_tasks()
    return {"status": "success", "count": len(tasks), "tasks": tasks}

# ── Autonomous Task Scheduler (Fase 5) ──

class AutonomousTaskCreateRequest(BaseModel):
    name: str
    prompt: str
    trigger_type: str = "interval"
    interval_seconds: int = 3600
    trust_level: str = "supervised"  # 'supervised' | 'semi_autonomous' | 'full_autonomous'
    target_channel: str = "telegram"
    target_channel_id: Optional[str] = None

@router.get("/api/agent/autonomous/tasks")
async def list_autonomous_tasks_endpoint():
    """Returns all registered autonomous background tasks."""
    from core.autonomous_engine import autonomous_engine
    return {"status": "success", "tasks": autonomous_engine.list_tasks()}

@router.post("/api/agent/autonomous/tasks")
async def create_autonomous_task_endpoint(req: AutonomousTaskCreateRequest):
    """Registers a new autonomous background task."""
    from core.autonomous_engine import autonomous_engine
    res = autonomous_engine.register_task(
        name=req.name,
        prompt=req.prompt,
        trigger_type=req.trigger_type,
        interval_seconds=req.interval_seconds,
        trust_level=req.trust_level,
        target_channel=req.target_channel,
        target_channel_id=req.target_channel_id,
    )
    return {"status": "success", "task": res}

@router.delete("/api/agent/autonomous/tasks/{task_id}")
async def delete_autonomous_task_endpoint(task_id: str):
    """Removes an autonomous task from the scheduler."""
    from core.autonomous_engine import autonomous_engine
    ok = autonomous_engine.delete_task(task_id)
    return {"status": "success" if ok else "error"}

@router.post("/api/agent/autonomous/tasks/{task_id}/trigger")
async def trigger_autonomous_task_endpoint(task_id: str):
    """Manually triggers an autonomous task immediately."""
    from core.autonomous_engine import autonomous_engine
    res = await autonomous_engine.trigger_task_now(task_id)
    return {"status": "success", "result": res}
