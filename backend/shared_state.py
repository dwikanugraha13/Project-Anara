"""
Shared State and Event Broadcast Hub for Project Anara Backend.
Houses active WebSocket pools, shared HTTP clients, diagnostic metrics,
and debounced real-time broadcast mechanisms.
"""
import asyncio
import io
import time
import logging
import threading
from typing import Dict, Optional, Any, Set, List
import httpx
from fastapi import WebSocket
from pydantic import BaseModel

logger = logging.getLogger("anara.shared_state")

# Active WebSocket connections & session registries
active_websockets: Set[WebSocket] = set()
websocket_session_map: Dict[WebSocket, Optional[int]] = {}
active_sessions: Dict[str, Any] = {}
last_active_visual_payload: Optional[Dict[str, Any]] = None

def register_websocket(ws: WebSocket, session_id: Optional[int] = None):
    """Registers an active WebSocket and binds it to a specific session ID for strict cross-talk isolation."""
    active_websockets.add(ws)
    websocket_session_map[ws] = session_id

def update_websocket_session(ws: WebSocket, session_id: Optional[int]):
    """Updates the active session ID that a connected WebSocket is currently viewing."""
    if ws in active_websockets:
        websocket_session_map[ws] = session_id

def unregister_websocket(ws: WebSocket):
    """Safely removes a WebSocket from the active broadcast pool."""
    active_websockets.discard(ws)
    websocket_session_map.pop(ws, None)

chat_diagnostics: Dict[str, Any] = {
    "active_requests": 0,
    "last_error": None,
    "last_stage": "idle",
    "last_updated": None,
    "last_model": None,
}

_shared_http_client: Optional[httpx.AsyncClient] = None
_http_client_lock = threading.Lock()
_main_event_loop: Optional[asyncio.AbstractEventLoop] = None


def set_main_event_loop(loop: asyncio.AbstractEventLoop):
    """Registers the primary backend event loop for thread-safe cross-service dispatch."""
    global _main_event_loop
    _main_event_loop = loop


def _get_active_loop() -> Optional[asyncio.AbstractEventLoop]:
    """Retrieves current running event loop or falls back to registered main event loop."""
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        if _main_event_loop and _main_event_loop.is_running():
            return _main_event_loop
    return None


def get_shared_http_client() -> httpx.AsyncClient:
    """Thread-safe lazy initialization of shared AsyncClient connection pool."""
    global _shared_http_client
    with _http_client_lock:
        if _shared_http_client is None or _shared_http_client.is_closed:
            _shared_http_client = httpx.AsyncClient(
                timeout=15.0,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
                follow_redirects=True,
            )
        return _shared_http_client


async def close_shared_http_client():
    """Cleanly closes shared HTTP client and resets instance."""
    global _shared_http_client
    with _http_client_lock:
        client = _shared_http_client
        _shared_http_client = None
    if client and not client.is_closed:
        try:
            await client.aclose()
        except Exception:
            pass


async def _safe_ws_send(ws: WebSocket, payload: Dict[str, Any]):
    """Safely dispatches JSON payload to WebSocket; auto-discards disconnected clients."""
    try:
        await ws.send_json(payload)
    except Exception:
        active_websockets.discard(ws)


# ── Debounced Brain Mutation Sync (Thread-Safe) ──
_brain_sync_pending: Dict[str, Dict[str, Any]] = {}
_brain_sync_dict_lock = threading.Lock()
_brain_sync_task: Optional[asyncio.Task] = None
_BRAIN_SYNC_DEBOUNCE_SEC = 2.0


async def _flush_brain_sync():
    """Debounced worker flushing pending SQLite mutations to active WebSockets."""
    await asyncio.sleep(_BRAIN_SYNC_DEBOUNCE_SEC)
    with _brain_sync_dict_lock:
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
        await _safe_ws_send(ws, payload)


def broadcast_brain_sync(event_type: str, data: Optional[Dict[str, Any]] = None):
    """Thread-safe debounced broadcast of memory engine mutations to frontend."""
    global _brain_sync_task
    with _brain_sync_dict_lock:
        _brain_sync_pending[event_type] = data or {}

    loop = _get_active_loop()
    if not loop:
        return

    if _brain_sync_task is None or _brain_sync_task.done():
        try:
            cur_loop = None
            try:
                cur_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
            if cur_loop and cur_loop == loop:
                _brain_sync_task = loop.create_task(_flush_brain_sync())
            else:
                asyncio.run_coroutine_threadsafe(_flush_brain_sync(), loop)
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

        loop = _get_active_loop()
        if not loop:
            return

        cur_loop = None
        try:
            cur_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        event_sid = event_data.get("session_id") or event_data.get("sessionId")
        for ws in list(active_websockets):
            ws_sid = websocket_session_map.get(ws)
            # Session Isolation Guard: If this event is scoped to a session,
            # only deliver to WebSockets currently tuned to that session.
            if event_sid is not None and ws_sid is not None and ws_sid != event_sid:
                continue

            if cur_loop and cur_loop == loop:
                loop.create_task(_safe_ws_send(ws, event_data))
            else:
                asyncio.run_coroutine_threadsafe(_safe_ws_send(ws, event_data), loop)
    except Exception as e:
        logger.debug(f"[SharedState] Broadcast notice: {e}")


def pcm_to_wav_bytes(pcm_data: bytes, sample_rate: int = 16000) -> bytes:
    """Encapsulates raw PCM16 samples into a valid WAV container with 16-bit alignment."""
    if not pcm_data:
        return b""
    # Ensure 16-bit (2-byte) frame boundary alignment
    aligned_data = pcm_data[: len(pcm_data) - (len(pcm_data) % 2)]
    buf = io.BytesIO()
    import wave
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(aligned_data)
    return buf.getvalue()
