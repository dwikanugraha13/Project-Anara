"""
Real-time Bidirectional Voice and Text WebSocket Handler for Project Anara.
Coordinates Live Audio Streaming, Biometrics, Proactive Reflections, and Autonomous Agent Loop.
"""
import asyncio
import base64
import json
import logging
import os
import re
import sys
import time
import time as _time
from typing import Dict, Optional, Any, List, Set, Tuple

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.genai import types
from google import genai

from core import (
    GeminiLiveService,
    SYSTEM_PROMPT,
    key_manager,
    ModelCapabilityRegistry,
    anara_agent,
)
from cognition import (
    estimate_audio_intensity,
    EmotionEngine,
    generate_smart_hud_card,
)
from memory import memory_engine
from providers import get_active_model_id

import shared_state
from shared_state import (
    active_websockets,
    active_sessions,
    chat_diagnostics,
)

from websocket.media_controller import MediaController
from websocket.voice_pipeline import VoicePipeline
from websocket.stream_consumer import AgentRunner

logger = logging.getLogger("anara.websocket")
router = APIRouter(tags=["WebSocket"])

last_active_visual_payload: Optional[Dict[str, Any]] = None

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time voice & text chat communication."""
    global last_active_visual_payload
    await websocket.accept()
    active_websockets.add(websocket)
    session_id = str(id(websocket))
    logger.info(f"WebSocket connected: {session_id}")

    initial_primary_speaker = memory_engine.get_last_active_speaker_name() or "Agnan"
    current_speaker_name = initial_primary_speaker
    await websocket.send_json({"type": "speaker_identified", "name": initial_primary_speaker})

    active_m = get_active_model_id()
    live_model = active_m if ModelCapabilityRegistry.supports_voice(active_m) else "gemini-3.1-flash-live-preview"
    api_key = key_manager.get_active_key()
    gemini_service: Optional[GeminiLiveService] = None
    gemini_task: Optional[asyncio.Task] = None
    if api_key:
        gemini_service = GeminiLiveService(api_key=api_key, active_speaker=initial_primary_speaker, model_id=live_model)
        active_sessions[session_id] = gemini_service
    else:
        logger.info(f"[WebSocket] Connected without Google AI Studio key (session {session_id}). Ready for Chat mode & Brain Console configuration.")

    emotion_engine = EmotionEngine()

    ai_transcript_buffer = ""
    ai_is_speaking = False
    ai_speaking_ts = 0.0
    dance_mode_until: float = 0.0
    active_text_task: Optional[asyncio.Task] = None

    active_session_id: Optional[int] = None
    try:
        last_sid = memory_engine.get_last_active_session_id(initial_primary_speaker)
        if last_sid:
            active_session_id = last_sid
            if gemini_service:
                gemini_service.bridge_context = memory_engine.get_conversational_bridge_context(session_id=last_sid, speaker_name=initial_primary_speaker)
            logger.info(f"[ChatSessions] Initialized with recent thread #{last_sid} for unified voice-chat context")
    except Exception as e_init_sess:
        logger.debug(f"[ChatSessions] Initial thread seed: {e_init_sess}")

    def get_current_speaker() -> str:
        return current_speaker_name

    def set_current_speaker(name: str):
        nonlocal current_speaker_name
        current_speaker_name = name

    def get_gemini_service() -> Optional[GeminiLiveService]:
        return gemini_service

    def get_active_session_id() -> Optional[int]:
        return active_session_id

    def set_active_session_id(sid: int):
        nonlocal active_session_id
        active_session_id = sid

    def dance_blocked() -> bool:
        return _time.monotonic() < dance_mode_until

    def ensure_session() -> int:
        nonlocal active_session_id
        if active_session_id is not None:
            existing = memory_engine.get_session(active_session_id)
            if existing:
                anara_agent.set_active_session_id(active_session_id)
                return active_session_id
        created = memory_engine.create_session(speaker_name=current_speaker_name)
        active_session_id = created["id"]
        anara_agent.set_active_session_id(active_session_id)
        logger.info(f"[ChatSessions] Active session -> #{active_session_id}")
        return active_session_id

    def log_turn(user_text: str, ai_text: str, **kwargs) -> int:
        sid = ensure_session()
        row_id = memory_engine.log_conversation(
            user_text=user_text,
            ai_text=ai_text,
            speaker_name=current_speaker_name,
            session_id=sid,
            media_type=kwargs.get("media_type"),
            media_url=kwargs.get("media_url"),
            visual_data=kwargs.get("visual_data"),
        )
        try:
            sess = memory_engine.get_session(sid)
            is_placeholder = not sess or not sess.get("title") or sess["title"] in ("New Chat", "New Session", "New Conversation")
            if sess and is_placeholder and (sess.get("message_count") or 0) >= 1:
                asyncio.create_task(
                    memory_engine.auto_title_session_async(key_manager.get_client(), sid)
                )
        except Exception as e:
            logger.debug(f"[ChatSessions] auto-title skip: {e}")
        return row_id

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

    async def activate_dance_llm_turn(user_text: str = ""):
        nonlocal dance_mode_until
        dance_mode_until = _time.monotonic() + 9.0
        voice_pipeline.user_audio_buffer.clear()
        voice_pipeline.has_speech_started = False
        logger.info(f"[Dance] Activating dance 3D animation for: {user_text!r}")
        await websocket.send_json({"type": "emotion_update", "emotion": "dance", "gesture": "joy", "intensity": 1.0})
        speak_cmd = (
            "[SYSTEM EVENT: 3D avatar dance animation initiated on screen. "
            "Acknowledge this cheerfully in 1 concise sentence matching the user's active language.]"
        )
        if gemini_service:
            await gemini_service.send_text(speak_cmd)

    # ── Initialize Sub-controllers ──
    media_controller = MediaController(
        websocket=websocket,
        get_gemini_service=get_gemini_service,
        get_speaker_name=get_current_speaker,
    )

    voice_pipeline = VoicePipeline(
        websocket=websocket,
        get_gemini_service=get_gemini_service,
        get_current_speaker=get_current_speaker,
        set_current_speaker=set_current_speaker,
        push_emotion=push_emotion,
        media_controller=media_controller,
        log_turn=log_turn,
        dance_blocked=dance_blocked,
    )

    agent_runner = AgentRunner(
        websocket=websocket,
        emotion_engine=emotion_engine,
        get_current_speaker=get_current_speaker,
        get_active_session_id=get_active_session_id,
        set_active_session_id=set_active_session_id,
        ensure_session=ensure_session,
        log_turn=log_turn,
        push_emotion=push_emotion,
        dance_blocked=dance_blocked,
        activate_dance_llm_turn=activate_dance_llm_turn,
    )

    # ── Gemini Live Callbacks ──
    async def on_audio_chunk(audio_bytes: bytes):
        nonlocal ai_is_speaking, ai_speaking_ts
        if not ai_is_speaking:
            ai_speaking_ts = _time.monotonic()
        ai_is_speaking = True

        if voice_pipeline.has_speech_started and len(voice_pipeline.user_audio_buffer) >= 4800:
            voice_pipeline.has_speech_started = False
            audio_copy = bytes(voice_pipeline.user_audio_buffer)
            voice_pipeline.user_audio_buffer.clear()
            voice_pipeline.ser_tracker.reset()
            asyncio.create_task(voice_pipeline.transcribe_and_subtitle_audio(audio_copy))

        try:
            await websocket.send_json({
                "type": "audio",
                "data": base64.b64encode(audio_bytes).decode("utf-8"),
                "sampleRate": 24000
            })
        except Exception:
            pass

    async def on_transcript(text: str, speaker: str):
        nonlocal ai_transcript_buffer

        if dance_blocked() and speaker == "output":
            return

        try:
            await websocket.send_json({
                "type": "transcript",
                "data": text,
                "speaker": speaker
            })
        except Exception:
            pass

        if speaker == "output":
            ai_transcript_buffer += " " + text
            try:
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

    async def auto_hud_enrichment(user_text: str, ai_text: str, force: bool = False, conversation_context: Optional[str] = None):
        if not user_text and not ai_text:
            return
        try:
            client = key_manager.get_client()
            card = await generate_smart_hud_card(
                client,
                user_text,
                ai_text,
                speaker_name=current_speaker_name,
                force=force,
                conversation_context=conversation_context
            )
            if not card or not card.get("has_visual"):
                return
            v_type = card.get("visual_type", "knowledge_card")
            new_imgs = len(card.get("images") or []) or (1 if card.get("image_url") else 0)
            elapsed = _time.monotonic() - voice_pipeline.last_visual_projection_ts
            if voice_pipeline.last_visual_projection_ts > 0 and elapsed < 20.0:
                logger.info(f"[Semantic HUD] Skipped '{v_type}' — visual already projected {elapsed:.1f}s ago")
                return
            if v_type == "image" and new_imgs <= 1 and voice_pipeline.last_visual_image_count > 1:
                return

            voice_pipeline.last_visual_projection_ts = _time.monotonic()
            voice_pipeline.last_visual_image_count = new_imgs

            await websocket.send_json({
                "type": "hud_visual",
                "data": card.get("reply_text", ""),
                "visualType": v_type,
                "imageUrl": card.get("image_url"),
                "imageTitle": card.get("image_title"),
                "sourceDomain": card.get("source_domain"),
                "sourceUrl": card.get("source_url"),
                "images": card.get("images", []),
                "knowledgeCardData": card.get("knowledge_card_data"),
                "mediaType": "image" if v_type == "image" else "hud",
            })
            try:
                memory_engine.attach_visual_to_latest_conversation(user_text, ai_text, current_speaker_name, card)
            except Exception as e_att:
                logger.warning(f"[Auto Smart HUD] Visual attach skipped: {e_att!r}")
        except Exception as e_hud:
            logger.error(f"[Auto Smart HUD] Enrichment CRASHED: {e_hud!r}", exc_info=True)

    async def on_turn_complete():
        nonlocal ai_transcript_buffer, ai_is_speaking
        ai_is_speaking = False

        if dance_blocked():
            ai_transcript_buffer = ""
            return

        if ai_transcript_buffer.strip():
            final = emotion_engine.analyze_full_turn(ai_transcript_buffer)
            if final:
                await push_emotion(final["emotion"], final["gesture"], final["intensity"])

            turn_user = (voice_pipeline.current_turn_user_text or voice_pipeline.last_user_voice_text or "").strip()
            turn_ai = ai_transcript_buffer.strip()
            if turn_user or turn_ai:
                log_turn(
                    user_text=turn_user,
                    ai_text=turn_ai,
                    speaker_name=current_speaker_name,
                    media_type="hud" if voice_pipeline.visual_projected_this_turn else None
                )
                voice_pipeline.last_user_voice_text = ""

            async def decide_hud_projection():
                if voice_pipeline.visual_projected_this_turn:
                    return
                convo = ""
                if agent_runner.prev_turn_user_text or agent_runner.prev_turn_ai_reply:
                    convo = f"Previous user: {agent_runner.prev_turn_user_text}\nPrevious Anara: {agent_runner.prev_turn_ai_reply}"
                u = turn_user or voice_pipeline.current_turn_user_text or ""
                t_ai = turn_ai
                await auto_hud_enrichment(u, t_ai or "(Anara menjawab secara lisan)", force=True, conversation_context=convo)

            asyncio.create_task(decide_hud_projection())

            if turn_user:
                agent_runner.prev_turn_user_text = turn_user
            if turn_ai:
                agent_runner.prev_turn_ai_reply = turn_ai

        ai_transcript_buffer = ""
        voice_pipeline.visual_projected_this_turn = False
        voice_pipeline.current_turn_user_text = ""
        try:
            await websocket.send_json({"type": "turn_complete"})
        except Exception:
            pass

    def ensure_gemini_service() -> Optional[GeminiLiveService]:
        nonlocal gemini_service, gemini_task
        fresh_key = key_manager.get_active_key()
        if fresh_key:
            if gemini_service is None:
                active_m = get_active_model_id()
                live_model = active_m if ModelCapabilityRegistry.supports_voice(active_m) else "gemini-3.1-flash-live-preview"
                gemini_service = GeminiLiveService(api_key=fresh_key, active_speaker=current_speaker_name, model_id=live_model)
                active_sessions[session_id] = gemini_service
                gemini_task = asyncio.create_task(
                    gemini_service.start_session(
                        on_audio_chunk=on_audio_chunk,
                        on_transcript=on_transcript,
                        on_interrupted=on_interrupted,
                        on_turn_complete=on_turn_complete,
                    )
                )
                logger.info(f"[WebSocket] Dynamically started GeminiLiveService for session {session_id}")
            elif not gemini_service.api_key:
                gemini_service.api_key = fresh_key
                gemini_service.client = genai.Client(api_key=fresh_key)
        return gemini_service

    if gemini_service:
        gemini_task = asyncio.create_task(
            gemini_service.start_session(
                on_audio_chunk=on_audio_chunk,
                on_transcript=on_transcript,
                on_interrupted=on_interrupted,
                on_turn_complete=on_turn_complete,
            )
        )

    async def ai_speaking_watchdog():
        nonlocal ai_is_speaking, ai_speaking_ts
        while True:
            await asyncio.sleep(5)
            if ai_is_speaking and (_time.monotonic() - ai_speaking_ts) > 20:
                logger.warning("[Watchdog] ai_is_speaking stuck >20s without turn_complete — force resetting echo gate")
                ai_is_speaking = False

    watchdog_task = asyncio.create_task(ai_speaking_watchdog())
    proactive_engine = None
    loop = asyncio.get_running_loop()

    # ── Main Receive Loop ──
    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            if message.get("bytes"):
                raw_audio = message["bytes"]
                if dance_blocked():
                    voice_pipeline.user_audio_buffer.clear()
                    voice_pipeline.has_speech_started = False
                    voice_pipeline.ser_tracker.reset()
                elif ai_is_speaking:
                    intensity = estimate_audio_intensity(raw_audio)
                    # Acoustic Barge-in detection (Hermes & Claude Code Parity):
                    # If user speech clearly exceeds ambient playback bleed, interrupt AI speech immediately!
                    if intensity > 0.045:
                        live_svc = ensure_gemini_service()
                        if live_svc:
                            await live_svc.interrupt()
                        await on_interrupted()
                        voice_pipeline.user_audio_buffer.clear()
                        voice_pipeline.has_speech_started = True
                        voice_pipeline.last_speech_time = loop.time()
                else:
                    live_svc = ensure_gemini_service()
                    if live_svc:
                        await live_svc.send_audio(raw_audio)
                    voice_pipeline.user_audio_buffer.extend(raw_audio)
                    if len(voice_pipeline.user_audio_buffer) > 480000:
                        del voice_pipeline.user_audio_buffer[:-480000]
                    intensity = estimate_audio_intensity(raw_audio)
                    now = loop.time()
                    if intensity > 0.015:
                        if not voice_pipeline.has_speech_started:
                            voice_pipeline.has_speech_started = True
                            voice_pipeline.speech_start_time = now
                            if voice_pipeline.pending_speaker_ctx is not None:
                                flush_ctx = voice_pipeline.pending_speaker_ctx
                                voice_pipeline.pending_speaker_ctx = None
                                if live_svc:
                                    asyncio.create_task(live_svc.inject_context(flush_ctx))
                                logger.info("[Speaker Sync] Deferred context flushed at turn start")
                            if (
                                voice_pipeline.sticky_speaker_name
                                and current_speaker_name != voice_pipeline.sticky_speaker_name
                                and (_time.time() - voice_pipeline.sticky_speaker_ts) < 90
                            ):
                                asyncio.create_task(voice_pipeline.notify_speaker_change(voice_pipeline.sticky_speaker_name, reason="sticky_identity"))
                        voice_pipeline.last_speech_time = now

                        buf_len = len(voice_pipeline.user_audio_buffer)
                        if buf_len >= 19200 and (now - voice_pipeline.bio_last_check) > 0.25:
                            voice_pipeline.bio_last_check = now
                            try:
                                buf_bytes = bytes(voice_pipeline.user_audio_buffer)
                                buf_rms = estimate_audio_intensity(buf_bytes)
                                if buf_rms >= 0.010:
                                    early_id, early_conf, _ = memory_engine.identify_speaker(buf_bytes)
                                    if early_id and early_id != current_speaker_name and early_conf >= 0.70:
                                        await voice_pipeline.notify_speaker_change(early_id, reason=f"early_match conf={early_conf:.2f}")
                            except Exception as e_early:
                                logger.debug(f"[Early Bio Error]: {e_early}")

                        live_tone = voice_pipeline.ser_tracker.push_chunk(raw_audio)
                        if live_tone and (now - voice_pipeline.last_ser_emit_time > 0.25):
                            voice_pipeline.last_ser_emit_time = now
                            try:
                                await websocket.send_json({
                                    "type": "acoustic_emotion",
                                    "data": live_tone
                                })
                            except Exception:
                                pass
                    elif voice_pipeline.has_speech_started:
                        if now - voice_pipeline.last_speech_time > 0.65:
                            voice_pipeline.has_speech_started = False
                            speech_dur = voice_pipeline.last_speech_time - voice_pipeline.speech_start_time
                            if voice_pipeline.voice_enrollment is not None:
                                if voice_pipeline.user_audio_buffer and len(voice_pipeline.user_audio_buffer) >= 4800:
                                    audio_copy = bytes(voice_pipeline.user_audio_buffer)
                                    voice_pipeline.user_audio_buffer.clear()
                                    voice_pipeline.ser_tracker.reset()
                                    asyncio.create_task(voice_pipeline.handle_enrollment_turn(audio_copy))
                                else:
                                    voice_pipeline.user_audio_buffer.clear()
                                    voice_pipeline.ser_tracker.reset()
                            else:
                                live_svc = ensure_gemini_service()
                                if live_svc:
                                    await live_svc.send_audio(b"", end_of_turn=True)
                                else:
                                    await websocket.send_json({
                                        "type": "transcript",
                                        "data": "Real-time voice provider not connected. Please configure an API key in Anara Console (Providers tab) to activate real-time audio.",
                                        "speaker": "output",
                                        "is_final": True
                                    })
                                    await websocket.send_json({"type": "turn_complete"})
                                if voice_pipeline.user_audio_buffer and len(voice_pipeline.user_audio_buffer) >= 4800:
                                    audio_copy = bytes(voice_pipeline.user_audio_buffer)
                                    voice_pipeline.user_audio_buffer.clear()
                                    voice_pipeline.ser_tracker.reset()
                                    if key_manager.get_active_key():
                                        asyncio.create_task(voice_pipeline.transcribe_and_subtitle_audio(audio_copy))
                                else:
                                    voice_pipeline.user_audio_buffer.clear()
                                    voice_pipeline.ser_tracker.reset()

            elif message.get("text"):
                try:
                    data = json.loads(message["text"])
                    msg_type = data.get("type")

                    if msg_type == "interrupt":
                        if not dance_blocked():
                            live_svc = ensure_gemini_service()
                            if live_svc:
                                await live_svc.interrupt()
                            await on_interrupted()
                        if active_text_task and not active_text_task.done():
                            active_text_task.cancel()
                            logger.info("[WebSocket] Cancelled active text turn task on interrupt request.")
                        try:
                            from core.session_manager import session_state_manager
                            if active_session_id:
                                await session_state_manager.request_hard_interrupt("web_studio", str(active_session_id))
                                await session_state_manager.request_hard_interrupt("web", str(active_session_id))
                        except Exception:
                            pass
                    elif msg_type == "set_active_speaker":
                        requested = data.get("name")
                        await voice_pipeline.notify_speaker_change(requested, reason="client_requested_profile_switch")
                    elif msg_type == "media_control":
                        act = data.get("action")
                        if act == "next":
                            await media_controller.playlist_jump(1)
                        elif act == "prev":
                            await media_controller.playlist_jump(-1)
                    elif msg_type == "switch_session":
                        target = data.get("sessionId")
                        if target:
                            active_session_id = int(target)
                            anara_agent.set_active_session_id(active_session_id)
                            sess = memory_engine.get_session(active_session_id) or {}
                            msgs = memory_engine.get_session_messages(active_session_id)

                            bridge_ctx = memory_engine.get_conversational_bridge_context(
                                session_id=active_session_id,
                                speaker_name=current_speaker_name
                            )
                            if gemini_service:
                                gemini_service.bridge_context = bridge_ctx
                                if bridge_ctx and gemini_service._is_running:
                                    asyncio.create_task(gemini_service.inject_context(bridge_ctx))

                            await websocket.send_json({
                                "type": "session_switched",
                                "sessionId": target,
                                "title": sess.get("title"),
                                "session_type": sess.get("session_type", "chat"),
                                "messages": msgs,
                            })
                    elif msg_type == "new_session":
                        req_type = data.get("session_type") or data.get("sessionType") or "chat"
                        req_title = data.get("title")
                        created = memory_engine.create_session(
                            speaker_name=current_speaker_name,
                            title=req_title,
                            session_type="code" if str(req_type).lower() == "code" else "chat"
                        )
                        active_session_id = created["id"]
                        anara_agent.set_active_session_id(active_session_id)
                        if gemini_service:
                            gemini_service.bridge_context = ""
                        await websocket.send_json({
                            "type": "session_switched",
                            "sessionId": created["id"],
                            "title": created["title"],
                            "session_type": created.get("session_type", "chat"),
                            "messages": [],
                        })
                    elif msg_type == "audio_chunk":
                        raw = base64.b64decode(data.get("data", ""))
                        if dance_blocked():
                            voice_pipeline.user_audio_buffer.clear()
                            voice_pipeline.has_speech_started = False
                            voice_pipeline.ser_tracker.reset()
                        elif raw:
                            intensity = estimate_audio_intensity(raw)
                            now = loop.time()
                            if intensity > 0.02:
                                if not voice_pipeline.has_speech_started:
                                    voice_pipeline.has_speech_started = True
                                    voice_pipeline.speech_start_time = now
                                voice_pipeline.last_speech_time = now
                                voice_pipeline.user_audio_buffer.extend(raw)
                                if len(voice_pipeline.user_audio_buffer) > 480000:
                                    del voice_pipeline.user_audio_buffer[:-480000]
                                live_tone = voice_pipeline.ser_tracker.push_chunk(raw)
                                if live_tone and (now - voice_pipeline.last_ser_emit_time > 0.25):
                                    voice_pipeline.last_ser_emit_time = now
                                    try:
                                        await websocket.send_json({
                                            "type": "acoustic_emotion",
                                            "data": live_tone
                                        })
                                    except Exception:
                                        pass
                            elif voice_pipeline.has_speech_started:
                                voice_pipeline.user_audio_buffer.extend(raw)
                                if len(voice_pipeline.user_audio_buffer) > 480000:
                                    del voice_pipeline.user_audio_buffer[:-480000]
                                if now - voice_pipeline.last_speech_time > 0.70:
                                    voice_pipeline.has_speech_started = False
                                    speech_dur = voice_pipeline.last_speech_time - voice_pipeline.speech_start_time
                                    if speech_dur >= 0.25 and len(voice_pipeline.user_audio_buffer) >= 4800:
                                        audio_copy = bytes(voice_pipeline.user_audio_buffer)
                                        voice_pipeline.user_audio_buffer.clear()
                                        voice_pipeline.ser_tracker.reset()
                                        asyncio.create_task(voice_pipeline.transcribe_and_subtitle_audio(audio_copy))
                                    else:
                                        voice_pipeline.user_audio_buffer.clear()
                                        voice_pipeline.ser_tracker.reset()
                    elif msg_type == "text_input":
                        if active_text_task and not active_text_task.done():
                            active_text_task.cancel()
                        active_text_task = asyncio.create_task(agent_runner.run_text_chat_turn(data))
                    elif msg_type == "question_response":
                        from tools.events import resolve_question_response
                        q_id = data.get("question_id") or data.get("questionId")
                        answers = data.get("answers")
                        dismissed = bool(data.get("dismissed", False))
                        if q_id:
                            resolve_question_response(q_id, answers, dismissed=dismissed)
                    elif msg_type == "dance_start":
                        dance_mode_until = _time.monotonic() + 9.0
                    elif msg_type == "dance_end":
                        dance_mode_until = 0.0
                    elif msg_type == "end_turn":
                        if not dance_blocked():
                            live_svc = ensure_gemini_service()
                            if live_svc:
                                await live_svc.send_audio(b"", end_of_turn=True)
                            elif voice_pipeline.user_audio_buffer:
                                await websocket.send_json({
                                    "type": "transcript",
                                    "data": "Real-time voice provider not connected. Please configure an API key in Anara Console (Providers tab) to activate real-time audio.",
                                    "speaker": "output",
                                    "is_final": True
                                })
                                await websocket.send_json({"type": "turn_complete"})
                            if voice_pipeline.user_audio_buffer:
                                audio_copy = bytes(voice_pipeline.user_audio_buffer)
                                voice_pipeline.user_audio_buffer.clear()
                                if key_manager.get_active_key():
                                    asyncio.create_task(voice_pipeline.transcribe_and_subtitle_audio(audio_copy))

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from client: {message['text']}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {session_id}: {e}")
    finally:
        active_websockets.discard(websocket)
        watchdog_task.cancel()
        if active_text_task and not active_text_task.done():
            active_text_task.cancel()
        if proactive_engine:
            proactive_engine.stop()
        if gemini_task:
            gemini_task.cancel()
        if gemini_service:
            await gemini_service.stop()
        active_sessions.pop(session_id, None)
        logger.info(f"Session {session_id} cleaned up")
