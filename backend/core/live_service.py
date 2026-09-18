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
from typing import Callable, Awaitable, Optional, Dict, Any, List

from google import genai
from google.genai import types
from tools import get_agent_tools, dispatch_tool_call
from cognition import get_soul_prompt

logger = logging.getLogger(__name__)

# Gemini Live API configuration
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-live-preview")
SYSTEM_PROMPT = get_soul_prompt(mode="voice")

# Audio format: PCM16, 16kHz mono (required by Gemini Live API)
INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000  # Gemini outputs at 24kHz


class GeminiLiveService:
    """
    Manages a Gemini Live API session for real-time voice conversation.
    Supports dynamic model switching and auto-reconnect on timeout/disconnect.
    """

    def __init__(self, api_key: Optional[str] = None, active_speaker: Optional[str] = None, model_id: Optional[str] = None):
        from core.key_manager import key_manager
        self.api_key = api_key or key_manager.get_active_key()
        self.active_speaker = active_speaker
        self.model_id = (model_id or os.getenv("GEMINI_MODEL", "gemini-3.1-flash-live-preview")).replace("models/", "")
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.session = None
        self._send_queue: asyncio.Queue = asyncio.Queue(maxsize=40)
        self._is_running = False
        self._session_ready = asyncio.Event()
        self._mic_buffer = bytearray()  # accumulate mic chunks before sending
        self._MIC_CHUNK_BYTES = 3200    # 200ms at 16kHz PCM16 (= 3200 bytes)
        self.bridge_context: Optional[str] = None

        # Callbacks (set in start_session)
        self._on_audio_chunk: Optional[Callable] = None
        self._on_transcript: Optional[Callable] = None
        self._on_interrupted: Optional[Callable] = None
        self._on_turn_complete: Optional[Callable] = None

    def _make_config(self) -> types.LiveConnectConfig:
        from memory import memory_engine
        soul_instruction = get_soul_prompt(mode="voice")
        dynamic_ctx = memory_engine.get_system_prompt_context(self.active_speaker)
        parts_text = [soul_instruction, dynamic_ctx]
        if self.bridge_context:
            parts_text.append(self.bridge_context)
        full_system_instruction = "\n\n".join(parts_text)
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
            # Universal Agent Tools (Native Function Calling for Anara Actions & Real-time Web Search)
            tools=get_agent_tools(),
        )

    async def switch_model(self, new_model_id: str):
        """Switches the live voice model dynamically and restarts connection with the new model."""
        clean_id = (new_model_id or "").replace("models/", "").strip()
        if not clean_id or clean_id == self.model_id:
            return
        logger.info(f"[GeminiLive] Dynamically switching live voice model: '{self.model_id}' -> '{clean_id}'")
        self.model_id = clean_id
        if self.session:
            try:
                if hasattr(self.session, "close"):
                    await self.session.close()
                elif hasattr(self.session, "_ws") and self.session._ws:
                    await self.session._ws.close()
            except Exception as e_close:
                logger.debug(f"[GeminiLive] session close on switch: {e_close}")
        self._session_ready.clear()
        # NOTE: google-genai 1.0.0 has no output_audio_transcription field, so Gemini
        # never returns a transcript of what Anara SAID. main.py therefore must NOT
        # depend on ai_transcript_buffer for HUD decisions (it uses the local STT
        # user transcript + previous-turn context instead).

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
            if not self.api_key:
                from core.key_manager import key_manager
                self.api_key = key_manager.get_active_key()
                if self.api_key:
                    self.client = genai.Client(api_key=self.api_key)
                    logger.info("[GeminiLive] Active key detected from pool, initiating Live session.")
                else:
                    await asyncio.sleep(2.0)
                    continue

            try:
                reconnect_delay = 1  # reset on successful session
                await self._run_single_session()
            except Exception as e:
                if not self._is_running:
                    logger.debug(f"[GeminiLive] Session ended cleanly during shutdown: {e}")
                    break

                err = str(e)
                from core.key_manager import key_manager

                # Check if this error is a genuine API key failure (quota limit 429 or permission denied 403)
                is_quota_or_auth = any(q in err.lower() for q in ["429", "quota", "resource_exhausted", "permission_denied", "403", "unauthenticated", "401"])
                if is_quota_or_auth:
                    # Only rotate key and apply cooldown if the key itself actually failed
                    new_key = key_manager.rotate_key(self.api_key, reason=f"live_quota_{err[:40]}")
                    self.api_key = new_key
                    self.client = genai.Client(api_key=new_key)
                    logger.warning(f"[GeminiLive] Quota/Auth error — rotated API key, reconnecting in {reconnect_delay}s: {e}")
                else:
                    # Normal connection aborts (1008, The operation was aborted, ConnectionClosed, idle timeout):
                    # Do NOT rotate key or penalize healthy keys with cooldown
                    if any(x in err for x in ["1008", "1011", "1012", "ConnectionClosed", "ping timeout", "The operation was aborted"]):
                        logger.info(f"[GeminiLive] Session closed ({err[:50]}), reconnecting in {reconnect_delay}s...")
                    else:
                        logger.warning(f"[GeminiLive] Session error: {e}. Reconnecting in {reconnect_delay}s...")
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
        logger.info(f"Connecting to Gemini Live model: {self.model_id}")

        # Reset ready event so callers wait for the NEW session to be ready
        self._session_ready.clear()

        async with self.client.aio.live.connect(
            model=self.model_id,
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

                            # ── 3. Agent Tool Call Handling (Native Function Calling from Gemini Live) ──
                            tool_calls_to_process = []
                            if getattr(sc, "tool_call", None) and getattr(sc.tool_call, "function_calls", None):
                                tool_calls_to_process.extend(sc.tool_call.function_calls)
                            if sc.model_turn:
                                for part in (sc.model_turn.parts or []):
                                    if getattr(part, "function_call", None):
                                        tool_calls_to_process.append(part.function_call)

                            if tool_calls_to_process:
                                for fc in tool_calls_to_process:
                                    fn_name = getattr(fc, "name", "")
                                    call_id = getattr(fc, "id", "")
                                    fn_args = getattr(fc, "args", {}) or {}
                                    logger.info(f"[Agent Live] Tool call received: {fn_name!r} id={call_id!r} args={fn_args}")
                                    asyncio.create_task(self._handle_and_send_tool_call(fn_name, call_id, fn_args))

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
                    if not self._is_running:
                        break
                    err = str(inner_e)
                    if any(x in err for x in ["1008", "1011", "1012", "keepalive", "ConnectionClosed", "ping timeout", "The operation was aborted"]):
                        logger.debug(f"[GeminiLive] Connection closed: {inner_e}")
                        break
                    logger.error(f"Receive inner loop error: {inner_e}", exc_info=True)
                    break

        except Exception as e:
            if not self._is_running:
                return
            err = str(e)
            RECOVERABLE = ["1008", "1011", "1012", "keepalive", "ConnectionClosed", "ping timeout", "The operation was aborted"]
            if any(x in err for x in RECOVERABLE):
                logger.debug(f"[GeminiLive] Connection closed (recoverable): {e} — will reconnect")
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

                    elif kind == "tool_response":
                        tool_data = item["data"]
                        logger.info(f"→ Gemini tool response: {tool_data.model_dump_json(exclude_none=True)}")
                        if hasattr(session, "_ws") and session._ws:
                            payload = {"tool_response": json.loads(tool_data.model_dump_json(exclude_none=True))}
                            await session._ws.send(json.dumps(payload))
                        else:
                            await session.send(input=tool_data)

                    elif kind == "text":
                        text = item["data"]
                        logger.info(f"→ Gemini text turn: {text!r}")
                        await session.send(
                            input=text,
                            end_of_turn=True
                        )

                    elif kind == "context":
                        # Silent mid-session context injection (end_of_turn=False):
                        # updates the model's knowledge (e.g. identified speaker profile)
                        # WITHOUT triggering a spoken response — zero interruption.
                        ctx_text = item["data"]
                        logger.info(f"→ Gemini context injection: {ctx_text[:80]!r}...")
                        try:
                            await session.send(
                                input=ctx_text,
                                end_of_turn=False
                            )
                        except Exception as ctx_err:
                            logger.warning(f"Context injection failed: {ctx_err}")

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

    async def _handle_and_send_tool_call(self, fn_name: str, call_id: str, fn_args: Dict[str, Any]):
        """Executes a function call from Gemini Live and queues the response back to the session."""
        try:
            exec_res = await dispatch_tool_call(fn_name, fn_args)
            logger.info(f"[Agent Live] Tool '{fn_name}' execution result: {exec_res.get('status')}")
            resp_obj = types.FunctionResponse(
                name=fn_name,
                id=call_id,
                response=exec_res
            )
            tool_resp_client = types.LiveClientToolResponse(function_responses=[resp_obj])
            await self._send_queue.put({"kind": "tool_response", "data": tool_resp_client})
        except Exception as e:
            logger.error(f"[Agent Live] Tool execution error in '{fn_name}': {e}", exc_info=True)
            err_resp = types.FunctionResponse(
                name=fn_name,
                id=call_id,
                response={"status": "error", "message": str(e)}
            )
            tool_resp_client = types.LiveClientToolResponse(function_responses=[err_resp])
            await self._send_queue.put({"kind": "tool_response", "data": tool_resp_client})

    async def send_audio(self, audio_bytes: bytes, end_of_turn: bool = False):
        """Send mic audio chunk or end_of_turn signal to Gemini Live with backpressure protection."""
        if not self._is_running or not self._session_ready.is_set():
            return
        if end_of_turn:
            try:
                self._send_queue.put_nowait({"kind": "end_of_turn"})
            except asyncio.QueueFull:
                try:
                    self._send_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                await self._send_queue.put({"kind": "end_of_turn"})
        elif audio_bytes:
            try:
                self._send_queue.put_nowait({"kind": "audio", "data": audio_bytes})
            except asyncio.QueueFull:
                try:
                    self._send_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    self._send_queue.put_nowait({"kind": "audio", "data": audio_bytes})
                except Exception:
                    pass

    async def send_text(self, text: str):
        """Queue a text turn to Gemini (processed by _send_loop)."""
        if self._is_running:
            logger.info(f"Queuing text for Gemini: {text!r}")
            await self._send_queue.put({"kind": "text", "data": text})

    async def inject_context(self, text: str):
        """
        Silently inject context into the live session (end_of_turn=False).
        Used to update the model mid-session — e.g. when the active speaker is
        identified via voice biometrics — WITHOUT triggering any spoken reply.
        """
        if self._is_running and self._session_ready.is_set():
            await self._send_queue.put({"kind": "context", "data": text})

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
