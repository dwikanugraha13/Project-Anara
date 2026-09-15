import asyncio
import html
import logging
import os
import re
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"

_recent_telegram_messages: List[Dict[str, Any]] = []
_last_update_id: int = 0


def get_stored_telegram_token() -> Optional[str]:
    """Retrieves the Telegram bot token from memory_service settings or env."""
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
    """Tests the configured bot token against Telegram getMe API."""
    token = get_stored_telegram_token()
    if not token:
        return {
            "status": "disconnected",
            "is_configured": False,
            "bot": None,
            "message": "Token Telegram Bot belum diatur.",
        }

    url = f"{TELEGRAM_API_BASE}/bot{token}/getMe"
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json()
                if data.get("ok"):
                    bot_info = data.get("result", {})
                    return {
                        "status": "connected",
                        "is_configured": True,
                        "bot": {
                            "id": bot_info.get("id"),
                            "username": bot_info.get("username"),
                            "first_name": bot_info.get("first_name"),
                        },
                        "default_chat_id": get_stored_telegram_chat_id(),
                        "admin_ids": get_stored_telegram_admin_ids(),
                        "unread_count": len(_recent_telegram_messages),
                    }
                else:
                    return {
                        "status": "error",
                        "is_configured": True,
                        "bot": None,
                        "default_chat_id": get_stored_telegram_chat_id(),
                        "admin_ids": get_stored_telegram_admin_ids(),
                        "message": data.get("description", "Token tidak valid."),
                    }
            else:
                return {
                    "status": "error",
                    "is_configured": True,
                    "bot": None,
                    "default_chat_id": get_stored_telegram_chat_id(),
                    "admin_ids": get_stored_telegram_admin_ids(),
                    "message": f"HTTP {res.status_code}: Token salah.",
                }
    except Exception as e:
        logger.warning(f"[TelegramService] getMe error: {e}")
        return {
            "status": "disconnected",
            "is_configured": True,
            "bot": None,
            "default_chat_id": get_stored_telegram_chat_id(),
            "admin_ids": get_stored_telegram_admin_ids(),
            "message": f"Koneksi error: {str(e)}",
        }


async def get_telegram_messages(limit: int = 10) -> List[Dict[str, Any]]:
    """Fetches recent updates from Telegram bot."""
    global _last_update_id, _recent_telegram_messages
    token = get_stored_telegram_token()
    if not token:
        return _recent_telegram_messages[:limit]

    url = f"{TELEGRAM_API_BASE}/bot{token}/getUpdates"
    params = {"limit": str(limit), "offset": str(_last_update_id + 1)}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(url, params=params)
            if res.status_code == 200:
                data = res.json()
                if data.get("ok"):
                    updates = data.get("result", [])
                    for u in updates:
                        up_id = u.get("update_id", 0)
                        if up_id > _last_update_id:
                            _last_update_id = up_id

                        msg = u.get("message") or u.get("edited_message")
                        if msg and msg.get("text"):
                            sender = msg.get("from", {})
                            chat = msg.get("chat", {})
                            sender_name = (
                                sender.get("first_name", "") + " " + sender.get("last_name", "")
                            ).strip() or sender.get("username", "Pengguna Telegram")
                            
                            msg_obj = {
                                "id": msg.get("message_id"),
                                "chat_id": chat.get("id"),
                                "sender": sender_name,
                                "username": sender.get("username"),
                                "text": msg.get("text"),
                                "date": msg.get("date"),
                                "is_group": chat.get("type") in ["group", "supergroup"],
                            }
                            _recent_telegram_messages.insert(0, msg_obj)
                            if len(_recent_telegram_messages) > 40:
                                _recent_telegram_messages.pop()
    except Exception as e:
        logger.warning(f"[TelegramService] getUpdates error: {e}")

    return _recent_telegram_messages[:limit]


# Alias for tool execution compatibility
get_recent_telegram_updates = get_telegram_messages


