"""
telemetry_routes.py — Server-Sent Events (SSE) & WebSocket Telemetry Streaming for Project Anara.
Allows Web Studio, HUD widgets, and external dashboards to subscribe to real-time agent telemetry.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from telemetry.event_bus import telemetry_bus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["telemetry"])


@router.get("/api/telemetry/stream/{session_id}")
async def sse_telemetry_stream(session_id: str):
    """Server-Sent Events (SSE) stream for browser front-end / Web Studio with periodic keepalive."""
    clean_sid = re.sub(r"[^a-zA-Z0-9_\-\.:]", "", str(session_id or "default"))[:128] or "default"
    queue = telemetry_bus.subscribe(clean_sid)

    async def event_generator():
        try:
            # Send initial connection confirmation
            yield f"data: {json.dumps({'event_type': 'connected', 'session_id': clean_sid})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event.to_dict(), default=str)}\n\n"
                except asyncio.TimeoutError:
                    # SSE keepalive comment prevents reverse proxies (NGINX, Cloudflare) from closing idle streams
                    yield f": keepalive {time.time():.0f}\n\n"
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"[TelemetrySSE] Stream terminated: {e}")
        finally:
            telemetry_bus.unsubscribe(clean_sid, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.websocket("/ws/telemetry/{session_id}")
async def websocket_telemetry(websocket: WebSocket, session_id: str):
    """
    Two-way WebSocket streaming endpoint for live HUD widgets.
    Decoupled sender and receiver pumps with guaranteed task lifecycle cancellation.
    """
    await websocket.accept()
    clean_sid = re.sub(r"[^a-zA-Z0-9_\-\.:]", "", str(session_id or "default"))[:128] or "default"
    queue = telemetry_bus.subscribe(clean_sid)

    async def _send_pump():
        await websocket.send_json({"event_type": "connected", "session_id": clean_sid})
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=20.0)
                await websocket.send_json(event.to_dict())
            except asyncio.TimeoutError:
                # Periodic application-level heartbeat
                await websocket.send_json({"event_type": "keepalive", "session_id": clean_sid})

    async def _recv_pump():
        while True:
            msg = await websocket.receive_text()
            clean_msg = (msg or "").strip().lower()
            if clean_msg == "ping" or '"ping"' in clean_msg:
                await websocket.send_text("pong")

    send_task = asyncio.create_task(_send_pump())
    recv_task = asyncio.create_task(_recv_pump())

    try:
        done, pending = await asyncio.wait(
            [send_task, recv_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for t in done:
            if not t.cancelled():
                exc = t.exception()
                if exc and not isinstance(exc, (WebSocketDisconnect, asyncio.CancelledError)):
                    logger.debug(f"[TelemetryWS] Pump error: {exc}")
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as e:
        logger.debug(f"[TelemetryWS] Connection closed: {e}")
    finally:
        send_task.cancel()
        recv_task.cancel()
        await asyncio.gather(send_task, recv_task, return_exceptions=True)
        telemetry_bus.unsubscribe(clean_sid, queue)
