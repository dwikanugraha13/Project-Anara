"""
gateway_manager.py — Cloudflare Remote Gateway & Tunnel Supervisor for Project Anara.
Anara Standard Gateway & Remote Tunnels:
1. Portable self-contained cloudflared resolution & auto-bootstrap.
2. Supervised Quick Tunnel execution forwarding to Next.js port 3000.
3. Dynamic extraction and recording of live HTTPS public URL.
4. Clean process lifecycle tracking under ANARA_HOME/run.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, Optional
import urllib.request

from constants import get_anara_home, get_anara_run_dir, get_anara_logs_dir
from core.lifecycle import is_pid_alive

logger = logging.getLogger("anara.gateway")

CLOUDFLARE_BINARIES = {
    ("windows", "amd64"): "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe",
    ("windows", "arm64"): "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-arm64.exe",
    ("linux", "x86_64"): "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
    ("linux", "aarch64"): "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64",
    ("linux", "arm64"): "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64",
    ("darwin", "x86_64"): "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64",
    ("darwin", "arm64"): "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64",
}
CLOUDFLARE_WINDOWS_URL = CLOUDFLARE_BINARIES[("windows", "amd64")]
TUNNEL_LIFECYCLE_FILE = get_anara_run_dir() / "tunnel.lifecycle.json"
TUNNEL_PID_FILE = get_anara_run_dir() / "tunnel.pid"

_START_LOCK: Optional[asyncio.Lock] = None


def _get_start_lock() -> asyncio.Lock:
    global _START_LOCK
    if _START_LOCK is None:
        _START_LOCK = asyncio.Lock()
    return _START_LOCK


def get_platform_download_url() -> str:
    """Resolves cloudflared download URL based on OS and architecture."""
    os_name = sys.platform
    if os_name.startswith("win"):
        os_key = "windows"
    elif os_name.startswith("linux"):
        os_key = "linux"
    elif os_name.startswith("darwin"):
        os_key = "darwin"
    else:
        os_key = "linux"

    arch = platform.machine().lower()
    if arch in ("x86_64", "amd64"):
        arch_key = "amd64" if os_key == "windows" else "x86_64"
    elif arch in ("aarch64", "arm64"):
        arch_key = "arm64"
    else:
        arch_key = "x86_64"

    return CLOUDFLARE_BINARIES.get((os_key, arch_key)) or CLOUDFLARE_WINDOWS_URL


def is_local_port_open(port: int) -> bool:
    """Pre-flight check: verifies local target port is listening to avoid 502 Bad Gateway."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except Exception:
        return False


def get_bin_dir() -> Path:
    """Returns portable binary directory under ANARA_HOME."""
    bd = get_anara_home() / "bin"
    bd.mkdir(parents=True, exist_ok=True)
    return bd