async def execute_remote_telegram_command(command_text: str, chat_id: str) -> str:
    """Executes a remote command sent via Telegram Bot on the local PC using Anara Agent."""
    from providers import call_universal_chat_model, get_active_model_id
    from cognition import get_soul_prompt
    logger.info(f"[TelegramGateway] Remote command from chat {chat_id}: '{command_text}'")
    
    soul = get_soul_prompt(mode="chat")
    sys_instruction = (
        f"{soul}\n\n"
        "[KONTEKS REMOTE TELEGRAM]:\n"
        "Kamu sedang dieksekusi secara remote via Telegram Bot.\n"
        "Lakukan tugas pengguna dengan memanggil tool yang relevan jika diperlukan (baca file, tulis file, riset web, to-do list).\n"
        "Berikan balasan yang jelas, ramah, dan terstruktur untuk dibaca di Telegram."
    )
    selected_model = get_active_model_id()
    try:
        reply = await call_universal_chat_model(
            model_id=selected_model,
            user_prompt=command_text,
            system_instruction=sys_instruction,
            max_tokens=450,
            temperature=0.7
        )
        final_reply = reply or "Perintah telah diproses oleh Anara Agent di PC."
        await send_telegram_message(text=final_reply, chat_id=chat_id)
        return final_reply
    except Exception as e:
        err_msg = f"Gagal mengeksekusi perintah di PC: {str(e)}"
        await send_telegram_message(text=err_msg, chat_id=chat_id)
        return err_msg


def format_telegram_html(text: str) -> str:
    """
    Converts markdown and mixed HTML into Telegram Bot API valid HTML entities:
    - Supported tags: <b>, <i>, <code>, <s>, <u>, <pre>, <a href="...">
    - Converts Markdown **bold** -> <b>bold</b>
    - Converts Markdown *italic* -> <i>italic</i>
    - Converts Markdown ```code``` -> <pre><code>code</code></pre>
    - Converts Markdown `code` -> <code>code</code>
    - Converts Markdown [text](url) -> <a href="url">text</a>
    - Safely escapes stray &, <, > that are not part of valid Telegram HTML tags.
    """
    if not text:
        return ""

    # 1. Placeholders for code blocks
    code_blocks = []
    def _cb_block(m):
        code_blocks.append(m.group(1))
        return f"___CODE_BLOCK_{len(code_blocks)-1}___"

    s = re.sub(r"```(?:[a-zA-Z0-9_\-\+\.]+)?\n?([\s\S]*?)```", _cb_block, text)

    # 2. Placeholders for inline code
    inline_codes = []
    def _cb_inline(m):
        inline_codes.append(m.group(1))
        return f"___INLINE_CODE_{len(inline_codes)-1}___"

    s = re.sub(r"`([^`\n]+)`", _cb_inline, s)

    # 3. Protect existing valid Telegram HTML tags
    valid_tags = []
    def _cb_tag(m):
        valid_tags.append(m.group(0))
        return f"___VALID_TAG_{len(valid_tags)-1}___"

    tag_pat = r"</?(?:b|i|u|s|code|pre|blockquote|a)(?:\s+href=[\"\'][^\"\']*[\"\'])?\s*/?>"
    s = re.sub(tag_pat, _cb_tag, s, flags=re.IGNORECASE)

    # 4. Escape remaining HTML entities (&, <, >)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # 5. Restore valid tags
    for i, t in enumerate(valid_tags):
        s = s.replace(f"___VALID_TAG_{i}___", t)

    # 6. Convert Markdown bold **text** -> <b>text</b>
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s, flags=re.DOTALL)

    # 7. Convert Markdown headers (### Header) -> <b>Header</b>
    s = re.sub(r"(?m)^#{1,6}\s*(.+)$", r"<b>\1</b>", s)

    # 8. Convert Markdown links [text](url) -> <a href=\"url\">text</a>
    s = re.sub(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)", r'<a href="\2">\1</a>', s)

    # 9. Restore code blocks & inline codes (escaped)
    for i, code in enumerate(code_blocks):
        clean = html.escape(code.strip())
        s = s.replace(f"___CODE_BLOCK_{i}___", f"<pre><code>{clean}</code></pre>")

    for i, code in enumerate(inline_codes):
        clean = html.escape(code.strip())
        s = s.replace(f"___INLINE_CODE_{i}___", f"<code>{clean}</code>")

    return s


