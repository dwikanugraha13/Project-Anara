"""
Agent Workspace, File Management, Terminal Shell, Git, Skills, and Soul Routes for Project Anara.
"""
import asyncio
import base64
import json
import logging
import os
import re
import subprocess
import tempfile
from typing import Optional, List, Dict, Any, Union

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from memory import memory_engine
from core import anara_agent, subagent_manager
from cognition import get_soul_raw, save_soul_raw, _find_soul_file
from tools import get_tools_catalog
from shared_state import broadcast_agent_event

logger = logging.getLogger("anara.routers.workspace")

router = APIRouter(tags=["Agent Workspace"])

class FolderImportRequest(BaseModel):
    folder_path: str
    session_id: Optional[Union[int, str]] = None

class InitEmptyWorkspaceRequest(BaseModel):
    folder_name: str
    session_id: Optional[Union[int, str]] = None

class SaveWorkspaceFileRequest(BaseModel):
    path: str
    content: str
    session_id: Optional[Union[int, str]] = None

class TerminalExecRequest(BaseModel):
    command: str
    session_id: Optional[Union[int, str]] = None
    workdir: Optional[str] = None

class CheckpointRevertRequest(BaseModel):
    checkpoint_id: str
    session_id: Optional[Union[int, str]] = None

class SkillAddRequest(BaseModel):
    name: str
    category: str
    description: str
    trigger_keywords: List[str] = Field(default_factory=list)
    procedure_steps: List[str] = Field(default_factory=list)

class SoulUpdateRequest(BaseModel):
    content: str

# ── File & Folder Imports ──

@router.post("/api/agent/pick-local-folder")
async def pick_local_folder_endpoint(req: FolderImportRequest):
    """Opens the native Windows folder picker and attaches the selected real folder to a chat session."""
    folder_path = req.folder_path
    if not folder_path:
        def _pick_sync() -> str:
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.wm_attributes("-topmost", 1)
                path = filedialog.askdirectory(title="Select Project Folder for Anara Agent")
                root.destroy()
                return path or ""
            except Exception as e:
                logger.warning(f"[Workspace Folder Picker] Tkinter dialog error: {e}")
                return ""

        folder_path = await asyncio.to_thread(_pick_sync)

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
    session_id: Optional[Union[int, str]] = Form(None)
):
    """Uploads a file into Anara Agent Workspace."""
    content = await file.read()
    try:
        res = anara_agent.save_uploaded_file(file.filename, content, relative_path=relative_path, session_id=session_id)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/api/agent/upload-folder")
