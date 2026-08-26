"""
Gemini Live API service for real-time voice-to-voice communication.
Handles bidirectional audio streaming with the Gemini model.
Includes auto-reconnect on session timeout/disconnect.
"""
import asyncio
import base64
import json
import logging
import os
from typing import Callable, Awaitable, Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Gemini Live API configuration
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-live-preview")
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    (
        "Kamu adalah Anara, asisten AI visual 3D multi-pengguna yang cerdas, ramah, hangat, dan ekspresif di layar. "
        "Nama kamu adalah Anara. Kamu memiliki sistem biometrik suara cerdas yang mampu mengenali berbagai orang berbeda dari sidik suaranya di database SQLite. "
        "Kamu memiliki kemampuan canggih menampilkan foto asli dan gambar dari pencarian web langsung ke layar pengguna saat pengguna memintanya. "
        "Fokus utama kamu adalah menjadi teman percakapan yang menyenangkan dan membantu menjawab berbagai topik serta pertanyaan pengguna dalam Bahasa Indonesia sehari-hari yang natural dan ringkas (1-2 kalimat). "
        "Sapa dan jawab setiap pengguna secara cerdas sesuai profil dan preferensi pribadi mereka yang teridentifikasi di database."
    )
)

# Audio format: PCM16, 16kHz mono (required by Gemini Live API)
INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000  # Gemini outputs at 24kHz


