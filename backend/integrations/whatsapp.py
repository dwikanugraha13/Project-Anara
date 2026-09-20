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
                data = res.json()
                if not data.get("user"):
                    data["status"] = "disconnected"
                return data
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


def format_whatsapp_message_context(msg: Dict[str, Any]) -> str:
    """Formats a WhatsApp message with reply/quoted context and local media attachments if present."""
    text = (msg.get("text") or "").strip()
    quoted = (msg.get("quotedText") or "").strip()
    local_path = (msg.get("localPath") or "").strip()
    file_name = (msg.get("fileName") or "").strip()
    media_type = (msg.get("mediaType") or "").strip().lower()
    
    quoted_local_path = (msg.get("quotedLocalPath") or "").strip()
    quoted_media_type = (msg.get("quotedMediaType") or "").strip().lower()

    # 1. Quoted / Reply Context
    quote_context = ""
    if quoted or quoted_local_path:
        q_sender = (msg.get("quotedSender") or "User").upper()
        q_body = quoted
        if quoted_local_path and os.path.isfile(quoted_local_path):
            q_label = (quoted_media_type or "file").capitalize()
            q_tag = f"[Attachment {q_label}: {os.path.basename(quoted_local_path)}]"
            q_body = f"{quoted}\n{q_tag}".strip() if quoted else q_tag
        if q_body:
            quote_context = f"[REPLY CONTEXT: User replied to message from {q_sender}]:\n\"{q_body}\"\n\n"

    # 2. Local Attachment Details (Photo, Video, Audio, Document)
    att_info = ""
    if local_path and os.path.isfile(local_path):
        m_label = (media_type or "file").capitalize()
        f_display = file_name or os.path.basename(local_path)
        att_parts = [
            "[ATTACHMENT RECEIVED VIA WHATSAPP]:",
            f"- Type: {m_label}",
            f"- File: {f_display}",
            f"- Path: {local_path}"
        ]
        # Text/code preview if applicable
        if any(f_display.lower().endswith(ext) for ext in [".md", ".txt", ".json", ".py", ".csv", ".yaml", ".yml", ".sql", ".sh"]):
            try:
                with open(local_path, "r", encoding="utf-8", errors="ignore") as tf:
                    snippet = tf.read(2500)
                    if snippet.strip():
                        att_parts.append(f"- File Content Preview:\n```\n{snippet.strip()}\n```")
            except Exception:
                pass
        att_info = "\n".join(att_parts)

    # 3. Clean user prompt text
    user_prompt = text
    placeholder_triggers = (
        "[Foto]", "[Foto terlampir]", "[Photo]", "[Video]", "[Video terlampir]",
        "[Pesan Suara / Voice Note]", "[Voice Note]", "[Dokumen]", "[Document]",
    )
    if not user_prompt or any(user_prompt == p for p in placeholder_triggers) or user_prompt.startswith(("[Dokumen:", "[Document:")):
        if media_type == "document":
            user_prompt = f"[User sent an attached document '{f_display}'. Inspect and respond naturally in the user's active language.]"
        elif media_type == "photo":
            user_prompt = "[User sent an attached photo without caption. Inspect and respond naturally in the user's active language.]"
        elif media_type == "video":
            user_prompt = "[User sent an attached video without caption. Inspect and respond naturally in the user's active language.]"
        elif media_type == "audio":
            user_prompt = "[User sent an attached voice audio without caption. Process and respond naturally in the user's active language.]"
        else:
            user_prompt = f"[User sent an attached {media_type or 'file'} without caption. Inspect and respond naturally in the user's active language.]"

    if quote_context:
        if att_info:
            return f"{quote_context}User: {user_prompt}\n\n{att_info}"
        return f"{quote_context}User: {user_prompt}"
    else:
        if att_info:
            return f"{user_prompt}\n\n{att_info}"
        return user_prompt


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
                raw_msgs = res.json().get("messages", [])
                for m in raw_msgs:
                    if isinstance(m, dict):
                        m["formatted_text"] = format_whatsapp_message_context(m)
                return raw_msgs
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


async def send_whatsapp_document(to: str, file_path: str, caption: Optional[str] = None) -> Dict[str, Any]:
    """Sends a native document file (.pdf, .docx, .zip, etc.) to a WhatsApp number via the bridge."""
    clean_path = os.path.abspath(os.path.expanduser(file_path.strip().strip('"\'')))
    if not os.path.isfile(clean_path):
        return {"status": "error", "message": f"Berkas tidak ditemukan: {clean_path}"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "to": to,
                "file_path": clean_path,
                "caption": caption or os.path.basename(clean_path),
                "filename": os.path.basename(clean_path)
            }
            res = await client.post(f"{WA_BRIDGE_URL}/send-document", json=payload)
            if res.status_code == 200:
                return res.json()
            else:
                try:
                    err_json = res.json()
                    return {"status": "error", "message": err_json.get("message", res.text)}
                except Exception:
                    return {"status": "error", "message": f"HTTP {res.status_code}: {res.text}"}
    except Exception as e:
        return {"status": "error", "message": f"Koneksi WhatsApp bridge error: {str(e)}"}
