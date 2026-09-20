"""
messaging_tools.py — Omnichannel Messaging Tools (Discord & Slack) for Project Anara.
Allows the agent to send and read messages from Discord and Slack channels.
"""

import os
from typing import Any, Dict, List, Optional
import httpx
from .events import _emit_agent_event


async def _tool_discord_send_message(text: str, channel_id: Optional[str] = None) -> Dict[str, Any]:
    """Sends a message to a Discord channel via ChannelManager."""
    from integrations.manager import channel_manager

    _emit_agent_event("agent_action_start", {
        "tool_name": "discord_send_message",
        "action_title": "Send Discord Message",
        "detail": f"Channel: {channel_id or 'Default'}",
        "icon": "message-square"
    })
    return await channel_manager.send_message("discord", target_id=channel_id or "", text=text)


async def _tool_discord_read_messages(channel_id: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    """Reads recent messages from a Discord channel."""
    _emit_agent_event("agent_action_start", {
        "tool_name": "discord_read_messages",
        "action_title": "Read Discord Messages",
        "detail": f"Limit: {limit}",
        "icon": "message-square"
    })
    token = (os.getenv("DISCORD_BOT_TOKEN") or "").strip()
    target_channel = (channel_id or os.getenv("DISCORD_CHANNEL_ID") or "").strip()
    if not token or not target_channel:
        return {
            "status": "error",
            "message": "DISCORD_BOT_TOKEN or target channel_id is not configured.",
        }

    try:
        headers = {"Authorization": f"Bot {token}", "User-Agent": "AnaraAgent/1.0"}
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"https://discord.com/api/v10/channels/{target_channel}/messages",
                headers=headers,
                params={"limit": min(limit, 50)},
            )
            if resp.status_code == 200:
                return {"status": "success", "messages": resp.json()}
            return {"status": "error", "code": resp.status_code, "detail": resp.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def _tool_slack_send_message(text: str, channel: Optional[str] = None) -> Dict[str, Any]:
    """Sends a message to a Slack channel via ChannelManager."""
    from integrations.manager import channel_manager

    _emit_agent_event("agent_action_start", {
        "tool_name": "slack_send_message",
        "action_title": "Send Slack Message",
        "detail": f"Channel: {channel or 'Default'}",
        "icon": "hash"
    })
    return await channel_manager.send_message("slack", target_id=channel or "", text=text)


async def _tool_slack_read_messages(channel: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    """Reads recent messages from a Slack channel."""
    _emit_agent_event("agent_action_start", {
        "tool_name": "slack_read_messages",
        "action_title": "Read Slack Messages",
        "detail": f"Limit: {limit}",
        "icon": "hash"
    })
    token = (os.getenv("SLACK_BOT_TOKEN") or "").strip()
    target_channel = (channel or os.getenv("SLACK_CHANNEL_ID") or "").strip()
    if not token or not target_channel:
        return {
            "status": "error",
            "message": "SLACK_BOT_TOKEN or target channel is not configured.",
        }

    try:
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://slack.com/api/conversations.history",
                headers=headers,
                params={"channel": target_channel, "limit": min(limit, 50)},
            )
            data = resp.json()
            if data.get("ok"):
                return {"status": "success", "messages": data.get("messages", [])}
            return {"status": "error", "error": data.get("error")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def _tool_whatsapp_read_messages(unread_only: bool = False) -> Dict[str, Any]:
    """Reads unread messages from WhatsApp Web."""
    from integrations import get_unread_whatsapp_messages, is_whatsapp_connected
    if not is_whatsapp_connected():
        return {"status": "error", "message": "WhatsApp bridge is not connected. Please scan QR code in Web Studio."}
    unread = await get_unread_whatsapp_messages()
    return {"status": "success", "unread_count": len(unread), "messages": unread}


async def _tool_whatsapp_send_message(recipient: str, message: str) -> Dict[str, Any]:
    """Sends a message via WhatsApp Web."""
    from integrations import send_whatsapp_message, is_whatsapp_connected
    if not is_whatsapp_connected():
        return {"status": "error", "message": "WhatsApp bridge is not connected."}
    phone = (recipient or "").strip()
    msg = (message or "").strip()
    ok = await send_whatsapp_message(phone, msg)
    return {"status": "success" if ok else "error", "sent_to": phone}


async def _tool_telegram_read_messages(limit: int = 5) -> Dict[str, Any]:
    """Reads recent messages from Telegram Bot."""
    from integrations import get_recent_telegram_updates, get_telegram_status
    st = await get_telegram_status()
    if st.get("status") != "connected":
        return {"status": "error", "message": "Telegram bot is not connected."}
    msgs = await get_recent_telegram_updates(limit=limit)
    return {"status": "success", "messages": msgs}


async def _tool_telegram_send_message(message: str, chat_id: Optional[str] = None) -> Dict[str, Any]:
    """Sends a message via Telegram Bot."""
    from integrations import send_telegram_message, get_telegram_status
    st = await get_telegram_status()
    if st.get("status") != "connected":
        return {"status": "error", "message": "Telegram bot token is not configured."}
    return await send_telegram_message(str(message or ""), chat_id=chat_id)

