import asyncio
import logging
import os
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


def save_telegram_config(token: str, default_chat_id: Optional[str] = None) -> bool:
    """Saves telegram configuration to database settings."""
    from memory import memory_engine
    if token:
        memory_engine.set_app_setting("telegram_bot_token", token.strip())
    if default_chat_id:
        memory_engine.set_app_setting("telegram_chat_id", default_chat_id.strip())
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
                        "unread_count": len(_recent_telegram_messages),
                    }
                else:
                    return {
                        "status": "error",
                        "is_configured": True,
                        "bot": None,
                        "message": data.get("description", "Token tidak valid."),
                    }
            else:
                return {
                    "status": "error",
                    "is_configured": True,
                    "bot": None,
                    "message": f"HTTP {res.status_code}: Token salah.",
                }
    except Exception as e:
        logger.warning(f"[TelegramService] getMe error: {e}")
        return {
            "status": "disconnected",
            "is_configured": True,
            "bot": None,
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


async def send_telegram_message(
    text: str,
    chat_id: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Sends a text message to a specific or default Telegram chat ID."""
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
    payload = {
        "chat_id": target_chat,
        "text": text,
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
                else:
                    return {"status": "error", "message": data.get("description", "Gagal mengirim pesan.")}
            else:
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
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                return res.json()
            return {"status": "error", "message": res.text}
    except Exception as e:
        logger.warning(f"[TelegramService] Edit message error: {e}")
        return {"status": "error", "message": str(e)}


async def send_telegram_model_selector(chat_id: str):
    """Sends an interactive inline keyboard for choosing the active AI model."""
    from providers.discovery import get_all_dynamic_models
    from providers import get_active_model_id

    active_id = get_active_model_id()
    all_models = await get_all_dynamic_models()
    configured = [m for m in all_models if m.get("is_configured")]
    if not configured:
        configured = all_models[:6]

    buttons = []
    for m in configured[:10]:
        m_id = m["id"]
        is_cur = (m_id == active_id)
        icon = "🔘 " if is_cur else "🔹 "
        name = m.get("name", m_id)
        btn_text = f"{icon}{name}"
        # Telegram callback_data limit is 64 bytes
        cb_val = f"setmodel:{m_id}"
        if len(cb_val.encode("utf-8")) <= 64:
            buttons.append([{"text": btn_text, "callback_data": cb_val}])

    keyboard = {"inline_keyboard": buttons}
    msg_text = (
        f"🤖 <b>PILIH MODEL AI (ANARA BRAIN)</b>\n\n"
        f"Model aktif saat ini:\n<code>{active_id}</code>\n\n"
        f"<i>Ketuk tombol di bawah untuk langsung mengganti model:</i>"
    )
    return await send_telegram_message(text=msg_text, chat_id=chat_id, reply_markup=keyboard)


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

    # ── 1. Handle Inline Keyboard Callbacks (Approval Gate & Model Switcher) ──
    cb = u.get("callback_query")
    if cb:
        cb_id = cb.get("id")
        cb_data = cb.get("data", "")
        sender = cb.get("from", {})
        sender_name = (sender.get("first_name", "") + " " + sender.get("last_name", "")).strip() or "Pengguna"
        chat_id = str(cb.get("message", {}).get("chat", {}).get("id", ""))
        message_id = cb.get("message", {}).get("message_id")
        user_id = str(sender.get("id", "telegram_user"))

        # Case A: Model Selector callback
        if cb_data.startswith("setmodel:"):
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

        # Case B: Plan Approval callback
        if ":" in cb_data:
            action, plan_id = cb_data.split(":", 1)
            await answer_telegram_callback_query(cb_id, text=f"Memproses {action}...")

            pending = resolve_pending_plan_callback(plan_id, action, user_id)
            if action == "approve":
                if pending:
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
                        progress_callback=_send_prog
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
        cmd_lower = text.lower()

        if cmd_lower in ["/start", "/help"]:
            help_text = (
                f"👋 <b>Halo {sender_name}! Saya Anara — General AI Agent Anda.</b>\n\n"
                "Saya terhubung dengan PC dan ruang kerja lokal Anda, siap membantu coding, riset, maupun percakapan dengan perlindungan Plan/Build Gate.\n\n"
                "📌 <b>Daftar Perintah Bot:</b>\n"
                "• <b>/model</b> — Pilih & ganti model AI aktif dengan tombol interaktif\n"
                "• <b>/status</b> — Periksa status bot, model aktif, dan memori sistem\n"
                "• <b>/memory</b> — Lihat ringkasan USER.md & MEMORY.md\n"
                "• <b>/skills</b> — Lihat daftar keahlian agen aktif (agentskills.io)\n"
                "• <b>/clear</b> — Bersihkan konteks dan mulai sesi percakapan baru\n"
                "• <b>/help</b> — Tampilkan bantuan ini\n\n"
                "💡 <i>Kirim pesan apa saja atau instruksi kerja untuk mulai!</i>"
            )
            await send_telegram_message(text=help_text, chat_id=chat_id)
            return

        if cmd_lower.startswith("/model") or cmd_lower.startswith("/models"):
            parts = text.split(maxsplit=1)
            if len(parts) > 1:
                # Direct switch via text: /model gemini-3.5-flash-lite
                target_m = parts[1].strip()
                from providers.accounts import set_active_model_id
                set_active_model_id(target_m)
                await send_telegram_message(
                    text=f"✅ Model AI aktif berhasil diubah ke:\n<code>{target_m}</code>",
                    chat_id=chat_id
                )
            else:
                # Interactive inline keyboard picker
                await send_telegram_model_selector(chat_id)
            return

        if cmd_lower == "/status":
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

        if cmd_lower == "/memory":
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

        if cmd_lower == "/skills":
            from core.skill_library import skill_library
            skills = skill_library.list_skills()
            active_skills = [s for s in skills if s.get("status") == "active"]
            lines = [f"📦 <b>SKILL LIBRARY V2 ({len(active_skills)} Aktif)</b>:\n"]
            for s in active_skills[:8]:
                lines.append(f"• <b>{s['name']}</b> ({s.get('category', 'general')})\n  <i>{s.get('description', '')[:90]}</i>")
            await send_telegram_message(text="\n".join(lines), chat_id=chat_id)
            return

        if cmd_lower in ["/clear", "/new"]:
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