async def send_telegram_message(
    text: str,
    chat_id: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Sends a text message to a specific or default Telegram chat ID with HTML formatting and auto-fallback."""
    token = get_stored_telegram_token()
    if not token:
        return {"status": "error", "message": "Token Telegram Bot belum diatur."}

    target_chat = chat_id or get_stored_telegram_chat_id()
    if not target_chat:
        if _recent_telegram_messages:
            target_chat = str(_recent_telegram_messages[0].get("chat_id"))
        else:
            return {"status": "error", "message": "Chat ID tujuan belum ditentukan. Kirim pesan ke bot terlebih dahulu."}

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    formatted_text = format_telegram_html(text)

    payload = {
        "chat_id": target_chat,
        "text": formatted_text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                data = res.json()
                if data.get("ok"):
                    logger.info(f"[TelegramService] Message sent to {target_chat}: {text[:50]!r}")
                    return {"status": "ok", "message_id": data["result"]["message_id"], "recipient": target_chat}

            # If HTML parsing error or failed, fallback to plain text stripped of HTML tags
            err_desc = res.json().get("description", "") if res.status_code != 200 else ""
            logger.warning(f"[TelegramService] HTML send failed ({res.status_code}: {err_desc}). Retrying with plain text fallback...")
            plain_text = re.sub(r"<[^>]+>", "", text)
            fallback_payload = {
                "chat_id": target_chat,
                "text": plain_text,
            }
            if reply_markup:
                fallback_payload["reply_markup"] = reply_markup

            fallback_res = await client.post(url, json=fallback_payload)
            if fallback_res.status_code == 200:
                fb_data = fallback_res.json()
                if fb_data.get("ok"):
                    return {"status": "ok", "message_id": fb_data["result"]["message_id"], "recipient": target_chat}

            return {"status": "error", "message": f"HTTP {res.status_code}: {res.text}"}
    except Exception as e:
        logger.error(f"[TelegramService] Send message error: {e}")
        return {"status": "error", "message": str(e)}


async def send_telegram_plan_proposal(chat_id: str, plan_text: str, plan_id: str) -> Dict[str, Any]:
    """
    Sends a structured Plan proposal with interactive Inline Keyboard Buttons (Bab 12.1 rancangan-general-agent.md):
    [✅ Setujui Rencana] [❌ Batalkan]
    """
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Setujui Rencana", "callback_data": f"approve:{plan_id}"},
                {"text": "❌ Batalkan", "callback_data": f"reject:{plan_id}"}
            ]
        ]
    }
    formatted = f"📋 <b>RENCANA KERJA ANARA</b>\n\n{plan_text}\n\n<i>Pilih tindakan Anda di bawah:</i>"
    return await send_telegram_message(text=formatted, chat_id=chat_id, reply_markup=keyboard)


async def answer_telegram_callback_query(callback_query_id: str, text: Optional[str] = None):
    """Acknowledges an inline button click to remove the loading state in Telegram."""
    token = get_stored_telegram_token()
    if not token:
        return
    url = f"{TELEGRAM_API_BASE}/bot{token}/answerCallbackQuery"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            payload = {"callback_query_id": callback_query_id}
            if text:
                payload["text"] = text
            await client.post(url, json=payload)
    except Exception:
        pass


async def edit_telegram_message(
    chat_id: str,
    message_id: int,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Edits an existing Telegram message in place (e.g. after clicking inline buttons)."""
    token = get_stored_telegram_token()
    if not token:
        return {"status": "error", "message": "Token Telegram Bot belum diatur."}

    url = f"{TELEGRAM_API_BASE}/bot{token}/editMessageText"
    formatted_text = format_telegram_html(text)
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": formatted_text,
        "parse_mode": "HTML",
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                return res.json()

            # Fallback to plain text if HTML parsing failed
            plain_text = re.sub(r"<[^>]+>", "", text)
            fallback_payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": plain_text,
            }
            if reply_markup is not None:
                fallback_payload["reply_markup"] = reply_markup
            fb_res = await client.post(url, json=fallback_payload)
            if fb_res.status_code == 200:
                return fb_res.json()
            return {"status": "error", "message": res.text}
    except Exception as e:
        logger.warning(f"[TelegramService] Edit message error: {e}")
        return {"status": "error", "message": str(e)}


