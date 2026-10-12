"""
terminal_routes.py — Professional Interactive PTY & Terminal WebSocket Engine for Project Anara.
Native interactive terminal process management for Project Anara:
1. Real-time bidirectional streaming via WebSocket.
2. Direct terminal input (stdin/stdout piping).
3. Multi-instance isolation per terminal tab.
4. Shell selection: PowerShell, Git Bash, Command Prompt.
5. Graceful process cleanup and SIGINT handling.
"""

from __future__ import annotations

import asyncio
import codecs
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("anara.terminal")
router = APIRouter(tags=["Terminal"])

# ConPTY support detection on Windows
HAS_WINPTY = False
if os.name == "nt":
    try:
        from winpty import PtyProcess  # type: ignore
        HAS_WINPTY = True
    except ImportError:
        HAS_WINPTY = False

# Active terminal sessions registry { terminal_id: process_handle }
_active_terminals: Dict[str, Any] = {}

def get_available_shells() -> List[Dict[str, str]]:
    """Detects available terminal shells installed on the system."""
    shells = []
    
    # 1. PowerShell
    pwsh = shutil.which("pwsh.exe") or shutil.which("pwsh")
    if pwsh:
        shells.append({"id": "pwsh", "name": "PowerShell 7", "path": pwsh})
    
    win_ps = shutil.which("powershell.exe") or "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
    if os.path.exists(win_ps):
        shells.append({"id": "powershell", "name": "Windows PowerShell", "path": win_ps})
        
    # 2. Git Bash / MSYS2 Bash (filter out dummy System32 WSL stub)
    bash_candidates = [
        "C:\\Program Files\\Git\\bin\\bash.exe",
        "C:\\Program Files\\Git\\usr\\bin\\bash.exe",
        os.path.expandvars("%LOCALAPPDATA%\\Programs\\Git\\bin\\bash.exe"),
        os.path.expandvars("%LOCALAPPDATA%\\hermes\\tools\\git-2.53.0+3-win32-x64\\usr\\bin\\bash.exe"),
        shutil.which("bash.exe"),
        shutil.which("bash"),
    ]
    bash_path = None
    for p in bash_candidates:
        if p and os.path.exists(p):
            if "system32" in p.lower():
                continue
            bash_path = p
            break
    if bash_path:
        shells.append({"id": "bash", "name": "Git Bash", "path": bash_path})
        
    # 3. Command Prompt
    cmd_path = shutil.which("cmd.exe") or "C:\\Windows\\System32\\cmd.exe"
    if os.path.exists(cmd_path):
        shells.append({"id": "cmd", "name": "Command Prompt", "path": cmd_path})
        
    if not shells:
        shells.append({"id": "default", "name": "Default Shell", "path": os.getenv("COMSPEC", "cmd.exe")})
        
    return shells

@router.get("/api/agent/terminal/shells")
async def list_terminal_shells():
    """Lists all detected available shells for terminal tab initialization."""
    return {"shells": get_available_shells(), "conpty_active": HAS_WINPTY}

@router.websocket("/ws/terminal/{terminal_id}")
async def terminal_websocket_endpoint(websocket: WebSocket, terminal_id: str):
    """
    Bidirectional WebSocket connection for live interactive terminal sessions.
    Handles continuous input, output streaming, resize notifications, and process termination.
    """
    await websocket.accept()
    
    # Query parameters
    params = websocket.query_params
    shell_id = params.get("shell", "powershell")
    cols = int(params.get("cols", 80) or 80)
    rows = int(params.get("rows", 24) or 24)
    
    # Validated CWD: default strictly to User Home or active project directory
    user_home = str(Path.home())
    req_cwd = (params.get("cwd") or "").strip()
    if req_cwd and os.path.isdir(req_cwd):
        cwd = os.path.abspath(req_cwd)
    else:
        try:
            cwd = os.getcwd() if os.path.isdir(os.getcwd()) else user_home
        except Exception:
            cwd = user_home
    
    # Resolve shell command
    available = {s["id"]: s["path"] for s in get_available_shells()}
    executable = available.get(shell_id) or available.get("powershell") or available.get("cmd") or "cmd.exe"
    
    cmd_args: List[str] = [executable]
    if "powershell" in executable.lower() or "pwsh" in executable.lower():
        cmd_args.extend(["-NoLogo", "-NoExit"])
    elif "bash" in executable.lower():
        cmd_args.extend(["-i", "-l"])
    elif "cmd.exe" in executable.lower():
        cmd_args.extend(["/K"])

    # Branch: Native ConPTY (Windows with pywinpty) vs Standard Subprocess Pipe
    if HAS_WINPTY and os.name == "nt":
        await _handle_winpty_session(websocket, terminal_id, cmd_args, cwd, cols, rows)
    else:
        await _handle_subprocess_session(websocket, terminal_id, cmd_args, cwd)


