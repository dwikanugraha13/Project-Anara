"""
driver.py — Native cua-driver resolution, verification, and RPC caller.
Hermes Agent Parity (tools/computer_use/cua_backend_driver.py).
"""
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("anara.computer_use.driver")

_CUA_INSTALL_PS1_URL = "https://raw.githubusercontent.com/trycua/cua/main/libs/cua-driver/scripts/install.ps1"
_CUA_INSTALL_SH_URL = "https://raw.githubusercontent.com/trycua/cua/main/libs/cua-driver/scripts/install.sh"


def _candidate_driver_paths() -> List[str]:
    """Candidate binary paths in order of resolution (matching Hermes standard)."""
    env_override = os.environ.get("CUA_DRIVER_CMD") or os.environ.get("HERMES_CUA_DRIVER_CMD", "")
    if env_override.strip():
        return [env_override.strip()]

    home = os.path.expanduser("~")
    local_app_data = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")

    if sys.platform == "win32":
        return [
            "cua-driver",
            os.path.join(local_app_data, "Programs", "Cua", "cua-driver", "bin", "cua-driver.exe"),
            os.path.join(home, ".local", "bin", "cua-driver.exe"),
            os.path.join(home, ".local", "bin", "cua-driver"),
            os.path.join(local_app_data, "cua-driver", "bin", "cua-driver.exe"),
        ]

    return [
        "cua-driver",
        os.path.join(home, ".local", "bin", "cua-driver"),
        os.path.join(home, ".cargo", "bin", "cua-driver"),
        "/opt/homebrew/bin/cua-driver",
        "/usr/local/bin/cua-driver",
    ]


def resolve_cua_driver_cmd() -> Optional[str]:
    """Resolves the executable path to cua-driver."""
    for cand in _candidate_driver_paths():
        if not cand:
            continue
        # Direct file path
        if os.sep in cand or (os.altsep and os.altsep in cand):
            expanded = os.path.abspath(os.path.expanduser(cand))
            if os.path.isfile(expanded):
                return expanded
        else:
            found = shutil.which(cand)
            if found and os.path.isfile(found):
                return found
    return None


def is_cua_driver_available() -> bool:
    """Returns True if cua-driver is installed and resolvable."""
    return resolve_cua_driver_cmd() is not None


def install_cua_driver(upgrade: bool = False) -> bool:
    """
    Downloads and installs the official cua-driver binary from upstream (Hermes Parity).
    Uses the canonical trycua/cua installer.
    """
    is_win = sys.platform == "win32"
    logger.info("[CuaDriver] Launching upstream cua-driver installer...")

    if is_win:
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-Command",
            f"$sc = irm {_CUA_INSTALL_PS1_URL}; & ([scriptblock]::Create($sc)) -NoAutoStart"
        ]
    else:
        cmd = [
            "bash",
            "-c",
            f"curl -fsSL {_CUA_INSTALL_SH_URL} | bash"
        ]

    creationflags = 0
    if is_win:
        creationflags = 0x08000000  # CREATE_NO_WINDOW

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180.0,
            creationflags=creationflags,
            check=False
        )
        if proc.returncode == 0 and is_cua_driver_available():
            logger.info("[CuaDriver] cua-driver installed successfully.")
            return True
        logger.warning(f"[CuaDriver] Installer exited with code {proc.returncode}: {proc.stderr[:300]}")
    except Exception as e:
        logger.error(f"[CuaDriver] Installation error: {e}")

    return is_cua_driver_available()


def ensure_cua_driver_daemon_running() -> bool:
    """
    Ensures cua-driver daemon is active on the host with self-healing kick (Hermes Parity).
    Prevents silent CUA input failures across restarts and background sessions.
    """
    driver_cmd = resolve_cua_driver_cmd()
    if not driver_cmd:
        return False
    try:
        proc = subprocess.run([driver_cmd, "status"], capture_output=True, text=True, timeout=3.0)
        if "daemon is running" in (proc.stdout or "").lower():
            return True
        logger.info("[CuaDriver] Daemon not active, initiating auto-kick...")
        subprocess.run([driver_cmd, "autostart", "kick"], capture_output=True, text=True, timeout=5.0)
        time.sleep(0.5)
        proc2 = subprocess.run([driver_cmd, "status"], capture_output=True, text=True, timeout=3.0)
        if "daemon is running" in (proc2.stdout or "").lower():
            logger.info("[CuaDriver] Daemon successfully started via autostart kick.")
            return True
        # Direct background spawn if autostart entry is unkicked
        creationflags = 0x08000000 if sys.platform == "win32" else 0
        subprocess.Popen([driver_cmd, "serve", "--embedded"], creationflags=creationflags)
        time.sleep(1.0)
        logger.info("[CuaDriver] Spawned embedded background daemon.")
        return True
    except Exception as e:
        logger.warning(f"[CuaDriver] Daemon check/spawn error: {e}")
        return False


def run_cua_call(tool_name: str, args: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> Dict[str, Any]:
    """
    Executes a cua-driver tool via CLI RPC ('cua-driver call <tool> <args_json>').
    Returns parsed dictionary result or error payload with automatic daemon self-healing.
    """
    driver_cmd = resolve_cua_driver_cmd()
    if not driver_cmd:
        return {
            "status": "error",
            "isError": True,
            "error": "cua_driver_not_installed",
            "message": "cua-driver is not installed. Run 'python cli.py computer-use install' to install."
        }

    args_json = json.dumps(args or {})
    cmd = [driver_cmd, "call", tool_name, args_json]

    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x08000000  # CREATE_NO_WINDOW

    for attempt in range(2):
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=creationflags,
                check=False
            )
            out = (proc.stdout or "").strip()
            if not out and proc.stderr:
                out = proc.stderr.strip()

            # Self-healing daemon recovery on attempt 0
            if attempt == 0 and ("daemon is not running" in (proc.stderr or "").lower() or "daemon is not running" in out.lower()):
                logger.warning("[CuaDriver] Detected dead daemon on call. Reviving daemon before retry...")
                ensure_cua_driver_daemon_running()
                continue

            start = min((i for i in (out.find("{"), out.find("[")) if i != -1), default=-1)
            if start != -1:
                try:
                    data = json.loads(out[start:])
                    if isinstance(data, dict):
                        # Flag known cua-driver error payloads as error status
                        if data.get("isError") or data.get("error") or data.get("code") in (
                            "desktop_coordinate_scope_required",
                            "background_unavailable",
                            "missing_field",
                        ):
                            data["isError"] = True
                            data["status"] = "error"
                        return data
                except json.JSONDecodeError:
                    pass

            out_lower = out.lower()
            if any(err_marker in out_lower for err_marker in ("missing required", "error:", "failed", "unrecognized", "invalid")):
                return {"status": "error", "isError": True, "error": out}

            if proc.returncode == 0:
                return {"status": "success", "raw": out}
            return {"status": "error", "isError": True, "error": out or "Command failed"}

        except subprocess.TimeoutExpired:
            return {"status": "error", "isError": True, "error": f"cua-driver call '{tool_name}' timed out after {timeout}s"}
        except Exception as e:
            return {"status": "error", "isError": True, "error": str(e)}

    return {"status": "error", "isError": True, "error": "cua-driver call failed after daemon recovery attempt."}