async def setup_telegram_bot_commands() -> bool:
    """Registers standard bot commands with Telegram via setMyCommands API."""
    token = get_stored_telegram_token()
    if not token:
        return False
    url = f"{TELEGRAM_API_BASE}/bot{token}/setMyCommands"
    commands = [
        {"command": "model", "description": "Pilih & ganti model AI aktif"},
        {"command": "status", "description": "Periksa status agen, model & memori"},
        {"command": "memory", "description": "Lihat USER.md & MEMORY.md"},
        {"command": "skills", "description": "Daftar keahlian otonom terdaftar"},
        {"command": "clear", "description": "Mulai sesi percakapan baru"},
        {"command": "help", "description": "Panduan & bantuan perintah"},
    ]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json={"commands": commands})
            if res.status_code == 200 and res.json().get("ok"):
                logger.info("[TelegramService] Registered bot commands via setMyCommands successfully.")
                return True
    except Exception as e:
        logger.warning(f"[TelegramService] setMyCommands error: {e}")
    return False


async def send_telegram_provider_selector(chat_id: str, message_id: Optional[int] = None):
    """Step 1: Displays the multi-provider menu (Google Gemini, 9Router, etc.) via inline keyboard."""
    from providers import get_active_model_id
    from memory import memory_engine

    active_id = get_active_model_id()
    custom_nodes = memory_engine.get_custom_providers()
    accounts = memory_engine.get_ai_accounts()

    has_gemini = any(a.get("provider") == "gemini" for a in accounts) or os.getenv("GEMINI_API_KEY")
    has_openai = any(a.get("provider") in ["openai", "codex"] for a in accounts) or os.getenv("OPENAI_API_KEY")
    has_anthropic = any(a.get("provider") == "anthropic" for a in accounts) or os.getenv("ANTHROPIC_API_KEY")

    buttons = []
    # Row for Google Gemini
    if has_gemini:
        buttons.append([{"text": "💎 Google Gemini (Native SDK)", "callback_data": "prov:gemini"}])

    # Rows for custom providers (e.g. 9Router Proxy)
    for node in custom_nodes:
        if node.get("is_active", 1):
            prefix = node.get("prefix", "custom")
            name = node.get("name", prefix)
            icon = "🌐 " if "9router" in prefix.lower() or "proxy" in name.lower() else "⚡ "
            buttons.append([{"text": f"{icon}{name}", "callback_data": f"prov:{prefix}"}])

    if has_anthropic:
        buttons.append([{"text": "🟣 Anthropic Claude", "callback_data": "prov:anthropic"}])
    if has_openai:
        buttons.append([{"text": "🟢 OpenAI / Codex", "callback_data": "prov:openai"}])

    if not buttons:
        buttons = [
            [{"text": "💎 Google Gemini", "callback_data": "prov:gemini"}],
            [{"text": "🌐 9Router Proxy", "callback_data": "prov:9router"}],
        ]

    keyboard = {"inline_keyboard": buttons}
    msg_text = (
        f"🤖 <b>PILIH PROVIDER MODEL AI (MULTI-PROVIDER)</b>\n\n"
        f"Model aktif saat ini:\n<code>{active_id}</code>\n\n"
        f"<i>Pilih provider di bawah untuk melihat daftar model yang tersedia:</i>"
    )
    if message_id:
        return await edit_telegram_message(chat_id=chat_id, message_id=message_id, text=msg_text, reply_markup=keyboard)
    return await send_telegram_message(text=msg_text, chat_id=chat_id, reply_markup=keyboard)


