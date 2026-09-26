"""
External Messaging & Service Integrations Routes (WhatsApp, Telegram, Google, Contacts) for Project Anara.
"""
import logging
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from memory import memory_engine
from integrations import (
    get_whatsapp_status,
    get_whatsapp_qr,
    logout_whatsapp,
    get_whatsapp_messages,
    send_whatsapp_message,
    format_whatsapp_message_context,
    get_telegram_status,
    save_telegram_config,
    get_telegram_messages,
    send_telegram_message,
    get_google_status,
    save_google_config,
    disconnect_google,
    get_unread_emails,
    get_upcoming_events,
    send_email,
)

logger = logging.getLogger("anara.routers.integrations")

router = APIRouter(tags=["Integrations"])

class ContactSaveRequest(BaseModel):
    name: str
    phone_number: str
    platform: str = "whatsapp"
    notes: Optional[str] = ""

class WhatsAppSendRequest(BaseModel):
    phone_number: str
    message: str

class TelegramConfigRequest(BaseModel):
    token: Optional[str] = None
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    default_chat_id: Optional[str] = None
    admin_ids: Optional[str] = None
    telegram_admin_ids: Optional[str] = None

class WhatsAppConfigRequest(BaseModel):
    allowed_numbers: Optional[str] = None

class TelegramSendRequest(BaseModel):
    message: str
    chat_id: Optional[str] = None

class GoogleConfigRequest(BaseModel):
    email: str
    credentials_json: Optional[str] = None

class EmailSendRequest(BaseModel):
    to: str
    subject: str
    body: str

# ── WhatsApp ──

@router.get("/api/integrations/whatsapp/status")
async def wa_status_endpoint():
    """Returns WhatsApp connection status and logged-in phone."""
    return await get_whatsapp_status()

@router.get("/api/integrations/whatsapp/qr")
async def wa_qr_endpoint():
    """Returns Base64 QR Code PNG Data URL for pairing."""
    return await get_whatsapp_qr()

@router.post("/api/integrations/whatsapp/logout")
async def wa_logout_endpoint():
    """Logs out and clears saved WhatsApp Web session."""
    return await logout_whatsapp()

@router.get("/api/integrations/whatsapp/messages")
async def wa_messages_endpoint(unread_only: bool = False, limit: int = 15):
    """Retrieves recent WhatsApp incoming messages."""
    return await get_whatsapp_messages(unread_only=unread_only, limit=limit)

@router.post("/api/integrations/whatsapp/send")
async def wa_send_endpoint(req: WhatsAppSendRequest):
    """Sends a WhatsApp text message."""
    return await send_whatsapp_message(req.phone_number, req.message)

@router.get("/api/integrations/whatsapp/config")
async def wa_get_config_endpoint():
    """Returns WhatsApp configuration including allowed numbers whitelist."""
    allowed = memory_engine.get_app_setting("whatsapp_allowed_numbers") or ""
    return {"allowed_numbers": allowed}

@router.post("/api/integrations/whatsapp/config")
async def wa_save_config_endpoint(req: WhatsAppConfigRequest):
    """Saves allowed numbers whitelist for WhatsApp."""
    if req.allowed_numbers is not None:
        memory_engine.set_app_setting("whatsapp_allowed_numbers", req.allowed_numbers.strip())
    return {"status": "success", "allowed_numbers": req.allowed_numbers}

class WhatsAppWebhookPayload(BaseModel):
    id: Optional[str] = None
    sender: Optional[str] = "WhatsApp User"
    phone: str
    participant: Optional[str] = None
    jid: Optional[str] = None
    isGroup: Optional[bool] = False
    text: str
    localPath: Optional[str] = None
    fileName: Optional[str] = None
    mediaType: Optional[str] = None
    mimeType: Optional[str] = None
    fileSize: Optional[int] = None
    quotedText: Optional[str] = None
    quotedSender: Optional[str] = None
    quotedLocalPath: Optional[str] = None
    quotedMediaType: Optional[str] = None
    timestamp: Optional[float] = None

