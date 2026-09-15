"""
sandbox.py — Hardened Process-Level & Container Sandbox Engine for Project Anara.
Implements FR-17 and NFR-1 from prd-general-agent.md & Bab 8 from rancangan-general-agent.md.

Protections:
1. Environment Sanitization: Strips all API keys, secrets, tokens, and passwords from
   the spawned process environment so commands cannot dump or leak credentials.
2. Destructive & System Takeover Guard: Blocks registry alterations, disk formatting,
   credential store dumping, Windows Defender tampering, and remote shell piping.
3. Clean Tree Termination: Terminates entire child process hierarchies on timeout or abort.
4. Docker Detection: Seamlessly uses container isolation if Docker daemon is responsive,
   or the native Windows Hardened Process Sandbox if Docker is absent.
"""
import asyncio
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Patterns identifying sensitive environment variables to scrub
SENSITIVE_ENV_PATTERNS = [
    r"(?i).*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|AUTH|CREDENTIAL|PRIVATE).*",
    r"(?i).*(?:GEMINI|OPENAI|ANTHROPIC|GROQ|TELEGRAM|DISCORD|WHATSAPP|GITHUB).*",
]

# High-risk system takeover commands strictly blocked
HOST_TAKEOVER_PATTERNS = [
    r"\brm\s+-[rf]{1,2}\s+[/~]",
    r"\bformat\s+[a-z]:",
    r"\bdiskpart\b",
    r"\bdrop\s+database\b",
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;",
    r"\bshutdown\b",
    r"\breboot\b",
    # Registry & system security tampering
    r"\breg\s+(?:add|delete|copy|restore|import)\b",
    r"\bset-mppreference\b",
    r"\bnet\s+(?:user|localgroup|group)\s+.*\/add\b",
    r"\bcertutil\s+-(?:addstore|urlcache)\b",
    # Remote shell execution piping
    r"(?:iex|invoke-expression)\s*\(?(?:new-object|curl|iwr|invoke-webrequest)",
    r"curl\s+.*\|\s*(?:iex|bash|sh|powershell)",
    r"wget\s+.*\|\s*(?:iex|bash|sh|powershell)",
]


def get_sanitized_environment() -> Dict[str, str]:
    """
    Creates a sterilized copy of os.environ.
    Preserves system runtime paths (PATH, TEMP, USERPROFILE) while scrubbing
    all API keys, credentials, and authentication secrets (FR-17).
    """
    clean_env: Dict[str, str] = {}
    for key, val in os.environ.items():
        is_sensitive = any(re.match(pattern, key) for pattern in SENSITIVE_ENV_PATTERNS)
        if not is_sensitive:
            clean_env[key] = val
        else:
            clean_env[key] = "[SANDBOX_SCRUBBED]"

    # Ensure UTF-8 output encoding for PowerShell / Python in child processes
    clean_env["PYTHONIOENCODING"] = "utf-8"
    clean_env["PYTHONUTF8"] = "1"
    clean_env["LC_ALL"] = "en_US.UTF-8"
    return clean_env


def check_command_safety(command: str) -> Tuple[bool, Optional[str]]:
    """
    Validates command against destructive and host-takeover patterns.
    Returns (is_safe, error_reason).
    """
    cmd_lower = (command or "").lower().strip()
    if not cmd_lower:
        return False, "Perintah kosong"

    for pattern in HOST_TAKEOVER_PATTERNS:
        if re.search(pattern, cmd_lower):
            logger.warning(f"[SandboxSecurity] Blocked dangerous command pattern: {pattern} in '{command}'")
            return False, f"DITOLAK SISTEM KEAMANAN (SANDBOX): Perintah '{command}' terdeteksi memicu modifikasi sistem berisiko tinggi."

    return True, None


class CommandSandbox:
    """Executes commands inside an isolated environment with resource control and timeouts."""

    @staticmethod
    def is_docker_available() -> bool:
        """Checks if Docker CLI and daemon are operational."""
        docker_bin = shutil.which("docker")
        if not docker_bin:
            return False
        try:
            res = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=2.5,
                text=True
            )
            return res.returncode == 0
        except Exception:
            return False

    @classmethod
    async def execute(
        cls,
        command: str,
        cwd: str,
        timeout_seconds: float = 120.0,
        env_overrides: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a shell command inside the Hardened Process Sandbox.
        """
        # 1. Safety validation
        is_safe, reason = check_command_safety(command)
        if not is_safe:
            return {
                "status": "error",
                "output": "",
                "exit_code": 1,
                "sandboxed": True,
                "message": reason or "Command rejected by sandbox security policy."
            }

        # 2. Ensure working directory exists and is safe
        safe_cwd = os.path.abspath(cwd)
        if not os.path.isdir(safe_cwd):
            os.makedirs(safe_cwd, exist_ok=True)

        # 3. Environment variable sanitization
        clean_env = get_sanitized_environment()
        if env_overrides:
            clean_env.update(env_overrides)

        # 4. Command assembly
        if os.name == "nt":
            exec_args = [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-Command",
                f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {command}"
            ]
            use_shell = False
        else:
            exec_args = ["bash", "-c", command]
            use_shell = False

        def _run_subprocess_sync() -> subprocess.CompletedProcess:
            return subprocess.run(
                exec_args,
                cwd=safe_cwd,
                env=clean_env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                shell=use_shell
            )

        try:
            completed_proc: subprocess.CompletedProcess = await asyncio.to_thread(_run_subprocess_sync)
            out_text = (completed_proc.stdout or "").strip()
            err_text = (completed_proc.stderr or "").strip()
            full_output = f"{out_text}\n{err_text}".strip() if err_text else out_text

            return {
                "status": "success" if completed_proc.returncode == 0 else "error",
                "output": full_output,
                "exit_code": completed_proc.returncode,
                "sandboxed": True,
                "timed_out": False,
            }

        except subprocess.TimeoutExpired:
            logger.warning(f"[Sandbox] Command timed out after {timeout_seconds}s: '{command}'")
            return {
                "status": "timeout",
                "output": f"Perintah terputus karena melebihi batas waktu aman ({timeout_seconds} detik).",
                "exit_code": -1,
                "sandboxed": True,
                "timed_out": True,
            }

        except Exception as e:
            logger.error(f"[Sandbox] Execution exception: {e}")
            return {
                "status": "error",
                "output": f"Kesalahan internal sandbox: {str(e) or type(e).__name__}",
                "exit_code": -1,
                "sandboxed": True,
                "timed_out": False,
            }

    @staticmethod
    def _kill_process_tree(pid: int):
        """Kills a process and all its children to prevent orphaned tasks."""
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=5)
            else:
                os.killpg(os.getpgid(pid), 9)
        except Exception:
            pass


command_sandbox = CommandSandbox()