async def send_telegram_models_for_provider(chat_id: str, provider_prefix: str, message_id: Optional[int] = None):
    """Step 2: Displays curated top models under the selected provider."""
    from providers.discovery import get_all_dynamic_models
    from providers import get_active_model_id

    active_id = get_active_model_id()
    all_models = await get_all_dynamic_models()

    prefix_lower = provider_prefix.lower()
    matching_models = []

    if prefix_lower == "gemini":
        matching_models = [m for m in all_models if m.get("provider") == "gemini"]
    else:
        matching_models = [
            m for m in all_models
            if m.get("provider") == prefix_lower or m["id"].startswith(f"{prefix_lower}/")
        ]

    if not matching_models:
        matching_models = [
            m for m in all_models
            if prefix_lower in m["id"].lower() or prefix_lower in m.get("name", "").lower()
        ]

    buttons = []
    for m in matching_models[:8]:
        m_id = m["id"]
        is_cur = (m_id == active_id)
        icon = "🔘 " if is_cur else "🔹 "
        name = m.get("name", m_id)
        clean_name = name.replace(f"({provider_prefix})", "").replace(f"({prefix_lower})", "").strip()
        btn_text = f"{icon}{clean_name}"

        cb_val = f"setm:{m_id}"
        if len(cb_val.encode("utf-8")) <= 64:
            buttons.append([{"text": btn_text, "callback_data": cb_val}])

    # Back navigation button
    buttons.append([{"text": "⬅️ Kembali ke Pilihan Provider", "callback_data": "prov:menu"}])

    prov_title = provider_prefix.upper()
    keyboard = {"inline_keyboard": buttons}
    msg_text = (
        f"💎 <b>DAFTAR MODEL [{prov_title}]</b>\n\n"
        f"Model aktif saat ini:\n<code>{active_id}</code>\n\n"
        f"<i>Ketuk model yang diinginkan untuk langsung mengaktifkannya:</i>"
    )
    if message_id:
        return await edit_telegram_message(chat_id=chat_id, message_id=message_id, text=msg_text, reply_markup=keyboard)
    return await send_telegram_message(text=msg_text, chat_id=chat_id, reply_markup=keyboard)


async def send_telegram_model_selector(chat_id: str):
    """Entry point for /model command: starts at Step 1 (Provider Selector)."""
    return await send_telegram_provider_selector(chat_id=chat_id)


_telegram_daemon_task: Optional[asyncio.Task] = None
_telegram_daemon_running: bool = False