@router.post("/api/integrations/whatsapp/webhook")
async def wa_webhook_endpoint(payload: WhatsAppWebhookPayload):
    """
    Receives incoming WhatsApp messages from local Baileys bridge and routes
    through the Unified Channel Adapter with Plan/Build Gate (FR-8, FR-9, FR-10).
    """
    from core.channel_adapter import ChannelRequest, process_channel_request

    p_dict = payload.dict()
    # If audio/voice note, attempt voice transcription
    if payload.mediaType == "audio" and payload.localPath:
        try:
            from cognition.audio import transcribe_audio_file
            transcript = await transcribe_audio_file(payload.localPath)
            if transcript:
                p_dict["text"] = f"{transcript}\n\n[Voice Note Transcription]"
        except Exception as stt_err:
            logger.debug(f"[WAWebhook] Audio STT skipped: {stt_err}")

    clean_text = format_whatsapp_message_context(p_dict).strip()
    if not clean_text:
        return {"status": "ignored", "reason": "empty_text"}

    # Check allowed numbers filter (optional security whitelist from app_settings)
    allowed_raw = memory_engine.get_app_setting("whatsapp_allowed_numbers")
    if allowed_raw:
        allowed_list = [n.strip().replace("+", "").replace("-", "") for n in allowed_raw.split(",") if n.strip()]
        clean_phone = payload.phone.replace("+", "").replace("-", "")
        if allowed_list and not any(clean_phone.endswith(allowed) or allowed.endswith(clean_phone) for allowed in allowed_list):
            logger.info(f"[WAWebhook] Message from {clean_phone} skipped (not in whatsapp_allowed_numbers whitelist).")
            return {"status": "skipped", "reason": "not_in_whitelist"}

    # Check for /stop command immediately before starting turn
    if clean_text.strip().lower().startswith(("/stop", "/cancel", "/abort")):
        from core.session_manager import session_state_manager
        interrupt_info = await session_state_manager.request_hard_interrupt(
            channel="whatsapp",
            channel_id=payload.phone,
            reason="whatsapp_user_stop"
        )
        details = []
        if interrupt_info.get("task_cancelled"):
            details.append("task cancelled")
        if interrupt_info.get("processes_killed", 0) > 0:
            details.append(f"{interrupt_info['processes_killed']} sub-processes terminated")
        if interrupt_info.get("pending_cleared"):
            details.append("pending plans cleared")
        detail_str = f" ({', '.join(details)})" if details else ""

        target_chat_id = payload.jid if (payload.isGroup and payload.jid) else payload.phone
        cancel_reply = f"🛑 *Agent task halted via /stop.*{detail_str}"
        await send_whatsapp_message(target_chat_id, cancel_reply)
        return {"status": "cancelled", "interrupt_info": interrupt_info}

    target_chat_id = payload.jid if (payload.isGroup and payload.jid) else payload.phone
    human_sender_id = payload.participant or payload.phone

    req = ChannelRequest(
        text=clean_text,
        channel="whatsapp",
        channel_id=target_chat_id,
        user_id=human_sender_id,
        sender_name=payload.sender or "WhatsApp User",
        trigger_type="interactive"
    )

    async def _send_prog(msg: str):
        try:
            await send_whatsapp_message(target_chat_id, msg)
        except Exception:
            pass

    try:
        res = await process_channel_request(req, progress_callback=_send_prog)
        from core.command_hub import get_chat_voice_mode
        voice_mode = get_chat_voice_mode("whatsapp", target_chat_id)  # 'text', 'only', 'both', 'auto'
        is_voice_turn = (payload.mediaType == "audio")

        # ALL slash commands and UI responses are ALWAYS delivered as text, NEVER voice!
        is_command_or_ui = getattr(res, "is_command", False) or clean_text.strip().startswith("/") or res.plan_pending

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
                voice_file = await synthesize_speech_audio(res.text)
                if voice_file:
                    from integrations.whatsapp import send_whatsapp_document
                    await send_whatsapp_document(to=target_chat_id, file_path=voice_file, caption="")
                    voice_sent = True
            except Exception as wa_v_err:
                logger.warning(f"[WAWebhook] Voice reply error: {wa_v_err}")

        should_send_text = (voice_mode != "only") or not voice_sent or is_command_or_ui
        if res.text and should_send_text:
            await send_whatsapp_message(target_chat_id, res.text)
        return {"status": "processed", "plan_pending": res.plan_pending}
    except Exception as e:
        logger.error(f"[WAWebhook] Error processing message: {e}")
        return {"status": "error", "message": str(e)}

