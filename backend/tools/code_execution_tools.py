"""
code_execution_tools.py — Sandboxed Code Execution REPL Engine for Project Anara.
Anara Standard execute_code: allows the agent to evaluate Python
and JavaScript scripts in a protected subprocess environment.
"""

import asyncio
import logging
import os
import sys
import tempfile
import time
from typing import Any, Dict, Optional

from .events import _emit_agent_event

logger = logging.getLogger(__name__)


async def _tool_execute_code(
    code: str,
    language: str = "python",
    timeout: int = 30
) -> Dict[str, Any]:
    """
    Evaluates Python or Node.js code snippets in an isolated sandboxed execution environment.
    language: 'python' (default) or 'javascript' / 'node'
    timeout: maximum execution seconds (default 30s)
    """
    clean_code = (code or "").strip()
    if not clean_code:
        return {"status": "error", "message": "Code to execute cannot be empty."}

    lang = language.strip().lower()

    _emit_agent_event("agent_action_start", {
        "tool_name": "execute_code",
        "action_title": f"Executing Code ({lang.capitalize()})",
        "detail": f"{len(clean_code.splitlines())} lines of code",
        "icon": "play"
    })

    suffix = ".py" if lang == "python" else (".js" if lang in ("javascript", "node", "js") else ".txt")
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8") as f:
        f.write(clean_code)
        temp_file_path = f.name

    try:
        if lang == "python":
            cmd = [sys.executable, temp_file_path]
        elif lang in ("javascript", "node", "js"):
            cmd = ["node", temp_file_path]
        else:
            return {"status": "error", "message": f"Language '{lang}' is not supported yet. Use 'python' or 'javascript'."}

        start_time = time.time()
        from core.sandbox import get_sanitized_environment
        from core.agent import anara_agent
        sanitized_env = get_sanitized_environment()
        session_cwd = anara_agent.get_session_dir()

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
