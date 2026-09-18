"""
polling.py — Supervised Long-Polling Daemon for Telegram Bot API in Project Anara.
Anara Standard polling daemon supervision:
Provides conflict handling (HTTP 409), command registration, and graceful shutdown.
"""

import asyncio
import logging
from typing import Optional
import httpx

from .client import (
    TELEGRAM_API_BASE,
    get_stored_telegram_token,
    setup_telegram_bot_commands,
)

logger = logging.getLogger(__name__)

_telegram_daemon_task: Optional[asyncio.Task] = None
_telegram_daemon_running: bool = False
_last_update_id: int = 0


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

    # Import handler lazily to avoid circular imports
    from .handlers import process_incoming_telegram_update

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