async def upload_agent_folder(
    files: List[UploadFile] = File(...),
    paths: Optional[str] = Form(None),
    session_id: Optional[Union[int, str]] = Form(None)
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
        try:
            anara_agent.save_uploaded_file(file.filename, content, relative_path=rel_p, session_id=session_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    tree = anara_agent.get_workspace_tree_shallow(session_id=session_id)
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
async def get_agent_workspace_tree(session_id: Optional[Union[int, str]] = None):
    """Returns workspace metadata + shallow root listing (Native Dynamic: lazy tree, 1 level per request).
    Frontend expands folders on demand via /api/agent/workspace/tree/children?path=...
    """
    return await asyncio.to_thread(anara_agent.get_workspace_tree_shallow, session_id=session_id)

@router.get("/api/agent/workspace/tree/children")
async def get_agent_workspace_tree_children(path: str, session_id: Optional[Union[int, str]] = None):
    """Returns children of a single directory (lazy expand on user click — Anara Parity)."""
    return await asyncio.to_thread(anara_agent.get_workspace_dir_children, dir_path=path, session_id=session_id)

@router.get("/api/agent/workspace/file-content")
@router.get("/api/agent/workspace/file")
async def get_agent_workspace_file_content(path: str, session_id: Optional[Union[int, str]] = None):
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

    # Sandbox Path Confinement & Credentials Exfiltration Guard (Anara Standard)
    from core.workspace_sentinel import workspace_sentinel
    is_safe, denial_reason = workspace_sentinel.validate_file_access(full_p, action="read", workspace_root=target_dir)
    if not is_safe:
        raise HTTPException(status_code=403, detail=f"Access denied: {denial_reason}")

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

    # Sandbox Path Confinement & Sacred Files Protection (Anara Standard)
    from core.workspace_sentinel import workspace_sentinel
    is_safe, denial_reason = workspace_sentinel.validate_file_access(full_p, action="write", workspace_root=target_dir)
    if not is_safe:
        raise HTTPException(status_code=403, detail=f"Access denied: {denial_reason}")

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
        "message": f"File '{filename}' saved successfully."
    }

@router.delete("/api/agent/workspace/file")
async def delete_agent_workspace_file(path: str, session_id: Optional[Union[int, str]] = None):
    """Deletes a file or directory safely from the active workspace."""
    target_dir = anara_agent.get_session_dir(session_id)
    clean_p = path.lstrip("/\\")
    full_p = os.path.join(target_dir, clean_p)
    if not os.path.exists(full_p):
        candidates = [clean_p, os.path.expanduser(clean_p)]
        for c in candidates:
            if c and os.path.exists(c):
                full_p = c
                break

    if not os.path.exists(full_p):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    from core.workspace_sentinel import workspace_sentinel
    is_safe, denial_reason = workspace_sentinel.validate_file_access(full_p, action="delete", workspace_root=target_dir)
    if not is_safe:
        raise HTTPException(status_code=403, detail=f"Access denied: {denial_reason}")

    try:
        if os.path.isdir(full_p):
            import shutil
            shutil.rmtree(full_p)
        else:
            os.remove(full_p)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {e}")

    filename = os.path.basename(full_p)
    broadcast_agent_event({
        "type": "workspace_file_deleted",
        "file_path": full_p,
        "filename": filename,
        "session_id": session_id
    })

    return {
        "status": "success",
        "filename": filename,
        "path": clean_p,
        "message": f"'{filename}' deleted successfully."
    }

@router.delete("/api/agent/workspace")
async def clear_agent_workspace(session_id: Optional[Union[int, str]] = None):
    """Resets and clears the active workspace for a specific session."""
    anara_agent.clear_workspace(session_id=session_id)
    broadcast_agent_event({"type": "workspace_updated", "session_id": session_id, "cleared": True})
    return {"status": "success", "message": "Workspace cleared", "session_id": session_id}

# ── Terminal Command Execution ──

@router.post("/api/agent/terminal/execute")
async def execute_terminal_command_endpoint(req: TerminalExecRequest):
    """Executes a real terminal shell command in the active workspace directory."""
    active_f = anara_agent.get_session_dir(req.session_id)
    cwd = os.path.abspath(os.path.expanduser(req.workdir)) if req.workdir else active_f
    user_home = os.path.expanduser("~")
    if not cwd or not os.path.exists(cwd):
        cwd = user_home

    cmd = (req.command or "").strip()
    if not cmd:
        return {"status": "error", "message": "Command is empty"}

    # Sandbox Security & Host-Takeover Defense (Anara Standard)
    from core.sandbox import CommandSandbox
    is_safe, denial_reason = CommandSandbox.check_command_safety(cmd)
    if not is_safe:
        return {"status": "error", "message": denial_reason or "Execution blocked by Anara Sandbox."}

    try:
        if os.name == "nt":
            encoded_bytes = f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;\n{cmd}".encode("utf-16le")
            encoded_cmd = base64.b64encode(encoded_bytes).decode("ascii")
            ps_cmd = [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-EncodedCommand",
                encoded_cmd
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
        return {"status": "error", "returncode": -1, "stdout": "", "stderr": "Command timed out (60s)."}
    except Exception as e:
        return {"status": "error", "returncode": -1, "stdout": "", "stderr": str(e) or type(e).__name__}

@router.post("/api/agent/terminal/stream")
async def stream_terminal_command_endpoint(req: TerminalExecRequest):
    """Streams terminal command execution line-by-line via Server-Sent Events (SSE)."""
    active_f = anara_agent.get_session_dir(req.session_id)
    cwd = os.path.abspath(os.path.expanduser(req.workdir)) if req.workdir else active_f
    user_home = os.path.expanduser("~")
    if not cwd or not os.path.exists(cwd):
        cwd = user_home

    cmd = (req.command or "").strip()
    if not cmd:
        async def empty_stream():
            yield "data: " + json.dumps({"error": "Command is empty"}) + "\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    # Sandbox Security & Host-Takeover Defense (Anara Standard)
    from core.sandbox import CommandSandbox
    is_safe, denial_reason = CommandSandbox.check_command_safety(cmd)
    if not is_safe:
        async def blocked_stream():
            yield "data: " + json.dumps({"error": denial_reason or "Execution blocked by Anara Sandbox."}) + "\n\n"
        return StreamingResponse(blocked_stream(), media_type="text/event-stream")

    async def sse_runner():
        proc = None
        try:
            if os.name == "nt":
                encoded_bytes = f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;\n{cmd}".encode("utf-16le")
                encoded_cmd = base64.b64encode(encoded_bytes).decode("ascii")
                ps_cmd = [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy", "Bypass",
                    "-EncodedCommand",
                    encoded_cmd
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
                line_str = line_bytes.decode("utf-8", errors="replace").strip()
                yield f"data: {json.dumps({'line': line_str})}\n\n"

            await proc.wait()
            yield f"data: {json.dumps({'done': True, 'returncode': proc.returncode})}\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            if proc and proc.returncode is None:
                try:
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=5)
                    else:
                        proc.kill()
                    await proc.wait()
                except Exception:
                    pass
            raise
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            if proc and proc.returncode is None:
                try:
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=5)
                    else:
                        proc.kill()
                    await proc.wait()
                except Exception:
                    pass

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
    def _rollback():
        return anara_agent.rollback_checkpoint(req.checkpoint_id, req.session_id)
    ok = await asyncio.to_thread(_rollback)
    if not ok:
        raise HTTPException(status_code=404, detail="Checkpoint not found or failed to restore.")
    broadcast_agent_event({"type": "workspace_updated", "session_id": req.session_id})
    return {"status": "success", "message": f"Workspace restored from checkpoint {req.checkpoint_id}."}

# ── Git Integration ──

@router.get("/api/agent/git/status")
async def get_agent_git_status(session_id: Optional[Union[int, str]] = None):
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
async def init_agent_git_repo(session_id: Optional[Union[int, str]] = None):
    """Initializes a git repository strictly within the active workspace folder."""
    ok = anara_agent.ensure_git_repo(session_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to initialize git repository in project directory.")
    status = await get_agent_git_status(session_id)
    return {"status": "success", "git": status}

class GitRollbackRequest(BaseModel):
    commit_sha: str
    session_id: Optional[Union[int, str]] = None

@router.post("/api/agent/git/rollback")
async def rollback_agent_git_commit(req: GitRollbackRequest):
    """Rolls back or reverts a specific git commit in the project workspace (FR-18)."""
    def _rollback_git():
        return anara_agent.rollback_git_commit(req.commit_sha, req.session_id)
    ok = await asyncio.to_thread(_rollback_git)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Failed to rollback commit '{req.commit_sha}'.")
    broadcast_agent_event({"type": "workspace_updated", "session_id": req.session_id})
    status = await get_agent_git_status(req.session_id)
    return {"status": "success", "message": f"Rollback commit {req.commit_sha} completed successfully.", "git": status}

class GitFileActionRequest(BaseModel):
    path: Optional[str] = None  # None indicates all files
    session_id: Optional[Union[int, str]] = None

class GitCommitRequest(BaseModel):
    message: str
    push: bool = False
    session_id: Optional[Union[int, str]] = None

@router.post("/api/agent/git/stage")
async def stage_agent_git_file(req: GitFileActionRequest):
    """Stages specific or all files into git staging index (Anara Desktop Standard)."""
    sid = req.session_id if req.session_id is not None else anara_agent.get_active_session_id()
    repo_dir = anara_agent.get_session_dir(sid) if sid is not None else anara_agent.default_workspace_dir
    cmd = f'git add "{req.path}"' if req.path else 'git add -A'
    p = await asyncio.create_subprocess_shell(cmd, cwd=repo_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await p.communicate()
    if p.returncode != 0:
        raise HTTPException(status_code=400, detail=stderr.decode().strip() or "Failed to stage file.")
    status = await get_agent_git_status(sid)
    return {"status": "success", "git": status}

@router.post("/api/agent/git/unstage")
async def unstage_agent_git_file(req: GitFileActionRequest):
    """Unstages specific or all files from git staging index (Anara Desktop Standard)."""
    sid = req.session_id if req.session_id is not None else anara_agent.get_active_session_id()
    repo_dir = anara_agent.get_session_dir(sid) if sid is not None else anara_agent.default_workspace_dir
    cmd = f'git restore --staged "{req.path}"' if req.path else 'git restore --staged .'
    p = await asyncio.create_subprocess_shell(cmd, cwd=repo_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await p.communicate()
    status = await get_agent_git_status(sid)
    return {"status": "success", "git": status}

@router.post("/api/agent/git/revert")
async def revert_agent_git_file(req: GitFileActionRequest):
    """Reverts working tree modifications for specific or all files with safety guard."""
    sid = req.session_id if req.session_id is not None else anara_agent.get_active_session_id()
    repo_dir = anara_agent.get_session_dir(sid) if sid is not None else anara_agent.default_workspace_dir
    if req.path:
        cmd = f'git restore "{req.path}"'
        p = await asyncio.create_subprocess_shell(cmd, cwd=repo_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await p.communicate()
        if p.returncode != 0:
            cmd_fallback = f'git checkout -- "{req.path}"'
            p2 = await asyncio.create_subprocess_shell(cmd_fallback, cwd=repo_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await p2.communicate()
    else:
        cmd = 'git restore .'
        p = await asyncio.create_subprocess_shell(cmd, cwd=repo_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await p.communicate()
    status = await get_agent_git_status(sid)
    return {"status": "success", "git": status}

@router.post("/api/agent/git/commit")
async def commit_agent_git_changes(req: GitCommitRequest):
    """Commits staged changes with optional push and returns commit SHA (Anara Desktop Standard)."""
    sid = req.session_id if req.session_id is not None else anara_agent.get_active_session_id()
    repo_dir = anara_agent.get_session_dir(sid) if sid is not None else anara_agent.default_workspace_dir
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Commit message cannot be empty.")
    safe_msg = req.message.replace('"', '\\"')
    cmd = f'git commit -m "{safe_msg}"'
    p = await asyncio.create_subprocess_shell(cmd, cwd=repo_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await p.communicate()
    if p.returncode != 0:
        raise HTTPException(status_code=400, detail=stderr.decode().strip() or "Failed to commit changes.")
    p_sha = await asyncio.create_subprocess_shell("git rev-parse --short HEAD", cwd=repo_dir, stdout=asyncio.subprocess.PIPE)
    sha_out, _ = await p_sha.communicate()
    commit_sha = sha_out.decode().strip()

    pushed = False
    if req.push:
        p_push = await asyncio.create_subprocess_shell("git push", cwd=repo_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await p_push.communicate()
        pushed = p_push.returncode == 0

    status = await get_agent_git_status(sid)
    return {"status": "success", "commit_sha": commit_sha, "pushed": pushed, "git": status}

@router.get("/api/agent/git/file-diff")
async def get_agent_git_file_diff(path: str, session_id: Optional[Union[int, str]] = None):
    """Retrieves unified git diff for a specific file (Anara Desktop Standard)."""
    sid = session_id if session_id is not None else anara_agent.get_active_session_id()
    repo_dir = anara_agent.get_session_dir(sid) if sid is not None else anara_agent.default_workspace_dir
    cmd = f'git diff HEAD -- "{path}"'
    p = await asyncio.create_subprocess_shell(cmd, cwd=repo_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, _ = await p.communicate()
    diff_text = out.decode("utf-8", errors="replace")
    if not diff_text:
        # Check staged diff
        cmd_staged = f'git diff --staged -- "{path}"'
        p_s = await asyncio.create_subprocess_shell(cmd_staged, cwd=repo_dir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out_s, _ = await p_s.communicate()
        diff_text = out_s.decode("utf-8", errors="replace")
    return {"path": path, "diff": diff_text}

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
    """Returns all Anara autonomous agent skills."""
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
    # Mirror into folder-based skill_library (SKILL.md)
    try:
        from core.skill_library import skill_library
        skill_library.save_skill(
            name=req.name,
            category=req.category,
            description=req.description,
            procedure_steps=req.procedure_steps,
            trigger_keywords=req.trigger_keywords,
            status="active",
            learned=False,
        )
    except Exception as e:
        logger.warning(f"[SkillSync] Failed to mirror skill to disk: {e}")

    return {"status": "success", "skill_id": sid}

@router.patch("/api/agent/skills/{skill_id}/toggle")
async def toggle_skill_endpoint(skill_id: int):
    """Toggles active/inactive status of a skill."""
    ok = memory_engine.toggle_agent_skill(skill_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"status": "success", "skill_id": skill_id}

@router.delete("/api/agent/skills/{skill_id}")
async def delete_skill_endpoint(skill_id: int):
    """Deletes a skill from Anara Agent's brain."""
    # Find skill name to remove folder as well
    skills = memory_engine.get_all_agent_skills()
    target_skill = next((s for s in skills if s.get("id") == skill_id), None)
    ok = memory_engine.delete_agent_skill(skill_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Skill not found")
    if target_skill and target_skill.get("name"):
        try:
            from core.skill_library import skill_library, slugify
            slug = slugify(target_skill["name"])
            skill_library.reject_skill(slug, delete_folder=True)
        except Exception as e:
            logger.warning(f"[SkillSync] Failed to remove skill folder: {e}")
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
        raise HTTPException(status_code=400, detail="soul.md content cannot be empty")
    ok = save_soul_raw(req.content)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save soul.md to disk")
    return {"status": "success", "message": "Soul of Anara updated and reloaded successfully."}

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
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success"}

@router.post("/api/agent/autonomous/tasks/{task_id}/trigger")
async def trigger_autonomous_task_endpoint(task_id: str):
    """Manually triggers an autonomous task immediately."""
    from core.autonomous_engine import autonomous_engine
    res = await autonomous_engine.trigger_task_now(task_id)
    return {"status": "success", "result": res}

@router.post("/api/agent/autonomous/tasks/{task_id}/pause")
async def pause_autonomous_task_endpoint(task_id: str):
    """Pauses a scheduled autonomous task."""
    from core.autonomous_engine import autonomous_engine
    ok = autonomous_engine.pause_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success"}

@router.post("/api/agent/autonomous/tasks/{task_id}/resume")
async def resume_autonomous_task_endpoint(task_id: str):
    """Resumes a paused autonomous task."""
    from core.autonomous_engine import autonomous_engine
    ok = autonomous_engine.resume_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success"}