# ── Contacts ──

@router.get("/api/integrations/contacts")
async def list_contacts_endpoint(platform: Optional[str] = None):
    """Lists saved contact mappings."""
    return memory_engine.get_all_contacts(platform=platform)

@router.post("/api/integrations/contacts")
async def save_contact_endpoint(req: ContactSaveRequest):
    """Saves or updates a contact mapping."""
    cid = memory_engine.save_contact(req.name, req.phone_number, req.platform, req.notes or "")
    return {"status": "success", "contact_id": cid}

@router.delete("/api/integrations/contacts/{contact_id}")
async def delete_contact_endpoint(contact_id: int):
    """Deletes a contact mapping."""
    ok = memory_engine.delete_contact(contact_id)
    return {"status": "success" if ok else "error"}

# ── Telegram ──

@router.get("/api/integrations/telegram/status")
async def telegram_status_endpoint():
    """Returns Telegram connection & bot status."""
    return await get_telegram_status()

@router.post("/api/integrations/telegram/config")
async def telegram_config_endpoint(req: TelegramConfigRequest):
    """
    Saves Telegram bot token, default chat ID & admin user IDs.
    Validates live connection via getMe API and auto-starts the background polling daemon.
    """
    token = (req.token or req.bot_token or "").strip()
    chat_id = (req.default_chat_id or req.chat_id or "").strip() or None
    admin_ids = (req.admin_ids or req.telegram_admin_ids or "").strip() or None

    save_telegram_config(token=token, default_chat_id=chat_id, admin_ids=admin_ids)
    if token:
        from integrations.telegram import start_telegram_polling_daemon
        start_telegram_polling_daemon()

    # Immediately query Telegram getMe API and return actual connection status
    return await get_telegram_status()

@router.get("/api/integrations/telegram/messages")
async def telegram_messages_endpoint(limit: int = 15):
    """Retrieves recent Telegram incoming messages."""
    return await get_telegram_messages(limit=limit)

@router.post("/api/integrations/telegram/send")
async def telegram_send_endpoint(req: TelegramSendRequest):
    """Sends a message via Telegram Bot."""
    return await send_telegram_message(req.message, req.chat_id)

# ── Google Workspace ──

@router.get("/api/integrations/google/status")
async def google_status_endpoint():
    """Returns Google Workspace connection status."""
    return await get_google_status()

@router.post("/api/integrations/google/config")
async def google_config_endpoint(req: GoogleConfigRequest):
    """Saves Google account email & credentials."""
    return await save_google_config(req.email)

@router.post("/api/integrations/google/disconnect")
async def google_disconnect_endpoint():
    """Disconnects Google Workspace account."""
    return await disconnect_google()

@router.get("/api/integrations/google/emails")
async def google_emails_endpoint(limit: int = 10):
    """Retrieves unread emails from Gmail."""
    return await get_unread_emails(limit=limit)

@router.get("/api/integrations/google/calendar")
async def google_calendar_endpoint(days: int = 7):
    """Retrieves upcoming calendar events."""
    return await get_upcoming_events(days=days)

@router.post("/api/integrations/google/send-email")
async def google_send_email_endpoint(req: EmailSendRequest):
    """Sends an email."""
    return await send_email(req.to, req.subject, req.body)
