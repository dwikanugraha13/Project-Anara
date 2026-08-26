"""
FastAPI backend for 3D AI Voice Assistant (J.A.R.V.I.S. Edition).
Provides WebSocket endpoint for real-time bidirectional voice communication
and REST API endpoints for Brain Database & Memory Management.
"""
import asyncio
import base64
import json
import logging
import os
import re
import sys
import time as _time
from typing import Dict, Optional, Any, List, Set, Tuple

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Prevent OpenBLAS / OMP multithreading memory errors on Windows
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.genai import types

from ai_service import GeminiLiveService, SYSTEM_PROMPT
from audio_utils import estimate_audio_intensity, analyze_speech_emotion, AcousticSERTracker
from emotion_engine import EmotionEngine
from image_service import generate_visual_projection, could_be_visual_request
from memory_service import memory_engine, get_current_indonesian_time_str
from key_manager import key_manager

# Specific explicit dance trigger verbs (only active dance actions)
DANCE_ACTION_WORDS = [
    "nari", "menari", "joget", "dance", "dansa", "rumba"
]

COMMAND_MARKERS = [
    "dong", "ayo", "coba", "tolong", "bisa", "yuk", "silakan", "coba kamu", "mohon"
]

REPEAT_WORDS = [
    "lagi", "sekali lagi", "ulang", "satu lagi", "encore",
]

NAME_VARIATIONS = [
    "anara", "hanara", "annara", "anarah", "nara"
]

INFO_QUERY_MARKERS = [
    "apa itu", "apa tarian", "sejarah", "adat", "tradisional", "nama tarian", "jenis tarian", "asal usul", "artinya", "definisi"
]

def normalize_text(text: str) -> str:
    """Strip all punctuation and convert to lowercase for robust matching."""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower(), flags=re.UNICODE)
    return " ".join(cleaned.split())

def is_dance_command(text: str) -> bool:
    """
    Return True strictly when the user EXPLICITLY commands Anara to dance using multi-word phrases (2-3+ words).
    Never triggers on single isolated words like 'nari', 'rumba', 'hibur', or casual conversation.
    """
    norm = normalize_text(text)
    if not norm:
        return False

    # Block informational or historical queries
    if any(q in norm for q in INFO_QUERY_MARKERS):
        return False

    words = norm.split()
    # Strict rule: Require at least 2 words
    if len(words) < 2:
        return False

    # Explicit multi-word command regex patterns (requires intent + action)
    DANCE_EXPLICIT_PATTERNS = [
        r"\b(?:ayo|yuk|coba|tolong|minta|silakan)\s+(?:nari|menari|joget|dansa|dance)\b",
        r"\b(?:nari|menari|joget|dansa|dance)\s+(?:dong|sekarang|lagi|yuk|nih|rumba|untukku)\b",
        r"\b(?:anara|nara)\s+(?:ayo|yuk|coba|tolong)?\s*(?:nari|menari|joget|dansa|dance)\b",
        r"\b(?:tunjukkan|tampilkan|mainkan)\s+(?:tarian|dance|joget|rumba)\b",
        r"\b(?:hibur|hiburan)\s+(?:aku|kami|saya)\s+(?:dengan|pake|pakai)?\s*(?:tarian|nari|joget|dance)\b",
        r"\b(?:dance|nari)\s+for\s+me\b",
    ]

    for pat in DANCE_EXPLICIT_PATTERNS:
        if re.search(pat, norm):
            return True

    return False

def get_dance_reply_prompt(text: str) -> str:
    norm = normalize_text(text)
    # 1. Perintah Menari Lagi -> "Oke, musik!"
    if any(q in norm for q in REPEAT_WORDS):
        return "Sistem: Perintah menari lagi diterima. Ucapkan dengan suara ceria dan manis hanya kalimat ini tanpa kata lain: Oke, musik!"
    # 2. Perintah Langsung -> "Anara siap!"
    return "Sistem: Perintah menari diterima. Ucapkan dengan suara ceria hanya dua kata ini tanpa kata lain: Anara siap!"

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("ai_service").setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Anara 3D Voice & Visual AI API",
    description="Real-time voice-to-voice AI assistant with 3D avatar & holographic HUD projections",
    version="2.5.0"
)

# CORS configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections
active_sessions: Dict[str, GeminiLiveService] = {}
active_websockets: Set[WebSocket] = set()


async def broadcast_brain_sync(event_type: str, data: Dict[str, Any]):
    """Broadcasts SQLite memory/todo mutations to all connected clients in real-time."""
    if not active_websockets:
        return
    payload = {
        "type": "brain_sync",
        "event": event_type,
        "data": data,
        "timestamp": _time.time()
    }
    dead = set()
    for ws in list(active_websockets):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)
    for d in dead:
        active_websockets.discard(d)


memory_engine.register_mutation_listener(broadcast_brain_sync)


def pcm_to_wav_bytes(pcm_data: bytes, sample_rate: int = 16000) -> bytes:
    import io, wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


# ── Pydantic Request Models ──────────────────────────────────────────────────

class MemoryCreateRequest(BaseModel):
    speaker_name: str
    key: str
    value: str
    category: str = "preference"

class NoteCreateRequest(BaseModel):
    title: str
    content: str = ""
    category: str = "todo"
    due_date: Optional[str] = None
    speaker_name: Optional[str] = None

class AnimationUpsertRequest(BaseModel):
    name: str
    category: str = "gesture"
    emotion: str = "neutral"
    gesture: str = "talking"
    keywords: List[str] = []
    intensity: float = 0.8
    duration_sec: float = 3.0
    description: str = ""


# ── REST Endpoints for Brain & Database Management ───────────────────────────

@app.get("/")
async def health_check():
    """Health check & status endpoint."""
    time_info = get_current_indonesian_time_str()
    stats = memory_engine.get_brain_stats()
    return {
        "status": "ok",
        "service": "Project Anara",
        "time": time_info,
        "active_sessions": len(active_sessions),
        "brain_stats": stats
    }

@app.get("/api/brain/overview")
async def get_brain_overview():
    """Returns complete summary of speakers, memories, notes, projects, and stats."""
    stats = memory_engine.get_brain_stats()
    speakers = memory_engine.get_all_speakers()
    notes = memory_engine.get_notes_and_todos()
    memories = memory_engine.get_all_memories()
    projects = memory_engine.get_projects_for_speaker()
    conversations = memory_engine.get_recent_conversations(limit=50)
    time_info = get_current_indonesian_time_str()

    return {
        "stats": stats,
        "speakers": speakers,
        "notes": notes,
        "memories": memories,
        "projects": projects,
        "recent_conversations": conversations,
        "time": time_info
    }

@app.get("/api/proxy-image")
async def proxy_image_endpoint(url: str):
    """Proxies real image requests to bypass browser referrer and CORS restrictions."""
    if not url or not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                c_type = resp.headers.get("content-type", "image/jpeg")
                if "image" not in c_type:
                    c_type = "image/jpeg"
                return Response(content=resp.content, media_type=c_type, headers={
                    "Cache-Control": "public, max-age=86400",
                    "Access-Control-Allow-Origin": "*"
                })
    except Exception as e:
        logger.warning(f"[ImageProxy] Error fetching image {url[:60]}: {e}")
    raise HTTPException(status_code=404, detail="Image could not be retrieved")

