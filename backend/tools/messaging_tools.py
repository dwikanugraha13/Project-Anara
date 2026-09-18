"""
messaging_tools.py — Omnichannel Messaging Tools (Discord & Slack) for Project Anara.
Allows the agent to send and read messages from Discord and Slack channels.
"""

from typing import Any, Dict, List, Optional
from .events import _emit_agent_event


async def _tool_discord_send_message(text: str, channel_id: Optional[str] = None) -> Dict[str, Any]:
    """Sends a message to a Discord channel."""
    from integrations.discord import send_discord_message

    _emit_agent_event("agent_action_start", {
        "tool_name": "discord_send_message",
        "action_title": "Kirim Pesan Discord",
        "detail": f"Channel: {channel_id or 'Default'}",
        "icon": "message-square"
    })
    return await send_discord_message(text=text, channel_id=channel_id)


async def _tool_discord_read_messages(channel_id: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    """Reads recent messages from a Discord channel."""
    from integrations.discord import read_discord_messages

    _emit_agent_event("agent_action_start", {
        "tool_name": "discord_read_messages",
        "action_title": "Baca Pesan Discord",
        "detail": f"Limit: {limit}",
        "icon": "message-square"
    })
    return await read_discord_messages(channel_id=channel_id, limit=limit)


async def _tool_slack_send_message(text: str, channel: Optional[str] = None) -> Dict[str, Any]:
    """Sends a message to a Slack channel."""
    from integrations.slack import send_slack_message

    _emit_agent_event("agent_action_start", {
        "tool_name": "slack_send_message",
        "action_title": "Kirim Pesan Slack",
        "detail": f"Channel: {channel or 'Default'}",
        "icon": "hash"
    })
    return await send_slack_message(text=text, channel=channel)


async def _tool_slack_read_messages(channel: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    """Reads recent messages from a Slack channel."""
    from integrations.slack import read_slack_messages

    _emit_agent_event("agent_action_start", {
        "tool_name": "slack_read_messages",
        "action_title": "Baca Pesan Slack",
        "detail": f"Limit: {limit}",
        "icon": "hash"
    })
    return await read_slack_messages(channel=channel, limit=limit)


async def _tool_whatsapp_read_messages(unread_only: bool = False) -> Dict[str, Any]:
    """Reads unread messages from WhatsApp Web."""
    from integrations import get_unread_whatsapp_messages, is_whatsapp_connected
    if not is_whatsapp_connected():
        return {"status": "error", "message": "WhatsApp belum terhubung. Silakan scan QR code terlebih dahulu."}
    unread = await get_unread_whatsapp_messages()
    return {"status": "success", "unread_count": len(unread), "messages": unread}


async def _tool_whatsapp_send_message(recipient: str, message: str) -> Dict[str, Any]:
    """Sends a message via WhatsApp Web."""
    from integrations import send_whatsapp_message, is_whatsapp_connected
    if not is_whatsapp_connected():
        return {"status": "error", "message": "WhatsApp belum terhubung."}
    phone = (recipient or "").strip()
    msg = (message or "").strip()
    ok = await send_whatsapp_message(phone, msg)
    return {"status": "success" if ok else "error", "sent_to": phone}


async def _tool_telegram_read_messages(limit: int = 5) -> Dict[str, Any]:
    """Reads recent messages from Telegram Bot."""
    from integrations import get_recent_telegram_updates, get_telegram_status
    st = await get_telegram_status()
    if st.get("status") != "connected":
        return {"status": "error", "message": "Bot Telegram belum terhubung."}
    msgs = await get_recent_telegram_updates(limit=limit)
    return {"status": "success", "messages": msgs}


async def _tool_telegram_send_message(message: str, chat_id: Optional[str] = None) -> Dict[str, Any]:
    """Sends a message via Telegram Bot."""
    from integrations import send_telegram_message, get_telegram_status
    st = await get_telegram_status()
    if st.get("status") != "connected":
        return {"status": "error", "message": "Bot Telegram belum diatur."}
    return await send_telegram_message(str(message or ""), chat_id=chat_id)

