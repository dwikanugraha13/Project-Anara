"""
gateway_manager.py — Cloudflare Remote Gateway & Tunnel Supervisor for Project Anara.
Full parity with Hermes Agent gateway subcommands & remote tunnels:
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
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, Optional
import urllib.request

from constants import get_anara_home, get_anara_run_dir, get_anara_logs_dir
from core.lifecycle import is_pid_alive

logger = logging.getLogger("anara.gateway")

CLOUDFLARE_WINDOWS_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
TUNNEL_LIFECYCLE_FILE = get_anara_run_dir() / "tunnel.lifecycle.json"
TUNNEL_PID_FILE = get_anara_run_dir() / "tunnel.pid"


def get_bin_dir() -> Path:
    """Returns portable binary directory under ANARA_HOME."""
    bd = get_anara_home() / "bin"
    bd.mkdir(parents=True, exist_ok=True)
    return bd


def get_cloudflared_path() -> Optional[Path]:
    """Resolves cloudflared executable from system PATH or ANARA_HOME/bin."""
    # 1. Check system PATH
    which_p = shutil.which("cloudflared")
    if which_p:
        return Path(which_p)

    # 2. Check ANARA_HOME/bin
    local_bin = get_bin_dir() / ("cloudflared.exe" if sys.platform == "win32" else "cloudflared")
    if local_bin.is_file() and os.access(local_bin, os.X_OK):
        return local_bin

    return None


def ensure_cloudflared_installed(progress_cb: Optional[Any] = None) -> Path:
    """Ensures cloudflared is available; downloads portable standalone binary if missing."""
    existing = get_cloudflared_path()
    if existing:
        return existing

    bin_path = get_bin_dir() / ("cloudflared.exe" if sys.platform == "win32" else "cloudflared")
    logger.info(f"[GatewayManager] Downloading portable cloudflared to {bin_path}...")
    if progress_cb:
        progress_cb("Mengunduh cloudflared portable dari GitHub...")

    headers = {"User-Agent": "Project-Anara-Gateway/3.0"}
    req = urllib.request.Request(CLOUDFLARE_WINDOWS_URL, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        with open(bin_path, "wb") as f:
            shutil.copyfileobj(resp, f)

    if sys.platform != "win32":
        bin_path.chmod(0o755)

    logger.info(f"[GatewayManager] Portable cloudflared installed successfully: {bin_path}")
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
    except Exception:
        pass

    return {"status": "stopped", "is_running": False}


def stop_tunnel() -> bool:
    """Terminates active Cloudflare tunnel."""
    st = get_tunnel_status()
    if not st.get("is_running"):
        return False

    pid = st.get("pid")
    if pid:
        try:
            if sys.platform == "win32":
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
            else:
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
    and records process metadata.
    """
    # Check if already running
    curr = get_tunnel_status()
    if curr.get("is_running") and curr.get("public_url"):
        return curr

    bin_path = ensure_cloudflared_installed()
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
    if sys.platform == "win32":
        creationflags = 0x08000000  # CREATE_NO_WINDOW

    f_out = open(log_file, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        cmd,
        stdout=f_out,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )

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
                content = log_file.read_text(encoding="utf-8", errors="replace")
                if is_named:
                    if conn_pattern.search(content):
                        public_url = "https://anara.my.id"
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
            "message": "Gagal mendapatkan URL Cloudflare Tunnel dalam batas waktu. Periksa koneksi internet.",
        }

    meta = {
        "status": "running",
        "pid": proc.pid,
        "public_url": public_url,
        "local_port": port,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    TUNNEL_LIFECYCLE_FILE.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info(f"[GatewayManager] Cloudflare Tunnel established: {public_url} -> : {port}")
    return meta
