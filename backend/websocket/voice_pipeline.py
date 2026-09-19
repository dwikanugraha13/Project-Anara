"""
Voice Pipeline for Project Anara WebSocket session.
Handles audio chunk ingestion, speech-to-text (STT), biometric voice identification,
speech emotion tracking (SER), and speaker enrollment turns.
"""
import asyncio
import json
import logging
import time as _time
from typing import Optional, Dict, Any, List, Callable
from fastapi import WebSocket
from google.genai import types

from core import GeminiLiveService, SYSTEM_PROMPT, key_manager
from cognition import (
    estimate_audio_intensity,
    analyze_speech_emotion,
    AcousticSERTracker,
    is_stt_hallucination,
    generate_visual_projection,
    could_be_visual_request,
    generate_daily_briefing,
    is_briefing_request,
)
from memory import memory_engine
from shared_state import pcm_to_wav_bytes

logger = logging.getLogger("anara.websocket.voice")

ENROLLMENT_PROMPTS = [
    "Halo Anara, senang berkenalan denganmu!",
    "Hari ini cuacanya cerah dan hariku menyenangkan.",
    "Tolong bantu aku menyelesaikan tugas dan pekerjaan ya."
]


def clean_transcript_text(text: str) -> str:
    """Removes common markdown and formatting noise from STT output."""
    if not text:
        return ""
    cleaned = text.strip().strip('"\'`')
    if cleaned.startswith("{") and cleaned.endswith("}"):
        try:
            d = json.loads(cleaned)
            return d.get("user_text", "") or d.get("text", "") or ""
        except Exception:
            pass
    return cleaned