@app.get("/api/brain/memories")
async def get_memories(speaker: Optional[str] = None):
    """Retrieves memories for a specific speaker or all."""
    if speaker:
        return memory_engine.get_memories_for_speaker(speaker)
    return memory_engine.get_all_memories()

@app.post("/api/brain/memories")
async def create_memory(req: MemoryCreateRequest):
    """Manually creates or updates a memory in SQLite."""
    ok = memory_engine.store_memory(req.speaker_name, req.key, req.value, req.category)
    return {"status": "success" if ok else "error"}

@app.delete("/api/brain/memories/{memory_id}")
async def delete_memory_endpoint(memory_id: int):
    """Deletes a memory by ID."""
    ok = memory_engine.delete_memory_by_id(memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "success", "deleted_id": memory_id}

@app.get("/api/brain/notes")
async def get_notes(category: Optional[str] = None, speaker: Optional[str] = None):
    """Retrieves notes and to-do lists."""
    return memory_engine.get_notes_and_todos(category=category, speaker_name=speaker)

@app.post("/api/brain/notes")
async def create_note(req: NoteCreateRequest):
    """Creates a new note or to-do task."""
    note_id = memory_engine.create_note_or_todo(
        title=req.title,
        content=req.content,
        category=req.category,
        due_date=req.due_date,
        speaker_name=req.speaker_name
    )
    return {"status": "success", "note_id": note_id}

@app.patch("/api/brain/notes/{note_id}/toggle")
async def toggle_note_todo(note_id: int):
    """Toggles to-do item completed state."""
    ok = memory_engine.toggle_todo(note_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"status": "success", "note_id": note_id}

@app.delete("/api/brain/notes/{note_id}")
async def delete_note_endpoint(note_id: int):
    """Deletes a note or to-do item."""
    ok = memory_engine.delete_note_or_todo(note_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"status": "success", "deleted_id": note_id}

@app.get("/api/brain/conversations")
async def get_conversations(limit: int = 25, speaker: Optional[str] = None):
    """Retrieves episodic conversation logs."""
    return memory_engine.get_recent_conversations(limit=limit, speaker_name=speaker)

@app.delete("/api/brain/conversations")
async def clear_conversations_endpoint():
    """Clears all conversation logs."""
    memory_engine.clear_conversations()
    return {"status": "success"}

