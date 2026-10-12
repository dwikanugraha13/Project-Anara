"""
code_execution_tools.py — Sandboxed Code Execution REPL Engine for Project Anara.
Anara Standard execute_code: allows the agent to evaluate Python
and JavaScript scripts in a protected subprocess environment.
"""

import asyncio
import contextlib
import io
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .events import _emit_agent_event

logger = logging.getLogger(__name__)

# Persistent interactive Python kernels per session (Parity with Oh My Pi & Hermes Agent)
_PERSISTENT_PYTHON_KERNELS: Dict[str, Dict[str, Any]] = {}


async def _tool_execute_code(
    code: str,
    language: str = "python",
    timeout: int = 30,
    reset: bool = False,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Evaluates Python or Node.js code snippets in a sandboxed execution environment.
    For Python, runs in a persistent session kernel: variables, imports, and state
    survive across tool calls within the same session unless reset=True.
    
    language: 'python' (default) or 'javascript' / 'node'
    timeout: maximum execution seconds (default 30s)
    reset: discard the kernel's persistent state and start fresh (default false)
    """
    clean_code = (code or "").strip()
    if not clean_code:
        return {"status": "error", "message": "Code to execute cannot be empty."}

    from core.sandbox import check_command_safety
    is_safe, denial_reason = check_command_safety(clean_code)
    if not is_safe:
        return {
            "status": "error",
            "message": denial_reason or "Code snippet rejected by sandbox safety guard."
        }

    lang = language.strip().lower()

    _emit_agent_event("agent_action_start", {
        "tool_name": "execute_code",
        "action_title": f"Executing Code ({lang.capitalize()})",
        "detail": f"{len(clean_code.splitlines())} lines of code" + (" [Kernel Reset]" if reset else ""),
        "icon": "play"
    })

    from core.agent import anara_agent
    session_cwd = anara_agent.get_session_dir()
    start_time = time.time()

    # ── 1. Python Persistent Interactive Session Kernel (OMP / Hermes Parity) ──
    if lang == "python":
        sid = str(anara_agent.get_active_session_id() or os.getenv("ANARA_SESSION_ID") or "global")
        if bool(reset) or sid not in _PERSISTENT_PYTHON_KERNELS:
            from tools import anara_tools
            sys.modules["anara_tools"] = anara_tools
            kernel_ns: Dict[str, Any] = {
                "__name__": "__main__",
                "__builtins__": __builtins__,
                "anara_tools": anara_tools,
            }
            # Pre-inject core tool helpers for instant direct calling
            for t_name in ["read_file", "write_file", "edit_file", "search_files", "terminal", "web_search", "json_parse"]:
                if hasattr(anara_tools, t_name):
                    kernel_ns[t_name] = getattr(anara_tools, t_name)

            def _safe_exit(code=0):
                raise SystemExit(code)

            kernel_ns["exit"] = _safe_exit
            kernel_ns["quit"] = _safe_exit
            _PERSISTENT_PYTHON_KERNELS[sid] = kernel_ns

        kernel_ns = _PERSISTENT_PYTHON_KERNELS[sid]

        def _run_in_kernel():
            sio = io.StringIO()
            eio = io.StringIO()
            old_cwd = os.getcwd()
            if session_cwd and os.path.isdir(session_cwd):
                try:
                    os.chdir(session_cwd)
                except Exception:
                    pass
            exit_code = 0
            try:
                with contextlib.redirect_stdout(sio), contextlib.redirect_stderr(eio):
                    try:
                        code_obj = compile(clean_code, f"<session_{sid}>", "exec")
                        exec(code_obj, kernel_ns)
                        exit_code = 0
                    except SystemExit as se:
                        exit_code = se.code if isinstance(se.code, int) else 0
                    except Exception:
                        import traceback
                        eio.write(traceback.format_exc())
                        exit_code = 1
            finally:
                try:
                    os.chdir(old_cwd)
                except Exception:
                    pass
            return exit_code, sio.getvalue(), eio.getvalue()

        try:
            exit_code, stdout_str, stderr_str = await asyncio.wait_for(
                asyncio.to_thread(_run_in_kernel),
                timeout=float(timeout)
            )
        except asyncio.TimeoutError:
            _PERSISTENT_PYTHON_KERNELS.pop(sid, None)
            return {
                "status": "error",
                "exit_code": -1,
                "timed_out": True,
                "message": f"Code execution timed out after {timeout}s threshold in persistent kernel."
            }

        elapsed = round(time.time() - start_time, 3)
        stdout_str = stdout_str.strip()
        stderr_str = stderr_str.strip()
        is_success = (exit_code == 0)

        return {
            "status": "success" if is_success else "error",
            "exit_code": exit_code,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "output": stdout_str or stderr_str,
            "elapsed_seconds": elapsed,
            "kernel_session": sid,
            "message": f"Kernel execution completed in {elapsed}s with exit code {exit_code}."
        }

    # ── 2. JavaScript / Node Subprocess Execution ──
    suffix = ".js" if lang in ("javascript", "node", "js") else ".txt"
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8") as f:
        f.write(clean_code)
        temp_file_path = f.name

    try:
        if lang in ("javascript", "node", "js"):
            cmd = ["node", temp_file_path]
        else:
            return {"status": "error", "message": f"Language '{lang}' is not supported. Use 'python' or 'javascript'."}

        from core.sandbox import get_sanitized_environment
        sanitized_env = get_sanitized_environment()
        if session_cwd:
            sanitized_env["ANARA_SESSION_DIR"] = str(session_cwd)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=session_cwd,
            env=sanitized_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=float(timeout))
        except asyncio.TimeoutError:
            try:
                if sys.platform == "win32":
                    import subprocess
                    subprocess.run(["taskkill", "/PID", str(proc.pid), "/F", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                else:
                    proc.kill()
            except Exception:
                pass
            return {
                "status": "error",
                "exit_code": -1,
                "timed_out": True,
                "message": f"Code execution timed out after safety threshold ({timeout}s)."
            }

        elapsed = round(time.time() - start_time, 3)
        stdout_str = stdout_b.decode("utf-8", errors="replace").strip()
        stderr_str = stderr_b.decode("utf-8", errors="replace").strip()
        is_success = (proc.returncode == 0)

        return {
            "status": "success" if is_success else "error",
            "exit_code": proc.returncode,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "output": stdout_str or stderr_str,
            "elapsed_seconds": elapsed,
            "message": f"Execution completed in {elapsed}s with returncode {proc.returncode}."
        }
    except Exception as e:
        logger.warning(f"[CodeExecution] Execution error: {e}")
        return {"status": "error", "message": f"Failed to execute code: {str(e)}"}
    finally:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass
                pass
