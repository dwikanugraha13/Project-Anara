"""
client.py — Telegram Bot API HTTP Client & Outbound Dispatcher for Project Anara.
Anara Standard gateway/platforms/telegram.py.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx

from constants import get_anara_staging_dir
from .formatter import (
    format_telegram_html,
    _rich_normalize_linebreaks,
    has_rich_telegram_constructs,
    split_html_chunks,
    split_message_chunks,
)

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
            "message": "Telegram Bot token not configured.",
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
                        "message": f"Connected as @{bot_info.get('username')}",
                    }
            elif res.status_code in (401, 404):
                return {
                    "status": "error",
                    "error_code": "INVALID_BOT_TOKEN",
                    "is_configured": True,
                    "bot": None,
                    "default_chat_id": chat_id,
                    "admin_ids": admin_ids,
                    "message": "Invalid Telegram Bot token (401/404).",
                }
    except Exception as e:
        logger.warning(f"[TelegramService] getMe error: {e}")

    return {
        "status": "error",
        "error_code": "API_CONNECTION_ERROR",
        "is_configured": True,
        "bot": None,
        "default_chat_id": chat_id,
        "admin_ids": admin_ids,
        "message": "Failed to connect to Telegram Bot API (timeout/network error).",
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
    """Executes a command received from Telegram via unified channel gateway."""
    from core.channel_adapter import ChannelRequest, process_channel_request
    req = ChannelRequest(
        text=command_text,
        channel="telegram",
        channel_id=chat_id or "default",
        user_id="telegram_remote",
        sender_name="User",
    )
    res = await process_channel_request(req)
    if res.text and chat_id:
        await send_telegram_message(text=res.text, chat_id=chat_id, reply_markup=res.reply_markup)
    return {"status": res.status, "result": res.text, "mode": res.mode}


async def _telegram_api_post(
    endpoint: str,
    payload: Dict[str, Any],
    token: str,
    timeout: float = 20.0,
    max_retries: int = 3,
) -> Tuple[int, Dict[str, Any]]:
    """
    Resilient HTTP POST request to Telegram Bot API with automatic exponential backoff,
    network timeout shielding, and 429 Too Many Requests (retry_after) rate-limit handling.
    """
    url = f"{TELEGRAM_API_BASE}/bot{token}/{endpoint}"
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.post(url, json=payload)
                status_code = res.status_code
                try:
                    data = res.json()
                except Exception:
                    data = {"ok": False, "description": res.text}

                if status_code == 200 and data.get("ok"):
                    return status_code, data

                # Handle 429 Rate Limit (Too Many Requests / Flood Control)
                if status_code == 429:
                    retry_after = data.get("parameters", {}).get("retry_after", 1.5)
                    wait_sec = min(max(float(retry_after), 1.0), 5.0)
                    logger.warning(f"[TelegramClient] Rate limited (429) on {endpoint}. Backing off {wait_sec}s...")
                    await asyncio.sleep(wait_sec)
                    continue

                # Don't retry unrecoverable client errors (e.g. 400 Bad Request, 401 Unauthorized, 404 Not Found)
                if status_code in (400, 401, 403, 404):
                    return status_code, data

                # Telegram Server Errors (500, 502, 503, 504) - retry with exponential backoff
                if status_code >= 500 and attempt < max_retries - 1:
                    wait_sec = 0.5 * (2 ** attempt)
                    await asyncio.sleep(wait_sec)
                    continue

                return status_code, data

        except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as net_err:
            if attempt < max_retries - 1:
                wait_sec = 0.5 * (2 ** attempt)
                logger.warning(f"[TelegramClient] Network glitch on {endpoint} (attempt {attempt+1}/{max_retries}): {net_err or 'timeout'}. Retrying in {wait_sec}s...")
                await asyncio.sleep(wait_sec)
            else:
                logger.error(f"[TelegramClient] Network failure calling {endpoint} after {max_retries} attempts: {net_err or 'timeout'}")
                return 0, {"ok": False, "error_code": 0, "description": f"Network error: {net_err or 'timeout'}"}
        except Exception as e:
            logger.error(f"[TelegramClient] Unexpected error calling {endpoint}: {e}")
            return 0, {"ok": False, "error_code": 0, "description": str(e)}

    return 0, {"ok": False, "error_code": 0, "description": "Max retries exceeded"}


async def send_telegram_message(
    text: str,
    chat_id: Optional[str] = None,
    parse_mode: str = "HTML",
    reply_markup: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Sends a text message with semantic chunking, rich constructs, tag balancing, and auto-fallbacks."""
    token = get_stored_telegram_token()
    if not token:
        return {"status": "error", "error_code": "MISSING_BOT_TOKEN", "message": "Telegram Bot token not configured."}

    target_chat = chat_id or get_stored_telegram_chat_id()
    if not target_chat:
        return {"status": "error", "error_code": "MISSING_CHAT_ID", "message": "Target chat ID not specified."}

    # ── 1. SEMANTIC CHUNKING (Threshold: 2000 chars for safe HTML expansion & zero message truncation) ──
    CHUNK_LIMIT = 2000
    if len(text) > CHUNK_LIMIT:
        parts = split_message_chunks(text, max_chars=CHUNK_LIMIT, add_part_headers=True)
        if len(parts) > 1:
            logger.info(f"[TelegramClient] Splitting message ({len(text)} chars) into {len(parts)} parts for chat {target_chat}")
            last_res: Dict[str, Any] = {"status": "ok", "chunks_sent": len(parts)}
            for idx, part in enumerate(parts):
                markup = reply_markup if (idx == len(parts) - 1) else None
                part_res = await send_telegram_message(part, chat_id=target_chat, parse_mode=parse_mode, reply_markup=markup)
                if part_res.get("status") == "ok":
                    last_res = part_res
                else:
                    logger.warning(f"[TelegramClient] Chunk {idx+1}/{len(parts)} delivery issue: {part_res.get('message')}")
                # Safe pacing between consecutive messages to respect Telegram chat rate limit (1 msg/sec)
                if idx < len(parts) - 1:
                    await asyncio.sleep(0.7)
            return last_res

    # ── 2. Native Bot API 10.1 sendRichMessage ──
    if parse_mode == "HTML" and has_rich_telegram_constructs(text):
        normalized_text = _rich_normalize_linebreaks(text)
        if len(normalized_text) <= 4000:
            rich_payload: Dict[str, Any] = {"chat_id": target_chat, "text": normalized_text}
            if reply_markup:
                rich_payload["reply_markup"] = reply_markup
            code, data = await _telegram_api_post("sendRichMessage", rich_payload, token, timeout=15.0)
            if code == 200 and data.get("ok"):
                res_data = data.get("result", {})
                msg_id = res_data.get("message_id") if isinstance(res_data, dict) else None
                return {"status": "ok", "method": "sendRichMessage", "result": res_data, "message_id": msg_id}

    # ── 3. Standard HTML Formatting & Balanced Tag Safety ──
    formatted = format_telegram_html(text) if parse_mode == "HTML" else text

    # Secondary Safety Splitter: If HTML expansion exceeds 4000 chars, split with tag balancing — NEVER truncate!
    if parse_mode == "HTML" and len(formatted) > 4000:
        html_subparts = split_html_chunks(formatted, max_chars=3800)
        if len(html_subparts) > 1:
            logger.info(f"[TelegramClient] HTML expansion exceeded limit ({len(formatted)} chars). Split into {len(html_subparts)} balanced sub-chunks.")
            sub_res: Dict[str, Any] = {"status": "ok", "subchunks_sent": len(html_subparts)}
            for s_idx, sub_chunk in enumerate(html_subparts):
                s_markup = reply_markup if (s_idx == len(html_subparts) - 1) else None
                code, data = await _telegram_api_post("sendMessage", {
                    "chat_id": target_chat,
                    "text": sub_chunk,
                    "parse_mode": "HTML",
                    **({"reply_markup": s_markup} if s_markup else {})
                }, token, timeout=15.0)
                if code == 200 and data.get("ok"):
                    res_data = data.get("result", {})
                    msg_id = res_data.get("message_id") if isinstance(res_data, dict) else None
                    sub_res = {"status": "ok", "method": "sendMessage_HTML_Subchunk", "result": res_data, "message_id": msg_id}
                if s_idx < len(html_subparts) - 1:
                    await asyncio.sleep(0.7)
            return sub_res

    # Send HTML message
    payload: Dict[str, Any] = {
        "chat_id": target_chat,
        "text": formatted,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    code, data = await _telegram_api_post("sendMessage", payload, token, timeout=15.0)
    if code == 200 and data.get("ok"):
        res_data = data.get("result", {})
        msg_id = res_data.get("message_id") if isinstance(res_data, dict) else None
        return {"status": "ok", "method": "sendMessage_HTML", "result": res_data, "message_id": msg_id}

    logger.warning(f"[TelegramClient] HTML sendMessage returned {code}: {data.get('description', '')}. Trying plain text fallback...")

    # ── 4. Fallback: plain text (preserves reply_markup so interactive buttons are never lost) ──
    clean_plain = text.replace("<details>", "").replace("</details>", "").replace("<summary>", "").replace("</summary>", "")
    if len(clean_plain) > 4000:
        plain_subparts = split_message_chunks(clean_plain, max_chars=3800, add_part_headers=False)
        sub_res: Dict[str, Any] = {"status": "ok", "plain_subchunks_sent": len(plain_subparts)}
        for p_idx, p_chunk in enumerate(plain_subparts):
            p_markup = reply_markup if (p_idx == len(plain_subparts) - 1) else None
            p_payload: Dict[str, Any] = {"chat_id": target_chat, "text": p_chunk}
            if p_markup:
                p_payload["reply_markup"] = p_markup
            p_code, p_data = await _telegram_api_post("sendMessage", p_payload, token, timeout=15.0)
            if p_code == 200 and p_data.get("ok"):
                res_data = p_data.get("result", {})
                msg_id = res_data.get("message_id") if isinstance(res_data, dict) else None
                sub_res = {"status": "ok", "method": "sendMessage_Plain_Subchunk", "result": res_data, "message_id": msg_id}
            if p_idx < len(plain_subparts) - 1:
                await asyncio.sleep(0.7)
        return sub_res

    plain_payload: Dict[str, Any] = {"chat_id": target_chat, "text": clean_plain}
    if reply_markup:
        plain_payload["reply_markup"] = reply_markup

    p_code, p_data = await _telegram_api_post("sendMessage", plain_payload, token, timeout=15.0)
    if p_code == 200 and p_data.get("ok"):
        res_data = p_data.get("result", {})
        msg_id = res_data.get("message_id") if isinstance(res_data, dict) else None
        return {"status": "ok", "method": "sendMessage_Plain", "result": res_data, "message_id": msg_id}

    logger.error(f"[TelegramClient] Plain sendMessage failed {p_code}: {p_data.get('description', '')}")
    return {"status": "error", "error_code": "SEND_MESSAGE_FAILED", "message": f"Failed to send Telegram message: {str(p_data.get('description', ''))[:120]}"}


async def send_telegram_document(
    file_path: str,
    chat_id: Optional[str] = None,
    caption: Optional[str] = None
) -> Dict[str, Any]:
    """Sends a native document file to Telegram chat."""
    token = get_stored_telegram_token()
    if not token:
        return {"status": "error", "error_code": "MISSING_BOT_TOKEN", "message": "Telegram Bot token not configured."}

    target_chat = chat_id or get_stored_telegram_chat_id()
    if not target_chat:
        return {"status": "error", "error_code": "MISSING_CHAT_ID", "message": "Target chat ID not specified."}

    clean_path = os.path.abspath(os.path.expanduser(file_path.strip().strip('"\'')))
    if not os.path.isfile(clean_path):
        return {"status": "error", "error_code": "FILE_NOT_FOUND", "message": f"Document file not found: {clean_path}"}

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
            return {"status": "error", "error_code": "SEND_DOCUMENT_FAILED", "message": res.text[:120]}
    except Exception as e:
        return {"status": "error", "error_code": "SEND_DOCUMENT_EXCEPTION", "message": str(e)}


async def send_telegram_voice(
    file_path: str,
    chat_id: Optional[str] = None,
    caption: Optional[str] = None
) -> Dict[str, Any]:
    """Sends a native voice note bubble (.ogg Opus) to Telegram chat."""
    token = get_stored_telegram_token()
    if not token:
        return {"status": "error", "error_code": "MISSING_BOT_TOKEN", "message": "Telegram Bot token not configured."}

    target_chat = chat_id or get_stored_telegram_chat_id()
    if not target_chat:
        return {"status": "error", "error_code": "MISSING_CHAT_ID", "message": "Target chat ID not specified."}

    clean_path = os.path.abspath(os.path.expanduser(file_path.strip().strip('"\'')))
    if not os.path.isfile(clean_path):
        return {"status": "error", "error_code": "FILE_NOT_FOUND", "message": f"Voice file not found: {clean_path}"}

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
            return {"status": "error", "error_code": "SEND_VOICE_FAILED", "message": res.text[:120]}
    except Exception as e:
        return {"status": "error", "error_code": "SEND_VOICE_EXCEPTION", "message": str(e)}


async def send_telegram_photo(
    photo: Any = None,
    chat_id: Optional[str] = None,
    caption: Optional[str] = None,
    file_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Sends a photo directly into Telegram chat from URL or local file path."""
    photo_target = photo or file_path
    token = get_stored_telegram_token()
    if not token:
        return {"status": "error", "error_code": "MISSING_BOT_TOKEN", "message": "Telegram Bot token not configured."}

    target_chat = chat_id or get_stored_telegram_chat_id()
    if not target_chat:
        return {"status": "error", "error_code": "MISSING_CHAT_ID", "message": "Target chat ID not specified."}

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendPhoto"

    try:
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            if isinstance(photo_target, str) and (photo_target.startswith("http://") or photo_target.startswith("https://")):
                data = {"chat_id": target_chat, "photo": photo_target}
                if caption:
                    data["caption"] = caption[:1024]
                res = await client.post(url, data=data)
                if res.status_code == 200 and res.json().get("ok"):
                    return {"status": "ok", "message_id": res.json()["result"]["message_id"]}
            elif isinstance(photo_target, str) and os.path.isfile(photo_target):
                with open(photo_target, "rb") as f:
                    file_bytes = f.read()
                files = {"photo": (os.path.basename(photo_target), file_bytes)}
                data = {"chat_id": target_chat}
                if caption:
                    data["caption"] = caption[:1024]
                res = await client.post(url, data=data, files=files)
                if res.status_code == 200 and res.json().get("ok"):
                    return {"status": "ok", "message_id": res.json()["result"]["message_id"]}
            return {"status": "error", "error_code": "SEND_PHOTO_FAILED", "message": "Failed to send photo: Invalid source or server error."}
    except Exception as e:
        return {"status": "error", "error_code": "SEND_PHOTO_EXCEPTION", "message": str(e)}


async def send_telegram_video(
    video: Any,
    chat_id: Optional[str] = None,
    caption: Optional[str] = None
) -> Dict[str, Any]:
    """Sends a video directly into Telegram chat."""
    token = get_stored_telegram_token()
    if not token:
        return {"status": "error", "error_code": "MISSING_BOT_TOKEN", "message": "Telegram Bot token not configured."}

    target_chat = chat_id or get_stored_telegram_chat_id()
    if not target_chat:
        return {"status": "error", "error_code": "MISSING_CHAT_ID", "message": "Target chat ID not specified."}

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
            return {"status": "error", "error_code": "SEND_VIDEO_FAILED", "message": "Failed to send video: Invalid source or server error."}
    except Exception as e:
        return {"status": "error", "error_code": "SEND_VIDEO_EXCEPTION", "message": str(e)}


async def answer_telegram_callback_query(callback_query_id: str, text: Optional[str] = None):
    """Acknowledges an inline keyboard button press."""
    token = get_stored_telegram_token()
    if not token or not callback_query_id:
        return
    await _telegram_api_post(
        "answerCallbackQuery",
        {"callback_query_id": callback_query_id, "text": text or ""},
        token,
        timeout=5.0,
        max_retries=2,
    )


async def edit_telegram_message(chat_id: str, message_id: int, text: str, reply_markup: Optional[Dict[str, Any]] = None):
    """Updates the content or buttons of an existing message."""
    token = get_stored_telegram_token()
    if not token:
        return False
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": format_telegram_html(text),
        "parse_mode": "HTML",
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    code, data = await _telegram_api_post("editMessageText", payload, token, timeout=10.0, max_retries=2)
    return code == 200 and data.get("ok", False)


async def delete_telegram_message(chat_id: str, message_id: int):
    """Deletes an ephemeral or superseded message with automatic retry."""
    token = get_stored_telegram_token()
    if not token:
        return False
    payload = {"chat_id": chat_id, "message_id": message_id}
    code, data = await _telegram_api_post("deleteMessage", payload, token, timeout=6.0, max_retries=3)
    return code == 200 and data.get("ok", False)


async def send_telegram_chat_action(chat_id: str, action: str = "typing"):
    """Displays 'typing', 'upload_document', or 'upload_photo' status."""
    token = get_stored_telegram_token()
    if not token or not chat_id:
        return
    await _telegram_api_post(
        "sendChatAction",
        {"chat_id": chat_id, "action": action},
        token,
        timeout=5.0,
        max_retries=1,
    )


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
        {"command": "plan", "description": "Formulate execution plan without direct mutating actions"},
        {"command": "stop", "description": "Halt execution or cancel pending action plan"},
        {"command": "model", "description": "Select or switch active AI model"},
        {"command": "workspace", "description": "Inspect or lock active workspace directory"},
        {"command": "status", "description": "Inspect Anara system status and telemetry"},
        {"command": "memory", "description": "View persistent memory facts and user profile"},
        {"command": "skills", "description": "View active skills library and capabilities"},
        {"command": "clear", "description": "Clear dialogue session history"},
        {"command": "help", "description": "Show universal commands manual and help guide"},
    ]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json={"commands": commands})
            return res.status_code == 200 and res.json().get("ok")
    except Exception as e:
        logger.debug(f"[TelegramService] setMyCommands notice: {e}")
    return False