async def process_incoming_telegram_update(u: Dict[str, Any]):
    """Processes an incoming Telegram update through the Unified Channel Adapter."""
    from core.channel_adapter import (
        ChannelRequest,
        process_channel_request,
        resolve_pending_plan_callback,
        _execute_build_mode,
    )

    # ── 1. Handle Inline Keyboard Callbacks (Approval Gate & Multi-Provider Model Switcher) ──
    cb = u.get("callback_query")
    if cb:
        cb_id = cb.get("id")
        cb_data = cb.get("data", "")
        sender = cb.get("from", {})
        sender_name = (sender.get("first_name", "") + " " + sender.get("last_name", "")).strip() or "Pengguna"
        chat_id = str(cb.get("message", {}).get("chat", {}).get("id", ""))
        message_id = cb.get("message", {}).get("message_id")
        user_id = str(sender.get("id", "telegram_user"))

        # Case A: Return to Provider Menu
        if cb_data == "prov:menu":
            await answer_telegram_callback_query(cb_id)
            await send_telegram_provider_selector(chat_id=chat_id, message_id=message_id)
            return

        # Case B: Selected a Provider -> Show models for that provider
        if cb_data.startswith("prov:"):
            target_prov = cb_data.split(":", 1)[1]
            await answer_telegram_callback_query(cb_id, text=f"Membuka {target_prov.upper()}...")
            await send_telegram_models_for_provider(chat_id=chat_id, provider_prefix=target_prov, message_id=message_id)
            return

        # Case C: Selected a Model -> Activate model immediately!
        if cb_data.startswith("setm:") or cb_data.startswith("setmodel:"):
            target_model = cb_data.split(":", 1)[1]
            from providers.accounts import set_active_model_id
            set_active_model_id(target_model)
            await answer_telegram_callback_query(cb_id, text=f"Model diubah ke {target_model}")
            if message_id:
                confirm_text = (
                    f"✅ <b>Model AI Aktif Berhasil Diubah!</b>\n\n"
                    f"Model yang sekarang digunakan:\n<code>{target_model}</code>\n\n"
                    f"<i>Kirim pesan untuk langsung berinteraksi dengan model ini.</i>"
                )
                await edit_telegram_message(chat_id=chat_id, message_id=message_id, text=confirm_text)
            return

        # Case D: Plan Approval callback
        if ":" in cb_data:
            action, plan_id = cb_data.split(":", 1)
            await answer_telegram_callback_query(cb_id, text=f"Memproses {action}...")

            pending = resolve_pending_plan_callback(plan_id, action, user_id)
            if action == "approve":
                if pending:
                    from core.security import is_authorized_approver
                    if not is_authorized_approver(user_id=user_id, plan_owner_id=pending.get("user_id", user_id), channel="telegram"):
                        await send_telegram_message(
                            text="⚠️ <b>Akses Ditolak:</b> Anda tidak memiliki otorisasi untuk menyetujui rencana kerja ini.",
                            chat_id=chat_id
                        )
                        return

                    await send_telegram_message(text="🔨 Rencana disetujui! Memulai eksekusi di latar belakang...", chat_id=chat_id)
                    req = ChannelRequest(
                        text=f"Eksekusi rencana: {pending['original_prompt']}",
                        channel="telegram",
                        channel_id=chat_id,
                        user_id=user_id,
                        sender_name=sender_name
                    )

                    async def _send_prog(msg: str):
                        await send_telegram_message(text=msg, chat_id=chat_id)

                    res = await _execute_build_mode(
                        session_id=pending["session_id"],
                        user_prompt=req.text,
                        req=req,
                        progress_callback=_send_prog,
                        pending_tool_call=pending.get("pending_tool_call"),
                    )
                    await send_telegram_message(text=f"✅ <b>Hasil Eksekusi:</b>\n{res.text}", chat_id=chat_id)
                else:
                    await send_telegram_message(text="⚠️ Rencana telah kedaluwarsa atau sudah diproses.", chat_id=chat_id)
            else:
                await send_telegram_message(text="❌ Rencana dibatalkan. Tidak ada perubahan yang dilakukan.", chat_id=chat_id)
        return

    # ── 2. Handle Text Messages & Slash Commands ──
    msg = u.get("message") or u.get("edited_message")
    if msg and msg.get("text"):
        chat_id = str(msg.get("chat", {}).get("id"))
        sender = msg.get("from", {})
        sender_name = (sender.get("first_name", "") + " " + sender.get("last_name", "")).strip() or sender.get("username") or "Pengguna"
        user_id = str(sender.get("id", "telegram_user"))
        text = msg.get("text").strip()

        # ── Handle Slash Commands ──
        cmd_clean = text.split("@")[0].strip().lower()

        if cmd_clean in ["/start", "/help"]:
            help_text = (
                f"👋 <b>Halo {sender_name}! Saya Anara — General AI Agent Anda.</b>\n\n"
                "Saya terhubung dengan PC dan ruang kerja lokal Anda, siap membantu percakapan, riset, maupun otomasi terminal dengan perlindungan Plan/Build Gate otomatis.\n\n"
                "📌 <b>Daftar Perintah Bot:</b>\n"
                "• <b>/model</b> — Pilih provider & ganti model AI aktif dengan tombol interaktif\n"
                "• <b>/status</b> — Periksa status bot, model aktif, dan memori sistem\n"
                "• <b>/memory</b> — Lihat ringkasan USER.md & MEMORY.md\n"
                "• <b>/skills</b> — Lihat daftar keahlian agen aktif (agentskills.io)\n"
                "• <b>/clear</b> — Bersihkan konteks dan mulai sesi percakapan baru\n"
                "• <b>/help</b> — Tampilkan bantuan ini\n\n"
                "🛡️ <b>Smart Plan Gate:</b> Perintah yang mengakses terminal atau hardware PC akan otomatis menyusun rencana kerja terstruktur dengan tombol <b>[Setujui Rencana]</b> sebelum dieksekusi."
            )
            await send_telegram_message(text=help_text, chat_id=chat_id)
            return

        if cmd_clean in ["/model", "/models"]:
            await send_telegram_model_selector(chat_id)
            return

        if cmd_clean == "/status":
            from providers import get_active_model_id
            from memory import memory_engine
            active_id = get_active_model_id()
            stats = memory_engine.get_brain_stats()
            status_text = (
                f"⚡ <b>STATUS ANARA GENERAL AGENT</b>\n\n"
                f"• <b>Channel</b>: Telegram Bot\n"
                f"• <b>Chat ID</b>: <code>{chat_id}</code>\n"
                f"• <b>Pengguna</b>: {sender_name}\n"
                f"• <b>Model AI Aktif</b>: <code>{active_id}</code>\n"
                f"• <b>Memori Fakta</b>: {stats.get('memories_count', 0)} node\n"
                f"• <b>Tugas & Catatan</b>: {stats.get('notes_count', 0)} item\n"
                f"• <b>Keahlian Otonom</b>: {stats.get('skills_count', 0)} skills\n"
                f"• <b>Kondisi Core</b>: OPTIMAL & Siap beroperasi."
            )
            await send_telegram_message(text=status_text, chat_id=chat_id)
            return

        if cmd_clean == "/memory":
            from memory import file_memory
            user_prof = file_memory.get_user_profile()
            mem_facts = file_memory.get_memory_facts()
            mem_text = (
                f"🧠 <b>MEMORI SISTEM 4-FILE ANARA</b>\n\n"
                f"<b>[PROFIL PENGGUNA - USER.md]</b>\n{user_prof[:500]}\n\n"
                f"<b>[FAKTA TERPELAJARI - MEMORY.md]</b>\n{mem_facts[:700]}"
            )
            await send_telegram_message(text=mem_text, chat_id=chat_id)
            return

        if cmd_clean == "/skills":
            from core.skill_library import skill_library
            skills = skill_library.list_skills()
            active_skills = [s for s in skills if s.get("status") == "active"]
            lines = [f"📦 <b>SKILL LIBRARY V2 ({len(active_skills)} Aktif)</b>:\n"]
            for s in active_skills[:8]:
                lines.append(f"• <b>{s['name']}</b> ({s.get('category', 'general')})\n  <i>{s.get('description', '')[:90]}</i>")
            await send_telegram_message(text="\n".join(lines), chat_id=chat_id)
            return

        if cmd_clean in ["/clear", "/new"]:
            from memory import memory_engine
            new_sess = memory_engine.create_session(
                speaker_name=sender_name,
                title=f"Telegram Chat ({sender_name})",
                session_type="chat",
                channel="telegram",
                session_mode="conversational"
            )
            await send_telegram_message(
                text=f"🧹 <b>Sesi percakapan baru telah dimulai (#{new_sess['id']}).</b>\nKonteks sebelumnya telah diarsipkan.",
                chat_id=chat_id
            )
            return

        # ── 3. Handle Standard Conversational / Agentic Requests ──
        req = ChannelRequest(
            text=text,
            channel="telegram",
            channel_id=chat_id,
            user_id=user_id,
            sender_name=sender_name,
            trigger_type="interactive"
        )

        # ── 3. Handle Standard Conversational / Agentic Requests ──
        req = ChannelRequest(
            text=text,
            channel="telegram",
            channel_id=chat_id,
            user_id=user_id,
            sender_name=sender_name,
            trigger_type="interactive"
        )

        async def _prog_cb(prog_msg: str):
            await send_telegram_message(text=prog_msg, chat_id=chat_id)

        try:
            res = await process_channel_request(req, progress_callback=_prog_cb)
            if res.plan_pending and res.plan_id:
                await send_telegram_plan_proposal(chat_id=chat_id, plan_text=res.text, plan_id=res.plan_id)
            else:
                await send_telegram_message(text=res.text, chat_id=chat_id)
        except Exception as e:
            logger.error(f"[TelegramDaemon] Error processing request: {e}")
            await send_telegram_message(text=f"Maaf, terjadi kesalahan pemrosesan: {str(e)}", chat_id=chat_id)