class VoicePipeline:
    def __init__(
        self,
        websocket: WebSocket,
        get_gemini_service: Callable[[], Optional[GeminiLiveService]],
        get_current_speaker: Callable[[], str],
        set_current_speaker: Callable[[str], None],
        push_emotion: Callable[[str, str, float], Any],
        media_controller: Any,
        log_turn: Callable[..., int],
        dance_blocked: Callable[[], bool],
    ):
        self.websocket = websocket
        self.get_gemini_service = get_gemini_service
        self.get_current_speaker = get_current_speaker
        self.set_current_speaker = set_current_speaker
        self.push_emotion = push_emotion
        self.media_controller = media_controller
        self.log_turn = log_turn
        self.dance_blocked = dance_blocked

        self.ser_tracker = AcousticSERTracker(sample_rate=16000, window_duration_sec=1.2)
        self.last_ser_emit_time = 0.0
        self.last_speech_time = 0.0
        self.speech_start_time = 0.0
        self.has_speech_started = False
        self.user_audio_buffer = bytearray()

        self.last_user_voice_text = ""
        self.current_turn_user_text = ""
        self.visual_projected_this_turn = False
        self.last_visual_projection_ts = 0.0
        self.last_visual_image_count = 0

        self.sticky_speaker_name: Optional[str] = None
        self.sticky_speaker_ts = 0.0
        self.unmatched_turn_streak = 0
        self.bio_last_check = 0.0

        self.last_emotion_style = ""
        self.last_emotion_style_ts = 0.0

        self.voice_enrollment: Optional[Dict[str, Any]] = None
        self.pending_speaker_ctx: Optional[str] = None

    async def notify_speaker_change(self, sp_name: Optional[str], reason: str = ""):
        """Propagates detected speaker change to frontend and Gemini context."""
        current_speaker = self.get_current_speaker()
        if sp_name == current_speaker:
            return

        new_name = sp_name or "Agnan"
        self.set_current_speaker(new_name)
        if sp_name:
            self.sticky_speaker_name = sp_name
            self.sticky_speaker_ts = _time.time()
            self.unmatched_turn_streak = 0
        else:
            self.sticky_speaker_name = None
            self.sticky_speaker_ts = 0.0

        logger.info(f"[Speaker Biometrics] Switched speaker -> '{new_name}' (reason: {reason})")
        try:
            await self.websocket.send_json({"type": "speaker_identified", "name": new_name})
        except Exception:
            pass

        ctx = memory_engine.get_system_prompt_context(new_name)
        live_svc = self.get_gemini_service()
        if live_svc and live_svc._is_running and not self.has_speech_started:
            asyncio.create_task(live_svc.inject_context(ctx))
        else:
            self.pending_speaker_ctx = ctx

    async def stt_transcribe(self, audio_pcm: bytes) -> str:
        """Transcribes PCM16 audio bytes using Gemini with anti-hallucination guard."""
        if len(audio_pcm) < 4800:
            return ""
        wav_bytes = pcm_to_wav_bytes(audio_pcm, sample_rate=16000)
        prompt = (
            "Transkripsikan ucapan pengguna dalam audio ini secara akurat dalam Bahasa Indonesia atau Inggris. "
            "Keluarkan HANYA JSON: {\"user_text\": \"...\"}. Jika hanya ada keheningan atau derau tanpa kata, keluarkan {\"user_text\": \"\"}."
        )
        try:
            active_key = key_manager.get_active_key()
            if not active_key:
                return ""
            res = None
            stt_config = types.GenerateContentConfig(max_output_tokens=80, temperature=0.1)
            active_client = key_manager.get_client()
            from core.capabilities import get_fast_auxiliary_model
            aux_m = get_fast_auxiliary_model()
            for mdl in [aux_m, "gemini-2.5-flash"]:
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
                        key_manager.rotate_key(active_key, reason="stt_quota_limit")
                        active_key = key_manager.get_active_key()
                        active_client = key_manager.get_client()

            raw = res.text.strip() if res and res.text else ""
            if "{" in raw and "}" in raw:
                j_str = raw[raw.find("{"):raw.rfind("}")+1]
                parsed = json.loads(j_str)
                u_text = clean_transcript_text(parsed.get("user_text", ""))
                if not u_text or len(u_text.strip()) < 2:
                    return ""
                norm_u = u_text.lower().strip()
                if is_stt_hallucination(norm_u):
                    return ""
                return u_text
        except Exception as e_stt:
            logger.warning(f"[Audio STT Exception]: {e_stt}")
        return ""

    async def apply_emotion_style(self, emotion: str):
        """Notifies Gemini Live of user's acoustic vocal tone naturally without hardcoded text scripts."""
        live_svc = self.get_gemini_service()
        if not emotion or emotion == "neutral" or self.dance_blocked() or not live_svc:
            return
        now = _time.monotonic()
        if emotion == self.last_emotion_style and (now - self.last_emotion_style_ts) < 180:
            return
        self.last_emotion_style = emotion
        self.last_emotion_style_ts = now

        directive = f"[Acoustic Tone]: Nada suara pengguna terdeteksi bernuansa {emotion}. Sesuaikan nada bicaramu secara alami dan empatik tanpa menyebut analisis ini secara lisan."
        try:
            trend = memory_engine.get_emotion_trend(self.get_current_speaker(), days=3)
            if trend.get("dominant") in ("sad", "tired") and trend.get("total", 0) >= 12 and emotion == trend["dominant"]:
                directive += f"\nCatatan: beberapa hari terakhir nada suaranya sering {trend['dominant']}."
        except Exception:
            pass

        try:
            await live_svc.inject_context(directive)
        except Exception as e:
            logger.debug(f"[Emotion-Aware] inject failed: {e}")

    async def handle_enrollment_turn(self, audio_pcm: bytes):
        """Guided conversational voice biometrics calibration flow."""
        if not self.voice_enrollment:
            return
        stage = self.voice_enrollment.get("stage")
        rnd = self.voice_enrollment.get("round", 0)
        sp_name = self.voice_enrollment.get("name")
        prompts = self.voice_enrollment.get("prompts", ENROLLMENT_PROMPTS)
        live_svc = self.get_gemini_service()

        if stage == "awaiting_confirmation":
            u_text = await self.stt_transcribe(audio_pcm)
            from core.plan_detector import classify_approval_intent
            spoken_intent = await classify_approval_intent(u_text or "", f"Konfirmasi kalibrasi suara untuk {sp_name}")
            if spoken_intent == "reject":
                self.voice_enrollment = None
                reply = f"Baik {sp_name}, kalibrasi dibatalkan. Kita lanjut ngobrol seperti biasa ya!"
                if live_svc:
                    await live_svc.interrupt()
                    await live_svc.send_text(f"Sistem: Ucapkan dengan suara ramah hanya kalimat ini: {reply}")
                await self.websocket.send_json({"type": "transcript", "data": reply, "speaker": "output"})
                self.log_turn(user_text=u_text, ai_text=reply, speaker_name=self.get_current_speaker())
                return
            elif spoken_intent == "approve":
                self.voice_enrollment["stage"] = "recording"
                self.voice_enrollment["round"] = 0
                self.voice_enrollment["last_ts"] = _time.time()
                p1 = prompts[0]
                reply = f"Bagus! Kalimat pertama, tolong ucapkan: \"{p1}\""
                if live_svc:
                    await live_svc.interrupt()
                    await live_svc.send_text(f"Sistem: Ucapkan dengan suara ceria dan jelas kalimat ini: {reply}")
                await self.websocket.send_json({"type": "transcript", "data": reply, "speaker": "output"})
                self.log_turn(user_text=u_text, ai_text=reply, speaker_name=self.get_current_speaker())
                return
            else:
                reply = f"Mau kalibrasi suara sekarang agar aku lebih akurat mengenalimu, {sp_name}? Jawab iya atau batal ya."
                if live_svc:
                    await live_svc.interrupt()
                    await live_svc.send_text(f"Sistem: Ucapkan dengan ramah kalimat ini: {reply}")
                await self.websocket.send_json({"type": "transcript", "data": reply, "speaker": "output"})
                return

        elif stage == "recording":
            self.voice_enrollment["last_ts"] = _time.time()
            curr_p = prompts[rnd]
            overall_intensity = estimate_audio_intensity(audio_pcm)
            if overall_intensity < 0.006 or len(audio_pcm) < 16000:
                reply = f"Suaramu kurang jelas terdengar. Tolong ulangi kalimat ini ya: \"{curr_p}\""
                if live_svc:
                    await live_svc.interrupt()
                    await live_svc.send_text(f"Sistem: Ucapkan dengan ramah kalimat ini: {reply}")
                await self.websocket.send_json({"type": "transcript", "data": reply, "speaker": "output"})
                return

            res = memory_engine.calibrate_speaker_voice(sp_name, audio_pcm)
            if not res or not res.get("success"):
                reply = f"Maaf, aku belum bisa menangkap sidik suaramu dengan jelas. Tolong ucapkan lagi ya: \"{curr_p}\""
                if live_svc:
                    await live_svc.interrupt()
                    await live_svc.send_text(f"Sistem: Ucapkan dengan ramah kalimat ini: {reply}")
                await self.websocket.send_json({"type": "transcript", "data": reply, "speaker": "output"})
                return

            next_round = rnd + 1
            if next_round < len(prompts):
                self.voice_enrollment["round"] = next_round
                next_p = prompts[next_round]
                reply = f"Bagus! Sekarang kalimat kedua: \"{next_p}\""
                if live_svc:
                    await live_svc.interrupt()
                    await live_svc.send_text(f"Sistem: Ucapkan dengan ceria kalimat ini: {reply}")
                await self.websocket.send_json({"type": "transcript", "data": reply, "speaker": "output"})
                return
            else:
                self.voice_enrollment = None
                reply = f"Sempurna, {sp_name}! Kalibrasi suara selesai dan tersimpan di database Anara. Sekarang aku jauh lebih akurat mengenali suaramu!"
                if live_svc:
                    await live_svc.interrupt()
                    await live_svc.send_text(f"Sistem: Ucapkan dengan suara sangat hangat dan senang kalimat ini: {reply}")
                await self.websocket.send_json({"type": "transcript", "data": reply, "speaker": "output"})
                self.log_turn(user_text="[Kalibrasi Suara Berhasil]", ai_text=reply, speaker_name=self.get_current_speaker())
                return

    async def transcribe_and_subtitle_audio(self, audio_pcm: bytes):
        """Processes incoming voice segment, handles live biometrics, SER, and intent routing."""
        if len(audio_pcm) < 4800:
            return

        overall_intensity = estimate_audio_intensity(audio_pcm)
        if overall_intensity < 0.005:
            return

        current_speaker_name = self.get_current_speaker()
        biometrics_allowed = len(audio_pcm) >= 25600
        if biometrics_allowed:
            try:
                id_name, conf, _ = memory_engine.identify_speaker(audio_pcm)
                if id_name:
                    self.unmatched_turn_streak = 0
                    if current_speaker_name != id_name:
                        await self.notify_speaker_change(id_name, reason=f"full_turn_match conf={conf:.2f}")
                elif current_speaker_name is not None:
                    if conf < 0.50:
                        self.unmatched_turn_streak += 1
                    else:
                        self.unmatched_turn_streak = 0
                    sticky_expired = (_time.time() - self.sticky_speaker_ts) > 90
                    if conf < 0.50 and (self.unmatched_turn_streak >= 2 or sticky_expired):
                        await self.notify_speaker_change(None, reason=f"voice_unmatched_x{self.unmatched_turn_streak} conf={conf:.2f}")
            except Exception as e_bio:
                logger.warning(f"[Voice Biometrics Error]: {e_bio}")

        try:
            acoustic_tone = analyze_speech_emotion(audio_pcm)
            await self.websocket.send_json({
                "type": "acoustic_emotion",
                "data": acoustic_tone
            })
            if acoustic_tone["emotion"] == "sad":
                await self.push_emotion("empathetic", "empathy", 0.95)
            elif acoustic_tone["emotion"] == "angry":
                await self.push_emotion("calm", "disagree", 0.75)
            elif acoustic_tone["emotion"] == "happy":
                await self.push_emotion("happy", "joy", 0.90)

            try:
                memory_engine.log_emotion(
                    current_speaker_name,
                    acoustic_tone.get("emotion", ""),
                    acoustic_tone.get("pitch_hz", 0),
                    acoustic_tone.get("rms", 0),
                    acoustic_tone.get("tone_description", ""),
                )
            except Exception:
                pass
            await self.apply_emotion_style(acoustic_tone.get("emotion", ""))
        except Exception as e_ser:
            logger.warning(f"[SER Tone Error]: {e_ser}")

        u_text = await self.stt_transcribe(audio_pcm)
        if not u_text:
            return

        self.last_user_voice_text = u_text
        self.current_turn_user_text = u_text
        logger.info(f"[Audio STT User] {u_text!r}")
        await self.websocket.send_json({"type": "transcript", "data": u_text, "speaker": "input"})

        asyncio.create_task(memory_engine.distill_and_store_memories_async(
            key_manager.get_client(), u_text, current_speaker_name
        ))

        live_svc = self.get_gemini_service()

        # ── VOICE PASS-THROUGH APPROVAL (Hands-Free Hermes Parity) ──
        from core.session_manager import session_state_manager, ActionState
        from core.plan_detector import is_explicit_plan_approval

        pending_act = (
            session_state_manager.get_pending("voice", "default")
            or session_state_manager.get_pending("voice_hud", "default")
            or session_state_manager.get_pending("web_studio", "default")
        )
        if not pending_act:
            from core.agent import anara_agent
            cur_sid = anara_agent.get_active_session_id()
            if cur_sid:
                pending_act = (
                    session_state_manager.get_pending("voice", str(cur_sid))
                    or session_state_manager.get_pending("voice_hud", str(cur_sid))
                    or session_state_manager.get_pending("web_studio", str(cur_sid))
                )

        if pending_act and pending_act.is_expired:
            session_state_manager.resolve_action(pending_act.channel, pending_act.channel_id, pending_act.action_id, ActionState.EXPIRED)
            pending_act = None

        u_text_clean = u_text.strip().lower()
        from core.plan_detector import classify_approval_intent
        plan_ctx = pending_act.plan_text if pending_act else ""
        spoken_intent = await classify_approval_intent(u_text_clean, plan_ctx)
        is_approval = (spoken_intent == "approve")
        is_cancel = (spoken_intent == "reject")

        if pending_act and is_approval:
            logger.info(f"[VoicePipeline] Spoken approval detected for pending action #{pending_act.action_id} ('{u_text}'). Executing...")
            session_state_manager.resolve_action(pending_act.channel, pending_act.channel_id, pending_act.action_id, ActionState.EXECUTING)
            if live_svc:
                await live_svc.interrupt()
                await live_svc.send_text("Sistem: Katakan singkat dengan mantap: Baik, tindakan disetujui. Sedang dieksekusi sekarang.")

            await self.websocket.send_json({
                "type": "transcript",
                "data": "Baik, tindakan disetujui. Sedang dieksekusi sekarang.",
                "speaker": "output",
                "is_final": True
            })

            from core.runner import AnaraExecutionRunner
            runner = AnaraExecutionRunner(
                session_id=pending_act.session_id,
                speaker_name=current_speaker_name,
                platform="voice",
            )
            exec_res = await runner.execute_turn(
                user_message=f"Eksekusi tindakan: {pending_act.original_prompt or pending_act.tool_name}",
                requested_mode="build"
            )
            session_state_manager.resolve_action(pending_act.channel, pending_act.channel_id, pending_act.action_id, ActionState.EXECUTED)

            from cognition.audio import filter_tts_speech_text
            spoken_summary = filter_tts_speech_text(exec_res.text)
            if live_svc:
                await live_svc.send_text(f"Sistem: Jelaskan hasil eksekusi ini kepada pengguna dengan ramah dan ringkas: {spoken_summary}")

            await self.websocket.send_json({
                "type": "transcript",
                "data": exec_res.text,
                "speaker": "output",
                "is_final": True
            })
            self.log_turn(user_text=u_text, ai_text=exec_res.text, speaker_name=current_speaker_name)
            return

        elif pending_act and is_cancel:
            logger.info(f"[VoicePipeline] Spoken cancellation for pending action #{pending_act.action_id}.")
            session_state_manager.resolve_action(pending_act.channel, pending_act.channel_id, pending_act.action_id, ActionState.REJECTED)
            cancel_msg = "Baik, tindakan telah dibatalkan. Tidak ada perubahan yang dilakukan."
            if live_svc:
                await live_svc.interrupt()
                await live_svc.send_text(f"Sistem: Ucapkan singkat dan ramah: {cancel_msg}")

            await self.websocket.send_json({
                "type": "transcript",
                "data": cancel_msg,
                "speaker": "output",
                "is_final": True
            })
            self.log_turn(user_text=u_text, ai_text=cancel_msg, speaker_name=current_speaker_name)
            return

        if is_briefing_request(u_text) and not self.dance_blocked():
            logger.info(f"[Briefing] Request detected: {u_text!r}")
            if live_svc:
                await live_svc.interrupt()
            try:
                brief = await generate_daily_briefing(
                    key_manager.get_client(), memory_engine, current_speaker_name
                )
                await self.websocket.send_json({
                    "type": "hud_visual",
                    "data": brief["reply_text"],
                    "visualType": "briefing",
                    "briefingData": brief["briefing_data"],
                    "mediaType": "hud",
                })
                await self.websocket.send_json({
                    "type": "transcript", "data": brief["reply_text"],
                    "speaker": "output", "is_final": True,
                })
                if live_svc:
                    await live_svc.send_text(f"Sistem: Bacakan ringkasan ini dengan gaya suara hangat: {brief['speech_text']}")
                self.log_turn(user_text=u_text, ai_text=brief["reply_text"], speaker_name=current_speaker_name)
            except Exception as e_brief:
                logger.error(f"[Briefing] Generation failed: {e_brief}")
            return

        media_resolved = await resolve_media_request(u_text)
        if media_resolved and not self.dance_blocked():
            logger.info(f"[Media Router] Matched media: {media_resolved.get('title')}")
            if live_svc:
                await live_svc.interrupt()
            track = media_resolved["track"]
            kind = media_resolved.get("kind", "music")
            await self.media_controller.send_media_play(track, kind=kind)
            reply = media_resolved.get("reply_text") or f"Memutar {track.get('title')}"
            await self.websocket.send_json({"type": "transcript", "data": reply, "speaker": "output", "is_final": True})
            if live_svc:
                await live_svc.send_text(f"Sistem: Ucapkan singkat dan ceria: {reply}")
            self.log_turn(user_text=u_text, ai_text=reply, speaker_name=current_speaker_name)
            return

        intent = memory_engine.classify_conversation_intent(u_text, current_speaker_name)
        if intent and intent.get("type") and intent["type"] not in ("chat", "other"):
            if intent.get("type") in ("playlist_create", "playlist_play", "playlist_add_current", "media_history", "playlist_list"):
                await self.media_controller.handle_playlist_intent(intent, u_text)
                return
            elif intent.get("type") == "read_animations":
                summary = memory_engine.format_animations_summary()
                if live_svc:
                    await live_svc.interrupt()
                    speak_cmd = (
                        f"[Info Sistem: Daftar animasi 3D Anara di database: {summary}. "
                        "Ceritakan kemampuan animasi tubuh dan ekspresi 3D ini kepada pengguna dengan ceria.]"
                    )
                    await live_svc.send_text(speak_cmd)
                self.log_turn(user_text=u_text, ai_text=summary, speaker_name=current_speaker_name)
                return
            elif intent.get("type") == "delete_memory":
                if live_svc:
                    await live_svc.interrupt()
                memory_engine.delete_memory(current_speaker_name, intent["key"])
                speak_cmd = (
                    f"[Info Sistem: Catatan '{intent['key']}' milik {current_speaker_name} telah dihapus dari database. "
                    "Beri tahu pengguna bahwa catatan tersebut sudah dilupakan.]"
                )
                if live_svc:
                    await live_svc.send_text(speak_cmd)
                return

        speaker_ctx = memory_engine.get_system_prompt_context(current_speaker_name)
        proactive_facts = memory_engine.get_proactive_relevant_facts(u_text, current_speaker_name)
        if proactive_facts:
            speaker_ctx = f"{speaker_ctx}\n{proactive_facts}"
        active_sys_prompt = f"{SYSTEM_PROMPT}\n{speaker_ctx}"

        if could_be_visual_request(u_text) and not self.dance_blocked():
            vis = await generate_visual_projection(key_manager.get_client(), u_text, active_sys_prompt)
            if vis.get("has_visual"):
                v_type = vis.get("visual_type", "image")
                r_text = vis.get("reply_text", "Protokol visual telah diproyeksikan ke layar HUD.")
                n_imgs = len(vis.get("images") or []) or (1 if vis.get("image_url") else 0)
                self.visual_projected_this_turn = True
                self.last_visual_projection_ts = _time.monotonic()
                self.last_visual_image_count = n_imgs
                await self.websocket.send_json({
                    "type": "transcript",
                    "data": r_text,
                    "speaker": "output",
                    "visualType": v_type,
                    "imageUrl": vis.get("image_url"),
                    "imageTitle": vis.get("image_title"),
                    "sourceDomain": vis.get("source_domain"),
                    "sourceUrl": vis.get("source_url"),
                    "images": vis.get("images"),
                    "weatherData": vis.get("weather_data"),
                    "codeData": vis.get("code_data"),
                    "systemHudData": vis.get("system_hud_data"),
                    "knowledgeCardData": vis.get("knowledge_card_data"),
                    "todoData": vis.get("todo_data"),
                    "mediaType": "image" if v_type == "image" else "hud",
                    "timestamp": _time.time(),
                })
                await self.websocket.send_json({
                    "type": "hud_visual",
                    "data": r_text,
                    "visualType": v_type,
                    "imageUrl": vis.get("image_url"),
                    "imageTitle": vis.get("image_title"),
                    "sourceDomain": vis.get("source_domain"),
                    "sourceUrl": vis.get("source_url"),
                    "images": vis.get("images"),
                    "weatherData": vis.get("weather_data"),
                    "codeData": vis.get("code_data"),
                    "systemHudData": vis.get("system_hud_data"),
                    "knowledgeCardData": vis.get("knowledge_card_data"),
                    "todoData": vis.get("todo_data"),
                    "mediaType": "image" if v_type == "image" else "hud",
                    "timestamp": _time.time(),
                })
                if live_svc:
                    await live_svc.interrupt()
                    speak_cmd = f"Sistem: Katakan ini dengan gaya suaramu yang hangat dan singkat: {r_text}"
                    await live_svc.send_text(speak_cmd)
                self.log_turn(user_text=u_text, ai_text=r_text, speaker_name=current_speaker_name, media_type=v_type)
                return
