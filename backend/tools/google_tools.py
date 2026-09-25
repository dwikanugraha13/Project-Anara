"""
google_tools.py — Google Workspace Tools for Project Anara.
Provides read-only access to Gmail inbox and Google Calendar schedules.
"""

import logging
from typing import Any, Dict
from .registry import registry

logger = logging.getLogger(__name__)


async def _tool_gmail_read_inbox(limit: int = 5) -> Dict[str, Any]:
    from integrations import get_unread_emails, get_google_status
    st = await get_google_status()
    if st.get("status") != "connected":
        return {"status": "error", "message": "Google Workspace account is not connected."}
    emails = await get_unread_emails(limit=limit)
    return {"status": "success", "emails": emails}


async def _tool_calendar_get_schedule(days: int = 3) -> Dict[str, Any]:
    from integrations import get_upcoming_events, get_google_status
    st = await get_google_status()
    if st.get("status") != "connected":
        return {"status": "error", "message": "Google Workspace account is not connected."}
    events = await get_upcoming_events(days=days)
    return {"status": "success", "events": events}


def register_tools():
    registry.register_tool(
        name="gmail_read_inbox",
        description="Reads recent incoming emails from the user's Gmail inbox.",
        parameters={
            "type": "OBJECT",
            "properties": {"limit": {"type": "INTEGER", "description": "Maximum number of emails to read."}}
        },
        handler=_tool_gmail_read_inbox,
        risk="read_only",
        toolset="google_workspace",
        category="communication",
        icon="mail",
    )

    registry.register_tool(
        name="calendar_get_schedule",
        description="Views upcoming appointments and events from Google Calendar.",
        parameters={
            "type": "OBJECT",
            "properties": {"days": {"type": "INTEGER", "description": "Number of days ahead (default 3 days)."}}
        },
        handler=_tool_calendar_get_schedule,
        risk="read_only",
        toolset="google_workspace",
        category="communication",
        icon="mail",
    )


# Auto-register at import time
register_tools()