async def _telegram_polling_worker():
    """Continuous background long-polling worker for Telegram bot updates."""
    global _last_update_id, _telegram_daemon_running
    logger.info("[TelegramDaemon] Worker started.")
    token = get_stored_telegram_token()
    if not token:
        logger.info("[TelegramDaemon] No token configured. Worker sleeping.")
        return

    # Automatically register native Telegram slash commands menu
    try:
        await setup_telegram_bot_commands()
    except Exception as e:
        logger.warning(f"[TelegramDaemon] setup_telegram_bot_commands warning: {e}")

    while _telegram_daemon_running:
        token = get_stored_telegram_token()
        if not token:
            await asyncio.sleep(10.0)
            continue

        url = f"{TELEGRAM_API_BASE}/bot{token}/getUpdates"
        params = {"limit": "20", "offset": str(_last_update_id + 1), "timeout": "15"}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.get(url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("ok"):
                        updates = data.get("result", [])
                        for u in updates:
                            up_id = u.get("update_id", 0)
                            if up_id > _last_update_id:
                                _last_update_id = up_id
                            asyncio.create_task(process_incoming_telegram_update(u))
                elif res.status_code == 409:
                    logger.warning("[TelegramDaemon] Conflict: another bot instance is polling. Waiting 20s.")
                    await asyncio.sleep(20.0)
        except Exception as e:
            logger.debug(f"[TelegramDaemon] Polling tick error: {e}")
            await asyncio.sleep(3.0)

        await asyncio.sleep(0.5)


def start_telegram_polling_daemon():
    """Starts the continuous background polling daemon for Telegram."""
    global _telegram_daemon_task, _telegram_daemon_running
    if _telegram_daemon_running:
        return
    _telegram_daemon_running = True
    _telegram_daemon_task = asyncio.create_task(_telegram_polling_worker())
    logger.info("[TelegramDaemon] Background polling daemon initiated.")


def stop_telegram_polling_daemon():
    """Gracefully terminates the Telegram polling daemon."""
    global _telegram_daemon_task, _telegram_daemon_running
    _telegram_daemon_running = False
    if _telegram_daemon_task:
        _telegram_daemon_task.cancel()
        _telegram_daemon_task = None
    logger.info("[TelegramDaemon] Background polling daemon stopped.")
