"""
Shared State and Event Broadcast Hub for Project Anara Backend.
Houses active WebSocket pools, shared HTTP clients, diagnostic metrics,
and debounced real-time broadcast mechanisms.
"""
import asyncio
import io
import time
import logging
from typing import Dict, Optional, Any, Set, List
import httpx
from fastapi import WebSocket
from pydantic import BaseModel

logger = logging.getLogger("anara.shared_state")

# Active WebSocket connections & session registries
active_websockets: Set[WebSocket] = set()
active_sessions: Dict[str, Any] = {}
last_active_visual_payload: Optional[Dict[str, Any]] = None

chat_diagnostics: Dict[str, Any] = {
    "active_requests": 0,
    "last_error": None,
    "last_stage": "idle",
    "last_updated": None,
    "last_model": None,
}

_shared_http_client: Optional[httpx.AsyncClient] = None

def get_shared_http_client() -> httpx.AsyncClient:
    global _shared_http_client
    if _shared_http_client is None or _shared_http_client.is_closed:
        _shared_http_client = httpx.AsyncClient(
            timeout=15.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
            follow_redirects=True,
        )
    return _shared_http_client

async def close_shared_http_client():
    global _shared_http_client
    if _shared_http_client and not _shared_http_client.is_closed:
        await _shared_http_client.aclose()

# ── Debounced Brain Mutation Sync ──
_brain_sync_pending: Dict[str, Dict[str, Any]] = {}
_brain_sync_lock = asyncio.Lock()
_brain_sync_task: Optional[asyncio.Task] = None
_BRAIN_SYNC_DEBOUNCE_SEC = 2.0

async def _flush_brain_sync():
    await asyncio.sleep(_BRAIN_SYNC_DEBOUNCE_SEC)
    async with _brain_sync_lock:
        pending = dict(_brain_sync_pending)
        _brain_sync_pending.clear()
    if not pending or not active_websockets:
        return
    payload = {
        "type": "brain_sync",
        "event": "batch",
        "data": {"events": list(pending.keys())},
        "timestamp": time.time(),
    }
    for ws in list(active_websockets):
        try:
            await ws.send_json(payload)
        except Exception:
            pass

def broadcast_brain_sync(event_type: str, data: Optional[Dict[str, Any]] = None):
    """Debounced broadcast of mutations to frontend."""
    global _brain_sync_task
    _brain_sync_pending[event_type] = data or {}
    if _brain_sync_task is None or _brain_sync_task.done():
        try:
            loop = asyncio.get_running_loop()
            _brain_sync_task = loop.create_task(_flush_brain_sync())
        except RuntimeError:
            pass

def broadcast_agent_event(event_data: Dict[str, Any]):
    """Broadcasts live agent tool executions and proactive HUD projections to frontend."""
    global last_active_visual_payload
    if not active_websockets:
        return
    try:
        e_type = event_data.get("type") or "agent_action"
        if e_type in ["hud_visual", "agent_hud_project"]:
            last_active_visual_payload = {
                "visualType": event_data.get("visual_type") or event_data.get("visualType") or "image",
                "imageUrl": event_data.get("image_url") or event_data.get("imageUrl"),
                "imageTitle": event_data.get("image_title") or event_data.get("imageTitle"),
                "sourceDomain": event_data.get("source_domain") or event_data.get("sourceDomain"),
                "sourceUrl": event_data.get("source_url") or event_data.get("sourceUrl"),
                "weatherData": event_data.get("weather_data") or event_data.get("weatherData"),
                "codeData": event_data.get("code_data") or event_data.get("codeData"),
                "systemHudData": event_data.get("system_hud_data") or event_data.get("systemHudData"),
                "knowledgeCardData": event_data.get("knowledge_card_data") or event_data.get("knowledgeCardData"),
                "todoData": event_data.get("todo_data") or event_data.get("todoData"),
                "planData": event_data.get("planData") or event_data.get("plan_data"),
                "images": event_data.get("images", []),
                "mediaType": event_data.get("mediaType") or "hud",
                "timestamp": time.time(),
            }

        loop = asyncio.get_running_loop()
        for ws in list(active_websockets):
            loop.create_task(ws.send_json(event_data))
    except RuntimeError:
        pass

def pcm_to_wav_bytes(pcm_data: bytes, sample_rate: int = 16000) -> bytes:
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_data)
    return buf.getvalue()
