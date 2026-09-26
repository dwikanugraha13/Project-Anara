"""
telemetry_routes.py — Server-Sent Events (SSE) & WebSocket Telemetry Streaming for Project Anara.
Allows Web Studio, HUD widgets, and external dashboards to subscribe to real-time agent telemetry.
"""

from __future__ import annotations

import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from telemetry.event_bus import telemetry_bus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["telemetry"])


@router.get("/api/telemetry/stream/{session_id}")
async def sse_telemetry_stream(session_id: str):
    """Server-Sent Events (SSE) stream for browser front-end / Web Studio."""
    clean_sid = str(session_id or "default")
    queue = telemetry_bus.subscribe(clean_sid)

    async def event_generator():
        try:
            # Send initial keepalive
            yield f"data: {json.dumps({'event_type': 'connected', 'session_id': clean_sid})}\n\n"
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event.to_dict())}\n\n"
        except asyncio.CancelledError:
            pass
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
    """Two-way WebSocket streaming endpoint for live HUD widgets (decoupled telemetry & ping pump)."""
    await websocket.accept()
    clean_sid = str(session_id or "default")
    queue = telemetry_bus.subscribe(clean_sid)

    async def _send_pump():
        await websocket.send_json({"event_type": "connected", "session_id": clean_sid})
        while True:
            event = await queue.get()
            await websocket.send_json(event.to_dict())

    async def _recv_pump():
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")

    try:
        await asyncio.gather(_send_pump(), _recv_pump())
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as e:
        logger.debug(f"[TelemetryWS] Connection closed: {e}")
    finally:
        telemetry_bus.unsubscribe(clean_sid, queue)