class GeminiLiveService:
    """
    Manages a Gemini Live API session for real-time voice conversation.
    Supports auto-reconnect on timeout/disconnect.
    """

    def __init__(self, api_key: Optional[str] = None, active_speaker: Optional[str] = None):
        from key_manager import key_manager
        self.api_key = api_key or key_manager.get_active_key()
        self.active_speaker = active_speaker
        self.client = genai.Client(api_key=self.api_key)
        self.session = None
        self._send_queue: asyncio.Queue = asyncio.Queue()
        self._is_running = False
        self._session_ready = asyncio.Event()
        self._mic_buffer = bytearray()  # accumulate mic chunks before sending
        self._MIC_CHUNK_BYTES = 3200    # 200ms at 16kHz PCM16 (= 3200 bytes)

        # Callbacks (set in start_session)
        self._on_audio_chunk: Optional[Callable] = None
        self._on_transcript: Optional[Callable] = None
        self._on_interrupted: Optional[Callable] = None
        self._on_turn_complete: Optional[Callable] = None

    def _make_config(self) -> types.LiveConnectConfig:
        from memory_service import memory_engine
        dynamic_ctx = memory_engine.get_system_prompt_context(self.active_speaker)
        full_system_instruction = f"{SYSTEM_PROMPT}\n{dynamic_ctx}"
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(
                parts=[types.Part(text=full_system_instruction)]
            ),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Aoede"
                    )
                )
            ),
        )

    def set_active_speaker(self, speaker_name: Optional[str]):
        """Dynamically update active speaker context for the session."""
        self.active_speaker = speaker_name

    async def start_session(
        self,
        on_audio_chunk: Callable[[bytes], Awaitable[None]],
        on_transcript: Callable[[str, str], Awaitable[None]],
        on_interrupted: Callable[[], Awaitable[None]],
        on_turn_complete: Callable[[], Awaitable[None]],
    ):
        """Start a Gemini Live session. Auto-reconnects and auto-rotates API keys on timeout/error."""
        self._on_audio_chunk = on_audio_chunk
        self._on_transcript = on_transcript
        self._on_interrupted = on_interrupted
        self._on_turn_complete = on_turn_complete
        self._is_running = True
        reconnect_delay = 1  # seconds, will back off on repeated failures

        while self._is_running:
            try:
                reconnect_delay = 1  # reset on successful session
                await self._run_single_session()
            except Exception as e:
                err = str(e)
                from key_manager import key_manager
                # Auto-rotate to a fresh healthy API key from the pool!
                new_key = key_manager.rotate_key(self.api_key, reason=f"live_reconnect_{err[:40]}")
                self.api_key = new_key
                self.client = genai.Client(api_key=new_key)

                if any(x in err for x in ["1008", "1011", "1012", "ConnectionClosed", "ping timeout"]):
                    logger.warning(f"Gemini Live session ended (recoverable) — rotated API key, reconnecting in {reconnect_delay}s: {e}")
                else:
                    logger.error(f"Gemini Live session error: {e}. Rotated to fresh API key, reconnecting in {reconnect_delay}s...")
                    reconnect_delay = min(reconnect_delay * 2, 8)  # max backoff 8s

            if self._is_running:
                # Drain mic buffer before reconnecting — stale audio causes 1008 on new session
                self._mic_buffer.clear()
                while not self._send_queue.empty():
                    try:
                        self._send_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                logger.info(f"Reconnecting to Gemini Live in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
            else:
                break

    async def _run_single_session(self):
        """Run one Gemini Live session until it disconnects."""
        config = self._make_config()
        logger.info(f"Connecting to Gemini Live model: {GEMINI_MODEL}")

        # Reset ready event so callers wait for the NEW session to be ready
        self._session_ready.clear()

        async with self.client.aio.live.connect(
            model=GEMINI_MODEL,
            config=config,
        ) as session:
            self.session = session
            self._session_ready.set()
            logger.info("Gemini Live session established")

            # Run receive and send loops concurrently
            await asyncio.gather(
                self._receive_loop(session),
                self._send_loop(session),
            )

    async def _receive_loop(self, session):
        """
        Continuously receive ALL messages across multiple turns from Gemini.
        Note: google-genai session.receive() breaks on turn_complete, so we wrap
        it in a while self._is_running loop to keep receiving subsequent turns!
        """
        try:
            while self._is_running:
                try:
                    async for response in session.receive():
                        if not self._is_running:
                            break

                        # 1. Process server content parts (audio bytes, user transcript, and AI output transcript)
                        if response.server_content:
                            sc = response.server_content

                            # User input voice transcription from Gemini
                            if getattr(sc, "input_transcription", None) and getattr(sc.input_transcription, "text", None):
                                if self._on_transcript:
                                    logger.info(f"User live transcript: {sc.input_transcription.text!r}")
                                    await self._on_transcript(sc.input_transcription.text, "input")

                            # Model turn (audio data & text)
                            if sc.model_turn:
                                for part in (sc.model_turn.parts or []):
                                    # Audio part (sent only once per chunk)
                                    if part.inline_data and part.inline_data.data:
                                        if self._on_audio_chunk:
                                            await self._on_audio_chunk(part.inline_data.data)
                                    # Text part
                                    if getattr(part, "text", None):
                                        if self._on_transcript:
                                            logger.info(f"AI live text: {part.text!r}")
                                            await self._on_transcript(part.text, "output")

                            # Live output speech transcription from Gemini
                            if getattr(sc, "output_transcription", None) and getattr(sc.output_transcription, "text", None):
                                if self._on_transcript:
                                    logger.info(f"AI live transcript: {sc.output_transcription.text!r}")
                                    await self._on_transcript(sc.output_transcription.text, "output")

                        # 2. Raw audio fallback (only if not already processed in server_content)
                        elif self._on_audio_chunk and response.data:
                            logger.debug(f"AI audio fallback: {len(response.data)} bytes")
                            await self._on_audio_chunk(response.data)

                        # Turn signals
                        if response.server_content:
                            sc = response.server_content
                            if sc.turn_complete and self._on_turn_complete:
                                logger.info("AI turn complete — ready for next turn")
                                await self._on_turn_complete()
                            if sc.interrupted and self._on_interrupted:
                                logger.info("AI response interrupted")
                                await self._on_interrupted()

                except Exception as inner_e:
                    err = str(inner_e)
                    if any(x in err for x in ["1008", "1011", "1012", "keepalive", "ConnectionClosed", "ping timeout", "The operation was aborted"]):
                        logger.warning(f"Gemini connection closed: {inner_e}")
                        break
                    logger.error(f"Receive inner loop error: {inner_e}", exc_info=True)
                    break

        except Exception as e:
            err = str(e)
            RECOVERABLE = ["1008", "1011", "1012", "keepalive", "ConnectionClosed", "ping timeout", "The operation was aborted"]
            if any(x in err for x in RECOVERABLE):
                logger.warning(f"Gemini connection closed (recoverable): {e} — will reconnect")
            else:
                logger.error(f"Receive loop error: {e}", exc_info=True)
            raise


    async def _send_loop(self, session):
        """Send queued items (audio or text) to Gemini via session.send()."""
        try:
            while self._is_running:
                try:
                    item = await asyncio.wait_for(
                        self._send_queue.get(), timeout=0.5
                    )
                    if item is None:
                        break

                    kind = item.get("kind")

                    if kind == "audio":
                        audio_bytes = item["data"]
                        if not audio_bytes:
                            continue
                        logger.debug(f"→ Gemini audio: {len(audio_bytes)} bytes")
                        b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
                        audio_payload = {
                            "realtime_input": {
                                "audio": {
                                    "data": b64_audio,
                                    "mime_type": f"audio/pcm;rate={INPUT_SAMPLE_RATE}",
                                }
                            }
                        }
                        if hasattr(session, "_ws") and session._ws:
                            await session._ws.send(json.dumps(audio_payload))
                        else:
                            await session.send(input={"data": audio_bytes, "mime_type": f"audio/pcm;rate={INPUT_SAMPLE_RATE}"})

                    elif kind == "end_of_turn":
                        logger.info("→ Signaling turn_complete to Gemini Live")
                        turn_payload = {"client_content": {"turn_complete": True}}
                        if hasattr(session, "_ws") and session._ws:
                            await session._ws.send(json.dumps(turn_payload))

                    elif kind == "text":
                        text = item["data"]
                        logger.info(f"→ Gemini text turn: {text!r}")
                        await session.send(
                            input=text,
                            end_of_turn=True
                        )

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    err = str(e)
                    if any(x in err for x in ["1011", "1012", "keepalive", "ConnectionClosed", "ping timeout"]):
                        logger.warning(f"Gemini connection closed in send: {e}")
                        self._is_running = False
                        break
                    logger.error(f"Send error: {e}")

        except Exception as e:
            logger.error(f"Send loop fatal: {e}", exc_info=True)
            raise

    async def send_audio(self, audio_bytes: bytes, end_of_turn: bool = False):
        """Send mic audio chunk or end_of_turn signal to Gemini Live."""
        if not self._is_running or not self._session_ready.is_set():
            return
        if end_of_turn:
            await self._send_queue.put({"kind": "end_of_turn"})
        elif audio_bytes:
            await self._send_queue.put({"kind": "audio", "data": audio_bytes})

    async def send_text(self, text: str):
        """Queue a text turn to Gemini (processed by _send_loop)."""
        if self._is_running:
            logger.info(f"Queuing text for Gemini: {text!r}")
            await self._send_queue.put({"kind": "text", "data": text})

    async def interrupt(self):
        """Signal interrupt (currently handled by Gemini VAD automatically)."""
        logger.info("Interrupt requested")

    async def stop(self):
        """Stop the session cleanly."""
        self._is_running = False
        self._mic_buffer.clear()
        while not self._send_queue.empty():
            try:
                self._send_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        await self._send_queue.put(None)  # sentinel to stop _send_loop
        self.session = None
        logger.info("Gemini Live session stopped")
