import asyncio
import logging
import os
import subprocess
import atexit
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

WA_BRIDGE_PORT = int(os.getenv("WA_BRIDGE_PORT", "8001"))
WA_BRIDGE_URL = f"http://localhost:{WA_BRIDGE_PORT}"

# Resolves to either backend/whatsapp_bridge or backend/integrations/whatsapp_bridge
_candidate_bridge = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "whatsapp_bridge")
if not os.path.exists(_candidate_bridge):
    _candidate_bridge = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whatsapp_bridge")
BRIDGE_DIR = _candidate_bridge

_bridge_process: Optional[subprocess.Popen] = None


def is_whatsapp_connected() -> bool:
    """Checks if the local WhatsApp Bridge port is listening and responsive."""
    try:
        import socket
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        res = probe.connect_ex(("127.0.0.1", WA_BRIDGE_PORT))
        probe.close()
        return res == 0
    except Exception:
        return False


def start_whatsapp_bridge():
    """Starts the local Node.js Baileys bridge in the background."""
    global _bridge_process
    if _bridge_process and _bridge_process.poll() is None:
        return  # already running

    bridge_script = os.path.join(BRIDGE_DIR, "bridge.js")
    if not os.path.exists(bridge_script):
        logger.warning(f"[WhatsAppService] bridge.js not found at {bridge_script}")
        return

    try:
        if is_whatsapp_connected():
            logger.info(f"[WhatsAppService] WhatsApp Bridge already listening on port {WA_BRIDGE_PORT}")
            return

        logger.info(f"[WhatsAppService] Spawning local WhatsApp bridge process on port {WA_BRIDGE_PORT}...")
        _bridge_process = subprocess.Popen(
            ["node", "bridge.js"],
            cwd=BRIDGE_DIR,
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info(f"[WhatsAppService] Bridge process spawned (PID {_bridge_process.pid})")
    except Exception as e:
        logger.warning(f"[WhatsAppService] Failed to spawn WhatsApp bridge: {e}")


def stop_whatsapp_bridge():
    """Stops the bridge process on shutdown."""
    global _bridge_process
    if _bridge_process and _bridge_process.poll() is None:
        try:
            _bridge_process.terminate()
            _bridge_process.wait(timeout=2.0)
        except Exception:
            try:
                _bridge_process.kill()
            except Exception:
                pass
        _bridge_process = None


atexit.register(stop_whatsapp_bridge)


async def get_whatsapp_status() -> Dict[str, Any]:
    """Fetches connection status and logged-in account info from the bridge."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            res = await client.get(f"{WA_BRIDGE_URL}/status")
            if res.status_code == 200:
                return res.json()
    except Exception:
        pass
    return {"status": "disconnected", "has_qr": False, "user": None, "unread_count": 0}


async def get_whatsapp_qr() -> Optional[str]:
    """Fetches the current Base64 QR Code PNG Data URL, or None if already connected."""
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            res = await client.get(f"{WA_BRIDGE_URL}/qr")
            if res.status_code == 200:
                data = res.json()
                return data.get("qr_data_url")
    except Exception:
        pass
    return None


async def logout_whatsapp() -> Dict[str, Any]:
    """Logs out and clears the saved WhatsApp session folder."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.post(f"{WA_BRIDGE_URL}/logout")
            if res.status_code == 200:
                return res.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "Gagal menghubungi WhatsApp bridge."}


async def get_whatsapp_messages(unread_only: bool = False, limit: int = 10, mark_read: bool = True) -> List[Dict[str, Any]]:
    """Retrieves recent incoming WhatsApp messages."""
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            params = {
                "unread_only": "true" if unread_only else "false",
                "limit": str(limit),
                "mark_read": "true" if mark_read else "false",
            }
            res = await client.get(f"{WA_BRIDGE_URL}/messages", params=params)
            if res.status_code == 200:
                return res.json().get("messages", [])
    except Exception:
        pass
    return []


async def get_unread_whatsapp_messages(limit: int = 10) -> List[Dict[str, Any]]:
    """Helper alias for unread WhatsApp messages."""
    return await get_whatsapp_messages(unread_only=True, limit=limit)


async def send_whatsapp_message(to: str, message: str) -> Dict[str, Any]:
    """Sends a text message to a WhatsApp number via the bridge."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {"to": to, "message": message}
            res = await client.post(f"{WA_BRIDGE_URL}/send", json=payload)
            if res.status_code == 200:
                return res.json()
            else:
                try:
                    err_json = res.json()
                    return {"status": "error", "message": err_json.get("message", res.text)}
                except Exception:
                    return {"status": "error", "message": f"HTTP {res.status_code}: {res.text}"}
    except Exception as e:
        return {"status": "error", "message": f"Koneksi error: {str(e)}"}
