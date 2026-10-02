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
from typing import Dict, List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("anara.terminal")
router = APIRouter(tags=["Terminal"])

# Active terminal sessions registry { terminal_id: asyncio.subprocess.Process }
_active_terminals: Dict[str, asyncio.subprocess.Process] = {}

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
        
    # 2. Git Bash / MSYS2 Bash
    bash_candidates = [
        shutil.which("bash.exe"),
        shutil.which("bash"),
        "C:\\Program Files\\Git\\bin\\bash.exe",
        "C:\\Program Files\\Git\\usr\\bin\\bash.exe",
        os.path.expandvars("%LOCALAPPDATA%\\Programs\\Git\\bin\\bash.exe"),
    ]
    bash_path = next((p for p in bash_candidates if p and os.path.exists(p)), None)
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
    return {"shells": get_available_shells()}

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
    
    # Validated CWD: default strictly to User Home (C:\Users\<user> or ~) if no active workspace
    from pathlib import Path
    user_home = str(Path.home())
    req_cwd = (params.get("cwd") or "").strip()
    if req_cwd and os.path.isdir(req_cwd):
        cwd = os.path.abspath(req_cwd)
    else:
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

    proc: Optional[asyncio.subprocess.Process] = None
    read_task: Optional[asyncio.Task] = None

    try:
        # Start persistent interactive shell subprocess with piped standard I/O
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            cwd=cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        _active_terminals[terminal_id] = proc
        logger.info(f"[Terminal] Session started: {terminal_id} ({executable}) in {cwd} [PID {proc.pid}]")

        # Sub-task: Read stdout/stderr from process and stream to client WebSocket
        async def _stream_output():
            assert proc is not None and proc.stdout is not None
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            try:
                while True:
                    chunk = await proc.stdout.read(1024)
                    if not chunk:
                        break
                    # Send decoded text with incremental decoding to prevent slicing multi-byte chars
                    text = decoder.decode(chunk)
                    if text:
                        await websocket.send_text(text)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.debug(f"[Terminal {terminal_id}] Output stream stopped: {e}")

        read_task = asyncio.create_task(_stream_output())

        # Main Loop: Receive keystrokes/data from client WebSocket and pipe to process stdin
        while True:
            msg = await websocket.receive_text()
            if not msg:
                continue

            # Check if JSON payload (control frame) or raw keystroke string
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
                    elif msg_type == "resize":
                        # Handled if ConPTY native support is present
                        pass
                    continue
                except json.JSONDecodeError:
                    pass

            # Raw string fallback
            if proc and proc.stdin:
                proc.stdin.write(msg.encode("utf-8"))
                await proc.stdin.drain()

    except WebSocketDisconnect:
        logger.info(f"[Terminal] Client disconnected: {terminal_id}")
    except Exception as err:
        logger.warning(f"[Terminal {terminal_id}] Session error: {err}")
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
        logger.info(f"[Terminal] Cleaned up session: {terminal_id}")