def verify_cloudflared_binary(bin_path: Path) -> bool:
    """Verifies that the binary exists, is executable, and runs without error."""
    if not bin_path.is_file():
        return False
    try:
        res = subprocess.run(
            [str(bin_path), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            creationflags=0x08000000 if sys.platform == "win32" else 0
        )
        return res.returncode == 0 and "cloudflared" in res.stdout.lower()
    except Exception:
        return False


def get_cloudflared_path() -> Optional[Path]:
    """Resolves cloudflared executable from system PATH or ANARA_HOME/bin."""
    which_p = shutil.which("cloudflared")
    if which_p and verify_cloudflared_binary(Path(which_p)):
        return Path(which_p)

    local_bin = get_bin_dir() / ("cloudflared.exe" if sys.platform == "win32" else "cloudflared")
    if verify_cloudflared_binary(local_bin):
        return local_bin

    return None


def ensure_cloudflared_installed(progress_cb: Optional[Any] = None) -> Path:
    """Ensures cloudflared is available; downloads portable standalone binary atomically if missing."""
    existing = get_cloudflared_path()
    if existing:
        return existing

    bin_path = get_bin_dir() / ("cloudflared.exe" if sys.platform == "win32" else "cloudflared")
    download_url = get_platform_download_url()
    logger.info(f"[GatewayManager] Downloading portable cloudflared from {download_url} to {bin_path}...")
    if progress_cb:
        progress_cb("Downloading cloudflared portable...")

    headers = {"User-Agent": "Project-Anara-Gateway/3.0"}
    req = urllib.request.Request(download_url, headers=headers)

    temp_fd, temp_path_str = tempfile.mkstemp(dir=str(get_bin_dir()), prefix=".cloudflared_dl_")
    try:
        with os.fdopen(temp_fd, "wb") as f_dst, urllib.request.urlopen(req, timeout=60) as resp:
            shutil.copyfileobj(resp, f_dst)

        temp_p = Path(temp_path_str)
        if sys.platform != "win32":
            temp_p.chmod(0o755)

        if not verify_cloudflared_binary(temp_p):
            raise RuntimeError("Downloaded cloudflared binary failed verification test (--version).")

        os.replace(temp_path_str, bin_path)
    except Exception:
        if os.path.exists(temp_path_str):
            try:
                os.remove(temp_path_str)
            except Exception:
                pass
        raise

    logger.info(f"[GatewayManager] Portable cloudflared verified and installed: {bin_path}")
    return bin_path


def get_tunnel_status() -> Dict[str, Any]:
    """Checks if the Cloudflare tunnel process is actively running."""
    if not TUNNEL_PID_FILE.is_file():
        return {"status": "stopped", "is_running": False}

    try:
        pid = int(TUNNEL_PID_FILE.read_text(encoding="utf-8").strip())
        if is_pid_alive(pid):
            meta = {}
            if TUNNEL_LIFECYCLE_FILE.is_file():
                try:
                    meta = json.loads(TUNNEL_LIFECYCLE_FILE.read_text(encoding="utf-8"))
                except Exception:
                    pass
            return {
                "status": "running",
                "is_running": True,
                "pid": pid,
                "public_url": meta.get("public_url"),
                "started_at": meta.get("started_at"),
            }
        else:
            # Stale PID file cleanup
            TUNNEL_PID_FILE.unlink(missing_ok=True)
            if TUNNEL_LIFECYCLE_FILE.is_file():
                try:
                    data = json.loads(TUNNEL_LIFECYCLE_FILE.read_text(encoding="utf-8"))
                    data["status"] = "stopped"
                    TUNNEL_LIFECYCLE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
                except Exception:
                    pass
    except Exception:
        pass

    return {"status": "stopped", "is_running": False}


def stop_tunnel() -> bool:
    """Terminates active Cloudflare tunnel tree cleanly."""
    st = get_tunnel_status()
    if not st.get("is_running"):
        return False

    pid = st.get("pid")
    if pid:
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=5,
                    creationflags=0x08000000
                )
            else:
                try:
                    import signal
                    pgid = os.getpgid(pid)
                    if pgid != os.getpgrp():
                        os.killpg(pgid, signal.SIGTERM)
                    else:
                        os.kill(pid, signal.SIGTERM)
                except Exception:
                    os.kill(pid, 15)
        except Exception:
            pass

    TUNNEL_PID_FILE.unlink(missing_ok=True)
    if TUNNEL_LIFECYCLE_FILE.is_file():
        try:
            data = json.loads(TUNNEL_LIFECYCLE_FILE.read_text(encoding="utf-8"))
            data["status"] = "stopped"
            data["stopped_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            TUNNEL_LIFECYCLE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    logger.info("[GatewayManager] Cloudflare tunnel stopped.")
    return True


async def start_quick_tunnel(port: int = 3000, timeout_seconds: int = 25) -> Dict[str, Any]:
    """
    Spawns Cloudflare Quick Tunnel forwarding to local port, waits for public URL,
    and records process metadata. Protected by re-entrant async lock.
    """
    async with _get_start_lock():
        # Check if already running
        curr = get_tunnel_status()
        if curr.get("is_running") and curr.get("public_url"):
            return curr

        # Pre-flight readiness check (Anara Standard)
        if not is_local_port_open(port):
            logger.warning(f"[GatewayManager] Target local port {port} is not yet listening. Spawning tunnel anyway...")

        bin_path = await asyncio.to_thread(ensure_cloudflared_installed)
        log_file = get_anara_logs_dir() / "tunnel.log"
        named_cfg = Path.home() / ".cloudflared" / "config.yml"

        is_named = named_cfg.is_file()
        if is_named:
            cmd = [
                str(bin_path),
                "tunnel",
                "run",
                "anara-gateway",
            ]
        else:
            cmd = [
                str(bin_path),
                "tunnel",
                "--protocol",
                "http2",
                "--url",
                f"http://127.0.0.1:{port}",
                "--no-autoupdate",
            ]

        creationflags = 0
        start_new_session = False
        if sys.platform == "win32":
            creationflags = 0x08000000 | subprocess.CREATE_NEW_PROCESS_GROUP  # CREATE_NO_WINDOW | Process Group
        else:
            start_new_session = True

        log_file.parent.mkdir(parents=True, exist_ok=True)
        f_out = open(log_file, "w", encoding="utf-8", errors="replace")
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=f_out,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
                start_new_session=start_new_session,
            )
        finally:
            # Parent must close descriptor immediately (Anara Engineering Standards)
            f_out.close()

        TUNNEL_PID_FILE.write_text(str(proc.pid), encoding="utf-8")

        # Poll log file for trycloudflare URL or named tunnel registration
        url_pattern = re.compile(r"(https://[a-zA-Z0-9-]+\.trycloudflare\.com)")
        conn_pattern = re.compile(r"Registered tunnel connection")
        public_url = None
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            if proc.poll() is not None:
                break
            if log_file.is_file():
                try:
                    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    if is_named:
                        if conn_pattern.search(content):
                            resolved_url = "https://anara.my.id"
                            try:
                                import yaml
                                if named_cfg.is_file():
                                    with open(named_cfg, "r", encoding="utf-8") as yf:
                                        ydata = yaml.safe_load(yf) or {}
                                        ing = ydata.get("ingress") or []
                                        for rule in ing:
                                            if isinstance(rule, dict) and rule.get("hostname"):
                                                resolved_url = f"https://{rule['hostname']}"
                                                break
                            except Exception:
                                pass
                            public_url = resolved_url
                            break
                    else:
                        match = url_pattern.search(content)
                        if match:
                            public_url = match.group(1)
                            break
                except Exception:
                    pass
            await asyncio.sleep(0.5)

        if not public_url:
            stop_tunnel()
            return {
                "status": "error",
                "message": "Failed to acquire Cloudflare Tunnel URL within timeout. Check internet connection and logs.",
            }

        meta = {
            "status": "running",
            "pid": proc.pid,
            "public_url": public_url,
            "local_port": port,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        TUNNEL_LIFECYCLE_FILE.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        logger.info(f"[GatewayManager] Cloudflare Tunnel established: {public_url} -> :{port}")
        return meta