async def _handle_winpty_session(
    websocket: WebSocket,
    terminal_id: str,
    cmd_args: List[str],
    cwd: str,
    cols: int,
    rows: int,
):
    """Handles an interactive terminal session backed by Windows ConPTY (pywinpty)."""
    from winpty import PtyProcess  # type: ignore

    loop = asyncio.get_running_loop()
    pty_proc: Optional[PtyProcess] = None
    read_task: Optional[asyncio.Task] = None

    try:
        pty_proc = PtyProcess.spawn(
            cmd_args,
            cwd=cwd,
            dimensions=(max(5, rows), max(10, cols)),
        )
        _active_terminals[terminal_id] = pty_proc
        logger.info(f"[Terminal ConPTY] Session started: {terminal_id} ({cmd_args[0]}) [PID {pty_proc.pid}] in {cwd}")

        # Send ready control frame
        await websocket.send_text(json.dumps({
            "type": "ready",
            "pid": pty_proc.pid,
            "conpty": True,
            "cols": cols,
            "rows": rows,
            "cwd": cwd,
        }))

        async def _stream_pty_output():
            while pty_proc and pty_proc.isalive():
                try:
                    chunk = await loop.run_in_executor(None, pty_proc.read, 1024)
                    if not chunk:
                        break
                    await websocket.send_text(chunk)
                except EOFError:
                    break
                except Exception as e:
                    logger.debug(f"[Terminal ConPTY {terminal_id}] Read stopped: {e}")
                    break

        read_task = asyncio.create_task(_stream_pty_output())

        while True:
            msg = await websocket.receive_text()
            if not msg:
                continue

            if msg.startswith("{") and msg.endswith("}"):
                try:
                    payload = json.loads(msg)
                    msg_type = payload.get("type")
                    if msg_type == "input":
                        data_str = payload.get("data", "")
                        if pty_proc and pty_proc.isalive():
                            pty_proc.write(data_str)
                    elif msg_type == "resize":
                        new_cols = int(payload.get("cols", cols) or cols)
                        new_rows = int(payload.get("rows", rows) or rows)
                        if pty_proc and pty_proc.isalive():
                            try:
                                pty_proc.setwinsize(max(5, new_rows), max(10, new_cols))
                            except Exception:
                                pass
                    elif msg_type == "kill":
                        if pty_proc and pty_proc.isalive():
                            pty_proc.terminate()
                        break
                    continue
                except json.JSONDecodeError:
                    pass

            if pty_proc and pty_proc.isalive():
                pty_proc.write(msg)

    except WebSocketDisconnect:
        logger.info(f"[Terminal ConPTY] Client disconnected: {terminal_id}")
    except Exception as err:
        logger.warning(f"[Terminal ConPTY {terminal_id}] Session error: {err}")
    finally:
        if read_task and not read_task.done():
            read_task.cancel()
        _active_terminals.pop(terminal_id, None)
        if pty_proc:
            try:
                if pty_proc.isalive():
                    pty_proc.terminate()
            except Exception:
                pass
        logger.info(f"[Terminal ConPTY] Cleaned up session: {terminal_id}")


async def _handle_subprocess_session(
    websocket: WebSocket,
    terminal_id: str,
    cmd_args: List[str],
    cwd: str,
):
    """Fallback standard subprocess pipe session for non-ConPTY environments."""
    proc: Optional[asyncio.subprocess.Process] = None
    read_task: Optional[asyncio.Task] = None

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            cwd=cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        _active_terminals[terminal_id] = proc
        logger.info(f"[Terminal Pipe] Session started: {terminal_id} ({cmd_args[0]}) [PID {proc.pid}] in {cwd}")

        # Send ready control frame
        await websocket.send_text(json.dumps({
            "type": "ready",
            "pid": proc.pid,
            "conpty": False,
            "cwd": cwd,
        }))

        async def _stream_pipe_output():
            assert proc is not None and proc.stdout is not None
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            try:
                while True:
                    chunk = await proc.stdout.read(1024)
                    if not chunk:
                        break
                    text = decoder.decode(chunk)
                    if text:
                        await websocket.send_text(text)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.debug(f"[Terminal Pipe {terminal_id}] Output stopped: {e}")

        read_task = asyncio.create_task(_stream_pipe_output())

        while True:
            msg = await websocket.receive_text()
            if not msg:
                continue

            if msg.startswith("{") and msg.endswith("}"):
                try:
                    payload = json.loads(msg)
                    msg_type = payload.get("type")
                    if msg_type == "input":
                        data_str = payload.get("data", "")
                        if proc and proc.stdin:
                            proc.stdin.write(data_str.encode("utf-8"))
                            await proc.stdin.drain()
                    elif msg_type == "kill":
                        if proc and proc.returncode is None:
                            try:
                                if os.name == "nt":
                                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
                                else:
                                    proc.kill()
                            except Exception:
                                pass
                        break
                    continue
                except json.JSONDecodeError:
                    pass

            if proc and proc.stdin:
                proc.stdin.write(msg.encode("utf-8"))
                await proc.stdin.drain()

    except WebSocketDisconnect:
        logger.info(f"[Terminal Pipe] Client disconnected: {terminal_id}")
    except Exception as err:
        logger.warning(f"[Terminal Pipe {terminal_id}] Session error: {err}")
    finally:
        if read_task and not read_task.done():
            read_task.cancel()
        _active_terminals.pop(terminal_id, None)
        if proc and proc.returncode is None:
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=3)
                else:
                    proc.kill()
                await proc.wait()
            except Exception:
                pass
        logger.info(f"[Terminal Pipe] Cleaned up session: {terminal_id}")
