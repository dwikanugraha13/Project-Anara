"""
handlers.py — Inbound Update Router & Slash Command Handlers for Telegram Bot in Project Anara.
Anara Standard plugins/platforms/telegram/handlers.
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .client import (
    send_telegram_message,
    edit_telegram_message,
    delete_telegram_message,
    answer_telegram_callback_query,
    send_telegram_chat_action,
    download_telegram_attachment,
)
from .keyboards import (
    send_telegram_provider_selector,
    send_telegram_models_for_provider,
    send_telegram_model_search,
    send_telegram_model_selector,
    send_telegram_plan_proposal,
    render_telegram_question,
    _MODEL_ID_SHORTMAP,
    _PENDING_TELEGRAM_QUESTIONS,
)

logger = logging.getLogger(__name__)

_ACTIVE_CHAT_TASKS: Dict[str, asyncio.Task] = {}


class TelegramStatusTracker:
    """Atomic in-place progress updater, continuous typing heartbeat, and auto-cleaner for Telegram turns."""
    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self.status_msg_id: Optional[int] = None
        self.last_text: str = ""
        self._lock = asyncio.Lock()
        self._last_edit_time: float = 0.0
        self._running: bool = True
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._start_heartbeat()

    def _start_heartbeat(self):
        async def _keep_typing():
            while self._running:
                try:
                    await send_telegram_chat_action(chat_id=self.chat_id, action="typing")
                except Exception:
                    pass
                await asyncio.sleep(4.0)

        self._heartbeat_task = asyncio.create_task(_keep_typing())

    async def update(self, text: str):
        clean = (text or "").strip()
        if not clean or clean == self.last_text:
            return
        self.last_text = clean
        async with self._lock:
            try:
                now = time.time()
                if self.status_msg_id is None:
                    res = await send_telegram_message(text=f"<i>{clean}</i>", chat_id=self.chat_id)
                    if isinstance(res, dict) and res.get("status") == "ok":
                        self.status_msg_id = res.get("message_id") or (res.get("result") or {}).get("message_id")
                        self._last_edit_time = now
                elif (now - self._last_edit_time) >= 0.8:
                    await edit_telegram_message(chat_id=self.chat_id, message_id=self.status_msg_id, text=f"<i>{clean}</i>")
                    self._last_edit_time = now
            except Exception:
                pass

    async def cleanup(self):
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        async with self._lock:
            if self.status_msg_id:
                try:
                    await delete_telegram_message(chat_id=self.chat_id, message_id=self.status_msg_id)
                except Exception:
                    pass
                self.status_msg_id = None


async def process_incoming_telegram_update(u: Dict[str, Any]):
    """Processes an incoming Telegram update through the Unified Channel Adapter."""
    from core.channel_adapter import (
        ChannelRequest,
        process_channel_request,
        resolve_pending_plan_callback,
        _execute_build_mode,
    )

    # ── 1. Handle Inline Keyboard Callbacks ──
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

        # Case B: Selected a Provider
        if cb_data.startswith("prov:"):
            target_prov = cb_data.split(":", 1)[1]
            await answer_telegram_callback_query(cb_id, text=f"Membuka {target_prov.upper()}...")
            await send_telegram_models_for_provider(chat_id=chat_id, provider_prefix=target_prov, message_id=message_id)
            return

        # Case C: Selected a Model
        if cb_data.startswith("setm:") or cb_data.startswith("setmodel:") or cb_data.startswith("setms:"):
            if cb_data.startswith("setms:"):
                h_key = cb_data.split(":", 1)[1]
                target_model = _MODEL_ID_SHORTMAP.get(h_key, "")
            else:
                target_model = cb_data.split(":", 1)[1]

            if not target_model:
                await answer_telegram_callback_query(cb_id, text="Model tidak ditemukan atau expired.")
                return
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

        # Case D: Interactive Question Wizard Answer
        if cb_data.startswith("qans:"):
            parts = cb_data.split(":")
            if len(parts) >= 4:
                _, q_id, q_idx_str, opt_idx_str = parts[:4]
                q_idx = int(q_idx_str)
                opt_idx = int(opt_idx_str)
                q_state = _PENDING_TELEGRAM_QUESTIONS.get(q_id)
                if q_state:
                    await answer_telegram_callback_query(cb_id, text="Pilihan diterima! ✍️")
                    questions = q_state["questions"]
                    if q_idx < len(questions):
                        cur_q = questions[q_idx]
                        opts = cur_q.get("options", [])
                        if opt_idx < len(opts):
                            chosen = opts[opt_idx]
                            ans_label = chosen.get("label", "") if isinstance(chosen, dict) else str(chosen)
                        else:
                            ans_label = f"Opsi {opt_idx+1}"
                        q_state["answers"].append({
                            "header": cur_q.get("header", ""),
                            "question": cur_q.get("question", ""),
                            "answer": ans_label
                        })
                    q_state["current_index"] = q_idx + 1
                    await render_telegram_question(q_id)
                    return

        # Case E: Interactive Question Skip / Dismiss
        if cb_data.startswith("qdis:"):
            _, q_id = cb_data.split(":", 1)
            await answer_telegram_callback_query(cb_id, text="Menggunakan rekomendasi default...")
            q_state = _PENDING_TELEGRAM_QUESTIONS.get(q_id)
            if q_state:
                from tools.events import resolve_question_response
                rec_answers = []
                for q in q_state["questions"]:
                    opts = q.get("options", [])
                    chosen = next((o for o in opts if "(Recommended)" in (o.get("label", "") if isinstance(o, dict) else str(o))), None)
                    if not chosen and opts:
                        chosen = opts[0]
                    ans_str = chosen.get("label", "") if isinstance(chosen, dict) else str(chosen) if chosen else "Default"
                    rec_answers.append({
                        "header": q.get("header", ""),
                        "question": q.get("question", ""),
                        "answer": ans_str
                    })
                resolve_question_response(q_id, rec_answers, dismissed=False)
                _PENDING_TELEGRAM_QUESTIONS.pop(q_id, None)

                if message_id:
                    skip_msg = (
                        "⏭️ <b>Kuesioner dilewati:</b> Anara menggunakan opsi rekomendasi terbaik secara otomatis.\n\n"
                        "<i>Memulai perancangan & pembuatan kode...</i>"
                    )
                    await edit_telegram_message(chat_id=chat_id, message_id=message_id, text=skip_msg, reply_markup=None)
            return

        # Case F: Plan Approval
        if ":" in cb_data:
            action, plan_id = cb_data.split(":", 1)
            await answer_telegram_callback_query(cb_id, text=f"Memproses {action}...")

            pending = resolve_pending_plan_callback(plan_id, action, user_id)
            if action == "approve":
                if pending:
                    from core.security import is_authorized_approver
                    if not is_authorized_approver(user_id=user_id, plan_owner_id=pending.get("user_id", user_id), channel="telegram"):
                        await send_telegram_message(
                            text="🛡️ <b>Akses Ditolak:</b> Anda tidak memiliki otorisasi untuk menyetujui rencana kerja ini.",
                            chat_id=chat_id
                        )
                        return

                    if message_id:
                        plan_display = pending.get("plan_text", "").split("\n<i>Apakah")[0].strip()
                        await edit_telegram_message(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=f"{plan_display}\n\n<i>[✓ Rencana disetujui — sedang dieksekusi di PC...]</i>",
                            reply_markup=None
                        )

                    req = ChannelRequest(
                        text=f"Eksekusi rencana: {pending['original_prompt']}",
                        channel="telegram",
                        channel_id=chat_id,
                        user_id=user_id,
                        sender_name=sender_name
                    )

                    status_tracker = TelegramStatusTracker(chat_id)
                    current_task = asyncio.current_task()
                    if current_task:
                        _ACTIVE_CHAT_TASKS[chat_id] = current_task

                    try:
                        res = await _execute_build_mode(
                            session_id=pending["session_id"],
                            user_prompt=req.text,
                            req=req,
                            progress_callback=status_tracker.update,
                            pending_tool_call=pending.get("pending_tool_call"),
                            plan=pending,
                        )
                        await status_tracker.cleanup()
                        await send_telegram_message(text=f"✅ <b>Hasil Eksekusi:</b>\n{res.text}", chat_id=chat_id)
                    except asyncio.CancelledError:
                        await status_tracker.cleanup()
                        logger.info(f"[TelegramService] Build mode execution in chat {chat_id} was stopped.")
                        await send_telegram_message(text="🛑 <b>Eksekusi Build Mode telah dihentikan via /stop.</b>", chat_id=chat_id)
                    except Exception as exec_err:
                        await status_tracker.cleanup()
                        logger.error(f"[TelegramService] Build mode execution error: {exec_err}", exc_info=True)
                        await send_telegram_message(text=f"⚠️ <b>Gagal mengeksekusi rencana:</b> {str(exec_err)}", chat_id=chat_id)
                    finally:
                        await status_tracker.cleanup()
                        if _ACTIVE_CHAT_TASKS.get(chat_id) is current_task:
                            _ACTIVE_CHAT_TASKS.pop(chat_id, None)
                else:
                    await send_telegram_message(text="⚠️ Rencana telah kedaluwarsa atau sedang/sudah diproses.", chat_id=chat_id)
            else:
                if message_id:
                    await edit_telegram_message(
                        chat_id=chat_id,
                        message_id=message_id,
                        text="❌ <b>Rencana dibatalkan.</b> Tidak ada perubahan yang dilakukan.",
                        reply_markup=None
                    )
                else:
                    await send_telegram_message(text="❌ Rencana dibatalkan. Tidak ada perubahan yang dilakukan.", chat_id=chat_id)
        return

    # ── 2. Handle Text Messages, Documents, Photos & Slash Commands ──
    msg = u.get("message") or u.get("edited_message")
    if msg:
        chat_id = str(msg.get("chat", {}).get("id"))
        sender = msg.get("from", {})
        sender_name = (sender.get("first_name", "") + " " + sender.get("last_name", "")).strip() or sender.get("username") or "Pengguna"
        user_id = str(sender.get("id", "telegram_user"))
        raw_text = (msg.get("text") or msg.get("caption") or "").strip()

        incoming_attachments = []
        doc = msg.get("document")
        photo_list = msg.get("photo")
        voice = msg.get("voice")
        audio = msg.get("audio")

        if doc and doc.get("file_id"):
            f_id = doc.get("file_id")
            f_name = doc.get("file_name", "telegram_document.bin")
            dl_path = await download_telegram_attachment(f_id, f_name)
            if dl_path:
                incoming_attachments.append({
                    "type": "document",
                    "file_name": f_name,
                    "local_path": dl_path,
                    "mime_type": doc.get("mime_type", ""),
                    "size": doc.get("file_size", 0),
                })
        elif photo_list and isinstance(photo_list, list) and len(photo_list) > 0:
            highest_photo = photo_list[-1]
            f_id = highest_photo.get("file_id")
            f_name = f"photo_{highest_photo.get('file_unique_id', 'snap')}.jpg"
            dl_path = await download_telegram_attachment(f_id, f_name)
            if dl_path:
                incoming_attachments.append({
                    "type": "photo",
                    "file_name": f_name,
                    "local_path": dl_path,
                    "size": highest_photo.get("file_size", 0),
                })
        elif voice and voice.get("file_id"):
            f_id = voice.get("file_id")
            f_name = f"voice_{voice.get('file_unique_id', 'note')}.ogg"
            dl_path = await download_telegram_attachment(f_id, f_name)
            if dl_path:
                incoming_attachments.append({
                    "type": "voice",
                    "file_name": f_name,
                    "local_path": dl_path,
                    "mime_type": voice.get("mime_type", "audio/ogg"),
                    "duration": voice.get("duration", 0),
                    "size": voice.get("file_size", 0),
                })
        elif audio and audio.get("file_id"):
            f_id = audio.get("file_id")
            f_name = audio.get("file_name") or f"audio_{audio.get('file_unique_id', 'clip')}.mp3"
            dl_path = await download_telegram_attachment(f_id, f_name)
            if dl_path:
                incoming_attachments.append({
                    "type": "audio",
                    "file_name": f_name,
                    "local_path": dl_path,
                    "mime_type": audio.get("mime_type", "audio/mpeg"),
                    "size": audio.get("file_size", 0),
                })

        if incoming_attachments:
            att_info = []
            for att in incoming_attachments:
                att_info.append(
                    f"[BERKAS DILAMPIRKAN DARI TELEGRAM]:\n"
                    f"- Nama Berkas: {att['file_name']}\n"
                    f"- Lokasi Tersimpan di PC: {att['local_path']}"
                )
                if any(att["file_name"].lower().endswith(ext) for ext in [".md", ".txt", ".json", ".py", ".csv", ".yaml", ".yml"]):
                    try:
                        with open(att["local_path"], "r", encoding="utf-8", errors="ignore") as tf:
                            snippet = tf.read(2500)
                            if snippet.strip():
                                att_info.append(f"- Pratinjau Isi:\n```\n{snippet.strip()}\n```")
                    except Exception:
                        pass
            att_header = "\n".join(att_info)
            voice_att = next((att for att in incoming_attachments if att.get("type") in ("voice", "audio")), None)
            if voice_att:
                from cognition.audio import transcribe_audio_file
                voice_transcript = await transcribe_audio_file(voice_att["local_path"])
                if voice_transcript:
                    text = f"{voice_transcript}\n\n<i>[Transkripsi Pesan Suara Telegram]:\n{att_header}</i>"
                else:
                    text = f"[Pesan suara masuk]\n\n{att_header}"
            elif raw_text:
                text = f"{raw_text}\n\n{att_header}"
            else:
                text = f"Tolong proses berkas yang saya kirimkan ini:\n\n{att_header}"
        else:
            text = raw_text

        if not text:
            return

        active_q_id = None
        active_q_state = None
        for q_id, q_data in list(_PENDING_TELEGRAM_QUESTIONS.items()):
            if q_data.get("chat_id") == chat_id:
                active_q_id = q_id
                active_q_state = q_data
                break

        if active_q_state and raw_text and not raw_text.startswith("/"):
            q_idx = active_q_state["current_index"]
            questions = active_q_state["questions"]
            if q_idx < len(questions):
                cur_q = questions[q_idx]
                active_q_state["answers"].append({
                    "header": cur_q.get("header", ""),
                    "question": cur_q.get("question", ""),
                    "answer": raw_text
                })
                active_q_state["current_index"] = q_idx + 1
                await render_telegram_question(active_q_id)
                return

        # ── Handle Slash Commands ──
        tokens = text.strip().split(maxsplit=1)
        cmd_name = tokens[0].split("@")[0].strip().lower()
        cmd_arg = tokens[1].strip() if len(tokens) > 1 else ""

        if cmd_name in ["/start", "/help"]:
            help_text = (
                f"👋 <b>Halo {sender_name}! Saya Anara — General AI Agent Anda.</b>\n\n"
                "Saya terhubung dengan PC dan ruang kerja lokal Anda, siap membantu percakapan, riset, maupun otomasi terminal dengan perlindungan Plan/Build Gate otomatis.\n\n"
                "📌 <b>Daftar Perintah Bot:</b>\n"
                "• <b>/plan [tugas]</b> — Tulis rencana implementasi arsitektur ke .anara/plans/ tanpa eksekusi langsung\n"
                "• <b>/stop</b> — Hentikan tugas agen, peramban browser, atau rencana yang sedang berjalan\n"
                "• <b>/model</b> — Pilih provider & ganti model AI aktif dengan tombol interaktif\n"
                "• <b>/workspace</b> — Lihat atau kunci bot ke folder proyek PC (Anara Code mode)\n"
                "• <b>/status</b> — Periksa status bot, model aktif, dan memori sistem\n"
                "• <b>/memory</b> — Lihat ringkasan USER.md & MEMORY.md\n"
                "• <b>/skills</b> — Lihat daftar keahlian agen aktif (agentskills.io)\n"
                "• <b>/clear</b> — Bersihkan konteks dan mulai sesi percakapan baru\n"
                "• <b>/help</b> — Tampilkan bantuan ini\n\n"
                "🛡️ <b>Anara Dangerous Guard:</b> Percakapan dan perintah normal berjalan bebas friksi. Konfirmasi persetujuan hanya muncul jika perintah berisiko tinggi terhadap sistem (rm -rf, format disk, registry, atau /plan)."
            )
            await send_telegram_message(text=help_text, chat_id=chat_id)
            return

        if cmd_name in ["/stop", "/cancel", "/abort"]:
            interrupted = False

            active_task = _ACTIVE_CHAT_TASKS.get(chat_id)
            if active_task and not active_task.done():
                active_task.cancel()
                _ACTIVE_CHAT_TASKS.pop(chat_id, None)
                interrupted = True

            for q_id, q_data in list(_PENDING_TELEGRAM_QUESTIONS.items()):
                if q_data.get("chat_id") == chat_id:
                    from tools.events import resolve_question_response
                    resolve_question_response(q_id, None, dismissed=True)
                    _PENDING_TELEGRAM_QUESTIONS.pop(q_id, None)
                    interrupted = True

            session_plan_key = f"telegram_{chat_id}"
            from core.channel_adapter import _PENDING_PLANS
            if session_plan_key in _PENDING_PLANS:
                _PENDING_PLANS.pop(session_plan_key, None)
                interrupted = True

            try:
                from tools.browser_tools import _tool_browser_close
                await _tool_browser_close()
            except Exception:
                pass

            if interrupted:
                stop_msg = (
                    "🛑 <b>TUGAS BERHASIL DIHENTIKAN!</b>\n\n"
                    "Seluruh proses kerja agen, peramban browser otomatis, dan rencana yang tertahan telah dibatalkan dengan aman.\n\n"
                    "<i>Anara siap menerima perintah baru Anda.</i>"
                )
            else:
                stop_msg = (
                    "ℹ️ <b>Tidak ada tugas yang sedang berjalan.</b>\n\n"
                    "Anara dalam kondisi siaga (idle). Kirimkan perintah apa pun untuk mulai."
                )
            await send_telegram_message(text=stop_msg, chat_id=chat_id)
            return

        if cmd_name in ["/model", "/models"]:
            if cmd_arg:
                await send_telegram_model_search(chat_id=chat_id, query=cmd_arg)
            else:
                await send_telegram_model_selector(chat_id)
            return

        if cmd_name in ["/workspace", "/ws", "/project"]:
            from core.channel_adapter import get_or_create_channel_session
            from core.agent import anara_agent

            temp_req = ChannelRequest(
                text="/workspace",
                channel="telegram",
                channel_id=chat_id,
                user_id=user_id,
                sender_name=sender_name,
            )
            session_id = get_or_create_channel_session(temp_req)

            if cmd_arg.lower() in ["reset", "clear", "default", "detach"]:
                anara_agent.detach_local_folder(session_id=session_id)
                reset_text = (
                    "🧹 <b>Workspace Direset ke Sandbox Terisolasi</b>\n\n"
                    "Bot tidak lagi terikat ke folder lokal eksternal. Semua operasi kembali aman di sandbox sementara."
                )
                await send_telegram_message(text=reset_text, chat_id=chat_id)
                return

            if cmd_arg:
                from core.security import is_authorized_approver
                if not is_authorized_approver(user_id=user_id, plan_owner_id=user_id, channel="telegram"):
                    await send_telegram_message(
                        text="🛡️ <b>Akses Ditolak:</b> Anda harus menjadi admin Telegram terdaftar untuk menautkan folder fisik host.",
                        chat_id=chat_id
                    )
                    return

                clean_path = os.path.abspath(os.path.expanduser(cmd_arg.strip().strip('"\'')))
                if not os.path.isdir(clean_path):
                    err_text = (
                        f"❌ <b>Folder Tidak Ditemukan di PC:</b>\n<code>{clean_path}</code>\n\n"
                        "<i>Pastikan path folder sudah benar dan drive dapat diakses.</i>"
                    )
                    await send_telegram_message(text=err_text, chat_id=chat_id)
                    return

                try:
                    tree = anara_agent.attach_local_folder(clean_path, session_id=session_id)
                    folder_name = tree.get("workspace_name", os.path.basename(clean_path))
                    total_files = tree.get("total_files", 0)
                    files_sample = [f.get("name", "") for f in tree.get("files", [])[:8]]
                    preview_str = ", ".join(files_sample) if files_sample else "(Folder kosong)"

                    success_text = (
                        f"✅ <b>WORKSPACE BERHASIL DITAUTKAN! (ANARA CODE MODE AKTIF)</b>\n\n"
                        f"• <b>Nama Proyek:</b> <code>{folder_name}</code>\n"
                        f"• <b>Root Path Fisik:</b> <code>{clean_path}</code>\n"
                        f"• <b>Total Berkas:</b> {total_files} berkas\n"
                        f"• <b>Pratinjau Berkas:</b> <i>{preview_str}</i>\n\n"
                        f"🔒 <i>Semua pembuatan berkas, pengeditan kode, dan terminal sekarang terkunci otomatis di dalam folder proyek ini!</i>"
                    )
                    await send_telegram_message(text=success_text, chat_id=chat_id)
                    return
                except Exception as ex:
                    await send_telegram_message(text=f"❌ Gagal menautkan workspace: {ex}", chat_id=chat_id)
                    return

            tree = anara_agent.get_workspace_tree(session_id=session_id)
            is_custom = anara_agent.has_active_custom_workspace(session_id=session_id)

            if is_custom:
                ws_text = (
                    f"📁 <b>WORKSPACE PROYEK TERHUBUNG (ANARA CODE MODE)</b>\n\n"
                    f"• <b>Nama Proyek:</b> <code>{tree.get('workspace_name')}</code>\n"
                    f"• <b>Root Path Fisik:</b> <code>{tree.get('root_path')}</code>\n"
                    f"• <b>Total Berkas:</b> {tree.get('total_files')} berkas\n"
                    f"• <b>Status:</b> 🔒 Terkunci di folder ini.\n\n"
                    f"💡 <i>Gunakan <code>/workspace &lt;path_baru&gt;</code> untuk ganti folder, atau <code>/workspace reset</code> untuk kembali ke sandbox aman.</i>"
                )
            else:
                current_temp = anara_agent.get_session_dir(session_id)
                ws_text = (
                    f"📁 <b>STATUS WORKSPACE: SANDBOX TERISOLASI</b>\n\n"
                    f"• <b>Mode:</b> Sandbox Aman Default\n"
                    f"• <b>Lokasi:</b> <code>{current_temp}</code>\n"
                    f"• <b>Status:</b> Beroperasi di sandbox sementara agar tidak mengotori file PC tanpa izin.\n\n"
                    f"💡 <b>Cara Mengunci Bot ke Folder Proyek Nyata:</b>\n"
                    f"Kirim perintah:\n"
                    f"<code>/workspace {os.path.join(str(Path.home()), 'Documents', 'nama-proyek')}</code>\n\n"
                    f"<i>Setelah ditautkan, bot akan bekerja langsung di dalam folder tersebut persis seperti di Anara Code!</i>"
                )
            await send_telegram_message(text=ws_text, chat_id=chat_id)
            return

        if cmd_name == "/status":
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

        if cmd_name == "/memory":
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

        if cmd_name == "/skills":
            from core.skill_library import skill_library
            skills = skill_library.list_skills()
            active_skills = [s for s in skills if s.get("status") == "active"]
            lines = [f"📦 <b>SKILL LIBRARY V2 ({len(active_skills)} Aktif)</b>:\n"]
            for s in active_skills[:8]:
                lines.append(f"• <b>{s['name']}</b> ({s.get('category', 'general')})\n  <i>{s.get('description', '')[:90]}</i>")
            await send_telegram_message(text="\n".join(lines), chat_id=chat_id)
            return

        if cmd_name in ["/clear", "/new"]:
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
            trigger_type="interactive",
            attachments=incoming_attachments,
        )

        status_tracker = TelegramStatusTracker(chat_id)
        current_task = asyncio.current_task()
        if current_task:
            _ACTIVE_CHAT_TASKS[chat_id] = current_task

        try:
            res = await process_channel_request(req, progress_callback=status_tracker.update)
            await status_tracker.cleanup()

            if res.plan_pending and res.plan_id:
                await send_telegram_plan_proposal(chat_id=chat_id, plan_text=res.text, plan_id=res.plan_id)
            else:
                await send_telegram_message(text=res.text, chat_id=chat_id)
        except asyncio.CancelledError:
            await status_tracker.cleanup()
            logger.info(f"[TelegramDaemon] Chat {chat_id} task was cancelled via /stop.")
            await send_telegram_message(text="🛑 <b>Tugas agen telah dihentikan via /stop.</b>", chat_id=chat_id)
        except Exception as e:
            await status_tracker.cleanup()
            logger.error(f"[TelegramDaemon] Error processing request: {e}")
            await send_telegram_message(text=f"Maaf, terjadi kesalahan pemrosesan: {str(e)}", chat_id=chat_id)
        finally:
            await status_tracker.cleanup()
            if _ACTIVE_CHAT_TASKS.get(chat_id) is current_task:
                _ACTIVE_CHAT_TASKS.pop(chat_id, None)
