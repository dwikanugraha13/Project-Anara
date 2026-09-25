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
        sender_name = (sender.get("first_name", "") + " " + sender.get("last_name", "")).strip() or "User"
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
            await answer_telegram_callback_query(cb_id, text=f"Opening {target_prov.upper()}...")
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
                await answer_telegram_callback_query(cb_id, text="Model not found or expired.")
                return
            from providers.accounts import set_active_model_id
            set_active_model_id(target_model)
            await answer_telegram_callback_query(cb_id, text=f"Model switched to {target_model}")
            if message_id:
                confirm_text = (
                    f"✅ <b>Active AI Model Updated!</b>\n\n"
                    f"Currently active model:\n<code>{target_model}</code>\n\n"
                    f"<i>Send a message to interact with this model.</i>"
                )
                await edit_telegram_message(chat_id=chat_id, message_id=message_id, text=confirm_text)
            return

        # Case D: Selected Voice Mode (/voice)
        if cb_data.startswith("vmode:"):
            target_mode = cb_data.split(":", 1)[1]
            from core.command_hub import set_chat_voice_mode, VOICE_MODE_LABELS
            new_m = set_chat_voice_mode("telegram", chat_id, target_mode)
            lbl = VOICE_MODE_LABELS.get(new_m, new_m)
            await answer_telegram_callback_query(cb_id, text=f"Voice mode: {new_m}")
            if message_id:
                await edit_telegram_message(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"✅ <b>Voice Mode Updated!</b>\n\nActive mode in this chat:\n<b>{lbl}</b>",
                    reply_markup=None
                )
            return

        # Case E: Interactive Question Wizard Answer
        if cb_data.startswith("qans:"):
            parts = cb_data.split(":")
            if len(parts) >= 4:
                _, q_id, q_idx_str, opt_idx_str = parts[:4]
                q_idx = int(q_idx_str)
                opt_idx = int(opt_idx_str)
                q_state = _PENDING_TELEGRAM_QUESTIONS.get(q_id)
                if q_state:
                    await answer_telegram_callback_query(cb_id, text="Choice accepted! ✍️")
                    questions = q_state["questions"]
                    if q_idx < len(questions):
                        cur_q = questions[q_idx]
                        opts = cur_q.get("options", [])
                        if opt_idx < len(opts):
                            chosen = opts[opt_idx]
                            ans_label = chosen.get("label", "") if isinstance(chosen, dict) else str(chosen)
                        else:
                            ans_label = f"Option {opt_idx+1}"
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
            q_state = _PENDING_TELEGRAM_QUESTIONS.get(q_id)
            await answer_telegram_callback_query(cb_id, text="Applying default recommendations...")
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
                        "⏭️ <b>Questionnaire Skipped:</b> "
                        "Anara applied the recommended options automatically.\n\n"
                        "<i>Starting execution...</i>"
                    )
                    await edit_telegram_message(chat_id=chat_id, message_id=message_id, text=skip_msg, reply_markup=None)
            return

        # Case F: Plan & Action Approval (Hermes Decoupled State Machine)
        if ":" in cb_data and (cb_data.startswith("approve:") or cb_data.startswith("reject:") or cb_data.startswith("appr:")):
            if cb_data.startswith("appr:"):
                parts = cb_data.split(":")
                action = parts[2] if len(parts) >= 3 else "approve"
                plan_id = parts[1]
            else:
                action, plan_id = cb_data.split(":", 1)

            action = "approve" if action in ("approve", "yes") else "reject"
            action_toast = f"Processing {action}..." if action == "approve" else "Cancelling action..."
            await answer_telegram_callback_query(cb_id, text=action_toast)

            from core.channel_adapter import dispatch_channel_approval_resolution
            status_tracker = TelegramStatusTracker(chat_id)
            current_task = asyncio.current_task()
            if current_task:
                _ACTIVE_CHAT_TASKS[chat_id] = current_task

            try:
                await dispatch_channel_approval_resolution(
                    channel="telegram",
                    channel_id=chat_id,
                    plan_id=plan_id,
                    action=action,
                    user_id=user_id,
                    sender_name=sender_name,
                    message_id=str(message_id) if message_id else None,
                    progress_callback=status_tracker.update,
                )
            finally:
                await status_tracker.cleanup()
                if _ACTIVE_CHAT_TASKS.get(chat_id) is current_task:
                    _ACTIVE_CHAT_TASKS.pop(chat_id, None)
            return

    # ── 2. Handle Text Messages, Documents, Photos & Slash Commands ──
    msg = u.get("message") or u.get("edited_message")
    if msg:
        chat_id = str(msg.get("chat", {}).get("id"))
        sender = msg.get("from", {})
        sender_name = (sender.get("first_name", "") + " " + sender.get("last_name", "")).strip() or sender.get("username") or "User"
        user_id = str(sender.get("id", "telegram_user"))
        raw_text = (msg.get("text") or msg.get("caption") or "").strip()

        incoming_attachments = []
        doc = msg.get("document")
        photo_list = msg.get("photo")
        voice = msg.get("voice")
        audio = msg.get("audio")
        video = msg.get("video")
        video_note = msg.get("video_note")

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
        elif video and video.get("file_id"):
            f_id = video.get("file_id")
            f_name = video.get("file_name") or f"video_{video.get('file_unique_id', 'clip')}.mp4"
            dl_path = await download_telegram_attachment(f_id, f_name)
            if dl_path:
                incoming_attachments.append({
                    "type": "video",
                    "file_name": f_name,
                    "local_path": dl_path,
                    "mime_type": video.get("mime_type", "video/mp4"),
                    "duration": video.get("duration", 0),
                    "size": video.get("file_size", 0),
                })
        elif video_note and video_note.get("file_id"):
            f_id = video_note.get("file_id")
            f_name = f"videonote_{video_note.get('file_unique_id', 'clip')}.mp4"
            dl_path = await download_telegram_attachment(f_id, f_name)
            if dl_path:
                incoming_attachments.append({
                    "type": "video",
                    "file_name": f_name,
                    "local_path": dl_path,
                    "mime_type": "video/mp4",
                    "duration": video_note.get("duration", 0),
                    "size": video_note.get("file_size", 0),
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

        # ── Quoted / Reply-To Message Context Extraction ──
        reply_msg = msg.get("reply_to_message")
        reply_context = ""
        if reply_msg and isinstance(reply_msg, dict):
            r_sender = reply_msg.get("from", {})
            r_sender_name = (r_sender.get("first_name", "") + " " + r_sender.get("last_name", "")).strip() or r_sender.get("username") or "User"
            r_text = (reply_msg.get("text") or reply_msg.get("caption") or "").strip()

            r_doc = reply_msg.get("document")
            r_photo = reply_msg.get("photo")
            r_video = reply_msg.get("video")
            r_media_info = ""

            if r_doc and r_doc.get("file_id"):
                r_fname = r_doc.get("file_name", "attached_document")
                r_dl = await download_telegram_attachment(r_doc.get("file_id"), r_fname)
                if r_dl:
                    incoming_attachments.append({
                        "type": "document",
                        "file_name": r_fname,
                        "local_path": r_dl,
                        "mime_type": r_doc.get("mime_type", ""),
                        "size": r_doc.get("file_size", 0),
                    })
                    r_media_info = f"[Attached Document: {r_fname} at {r_dl}]"
            elif r_photo and isinstance(r_photo, list) and len(r_photo) > 0:
                highest_r_photo = r_photo[-1]
                r_pname = f"replied_photo_{highest_r_photo.get('file_unique_id', 'snap')}.jpg"
                r_pdl = await download_telegram_attachment(highest_r_photo.get("file_id"), r_pname)
                if r_pdl:
                    incoming_attachments.append({
                        "type": "photo",
                        "file_name": r_pname,
                        "local_path": r_pdl,
                        "size": highest_r_photo.get("file_size", 0),
                    })
                    r_media_info = f"[Attached Photo: {r_pname} at {r_pdl}]"
            elif r_video and r_video.get("file_id"):
                r_vname = r_video.get("file_name") or f"replied_video_{r_video.get('file_unique_id', 'clip')}.mp4"
                r_vdl = await download_telegram_attachment(r_video.get("file_id"), r_vname)
                if r_vdl:
                    incoming_attachments.append({
                        "type": "video",
                        "file_name": r_vname,
                        "local_path": r_vdl,
                        "mime_type": r_video.get("mime_type", "video/mp4"),
                        "size": r_video.get("file_size", 0),
                    })
                    r_media_info = f"[Attached Video: {r_vname} at {r_vdl}]"

            quoted_body = f"{r_text}\n{r_media_info}".strip() if r_media_info else r_text
            if quoted_body:
                reply_context = f"[REPLY_TO_MESSAGE from {r_sender_name.upper()}]:\n\"{quoted_body}\"\n\n"

        if incoming_attachments:
            voice_att = next((att for att in incoming_attachments if att.get("type") in ("voice", "audio")), None)
            photo_att = [att for att in incoming_attachments if att.get("type") == "photo"]
            doc_attachments = [att for att in incoming_attachments if att.get("type") not in ("voice", "audio", "photo")]

            att_info = []
            for att in doc_attachments:
                att_info.append(
                    f"[ATTACHED_DOCUMENT]:\n"
                    f"- File Name: {att['file_name']}\n"
                    f"- Local Path: {att['local_path']}"
                )
                if any(att["file_name"].lower().endswith(ext) for ext in [".md", ".txt", ".json", ".py", ".csv", ".yaml", ".yml"]):
                    try:
                        with open(att["local_path"], "r", encoding="utf-8", errors="ignore") as tf:
                            snippet = tf.read(2500)
                            if snippet.strip():
                                att_info.append(f"- Content Preview:\n```\n{snippet.strip()}\n```")
                    except Exception:
                        pass
            att_header = "\n".join(att_info)

            if voice_att:
                from cognition.audio import transcribe_audio_file
                voice_transcript = await transcribe_audio_file(voice_att["local_path"])
                if voice_transcript and voice_transcript.strip():
                    text = voice_transcript.strip()
                    if att_header:
                        text = f"{text}\n\n{att_header}"
                else:
                    fallback_audio_msg = (
                        "🎙️ <i>Voice message could not be transcribed. Please ensure the active model supports audio input or send your request in text.</i>"
                    )
                    await send_telegram_message(
                        chat_id=chat_id,
                        text=fallback_audio_msg
                    )
                    return
            elif raw_text:
                text = f"{raw_text}\n\n{att_header}" if att_header else raw_text
            elif photo_att:
                default_prompt = "[User sent an attached photo without caption. Inspect and respond naturally in the user's active language.]"
                text = f"{default_prompt}\n\n{att_header}" if att_header else default_prompt
            else:
                default_prompt = "[User sent an attached file without caption. Process and respond naturally in the user's active language.]"
                text = f"{default_prompt}\n\n{att_header}" if att_header else default_prompt
        else:
            text = raw_text

        if reply_context:
            text = f"{reply_context}{text}"

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

        # ── 3. Handle Commands & Standard Requests via Unified Dispatcher ──
        if text.strip().lower().startswith(("/stop", "/cancel", "/abort")):
            from core.session_manager import session_state_manager
            interrupt_info = await session_state_manager.request_hard_interrupt("telegram", chat_id, reason="telegram_stop")
            active_task = _ACTIVE_CHAT_TASKS.pop(chat_id, None)
            if active_task and not active_task.done():
                active_task.cancel()

            for q_id, q_data in list(_PENDING_TELEGRAM_QUESTIONS.items()):
                if q_data.get("chat_id") == chat_id:
                    from tools.events import resolve_question_response
                    resolve_question_response(q_id, None, dismissed=True)
                    _PENDING_TELEGRAM_QUESTIONS.pop(q_id, None)

            details = []
            if interrupt_info.get("task_cancelled"):
                details.append("task execution cancelled")
            if interrupt_info.get("processes_killed", 0) > 0:
                details.append(f"{interrupt_info['processes_killed']} OS sub-processes killed")
            if interrupt_info.get("pending_cleared"):
                details.append("pending plans cleared")
            detail_str = f" ({', '.join(details)})" if details else ""

            await send_telegram_message(
                text=f"🛑 <b>Agent tasks stopped via /stop.</b>{detail_str}",
                chat_id=chat_id
            )
            return

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
            prev_task = _ACTIVE_CHAT_TASKS.get(chat_id)
            if prev_task and not prev_task.done() and prev_task is not current_task:
                logger.info(f"[TelegramDaemon] Superseding previous in-flight task for chat {chat_id}")
                prev_task.cancel()
            _ACTIVE_CHAT_TASKS[chat_id] = current_task

        try:
            await status_tracker.update("⚙️ Analyzing request and formulating steps...")
            res = await process_channel_request(req, progress_callback=status_tracker.update)
            await status_tracker.cleanup()

            from core.command_hub import get_chat_voice_mode
            voice_mode = get_chat_voice_mode("telegram", chat_id)  # 'text', 'only', 'both', 'auto'
            is_voice_turn = any(att.get("type") in ("voice", "audio") for att in incoming_attachments)

            # ALL slash commands (e.g. /voice, /model, /help) and UI button responses are ALWAYS delivered as text/UI, NEVER voice!
            is_command_or_ui = getattr(res, "is_command", False) or text.strip().startswith("/") or bool(res.reply_markup) or res.plan_pending

            should_send_voice = False
            if not is_command_or_ui:
                if voice_mode in ("only", "both"):
                    should_send_voice = True
                elif voice_mode == "auto":
                    should_send_voice = is_voice_turn

            voice_sent = False
            if should_send_voice and res.text:
                try:
                    from cognition.audio import synthesize_speech_audio
                    from .client import send_telegram_voice
                    voice_file = await synthesize_speech_audio(res.text)
                    if voice_file:
                        await send_telegram_voice(file_path=voice_file, chat_id=chat_id)
                        voice_sent = True
                except Exception as v_err:
                    logger.warning(f"[TelegramVoice] Error sending voice note: {v_err}")

            should_send_text = (voice_mode != "only") or not voice_sent or is_command_or_ui

            if res.plan_pending:
                markup = res.reply_markup
                if not markup and res.plan_id:
                    from core.channel_adapter import UniversalChannelAdapter
                    from core.session_manager import session_state_manager
                    p = session_state_manager.get_pending_by_id(res.plan_id)
                    if p:
                        rendered = UniversalChannelAdapter.render_approval_payload("telegram", res.text, p)
                        markup = rendered.get("reply_markup")
                        res.text = rendered.get("text") or res.text
                if not markup and res.plan_id:
                    await send_telegram_plan_proposal(chat_id=chat_id, plan_text=res.text, plan_id=res.plan_id)
                else:
                    await send_telegram_message(text=res.text, chat_id=chat_id, reply_markup=markup)
            elif res.text and should_send_text:
                await send_telegram_message(text=res.text, chat_id=chat_id, reply_markup=res.reply_markup)
        except asyncio.CancelledError:
            await status_tracker.cleanup()
            logger.info(f"[TelegramDaemon] Chat {chat_id} task was cancelled or superseded.")
            return
        except Exception as e:
            await status_tracker.cleanup()
            logger.error(f"[TelegramDaemon] Error processing request: {e}")
            from core.channel_adapter import synthesize_channel_notice
            err_msg = await synthesize_channel_notice("error", channel="telegram", error_detail=str(e))
            await send_telegram_message(text=f"⚠️ {err_msg}", chat_id=chat_id)
        finally:
            await status_tracker.cleanup()
            if _ACTIVE_CHAT_TASKS.get(chat_id) is current_task:
                _ACTIVE_CHAT_TASKS.pop(chat_id, None)
