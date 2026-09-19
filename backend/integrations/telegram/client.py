"""
client.py — Telegram Bot API HTTP Client & Outbound Dispatcher for Project Anara.
Anara Standard gateway/platforms/telegram.py.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

from constants import get_anara_staging_dir
from .formatter import format_telegram_html, _rich_normalize_linebreaks, has_rich_telegram_constructs

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
_recent_telegram_messages: List[Dict[str, Any]] = []


def get_stored_telegram_token() -> Optional[str]:
    """Retrieves the Telegram bot token from memory settings or env."""
    from memory import memory_engine
    token = memory_engine.get_app_setting("telegram_bot_token")
    if token:
        return token.strip()
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or None


def get_stored_telegram_chat_id() -> Optional[str]:
    """Retrieves default Telegram target chat ID."""
    from memory import memory_engine
    chat_id = memory_engine.get_app_setting("telegram_chat_id")
    if chat_id:
        return chat_id.strip()
    return os.environ.get("TELEGRAM_CHAT_ID", "").strip() or None


def get_stored_telegram_admin_ids() -> Optional[str]:
    """Retrieves allowed Telegram admin user IDs for approval security."""
    from memory import memory_engine
    ids = memory_engine.get_app_setting("telegram_admin_ids")
    if ids:
        return ids.strip()
    return os.environ.get("TELEGRAM_ADMIN_IDS", "").strip() or None


def save_telegram_config(token: str, default_chat_id: Optional[str] = None, admin_ids: Optional[str] = None) -> bool:
    """Saves telegram configuration to database settings."""
    from memory import memory_engine
    if token:
        memory_engine.set_app_setting("telegram_bot_token", token.strip())
    if default_chat_id is not None:
        memory_engine.set_app_setting("telegram_chat_id", default_chat_id.strip())
    if admin_ids is not None:
        memory_engine.set_app_setting("telegram_admin_ids", admin_ids.strip())
    return True


async def get_telegram_status() -> Dict[str, Any]:
    """Validates Telegram token by querying getMe."""
    token = get_stored_telegram_token()
    if not token:
        return {
            "status": "disconnected",
            "is_configured": False,
            "bot": None,
            "default_chat_id": None,
            "message": "Token Telegram Bot belum diatur.",
        }

    chat_id = get_stored_telegram_chat_id()
    admin_ids = get_stored_telegram_admin_ids()
    url = f"{TELEGRAM_API_BASE}/bot{token}/getMe"

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json()
                if data.get("ok"):
                    bot_info = data["result"]
                    return {
                        "status": "connected",
                        "is_configured": True,
                        "bot": {
                            "id": bot_info["id"],
                            "first_name": bot_info.get("first_name"),
                            "username": bot_info.get("username"),
                        },
                        "default_chat_id": chat_id,
                        "admin_ids": admin_ids,
                        "message": f"Terhubung sebagai @{bot_info.get('username')}",
                    }
            elif res.status_code in (401, 404):
                return {
                    "status": "error",
                    "is_configured": True,
                    "bot": None,
                    "default_chat_id": chat_id,
                    "admin_ids": admin_ids,
                    "message": "Token Telegram Bot tidak valid (401/404).",
                }
    except Exception as e:
        logger.warning(f"[TelegramService] getMe error: {e}")

    return {
        "status": "error",
        "is_configured": True,
        "bot": None,
        "default_chat_id": chat_id,
        "admin_ids": admin_ids,
        "message": "Gagal menghubungi Telegram Bot API (timeout/network error).",
    }


async def get_telegram_messages(limit: int = 10) -> List[Dict[str, Any]]:
    """Returns recently captured Telegram messages."""
    return _recent_telegram_messages[:limit]


async def get_recent_telegram_updates(limit: int = 15) -> List[Dict[str, Any]]:
    """Polls recent updates via getUpdates."""
    token = get_stored_telegram_token()
    if not token:
        return []
    url = f"{TELEGRAM_API_BASE}/bot{token}/getUpdates?limit={limit}"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(url)
            if res.status_code == 200:
                d = res.json()
                if d.get("ok"):
                    return d.get("result", [])
    except Exception as e:
        logger.debug(f"[TelegramService] getUpdates notice: {e}")
    return []


async def execute_remote_telegram_command(command_text: str, chat_id: Optional[str] = None) -> Dict[str, Any]:
    """Executes a command received from Telegram."""
    from providers import call_universal_chat_model, get_active_model_id
    sys_inst = (
        "Kamu adalah Anara, AI assistant yang terhubung melalui Telegram. "
        "Jawab dengan cerdas, ramah, dan ringkas. Gunakan format yang rapi."
    )
    res = await call_universal_chat_model(
        model_id=get_active_model_id(),
        user_prompt=command_text,
        system_instruction=sys_inst,
        max_tokens=450,
        temperature=0.7,
        read_only=False
    )
    if res and chat_id:
        await send_telegram_message(text=res, chat_id=chat_id)
    return {"status": "success", "result": res}


async def send_telegram_message(
    text: str,
    chat_id: Optional[str] = None,
    parse_mode: str = "HTML",
    reply_markup: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Sends a text message with semantic chunking, rich constructs, and auto-fallbacks."""
    token = get_stored_telegram_token()
    if not token:
        return {"status": "error", "message": "Token Telegram Bot belum diatur."}

    target_chat = chat_id or get_stored_telegram_chat_id()
    if not target_chat:
        return {"status": "error", "message": "Chat ID tujuan belum ditentukan."}

    # ── SEMANTIC CHUNKING (Threshold: 3000 chars for safe HTML expansion & unlimited parts) ──
    if len(text) > 3000:
        try:
            from .formatter import split_message_chunks
            parts = split_message_chunks(text, max_chars=3000, add_part_headers=True)
            if len(parts) > 1:
                logger.info(f"[TelegramClient] Splitting message ({len(text)} chars) into {len(parts)} parts for chat {target_chat}")
                last_res: Dict[str, Any] = {"status": "ok", "chunks_sent": len(parts)}
                for idx, part in enumerate(parts):
                    markup = reply_markup if (idx == len(parts) - 1) else None
                    last_res = await send_telegram_message(part, chat_id=target_chat, parse_mode=parse_mode, reply_markup=markup)
                    if idx < len(parts) - 1:
                        await asyncio.sleep(0.35)
                return last_res
        except Exception as chunk_err:
            logger.warning(f"[TelegramClient] Chunking error: {chunk_err}")

    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Native Bot API 10.1 sendRichMessage
        if parse_mode == "HTML" and has_rich_telegram_constructs(text):
            try:
                rich_url = f"{TELEGRAM_API_BASE}/bot{token}/sendRichMessage"
                normalized_text = _rich_normalize_linebreaks(text)
                rich_payload: Dict[str, Any] = {"chat_id": target_chat, "text": normalized_text}
                if reply_markup:
                    rich_payload["reply_markup"] = reply_markup
                rich_res = await client.post(rich_url, json=rich_payload)
                if rich_res.status_code == 200 and rich_res.json().get("ok"):
                    res_json = rich_res.json()
                    res_data = res_json.get("result", {})
                    msg_id = res_data.get("message_id") if isinstance(res_data, dict) else None
                    return {"status": "ok", "method": "sendRichMessage", "result": res_data, "message_id": msg_id}
            except Exception:
                pass

        # 2. Standard sendMessage with format_telegram_html
        formatted = format_telegram_html(text) if parse_mode == "HTML" else text
        url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
        payload: Dict[str, Any] = {
            "chat_id": target_chat,
            "text": formatted,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        res = await client.post(url, json=payload)
        if res.status_code == 200 and res.json().get("ok"):
            res_json = res.json()
            res_data = res_json.get("result", {})
            msg_id = res_data.get("message_id") if isinstance(res_data, dict) else None
            return {"status": "ok", "method": "sendMessage_HTML", "result": res_data, "message_id": msg_id}

        logger.warning(f"[TelegramClient] HTML sendMessage returned {res.status_code}: {res.text}. Trying plain text fallback...")
        # 3. Fallback: plain text (preserves reply_markup so interactive buttons are never lost)
        clean_plain = text.replace("<details>", "").replace("</details>", "").replace("<summary>", "").replace("</summary>", "")
        plain_payload: Dict[str, Any] = {"chat_id": target_chat, "text": clean_plain}
        if reply_markup:
            plain_payload["reply_markup"] = reply_markup
        res_plain = await client.post(url, json=plain_payload)
        if res_plain.status_code == 200 and res_plain.json().get("ok"):
            res_json = res_plain.json()
            res_data = res_json.get("result", {})
            msg_id = res_data.get("message_id") if isinstance(res_data, dict) else None
            return {"status": "ok", "method": "sendMessage_Plain", "result": res_data, "message_id": msg_id}

        logger.error(f"[TelegramClient] Plain sendMessage failed {res_plain.status_code}: {res_plain.text}")
        return {"status": "error", "message": f"Gagal mengirim pesan Telegram: {res_plain.text[:120]}"}


async def send_telegram_document(
    file_path: str,
    chat_id: Optional[str] = None,
    caption: Optional[str] = None
) -> Dict[str, Any]:
    """Sends a native document file to Telegram chat."""
    token = get_stored_telegram_token()
    if not token:
        return {"status": "error", "message": "Token Telegram Bot belum diatur."}

    target_chat = chat_id or get_stored_telegram_chat_id()
    if not target_chat:
        return {"status": "error", "message": "Chat ID tujuan belum ditentukan."}

    clean_path = os.path.abspath(os.path.expanduser(file_path.strip().strip('"\'')))
    if not os.path.isfile(clean_path):
        return {"status": "error", "message": f"Berkas tidak ditemukan: {clean_path}"}

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendDocument"
    filename = os.path.basename(clean_path)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(clean_path, "rb") as f:
                file_bytes = f.read()
            files = {"document": (filename, file_bytes)}
            data = {"chat_id": target_chat}
            if caption:
                data["caption"] = caption[:1000]

            res = await client.post(url, data=data, files=files)
            if res.status_code == 200 and res.json().get("ok"):
                return {"status": "ok", "message_id": res.json()["result"]["message_id"], "filename": filename}
            return {"status": "error", "message": res.text[:120]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def send_telegram_voice(
    file_path: str,
    chat_id: Optional[str] = None,
    caption: Optional[str] = None
) -> Dict[str, Any]:
    """Sends a native voice note bubble (.ogg Opus) to Telegram chat."""
    token = get_stored_telegram_token()
    if not token:
        return {"status": "error", "message": "Token Telegram Bot belum diatur."}

    target_chat = chat_id or get_stored_telegram_chat_id()
    if not target_chat:
        return {"status": "error", "message": "Chat ID tujuan belum ditentukan."}

    clean_path = os.path.abspath(os.path.expanduser(file_path.strip().strip('"\'')))
    if not os.path.isfile(clean_path):
        return {"status": "error", "message": f"Berkas suara tidak ditemukan: {clean_path}"}

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendVoice"
    filename = os.path.basename(clean_path)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(clean_path, "rb") as f:
                file_bytes = f.read()
            files = {"voice": (filename, file_bytes)}
            data = {"chat_id": target_chat}
            if caption:
                data["caption"] = caption[:1000]

            res = await client.post(url, data=data, files=files)
            if res.status_code == 200 and res.json().get("ok"):
                return {"status": "ok", "message_id": res.json()["result"]["message_id"], "filename": filename}
            return {"status": "error", "message": res.text[:120]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def send_telegram_photo(
    photo: Any,
    chat_id: Optional[str] = None,
    caption: Optional[str] = None
) -> Dict[str, Any]:
    """Sends a photo directly into Telegram chat from URL or local file path."""
    token = get_stored_telegram_token()
    if not token:
        return {"status": "error", "message": "Token Telegram Bot belum diatur."}

    target_chat = chat_id or get_stored_telegram_chat_id()
    if not target_chat:
        return {"status": "error", "message": "Chat ID tujuan belum ditentukan."}

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendPhoto"

    try:
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            if isinstance(photo, str) and (photo.startswith("http://") or photo.startswith("https://")):
                data = {"chat_id": target_chat, "photo": photo}
                if caption:
                    data["caption"] = caption[:1024]
                res = await client.post(url, data=data)
                if res.status_code == 200 and res.json().get("ok"):
                    return {"status": "ok", "message_id": res.json()["result"]["message_id"]}
            elif isinstance(photo, str) and os.path.isfile(photo):
                with open(photo, "rb") as f:
                    file_bytes = f.read()
                files = {"photo": (os.path.basename(photo), file_bytes)}
                data = {"chat_id": target_chat}
                if caption:
                    data["caption"] = caption[:1024]
                res = await client.post(url, data=data, files=files)
                if res.status_code == 200 and res.json().get("ok"):
                    return {"status": "ok", "message_id": res.json()["result"]["message_id"]}
            return {"status": "error", "message": "Gagal mengirim foto."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def send_telegram_video(
    video: Any,
    chat_id: Optional[str] = None,
    caption: Optional[str] = None
) -> Dict[str, Any]:
    """Sends a video directly into Telegram chat."""
    token = get_stored_telegram_token()
    if not token:
        return {"status": "error", "message": "Token Telegram Bot belum diatur."}

    target_chat = chat_id or get_stored_telegram_chat_id()
    if not target_chat:
        return {"status": "error", "message": "Chat ID tujuan belum ditentukan."}

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendVideo"

    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            if isinstance(video, str) and (video.startswith("http://") or video.startswith("https://")):
                data = {"chat_id": target_chat, "video": video}
                if caption:
                    data["caption"] = caption[:1024]
                res = await client.post(url, data=data)
                if res.status_code == 200 and res.json().get("ok"):
                    return {"status": "ok", "message_id": res.json()["result"]["message_id"]}
            elif isinstance(video, str) and os.path.isfile(video):
                with open(video, "rb") as f:
                    file_bytes = f.read()
                files = {"video": (os.path.basename(video), file_bytes)}
                data = {"chat_id": target_chat}
                if caption:
                    data["caption"] = caption[:1024]
                res = await client.post(url, data=data, files=files)
                if res.status_code == 200 and res.json().get("ok"):
                    return {"status": "ok", "message_id": res.json()["result"]["message_id"]}
            return {"status": "error", "message": "Gagal mengirim video."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def answer_telegram_callback_query(callback_query_id: str, text: Optional[str] = None):
    """Acknowledges an inline keyboard button press."""
    token = get_stored_telegram_token()
    if not token or not callback_query_id:
        return
    url = f"{TELEGRAM_API_BASE}/bot{token}/answerCallbackQuery"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json={"callback_query_id": callback_query_id, "text": text or ""})
    except Exception:
        pass


async def edit_telegram_message(chat_id: str, message_id: int, text: str, reply_markup: Optional[Dict[str, Any]] = None):
    """Updates the content or buttons of an existing message."""
    token = get_stored_telegram_token()
    if not token:
        return False
    url = f"{TELEGRAM_API_BASE}/bot{token}/editMessageText"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": format_telegram_html(text),
                "parse_mode": "HTML",
            }
            if reply_markup is not None:
                payload["reply_markup"] = reply_markup
            res = await client.post(url, json=payload)
            return res.status_code == 200 and res.json().get("ok")
    except Exception:
        return False


async def delete_telegram_message(chat_id: str, message_id: int):
    """Deletes an ephemeral or superseded message."""
    token = get_stored_telegram_token()
    if not token:
        return False
    url = f"{TELEGRAM_API_BASE}/bot{token}/deleteMessage"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.post(url, json={"chat_id": chat_id, "message_id": message_id})
            return res.status_code == 200 and res.json().get("ok")
    except Exception:
        return False


async def send_telegram_chat_action(chat_id: str, action: str = "typing"):
    """Displays 'typing', 'upload_document', or 'upload_photo' status."""
    token = get_stored_telegram_token()
    if not token or not chat_id:
        return
    url = f"{TELEGRAM_API_BASE}/bot{token}/sendChatAction"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json={"chat_id": chat_id, "action": action})
    except Exception:
        pass


async def download_telegram_attachment(file_id: str, destination_filename: str) -> Optional[str]:
    """Downloads an inbound file from Telegram servers to the local staging folder."""
    token = get_stored_telegram_token()
    if not token:
        return None

    try:
        staging_dir = str(get_anara_staging_dir("telegram_uploads"))
        os.makedirs(staging_dir, exist_ok=True)
        local_path = os.path.join(staging_dir, destination_filename)

        async with httpx.AsyncClient(timeout=30.0) as client:
            get_file_url = f"{TELEGRAM_API_BASE}/bot{token}/getFile?file_id={file_id}"
            res = await client.get(get_file_url)
            if res.status_code != 200 or not res.json().get("ok"):
                return None

            file_path_on_tg = res.json()["result"]["file_path"]
            dl_url = f"{TELEGRAM_API_BASE}/file/bot{token}/{file_path_on_tg}"
            dl_res = await client.get(dl_url)
            if dl_res.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(dl_res.content)
                return local_path
    except Exception as e:
        logger.warning(f"[TelegramService] Download error for {destination_filename}: {e}")
    return None


async def setup_telegram_bot_commands() -> bool:
    """Registers standard bot commands with Telegram."""
    token = get_stored_telegram_token()
    if not token:
        return False
    url = f"{TELEGRAM_API_BASE}/bot{token}/setMyCommands"
    commands = [
        {"command": "plan", "description": "Susun rencana kerja arsitektur tanpa eksekusi langsung"},
        {"command": "stop", "description": "Batalkan rencana kerja yang sedang menunggu persetujuan"},
        {"command": "model", "description": "Pilih dan ganti model AI aktif (Multi-Provider)"},
        {"command": "workspace", "description": "Lihat atau kunci bot ke folder project lokal PC"},
        {"command": "status", "description": "Cek kesehatan sistem Anara & status AI"},
        {"command": "memory", "description": "Lihat ringkasan memori dan profil tersimpan"},
        {"command": "skills", "description": "Lihat daftar keahlian aktif (Anara Skill Library)"},
        {"command": "clear", "description": "Bersihkan riwayat percakapan sesi ini"},
        {"command": "help", "description": "Panduan lengkap penggunaan bot Anara"},
    ]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json={"commands": commands})
            return res.status_code == 200 and res.json().get("ok")
    except Exception as e:
        logger.debug(f"[TelegramService] setMyCommands notice: {e}")
    return False