@app.delete("/api/brain/conversations/{conversation_id}")
async def delete_conversation_endpoint(conversation_id: int):
    """Deletes a single conversation log entry."""
    ok = memory_engine.delete_conversation_by_id(conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation entry not found")
    return {"status": "success", "deleted_id": conversation_id}

class SpeakerCreateRequest(BaseModel):
    name: str

class SpeakerCalibrateRequest(BaseModel):
    audio_base64: str

class ActiveSpeakerRequest(BaseModel):
    name: Optional[str] = None

@app.get("/api/brain/speakers")
async def get_speakers():
    """Returns registered speakers and voice biometric profiles."""
    return memory_engine.get_all_speakers()

@app.post("/api/brain/speakers")
async def create_speaker_endpoint(req: SpeakerCreateRequest):
    """Creates a new speaker profile in SQLite."""
    res = memory_engine.enroll_or_update_speaker(req.name)
    return res

@app.post("/api/brain/speakers/{speaker_name}/calibrate")
async def calibrate_speaker_endpoint(speaker_name: str, req: SpeakerCalibrateRequest):
    """Calibrates voice biometrics for a speaker profile from base64 audio."""
    try:
        raw_bytes = base64.b64decode(req.audio_base64)
        pcm_bytes = raw_bytes
        if len(raw_bytes) > 44 and raw_bytes[:4] == b"RIFF":
            import io, wave
            with wave.open(io.BytesIO(raw_bytes), "rb") as wf:
                pcm_bytes = wf.readframes(wf.getnframes())
        res = memory_engine.calibrate_speaker_voice(speaker_name, pcm_bytes)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal memproses kalibrasi suara: {e}")

class ProjectCreateRequest(BaseModel):
    name: str
    speaker_name: Optional[str] = None
    tech_stack: Optional[str] = ""
    goal: Optional[str] = ""
    status: Optional[str] = "active"
    notes: Optional[str] = ""

@app.get("/api/brain/projects")
async def get_projects(speaker_name: Optional[str] = None):
    """Retrieves personal projects for a speaker."""
    return memory_engine.get_projects_for_speaker(speaker_name)

@app.post("/api/brain/projects")
async def create_project_endpoint(req: ProjectCreateRequest):
    """Creates or updates a personal project for a speaker."""
    proj_id = memory_engine.create_or_update_project(
        name=req.name,
        speaker_name=req.speaker_name,
        tech_stack=req.tech_stack or "",
        goal=req.goal or "",
        status=req.status or "active",
        notes=req.notes or ""
    )
    return {"status": "success", "id": proj_id}

@app.delete("/api/brain/projects/{project_id}")
async def delete_project_endpoint(project_id: int):
    """Deletes a project by its ID."""
    ok = memory_engine.delete_project(project_id)
    return {"status": "success" if ok else "error"}

@app.delete("/api/brain/speakers/{speaker_name}")
async def delete_speaker_endpoint(speaker_name: str):
    """Deletes a speaker and all associated data."""
    ok = memory_engine.delete_speaker(speaker_name)
    return {"status": "success" if ok else "error"}

@app.get("/api/brain/semantic-search")
async def semantic_search_endpoint(query: str, speaker_name: Optional[str] = None, limit: int = 6):
    """JARVIS 2.0 Semantic Memory RAG search endpoint."""
    return memory_engine.semantic_search_brain(query, speaker_name=speaker_name, top_k=limit)

@app.get("/api/brain/animations")
async def get_animations_endpoint():
    """Returns all registered 3D animation & behavior profiles from the database."""
    return memory_engine.get_all_animations()

@app.post("/api/brain/animations")
async def upsert_animation_endpoint(req: AnimationUpsertRequest):
    """Creates or updates a 3D animation/behavior profile in the database."""
    ok = memory_engine.upsert_animation(
        name=req.name,
        category=req.category,
        emotion=req.emotion,
        gesture=req.gesture,
        keywords=req.keywords,
        intensity=req.intensity,
        duration_sec=req.duration_sec,
        description=req.description
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Gagal menyimpan animasi")
    return {"status": "success"}

@app.delete("/api/brain/animations/{animation_name}")
async def delete_animation_endpoint(animation_name: str):
    """Deletes an animation profile from the database."""
    ok = memory_engine.delete_animation(animation_name)
    if not ok:
        raise HTTPException(status_code=404, detail="Animation not found")
    return {"status": "success"}

@app.get("/api/brain/system-status")
async def get_system_status():
    """JARVIS Core telemetry stats."""
    stats = memory_engine.get_brain_stats()
    active_key = key_manager.get_active_key()
    k_preview = f"{active_key[:8]}...{active_key[-4:]}" if len(active_key) > 12 else "configured"
    
    return {
        "core_status": "OPTIMAL",
        "ai_model": os.getenv("GEMINI_MODEL", "gemini-3.1-flash-live-preview"),
        "key_pool_total": key_manager.total_keys,
        "active_key_preview": k_preview,
        "memory_nodes": stats["memories_count"],
        "notes_count": stats["notes_count"],
        "conversations_logged": stats["conversations_count"],
        "active_websocket_sessions": len(active_sessions),
        "db_size_kb": round(stats["db_size_bytes"] / 1024, 2)
    }


# ── WebSocket Real-Time Voice & HUD Communication ────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for real-time voice communication and JARVIS Holographic HUD projections.
    """
    await websocket.accept()
    active_websockets.add(websocket)
    session_id = str(id(websocket))
    logger.info(f"WebSocket connected: {session_id}")

    api_key = key_manager.get_active_key()
    if not api_key:
        await websocket.send_json({
            "type": "error",
            "data": "GEMINI_API_KEY not configured on server"
        })
        await websocket.close()
        return

    # Start session in Guest / Waiting state until dynamic voice biometrics matches
    current_speaker_name = None
    await websocket.send_json({"type": "speaker_identified", "name": None})

    gemini_service = GeminiLiveService(api_key=api_key, active_speaker=None)
    emotion_engine = EmotionEngine()
    active_sessions[session_id] = gemini_service

    # VAD, Audio & Speaker Memory state
    ai_transcript_buffer = ""
    ai_is_speaking = False
    user_audio_buffer = bytearray()
    last_speech_time = 0.0
    speech_start_time = 0.0
    last_user_voice_text = ""
    ser_tracker = AcousticSERTracker(sample_rate=16000, window_duration_sec=1.2)
    last_ser_emit_time = 0.0

    HALLUCINATED_PHRASES = [
        "terima kasih sudah menonton",
        "terima kasih telah menonton",
        "terimakasih sudah menonton",
        "terimakasih telah menonton",
        "jangan lupa like comment and subscribe",
        "subtitles by",
        "subtitle by",
        "amara.org",
        "transcribed by",
        "silakan menonton",
        "selamat menonton",
        "thank you for watching",
        "thanks for watching",
        "bye bye",
        "titik",
        "koma",
    ]

    def clean_transcript_text(text: str) -> str:
        """Strip audio model timestamps (e.g. 00:00, 00:01, 000) and extra artifacts."""
        cleaned = re.sub(r"\[?\b\d{1,3}(?::\d{2})+(?:\.\d+)?\b\]?", "", text)
        cleaned = re.sub(r"\b000\b", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    async def transcribe_and_subtitle_audio(audio_pcm: bytes):
        """Transcribes user speech with strict anti-hallucination filtering."""
        nonlocal current_speaker_name
        if len(audio_pcm) < 4800:  # less than 150ms of audio
            return

        # ── 1. INSTANT LOCAL VOICE BIOMETRICS MATCH (Runs in ~5ms locally) ──
        try:
            id_name, conf, _ = memory_engine.identify_speaker(audio_pcm)
            if id_name:
                if current_speaker_name != id_name:
                    current_speaker_name = id_name
                    gemini_service.set_active_speaker(id_name)
                    await websocket.send_json({"type": "speaker_identified", "name": id_name})
                    logger.info(f"[Voice Biometrics Match] Recognized active speaker: '{id_name}' (conf={conf:.3f})")
            else:
                # Friend or Unregistered voice detected -> automatically switch to Tamu (Guest)
                if current_speaker_name is not None:
                    current_speaker_name = None
                    gemini_service.set_active_speaker(None)
                    await websocket.send_json({"type": "speaker_identified", "name": None})
                    logger.info(f"[Voice Biometrics Match] Voice not recognized (best_conf={conf:.3f}) -> Switched to Tamu (Guest)")
        except Exception as e_bio:
            logger.warning(f"[Voice Biometrics Error]: {e_bio}")

        # ── 2. Speech Emotion Recognition (SER) Acoustic Tone Analysis ──
        try:
            acoustic_tone = analyze_speech_emotion(audio_pcm)
            logger.info(f"[Acoustic Tone SER] Emotion: {acoustic_tone['emotion'].upper()} | Pitch: {acoustic_tone['pitch_hz']}Hz | RMS: {acoustic_tone['rms']} | {acoustic_tone['tone_description']}")
            await websocket.send_json({
                "type": "acoustic_emotion",
                "data": acoustic_tone
            })
            if acoustic_tone["emotion"] == "sad":
                await push_emotion("empathetic", "empathy", 0.95)
            elif acoustic_tone["emotion"] == "angry":
                await push_emotion("calm", "disagree", 0.75)
            elif acoustic_tone["emotion"] == "happy":
                await push_emotion("happy", "joy", 0.90)
        except Exception as e_ser:
            logger.warning(f"[SER Tone Error]: {e_ser}")

        overall_intensity = estimate_audio_intensity(audio_pcm)
        if overall_intensity < 0.005:
            logger.info(f"[Audio STT] Ignored low-energy ambient noise (RMS={overall_intensity:.4f})")
            return

        try:
            wav_bytes = pcm_to_wav_bytes(audio_pcm, 16000)
            prompt = (
                "Kamu adalah modul transkripsi suara Bahasa Indonesia yang sangat akurat untuk asisten Anara.\n\n"
                "Tugas Utama:\n"
                "1. Transkripsikan dengan PERSIS apa yang diucapkan pengguna dalam audio ini.\n"
                "2. PENTING (ANTI-HALUSINASI): Jika audio HANYA berisi hening, desis mikrofon, nafas, ketukan, atau suara bising tanpa kata-kata manusia yang jelas, KEMBALIKAN: {\"user_text\": \"\"}.\n"
                "3. DILARANG KERAS mengarang kalimat jika tidak ada orang berbicara.\n"
                "4. DILARANG menyertakan timestamp atau angka durasi waktu (seperti 00:00, 000, 00:01).\n\n"
                "KEMBALIKAN HANYA FORMAT JSON VALID:\n"
                '{"user_text": "..."}'
            )
            res = None
            stt_config = types.GenerateContentConfig(max_output_tokens=80, temperature=0.1)
            active_client = key_manager.get_client()
            for mdl in ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]:
                try:
                    res = await asyncio.wait_for(
                        active_client.aio.models.generate_content(
                            model=mdl,
                            contents=types.Content(
                                parts=[
                                    types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav"),
                                    types.Part.from_text(text=prompt),
                                ]
                            ),
                            config=stt_config
                        ),
                        timeout=3.0
                    )
                    if res and res.text:
                        break
                except Exception as g_err:
                    err_s = str(g_err).lower()
                    if any(q in err_s for q in ["429", "quota", "resource_exhausted", "rate limit"]):
                        logger.warning(f"[Audio STT] Quota hit on key. Rotating key and retrying...")
                        key_manager.rotate_key(reason="stt_quota_limit")
                        active_client = key_manager.get_client()
                    logger.warning(f"[Audio STT] Fast model {mdl} error/timeout: {g_err}")

            raw = res.text.strip() if res and res.text else ""
            if "{" in raw and "}" in raw:
                j_str = raw[raw.find("{"):raw.rfind("}")+1]
                parsed = json.loads(j_str)
                u_text = clean_transcript_text(parsed.get("user_text", ""))
                
                # Check for empty or hallucinated noise phrases
                if not u_text or len(u_text.strip()) < 3:
                    return
                norm_u = u_text.lower().strip()
                if any(h in norm_u for h in HALLUCINATED_PHRASES):
                    logger.info(f"[Audio STT] Filtered out known noise hallucination: {u_text!r}")
                    return

                last_user_voice_text = u_text
                logger.info(f"[Audio STT User] {u_text!r}")
                await websocket.send_json({"type": "transcript", "data": u_text, "speaker": "input"})

                # Background Zero-Shot AI Memory Distillation
                asyncio.create_task(memory_engine.distill_and_store_memories_async(
                    key_manager.get_client(), u_text, current_speaker_name
                ))

                # Deterministic Intent Handling
                intent = memory_engine.extract_and_apply_intent(u_text, audio_pcm, current_speaker_name)
                if intent:
                    if intent.get("type") == "hud_timer":
                        await gemini_service.interrupt()
                        await websocket.send_json({
                            "type": "hud_timer",
                            "durationSeconds": intent["duration_seconds"],
                            "label": intent["label"],
                            "data": intent["reply_text"],
                            "speaker": "output"
                        })
                        speak_cmd = f"Sistem: Ucapkan dengan suara ramah dan manis hanya kalimat ini tanpa kata lain: {intent['reply_text']}"
                        await gemini_service.send_text(speak_cmd)
                        memory_engine.log_conversation(user_text=u_text, ai_text=intent['reply_text'], speaker_name=current_speaker_name)
                        return
                    elif intent.get("type") == "direct_answer":
                        await gemini_service.interrupt()
                        speak_cmd = f"Sistem: Ucapkan dengan suara ramah, manis, dan akurat kalimat ini tanpa kata lain: {intent['reply_text']}"
                        await gemini_service.send_text(speak_cmd)
                        await websocket.send_json({"type": "transcript", "data": intent['reply_text'], "speaker": "output"})
                        memory_engine.log_conversation(user_text=u_text, ai_text=intent['reply_text'], speaker_name=current_speaker_name)
                        return
                    elif intent.get("type") == "delete_speaker":
                        if current_speaker_name == intent.get("speaker_name"):
                            current_speaker_name = None
                        await gemini_service.interrupt()
                        speak_cmd = f"[Pemberitahuan Sistem: Ucapkan kalimat konfirmasi ini dengan ramah]: {intent['reply_text']}"
                        await gemini_service.send_text(speak_cmd)
                        await websocket.send_json({"type": "transcript", "data": intent['reply_text'], "speaker": "output"})
                        memory_engine.log_conversation(user_text=u_text, ai_text=intent['reply_text'], speaker_name=current_speaker_name)
                        return
                    elif intent.get("type") == "introduction":
                        current_speaker_name = intent["speaker_name"]
                        logger.info(f"[AnaraMemory Voice] Active speaker set to: '{current_speaker_name}'")
                        await websocket.send_json({"type": "speaker_identified", "name": current_speaker_name})
                        await gemini_service.interrupt()
                        speak_cmd = f"Sistem: Ucapkan dengan suara ramah, manis, dan hangat kalimat ini: {intent['reply_text']}"
                        await gemini_service.send_text(speak_cmd)
                        await websocket.send_json({"type": "transcript", "data": intent['reply_text'], "speaker": "output"})
                        memory_engine.log_conversation(user_text=u_text, ai_text=intent['reply_text'], speaker_name=current_speaker_name)
                        return
                    elif intent.get("type") == "read_memories":
                        target_name = current_speaker_name
                        if target_name:
                            summary = memory_engine.format_memories_summary(target_name)
                            await gemini_service.interrupt()
                            speak_cmd = f"[Pemberitahuan Sistem: Ucapkan dengan ramah ringkasan ingatan ini kepada {target_name}]: {summary}"
                            await gemini_service.send_text(speak_cmd)
                            await websocket.send_json({"type": "transcript", "data": summary, "speaker": "output"})
                            memory_engine.log_conversation(user_text=u_text, ai_text=summary, speaker_name=current_speaker_name)
                        else:
                            await gemini_service.interrupt()
                            msg = "Beri tahu dulu siapa namamu agar aku bisa membuka catatan preferensimu di database."
                            speak_cmd = f"Ucapkan dengan ramah kalimat ini: {msg}"
                            await gemini_service.send_text(speak_cmd)
                            await websocket.send_json({"type": "transcript", "data": msg, "speaker": "output"})
                        return
                    elif intent.get("type") == "read_todos":
                        target_name = current_speaker_name
                        if target_name:
                            summary = memory_engine.format_todos_summary(target_name)
                            todos = memory_engine.get_notes_and_todos(speaker_name=target_name)
                            await gemini_service.interrupt()
                            speak_cmd = f"[Pemberitahuan Sistem: Ucapkan dengan ramah ringkasan to-do ini]: {summary}"
                            await gemini_service.send_text(speak_cmd)
                            await websocket.send_json({
                                "type": "transcript",
                                "data": summary,
                                "speaker": "output",
                                "visualType": "todo_list",
                                "todoData": {"items": todos},
                                "mediaType": "hud"
                            })
                            memory_engine.log_conversation(user_text=u_text, ai_text=summary, speaker_name=current_speaker_name)
                        else:
                            await gemini_service.interrupt()
                            msg = "Beri tahu dulu siapa namamu agar aku bisa membuka daftar to-do kamu di database."
                            speak_cmd = f"Ucapkan dengan ramah kalimat ini: {msg}"
                            await gemini_service.send_text(speak_cmd)
                            await websocket.send_json({"type": "transcript", "data": msg, "speaker": "output"})
                        return
                    elif intent.get("type") == "read_animations":
                        summary = memory_engine.format_animations_summary()
                        await gemini_service.interrupt()
                        speak_cmd = f"[Pemberitahuan Sistem: Ucapkan dengan ceria daftar animasi 3D ini]: {summary}"
                        await gemini_service.send_text(speak_cmd)
                        await websocket.send_json({"type": "transcript", "data": summary, "speaker": "output"})
                        memory_engine.log_conversation(user_text=u_text, ai_text=summary, speaker_name=current_speaker_name)
                        return
                    elif intent.get("type") == "dance_capability":
                        await gemini_service.interrupt()
                        speak_cmd = f"[Pemberitahuan Sistem: Ucapkan dengan ceria dan antusias]: {intent['reply_text']}"
                        await gemini_service.send_text(speak_cmd)
                        await websocket.send_json({"type": "transcript", "data": intent['reply_text'], "speaker": "output"})
                        memory_engine.log_conversation(user_text=u_text, ai_text=intent['reply_text'], speaker_name=current_speaker_name)
                        return
                    elif intent.get("type") == "delete_memory":
                        target_name = current_speaker_name
                        if target_name:
                            memory_engine.delete_memory(target_name, intent["key"])
                            del_msg = f"Aku sudah melupakan catatan {intent['key'].replace('_', ' ')} kamu dari database ya."
                        else:
                            del_msg = f"Catatan {intent['key'].replace('_', ' ')} sudah dihapus dari database."
                        speak_cmd = f"[Pemberitahuan Sistem: Catatan '{intent['key'].replace('_', ' ')}' telah dihapus dari database. Ucapkan: {del_msg}]"
                        await gemini_service.send_text(speak_cmd)
                        await websocket.send_json({"type": "transcript", "data": del_msg, "speaker": "output"})
                        memory_engine.log_conversation(user_text=u_text, ai_text=del_msg, speaker_name=current_speaker_name)
                        return

                # ── JARVIS Multimodal Visual Projection Check from Voice ──
                speaker_ctx = memory_engine.get_system_prompt_context(current_speaker_name)
                proactive_facts = memory_engine.get_proactive_relevant_facts(u_text, current_speaker_name)
                if proactive_facts:
                    speaker_ctx = f"{speaker_ctx}\n{proactive_facts}"
                active_sys_prompt = f"{SYSTEM_PROMPT}\n{speaker_ctx}"

                if could_be_visual_request(u_text) and not dance_blocked():
                    logger.info(f"[JARVIS Visual Voice Intent] Checking visual request: {u_text!r}")
                    vis = await generate_visual_projection(key_manager.get_client(), u_text, active_sys_prompt)
                    if vis.get("has_visual"):
                        v_type = vis.get("visual_type", "image")
                        r_text = vis.get("reply_text", "Protokol visual telah diproyeksikan ke layar HUD.")
                        
                        logger.info(f"[Visual Projection HUD] Type: {v_type}")
                        await websocket.send_json({
                            "type": "transcript",
                            "data": r_text,
                            "speaker": "output",
                            "visualType": v_type,
                            "imageUrl": vis.get("image_url"),
                            "imageTitle": vis.get("image_title"),
                            "sourceDomain": vis.get("source_domain"),
                            "sourceUrl": vis.get("source_url"),
                            "weatherData": vis.get("weather_data"),
                            "codeData": vis.get("code_data"),
                            "systemHudData": vis.get("system_hud_data"),
                            "knowledgeCardData": vis.get("knowledge_card_data"),
                            "todoData": vis.get("todo_data"),
                            "images": vis.get("images", []),
                            "mediaType": "image" if v_type == "image" else "hud"
                        })
                        
                        # Log to SQLite conversations table
                        memory_engine.log_conversation(
                            user_text=u_text,
                            ai_text=r_text,
                            speaker_name=current_speaker_name,
                            media_type=v_type,
                            media_url=vis.get("image_url"),
                            visual_data=vis
                        )
                        
                        em = emotion_engine.analyze(r_text)
                        if em:
                            await push_emotion(em["emotion"], em["gesture"], em["intensity"])
                        await gemini_service.interrupt()
                        speak_cmd = f"Sistem: Ucapkan dengan suara ramah dan manis hanya kalimat ini tanpa kata lain: {r_text}"
                        await gemini_service.send_text(speak_cmd)
                        return

                # Normal conversational voice turn:
                # Gemini Live is already responding directly from the live audio stream.
                # We do NOT send duplicate send_text, preserving 100% fluid, uninterrupted audio streaming!
                logger.info(f"[Voice Turn] Audio turn streaming naturally for: {u_text!r}")
        except Exception as e:
            logger.error(f"[Audio STT] Error in STT: {e}")

    # ── Dance mode gate ──
    dance_mode_until: float = 0.0

    def dance_blocked() -> bool:
        return _time.monotonic() < dance_mode_until

    async def activate_dance_llm_turn(user_text: str = ""):
        nonlocal dance_mode_until, has_speech_started
        dance_mode_until = _time.monotonic() + 9.0  # Lock backend mic processing during dance
        user_audio_buffer.clear()
        has_speech_started = False

        norm = normalize_text(user_text)
        if any(q in norm for q in REPEAT_WORDS):
            reply_text = "Oke, musik!"
        else:
            reply_text = "Anara siap!"

        logger.info(f"[Dance] Activating dance with response: {reply_text!r}")
        await websocket.send_json({"type": "emotion_update", "emotion": "dance", "gesture": "joy", "intensity": 1.0})
        
        try:
            await websocket.send_json({"type": "transcript", "data": reply_text, "speaker": "output"})
        except Exception:
            pass

        speak_cmd = f"Ucapkan dengan suara ceria dan manis hanya kalimat ini tanpa kata lain: {reply_text}"
        await gemini_service.send_text(speak_cmd)

    async def push_emotion(emotion: str, gesture: str, intensity: float = 0.7):
        if dance_blocked():
            return
        try:
            await websocket.send_json({
                "type": "emotion_update",
                "emotion": emotion,
                "gesture": gesture,
                "intensity": round(intensity, 3),
            })
        except Exception:
            pass

    # ── Callbacks for Gemini responses ──────────────────────────────────────

    async def on_audio_chunk(audio_bytes: bytes):
        """Send audio chunk back to browser."""
        nonlocal ai_is_speaking, has_speech_started
        ai_is_speaking = True
        
        # If user just finished speech before Gemini started speaking, preserve and transcribe their speech turn!
        if has_speech_started and len(user_audio_buffer) >= 4800:
            has_speech_started = False
            audio_copy = bytes(user_audio_buffer)
            user_audio_buffer.clear()
            ser_tracker.reset()
            asyncio.create_task(transcribe_and_subtitle_audio(audio_copy))

        if dance_blocked():
            return
        intensity = estimate_audio_intensity(audio_bytes)
        try:
            await websocket.send_json({
                "type": "audio_chunk",
                "data": base64.b64encode(audio_bytes).decode("utf-8"),
                "intensity": round(intensity * 5, 3),
                "sampleRate": 24000
            })
        except Exception:
            pass

    async def on_transcript(text: str, speaker: str):
        """Send transcript to browser; analyze emotion for AI output."""
        nonlocal ai_transcript_buffer

        if speaker == "input" and is_dance_command(text):
            logger.info(f"[Dance] Voice command detected: {text!r}")
            try:
                await websocket.send_json({"type": "transcript", "data": text, "speaker": "input"})
            except Exception:
                pass
            await activate_dance_llm_turn(text)
            return

        if dance_blocked() and speaker == "output":
            return

        try:
            await websocket.send_json({
                "type": "transcript",
                "data": text,
                "speaker": speaker
            })

            if speaker == "output":
                ai_transcript_buffer += " " + text
                result = emotion_engine.analyze(text)
                if result:
                    await push_emotion(result["emotion"], result["gesture"], result["intensity"])

        except Exception:
            pass

    async def on_interrupted():
        nonlocal ai_transcript_buffer, ai_is_speaking
        ai_is_speaking = False
        ai_transcript_buffer = ""
        if dance_blocked():
            return
        try:
            await websocket.send_json({"type": "interrupted"})
            await push_emotion("neutral", "idle", 0.5)
        except Exception:
            pass

    async def on_turn_complete():
        nonlocal ai_transcript_buffer, ai_is_speaking, last_user_voice_text
        ai_is_speaking = False

        if dance_blocked():
            ai_transcript_buffer = ""
            return

        if ai_transcript_buffer.strip():
            final = emotion_engine.analyze_full_turn(ai_transcript_buffer)
            if final:
                await push_emotion(final["emotion"], final["gesture"], final["intensity"])
            
            # Persist dialogue turn to episodic conversations database
            if bool(last_user_voice_text and last_user_voice_text.strip()):
                memory_engine.log_conversation(
                    user_text=last_user_voice_text,
                    ai_text=ai_transcript_buffer.strip(),
                    speaker_name=current_speaker_name
                )
                last_user_voice_text = ""

        ai_transcript_buffer = ""
        try:
            await websocket.send_json({"type": "turn_complete"})
        except Exception:
            pass

    # ── Start Gemini session ─────────────────────────────────────────────────

    gemini_task = asyncio.create_task(
        gemini_service.start_session(
            on_audio_chunk=on_audio_chunk,
            on_transcript=on_transcript,
            on_interrupted=on_interrupted,
            on_turn_complete=on_turn_complete,
        )
    )

    try:
        if current_speaker_name:
            await websocket.send_json({"type": "speaker_identified", "name": current_speaker_name})
    except Exception:
        pass

    has_speech_started = False
    last_speech_time = 0.0
    loop = asyncio.get_running_loop()

    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            if message.get("bytes"):
                raw_audio = message["bytes"]
                if dance_blocked():
                    user_audio_buffer.clear()
                    has_speech_started = False
                    ser_tracker.reset()
                elif ai_is_speaking:
                    # Echo prevention: ignore mic chunks while AI is actively speaking
                    pass
                else:
                    await gemini_service.send_audio(raw_audio)
                    user_audio_buffer.extend(raw_audio)
                    intensity = estimate_audio_intensity(raw_audio)
                    now = loop.time()
                    if intensity > 0.015:
                        if not has_speech_started:
                            has_speech_started = True
                            speech_start_time = now
                        last_speech_time = now

                        # Real-time Streaming Early Biometrics Match
                        if len(user_audio_buffer) >= 6400 and (len(user_audio_buffer) % 6400 < 3200):
                            try:
                                early_id, early_conf, _ = memory_engine.identify_speaker(bytes(user_audio_buffer))
                                if early_id and early_id != current_speaker_name:
                                    current_speaker_name = early_id
                                    gemini_service.set_active_speaker(early_id)
                                    await websocket.send_json({"type": "speaker_identified", "name": early_id})
                                    logger.info(f"[Real-Time Voice Biometrics] Switched speaker: '{early_id}' (conf={early_conf:.3f})")
                            except Exception as e_early:
                                logger.debug(f"[Early Bio Error]: {e_early}")

                        # Real-time streaming SER tone update with 250ms throttling
                        live_tone = ser_tracker.push_chunk(raw_audio)
                        if live_tone and (now - last_ser_emit_time > 0.25):
                            last_ser_emit_time = now
                            try:
                                await websocket.send_json({
                                    "type": "acoustic_emotion",
                                    "data": live_tone
                                })
                            except Exception:
                                pass
                    elif has_speech_started:
                        if now - last_speech_time > 0.65:
                            has_speech_started = False
                            speech_dur = last_speech_time - speech_start_time
                            logger.info(f"Auto-VAD: Speech ended ({speech_dur:.2f}s), triggering turn!")
                            await gemini_service.send_audio(b"", end_of_turn=True)
                            if user_audio_buffer and len(user_audio_buffer) >= 4800:
                                audio_copy = bytes(user_audio_buffer)
                                user_audio_buffer.clear()
                                ser_tracker.reset()
                                asyncio.create_task(transcribe_and_subtitle_audio(audio_copy))
                            else:
                                user_audio_buffer.clear()
                                ser_tracker.reset()
                    else:
                        # Keep ~300ms pre-roll during silence
                        if len(user_audio_buffer) > 4800:
                            del user_audio_buffer[:-4800]

            elif message.get("text"):
                try:
                    data = json.loads(message["text"])
                    msg_type = data.get("type")

                    if msg_type == "interrupt":
                        dance_mode_until = 0.0
                        has_speech_started = False
                        user_audio_buffer.clear()
                        ser_tracker.reset()
                        await gemini_service.interrupt()
                    elif msg_type == "dance_start":
                        dance_mode_until = _time.monotonic() + 9.0
                        user_audio_buffer.clear()
                        has_speech_started = False
                        ser_tracker.reset()
                    elif msg_type == "dance_end":
                        dance_mode_until = 0.0
                        user_audio_buffer.clear()
                        has_speech_started = False
                        ser_tracker.reset()
                    elif msg_type == "calibrate_voice":
                        sp_name = data.get("name", "").strip()
                        b64_audio = data.get("audio", "")
                        if sp_name and b64_audio:
                            try:
                                raw_bytes = base64.b64decode(b64_audio)
                                pcm_bytes = raw_bytes
                                if len(raw_bytes) > 44 and raw_bytes[:4] == b"RIFF":
                                    import io, wave
                                    with wave.open(io.BytesIO(raw_bytes), "rb") as wf:
                                        pcm_bytes = wf.readframes(wf.getnframes())
                                res = memory_engine.calibrate_speaker_voice(sp_name, pcm_bytes)
                                current_speaker_name = sp_name
                                gemini_service.set_active_speaker(sp_name)
                                await websocket.send_json({"type": "speaker_identified", "name": sp_name})
                                await websocket.send_json({"type": "calibrate_result", "status": "success", "data": res})
                                logger.info(f"[Voice Biometrics Calibrated] Manually calibrated profile '{sp_name}' via WS")
                            except Exception as err:
                                await websocket.send_json({"type": "calibrate_result", "status": "error", "message": str(err)})
                    elif msg_type == "set_active_speaker":
                        sp_name = data.get("name")
                        current_speaker_name = sp_name if sp_name else None
                        gemini_service.set_active_speaker(current_speaker_name)
                        await websocket.send_json({"type": "speaker_identified", "name": current_speaker_name})
                        logger.info(f"[Active Speaker Switch] Switched active profile to '{current_speaker_name}' via WS")
                    elif msg_type == "audio_chunk":
                        raw = base64.b64decode(data.get("data", ""))
                        if dance_blocked():
                            user_audio_buffer.clear()
                            has_speech_started = False
                            ser_tracker.reset()
                        elif raw:
                            intensity = estimate_audio_intensity(raw)
                            now = loop.time()
                            if intensity > 0.02:
                                if not has_speech_started:
                                    has_speech_started = True
                                    speech_start_time = now
                                last_speech_time = now
                                user_audio_buffer.extend(raw)
                                live_tone = ser_tracker.push_chunk(raw)
                                if live_tone and (now - last_ser_emit_time > 0.25):
                                    last_ser_emit_time = now
                                    try:
                                        await websocket.send_json({
                                            "type": "acoustic_emotion",
                                            "data": live_tone
                                        })
                                    except Exception:
                                        pass
                            elif has_speech_started:
                                user_audio_buffer.extend(raw)
                                if now - last_speech_time > 0.70:
                                    has_speech_started = False
                                    speech_dur = last_speech_time - speech_start_time
                                    if speech_dur >= 0.25 and len(user_audio_buffer) >= 4800:
                                        logger.info(f"Auto-VAD: Valid speech turn completed ({speech_dur:.2f}s).")
                                        audio_copy = bytes(user_audio_buffer)
                                        user_audio_buffer.clear()
                                        ser_tracker.reset()
                                        asyncio.create_task(transcribe_and_subtitle_audio(audio_copy))
                                    else:
                                        user_audio_buffer.clear()
                                        ser_tracker.reset()
                    elif msg_type == "text_input":
                        text = data.get("text", "")
                        if text:
                            if is_dance_command(text) or text.startswith("Sistem:"):
                                logger.info(f"[Dance] Text dance command: {text!r}")
                                await activate_dance_llm_turn(text)
                            else:
                                logger.info(f"[Chat Mode Input] Processing: {text!r}")
                                
                                # Background Zero-Shot AI Memory Distillation
                                asyncio.create_task(memory_engine.distill_and_store_memories_async(
                                    key_manager.get_client(), text, current_speaker_name
                                ))

                                 # Deterministic Command Check
                                intent = memory_engine.extract_and_apply_intent(text, speaker_name=current_speaker_name)
                                if intent:
                                    if intent.get("type") == "hud_timer":
                                        reply_text = intent["reply_text"]
                                        await websocket.send_json({
                                            "type": "hud_timer",
                                            "durationSeconds": intent["duration_seconds"],
                                            "label": intent["label"],
                                            "data": reply_text,
                                            "speaker": "output",
                                            "is_final": True
                                        })
                                        speak_cmd = f"Sistem: Ucapkan dengan suara ramah dan manis hanya kalimat ini tanpa kata lain: {reply_text}"
                                        await gemini_service.send_text(speak_cmd)
                                        memory_engine.log_conversation(user_text=text, ai_text=reply_text, speaker_name=current_speaker_name)
                                        continue
                                    elif intent.get("type") == "direct_answer":
                                        reply_text = intent["reply_text"]
                                        await websocket.send_json({
                                            "type": "transcript",
                                            "data": reply_text,
                                            "speaker": "output",
                                            "is_final": True
                                        })
                                        em = emotion_engine.analyze(reply_text)
                                        if em:
                                            await push_emotion(em["emotion"], em["gesture"], em["intensity"])
                                        speak_cmd = f"Sistem: Ucapkan dengan suara ramah dan manis hanya kalimat ini tanpa kata lain: {reply_text}"
                                        await gemini_service.send_text(speak_cmd)
                                        continue
                                    elif intent.get("type") == "delete_speaker":
                                        if current_speaker_name == intent.get("speaker_name"):
                                            current_speaker_name = None
                                        await websocket.send_json({
                                            "type": "transcript",
                                            "data": intent.get("reply_text"),
                                            "speaker": "output",
                                            "is_final": True
                                        })
                                        continue
                                    elif intent.get("type") == "introduction":
                                        current_speaker_name = intent["speaker_name"]
                                        logger.info(f"[AnaraMemory Chat] Active speaker switched to: '{current_speaker_name}'")
                                        await websocket.send_json({"type": "speaker_identified", "name": current_speaker_name})
                                        reply_text = intent.get("reply_text", f"Halo {current_speaker_name}! Profilmu sekarang aktif di database Anara.")
                                        await websocket.send_json({
                                            "type": "transcript",
                                            "data": reply_text,
                                            "speaker": "output",
                                            "is_final": True
                                        })
                                        em = emotion_engine.analyze(reply_text)
                                        if em:
                                            await push_emotion(em["emotion"], em["gesture"], em["intensity"])
                                        speak_cmd = f"Sistem: Ucapkan dengan suara ramah dan manis hanya kalimat ini tanpa kata lain: {reply_text}"
                                        await gemini_service.send_text(speak_cmd)
                                        continue
                                    elif intent.get("type") == "read_memories":
                                        target_name = current_speaker_name
                                        if target_name:
                                            summary = memory_engine.format_memories_summary(target_name)
                                        else:
                                            summary = "Beri tahu dulu siapa namamu agar aku bisa membuka catatan preferensimu di database."
                                        await websocket.send_json({
                                            "type": "transcript",
                                            "data": summary,
                                            "speaker": "output",
                                            "is_final": True
                                        })
                                        continue
                                    elif intent.get("type") == "read_todos":
                                        target_name = current_speaker_name
                                        if target_name:
                                            summary = memory_engine.format_todos_summary(target_name)
                                            todos = memory_engine.get_notes_and_todos(speaker_name=target_name)
                                        else:
                                            summary = "Beri tahu dulu siapa namamu agar aku bisa membuka daftar to-do kamu di database."
                                            todos = []
                                        await websocket.send_json({
                                            "type": "transcript",
                                            "data": summary,
                                            "speaker": "output",
                                            "visualType": "todo_list",
                                            "todoData": {"items": todos},
                                            "mediaType": "hud",
                                            "is_final": True
                                        })
                                        continue
                                    elif intent.get("type") == "read_animations":
                                        summary = memory_engine.format_animations_summary()
                                        await websocket.send_json({
                                            "type": "transcript",
                                            "data": summary,
                                            "speaker": "output",
                                            "is_final": True
                                        })
                                        continue
                                    elif intent.get("type") == "dance_capability":
                                        await websocket.send_json({
                                            "type": "transcript",
                                            "data": intent.get("reply_text"),
                                            "speaker": "output",
                                            "is_final": True
                                        })
                                        continue
                                    elif intent.get("type") == "delete_memory":
                                        target_name = current_speaker_name
                                        if target_name:
                                            memory_engine.delete_memory(target_name, intent["key"])
                                            msg = f"Baik {target_name}, catatan {intent['key'].replace('_', ' ')} sudah aku hapus dari database."
                                        else:
                                            msg = "Catatan telah dihapus dari database."
                                        await websocket.send_json({
                                            "type": "transcript",
                                            "data": msg,
                                            "speaker": "output",
                                            "is_final": True
                                        })
                                        continue

                                speaker_ctx = memory_engine.get_system_prompt_context(current_speaker_name)
                                proactive_facts = memory_engine.get_proactive_relevant_facts(text, current_speaker_name)
                                proactive_brief = memory_engine.get_proactive_briefing_guidance(current_speaker_name)
                                if proactive_facts:
                                    speaker_ctx = f"{speaker_ctx}\n{proactive_facts}"
                                if proactive_brief:
                                    speaker_ctx = f"{speaker_ctx}\n{proactive_brief}"
                                active_sys_prompt = f"{SYSTEM_PROMPT}\n{speaker_ctx}"

                                # ── JARVIS Multimodal Visual Projection ──
                                vis = await generate_visual_projection(key_manager.get_client(), text, active_sys_prompt)
                                if vis.get("has_visual"):
                                    v_type = vis.get("visual_type", "image")
                                    reply_text = vis.get("reply_text", "Protokol visual diproyeksikan ke layar HUD.")
                                    logger.info(f"[Visual Projection Text] Type: {v_type}")
                                    
                                    await websocket.send_json({
                                        "type": "transcript",
                                        "data": reply_text,
                                        "speaker": "output",
                                        "visualType": v_type,
                                        "imageUrl": vis.get("image_url"),
                                        "imageTitle": vis.get("image_title"),
                                        "sourceDomain": vis.get("source_domain"),
                                        "sourceUrl": vis.get("source_url"),
                                        "weatherData": vis.get("weather_data"),
                                        "codeData": vis.get("code_data"),
                                        "systemHudData": vis.get("system_hud_data"),
                                        "knowledgeCardData": vis.get("knowledge_card_data"),
                                        "todoData": vis.get("todo_data"),
                                        "images": vis.get("images", []),
                                        "mediaType": "image" if v_type == "image" else "hud"
                                    })
                                    
                                    # Log to SQLite conversations
                                    memory_engine.log_conversation(
                                        user_text=text,
                                        ai_text=reply_text,
                                        speaker_name=current_speaker_name,
                                        media_type=v_type,
                                        media_url=vis.get("image_url"),
                                        visual_data=vis
                                    )
                                    
                                    em = emotion_engine.analyze(reply_text)
                                    if em:
                                        await push_emotion(em["emotion"], em["gesture"], em["intensity"])
                                    speak_cmd = f"Sistem: Ucapkan dengan suara ramah dan manis hanya kalimat ini tanpa kata lain: {reply_text}"
                                    await gemini_service.send_text(speak_cmd)
                                else:
                                    # Normal conversational text turn -> Fast Generation
                                    logger.info(f"[Text Chat Turn] Generating fast response ({current_speaker_name}): {text!r}")
                                    reply_text = ""
                                    
                                    # Prepend recent conversation dialogue context so short follow-ups (e.g. 'ya', 'lanjutkan', 'kenapa') stay 100% on topic
                                    recent_history = memory_engine.get_recent_conversations(limit=4)
                                    dialogue_context = ""
                                    if recent_history:
                                        d_lines = []
                                        for h in recent_history:
                                            u = (h.get("user_text") or "").strip()
                                            a = (h.get("ai_text") or "").strip()
                                            if u or a:
                                                d_lines.append(f"User: {u}\nAnara: {a}")
                                        if d_lines:
                                            dialogue_context = "KONTEKS PERCAKAPAN SEBELUMNYA:\n" + "\n---\n".join(d_lines) + "\n\n"

                                    full_user_input = f"{dialogue_context}Pesan User Sekarang: {text}" if dialogue_context else text

                                    clean_sys_instruction = (
                                        f"{active_sys_prompt}\n\n"
                                        "ATURAN MUTLAK:\n"
                                        "- Jawablah sebagai Anara secara cerdas, ramah, hangat, dan ringkas (1-2 kalimat) dalam Bahasa Indonesia alami.\n"
                                        "- Jika pengguna menjawab singkat seperti 'ya', 'tentu', 'boleh', 'lanjutkan', lanjutkan obrolan sesuai topik pada KONTEKS PERCAKAPAN SEBELUMNYA.\n"
                                        "- DILARANG KERAS menuliskan awalan atau label seperti 'Language:', 'Response:', 'Anara:', 'Output:', dsb.\n"
                                        "- DILARANG menuliskan teks aksi roleplay dalam tanda bintang seperti *tersenyum*, *mengangguk*, dsb."
                                    )
                                    models_to_try = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-3.6-flash"]
                                    for mdl in models_to_try:
                                        try:
                                            active_client = key_manager.get_client()
                                            res = await asyncio.wait_for(
                                                active_client.aio.models.generate_content(
                                                    model=mdl,
                                                    contents=full_user_input,
                                                    config=types.GenerateContentConfig(
                                                        system_instruction=clean_sys_instruction,
                                                        max_output_tokens=250,
                                                        temperature=0.7
                                                    )
                                                ),
                                                timeout=4.5
                                            )
                                            if res and res.text:
                                                raw_out = res.text.strip()
                                                # Strip meta labels like 'Language: Natural, everyday' or 'Anara:'
                                                raw_out = re.sub(r"^(?:Language|Response|Output|Anara|Assistant)\s*:\s*[^\n]*\n*", "", raw_out, flags=re.IGNORECASE).strip()
                                                # Strip any accidental roleplay asterisks
                                                raw_out = re.sub(r"\*[^*]+\*", "", raw_out).strip()
                                                if raw_out:
                                                    reply_text = raw_out
                                                    break
                                        except Exception as c_err:
                                            logger.warning(f"[Text Chat Fast] Model {mdl} error: {c_err}")
                                            continue

                                    if not reply_text:
                                        eff_n = f" {current_speaker_name}" if current_speaker_name else ""
                                        if text.lower().strip() in ["halo", "haloo", "hai", "hei", "hello", "hi"]:
                                            reply_text = f"Halo{eff_n}! Senang bisa ngobrol lagi denganmu. Ada yang bisa Anara bantu?"
                                        else:
                                            reply_text = f"Iya{eff_n}, aku mendengarkanmu. Ada yang ingin kamu diskusikan atau tanyakan?"

                                    # 1. Send text bubble to frontend immediately
                                    await websocket.send_json({
                                        "type": "transcript",
                                        "data": reply_text,
                                        "speaker": "output",
                                        "is_final": True
                                    })

                                    # 2. Log conversation
                                    memory_engine.log_conversation(
                                        user_text=text,
                                        ai_text=reply_text,
                                        speaker_name=current_speaker_name
                                    )

                                    # 3. Trigger 3D Avatar Emotion & Speak via Gemini Live
                                    em = emotion_engine.analyze(reply_text)
                                    if em:
                                        await push_emotion(em["emotion"], em["gesture"], em["intensity"])
                                    speak_cmd = f"Ucapkan dengan suara ramah dan manis hanya kalimat ini tanpa kata lain: {reply_text}"
                                    await gemini_service.send_text(speak_cmd)
                    elif msg_type == "end_turn":
                        if not dance_blocked():
                            await gemini_service.send_audio(b"", end_of_turn=True)
                            if user_audio_buffer:
                                audio_copy = bytes(user_audio_buffer)
                                user_audio_buffer.clear()
                                asyncio.create_task(transcribe_and_subtitle_audio(audio_copy))

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from client: {message['text']}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {session_id}: {e}")
    finally:
        active_websockets.discard(websocket)
        gemini_task.cancel()
        await gemini_service.stop()
        active_sessions.pop(session_id, None)
        logger.info(f"Session {session_id} cleaned up")


if __name__ == "__main__":
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[backend_dir],
        log_level="info"
    )
