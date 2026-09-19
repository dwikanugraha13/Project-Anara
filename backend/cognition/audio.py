"""
Audio utilities for processing audio chunks between browser and Gemini API.
"""
import base64
import io
from typing import Optional, Dict, Any, List
import numpy as np


def pcm16_to_base64(pcm_bytes: bytes) -> str:
    """Convert raw PCM16 bytes to base64 string for Gemini API."""
    return base64.b64encode(pcm_bytes).decode("utf-8")


def base64_to_pcm16(b64_str: str) -> bytes:
    """Decode base64 audio from browser (PCM16 format)."""
    return base64.b64decode(b64_str)


def float32_to_pcm16(float32_array: list[float]) -> bytes:
    """Convert Float32 audio samples (from browser AudioWorklet) to PCM16 bytes."""
    arr = np.array(float32_array, dtype=np.float32)
    arr = np.clip(arr, -1.0, 1.0)
    pcm16 = (arr * 32767).astype(np.int16)
    return pcm16.tobytes()


def pcm16_to_float32(pcm_bytes: bytes) -> list[float]:
    """Convert PCM16 bytes to float32 list (for debugging/visualization)."""
    arr = np.frombuffer(pcm_bytes, dtype=np.int16)
    return (arr / 32767.0).tolist()


def estimate_audio_intensity(pcm_bytes: bytes) -> float:
    """
    Estimate audio intensity (RMS) from PCM16 bytes.
    Returns value between 0.0 and 1.0.
    Used for driving talking animation intensity on avatar.
    """
    if not pcm_bytes:
        return 0.0
    arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    rms = np.sqrt(np.mean(arr ** 2))
    # Normalize to 0-1 range (max PCM16 value is 32767)
    return float(np.clip(rms / 32767.0, 0.0, 1.0))


def analyze_speech_emotion(pcm_bytes: bytes, sample_rate: int = 16000) -> dict:
    """
    High-precision Speech Emotion Recognition (SER) acoustic classifier.
    Extracts:
    - RMS Energy on active voiced segments (Loudness dynamics)
    - Harmonic Pitch (F0 Mean & Pitch Modulation/Variance) via NCCF
    - Spectral Centroid (Timbre brightness & tension)
    - Zero-Crossing Rate (ZCR)
    - Voicing Activity Ratio
    
    Returns structured acoustic emotion classification:
        {
            "emotion": "sad" | "angry" | "happy" | "neutral",
            "confidence": float,
            "pitch_hz": float,
            "pitch_variance": float,
            "rms": float,
            "spectral_centroid_hz": float,
            "tone_description": str
        }
    """
    if not pcm_bytes or len(pcm_bytes) < 3200:  # Need at least 100ms
        return {
            "emotion": "neutral",
            "confidence": 0.85,
            "pitch_hz": 0.0,
            "pitch_variance": 0.0,
            "rms": 0.0,
            "spectral_centroid_hz": 0.0,
            "tone_description": "Nada suara santai / percakapan netral"
        }
        
    arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    
    # 1. Overall RMS Energy & Voiced Segment Separation
    frame_len = int(0.03 * sample_rate)  # 30ms frames
    hop_len = int(0.015 * sample_rate)   # 15ms hop
    
    frame_rms_list = []
    pitch_estimates = []
    
    for start in range(0, len(arr) - frame_len, hop_len):
        frame = arr[start:start + frame_len]
        f_rms = float(np.sqrt(np.mean(frame ** 2)))
        frame_rms_list.append(f_rms)
        
        # 2. Harmonic Pitch Estimation (only for voiced frames with adequate energy)
        if f_rms > 0.015:
            # Normalized Autocorrelation
            windowed = frame * np.hanning(len(frame))
            corr = np.correlate(windowed, windowed, mode='full')
            corr = corr[len(corr)//2:]
            
            # Human pitch range: 75Hz to 400Hz
            min_lag = int(sample_rate / 400)
            max_lag = int(sample_rate / 75)
            
            if max_lag < len(corr):
                peak_sub = corr[min_lag:max_lag]
                if len(peak_sub) > 0 and np.max(peak_sub) > 0.3 * (corr[0] + 1e-9):
                    peak_idx = min_lag + np.argmax(peak_sub)
                    # Parabolic interpolation for sub-sample accuracy
                    if 0 < peak_idx < len(corr) - 1:
                        alpha = corr[peak_idx - 1]
                        beta = corr[peak_idx]
                        gamma = corr[peak_idx + 1]
                        denom = 2 * (2 * beta - alpha - gamma)
                        delta = (alpha - gamma) / denom if denom != 0 else 0
                        refined_lag = peak_idx + delta
                    else:
                        refined_lag = peak_idx
                        
                    if refined_lag > 0:
                        pitch_estimates.append(sample_rate / refined_lag)

    # 3. Aggregate Acoustic Features
    overall_rms = float(np.sqrt(np.mean(arr ** 2)))
    voiced_rms = float(np.mean([r for r in frame_rms_list if r > 0.015])) if any(r > 0.015 for r in frame_rms_list) else overall_rms
    
    # Fundamental Pitch Statistics
    if len(pitch_estimates) >= 3:
        pitch_hz = float(np.median(pitch_estimates))
        pitch_std = float(np.std(pitch_estimates))
    elif len(pitch_estimates) > 0:
        pitch_hz = float(np.mean(pitch_estimates))
        pitch_std = 0.0
    else:
        pitch_hz = 0.0
        pitch_std = 0.0

    # 4. Zero-Crossing Rate (ZCR)
    zcr = float(np.mean(np.abs(np.diff(np.sign(arr)))) / 2.0)
    
    # 5. Spectral Centroid via FFT
    fft_vals = np.abs(np.fft.rfft(arr))
    freqs = np.fft.rfftfreq(len(arr), 1.0 / sample_rate)
    sum_fft = np.sum(fft_vals)
    spectral_centroid = float(np.sum(freqs * fft_vals) / (sum_fft + 1e-9))

    # 6. Robust Multi-Feature Acoustic Classifier with Realistic Human Ranges
    # Sad / Low Energy / Depressed Tone:
    # Requires VERY low overall energy + flat pitch variation + low brightness
    is_sad = (
        voiced_rms < 0.022 and 
        overall_rms < 0.020 and 
        spectral_centroid < 1550 and 
        (pitch_std < 12.0 or pitch_hz < 130)
    )
    
    # Angry / Agitated / Harsh Tone:
    # Requires sustained intense RMS + high spectral centroid + high ZCR/strain
    is_angry = (
        (overall_rms > 0.20 and spectral_centroid > 2600) or
        (overall_rms > 0.25 and pitch_hz > 175) or
        (voiced_rms > 0.22 and spectral_centroid > 2800 and zcr > 0.12)
    )
    
    # Happy / Cheerful / Lively Tone:
    # Requires dynamic pitch variation + elevated pitch + healthy energy + bright timbre
    is_happy = (
        (pitch_hz > 195 and pitch_std > 30.0 and voiced_rms > 0.040 and spectral_centroid > 1850) or
        (pitch_hz > 230 and voiced_rms > 0.035 and spectral_centroid > 2000)
    )
    
    if is_angry:
        confidence = min(0.95, 0.70 + (overall_rms / 0.30) * 0.25)
        return {
            "emotion": "angry",
            "confidence": round(confidence, 2),
            "pitch_hz": round(pitch_hz, 1),
            "pitch_variance": round(pitch_std, 1),
            "rms": round(overall_rms, 4),
            "spectral_centroid_hz": round(spectral_centroid, 1),
            "tone_description": "Nada suara marah / kesal / tegas (Intensitas Tinggi, Frekuensi Tajam)"
        }
    elif is_sad:
        confidence = min(0.92, 0.70 + (1.0 - (overall_rms / 0.03)) * 0.22)
        return {
            "emotion": "sad",
            "confidence": round(confidence, 2),
            "pitch_hz": round(pitch_hz, 1),
            "pitch_variance": round(pitch_std, 1),
            "rms": round(overall_rms, 4),
            "spectral_centroid_hz": round(spectral_centroid, 1),
            "tone_description": "Nada suara sedih / lemas / pelan (Energi Sangat Lemah, Intonasi Datar)"
        }
    elif is_happy:
        confidence = min(0.92, 0.72 + (pitch_std / 50.0) * 0.20)
        return {
            "emotion": "happy",
            "confidence": round(confidence, 2),
            "pitch_hz": round(pitch_hz, 1),
            "pitch_variance": round(pitch_std, 1),
            "rms": round(overall_rms, 4),
            "spectral_centroid_hz": round(spectral_centroid, 1),
            "tone_description": "Nada suara ceria / antusias (Pitch Tinggi Melodis)"
        }
    else:
        # Default Natural Conversation
        confidence = 0.85
        return {
            "emotion": "neutral",
            "confidence": confidence,
            "pitch_hz": round(pitch_hz, 1),
            "pitch_variance": round(pitch_std, 1),
            "rms": round(overall_rms, 4),
            "spectral_centroid_hz": round(spectral_centroid, 1),
            "tone_description": "Nada suara santai / percakapan netral"
        }


class AcousticSERTracker:
    """
    Real-time streaming Speech Emotion Recognition (SER) buffer tracker.
    Maintains a rolling acoustic window with Exponential Moving Average (EMA)
    and hysteresis debouncing to prevent sudden flickering during speech.
    """

    def __init__(self, sample_rate: int = 16000, window_duration_sec: float = 1.2):
        self.sample_rate = sample_rate
        self.max_bytes = int(window_duration_sec * sample_rate * 2)  # 16-bit PCM = 2 bytes/sample
        self._buffer = bytearray()
        self._current_emotion = "neutral"
        self._consecutive_count = 0
        self._last_result: Optional[dict] = None

    def reset(self):
        """Resets buffer and state between speech turns."""
        self._buffer.clear()
        self._current_emotion = "neutral"
        self._consecutive_count = 0
        self._last_result = None

    def push_chunk(self, raw_bytes: bytes) -> Optional[dict]:
        """
        Pushes a new audio chunk into the sliding window and computes
        smoothed acoustic emotion recognition in real-time.
        Returns result dict if valid speech is detected.
        """
        if not raw_bytes:
            return None

        self._buffer.extend(raw_bytes)
        if len(self._buffer) > self.max_bytes:
            self._buffer = self._buffer[-self.max_bytes:]

        # Need at least 300ms of audio in the buffer to analyze accurately
        if len(self._buffer) < int(0.30 * self.sample_rate * 2):
            return None

        # Analyze current window
        raw_res = analyze_speech_emotion(bytes(self._buffer), self.sample_rate)
        candidate_emotion = raw_res["emotion"]

        # Hysteresis & Debouncing:
        # Switching away from neutral to emotional (angry/sad/happy) requires at least 2 consistent frames
        if candidate_emotion == self._current_emotion:
            self._consecutive_count += 1
        else:
            if candidate_emotion == "neutral":
                # Quick return to neutral
                self._current_emotion = "neutral"
                self._consecutive_count = 1
            else:
                self._consecutive_count += 1
                # Require 2 frames to confirm an emotional shift
                if self._consecutive_count >= 2:
                    self._current_emotion = candidate_emotion
                    self._consecutive_count = 0

        raw_res["emotion"] = self._current_emotion
        self._last_result = raw_res
        return raw_res


# ── Acoustic Noise & STT Hallucination Filter ──
STT_HALLUCINATED_PHRASES = (
    "terima kasih", "terima kasih telah menonton", "subtitle by", "subtitles by",
    "diedit oleh", "diterjemahkan oleh", "like and subscribe", "sampai jumpa",
    "menonton video ini", "link di deskripsi", "jangan lupa like", "di video kali ini",
    "halo semuanya", "hai teman-teman", "selamat datang kembali", "bye bye", "dadah",
    "amara", "kamara", "samara", "tamara"
)


def is_stt_hallucination(text: str) -> bool:
    """Returns True if the transcribed text is an acoustic noise artifact or empty hallucination."""
    clean = (text or "").strip().lower()
    if not clean or len(clean) < 2:
        return True
    return any(phrase in clean for phrase in STT_HALLUCINATED_PHRASES)


async def transcribe_audio_file(audio_path: str) -> Optional[str]:
    """
    Dynamic Tiered Audio Transcription Engine (Hermes Parity):
    Tier 1: Directly probes user's active provider (e.g. 9router with input_audio, OpenAI multimodal, etc.).
    Tier 2: Discovers secondary configured audio providers in SQLite (Google AI Studio gemini-3.6-flash, etc.).
    Tier 3: Graceful fallback without hardcoding or unhandled exceptions.
    """
    import os
    import base64
    import json
    import logging
    import httpx
    _log = logging.getLogger(__name__)

    if not audio_path or not os.path.isfile(audio_path):
        return None

    ext = os.path.splitext(audio_path)[1].lower()
    clean_fmt = ext.lstrip(".") or "ogg"

    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    # ── TIER 1: User's Active Provider Probe (Dynamic & Zero-Hardcode) ──
    try:
        from providers.accounts import get_active_model_id
        from memory import memory_engine
        active_m = get_active_model_id()
        custom_providers = memory_engine.get_custom_providers()

        for cp in custom_providers:
            prefix = cp.get("prefix", "")
            if prefix and active_m.startswith(f"{prefix}/"):
                target_model = active_m.replace(f"{prefix}/", "")
                base_url = cp.get("base_url", "").rstrip("/")
                api_key = cp.get("api_key", "")
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                payload = {
                    "model": target_model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Transkripsikan isi ucapan dalam audio ini secara persis kata per kata. Tuliskan teks ucapannya saja tanpa awalan atau akhiran."},
                            {"type": "input_audio", "input_audio": {"data": audio_b64, "format": clean_fmt}}
                        ]
                    }],
                    "max_tokens": 120,
                    "temperature": 0.0,
                    "stream": False
                }

                async with httpx.AsyncClient(timeout=25.0) as client:
                    resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        raw_body = resp.text.strip()
                        extracted = ""
                        if raw_body.startswith("data:"):
                            chunks = []
                            for line in raw_body.splitlines():
                                if line.startswith("data:") and "[DONE]" not in line:
                                    try:
                                        j = json.loads(line[5:].strip())
                                        d = j.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                        if d:
                                            chunks.append(d)
                                    except Exception:
                                        pass
                            extracted = "".join(chunks).strip()
                        else:
                            try:
                                j = resp.json()
                                extracted = j.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                            except Exception:
                                pass

                        if extracted and not is_stt_hallucination(extracted):
                            _log.info(f"[AudioSTT] Successfully transcribed via active provider '{prefix}' ({target_model}): '{extracted}'")
                            return extracted
    except Exception as e_t1:
        _log.debug(f"[AudioSTT] Tier 1 active provider probe notice: {e_t1}")

    # ── TIER 2: Secondary Configured Providers (Google GenAI Gemini 3.6 Flash Fallback) ──
    try:
        from core import key_manager
        from google.genai import types

        mime_map = {".ogg": "audio/ogg", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4"}
        mime = mime_map.get(ext, "audio/ogg")

        async def _transcribe_call(client: Any) -> str:
            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime)
            prompt = "Transkripsikan isi rekaman suara ini secara akurat kata per kata dalam teks. Keluarkan hanya teks hasil transkripsi ucapan."
            for m_candidate in ["gemini-3.6-flash", "gemini-3.0-flash", "gemini-2.5-flash"]:
                try:
                    response = await client.aio.models.generate_content(
                        model=m_candidate,
                        contents=[audio_part, prompt],
                        config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=256)
                    )
                    if response and response.text:
                        return response.text
                except Exception as m_err:
                    _log.debug(f"[AudioSTT] Candidate '{m_candidate}' tried: {m_err}")
            return ""

        text = await key_manager.execute_with_failover(_transcribe_call)
        clean = text.strip() if text else ""
        if clean and not is_stt_hallucination(clean):
            _log.info(f"[AudioSTT] Successfully transcribed via Google GenAI key pool: '{clean}'")
            return clean
    except Exception as e_t2:
        _log.debug(f"[AudioSTT] Tier 2 Google GenAI fallback notice: {e_t2}")

    return None


def filter_tts_speech_text(text: str) -> str:
    """
    Cleans text intended for Text-to-Speech (TTS) / Gemini Live voice synthesis (Hermes Parity).
    Strips raw code blocks, file paths, URLs, markdown symbols, and technical syntax
    so that voice synthesis speaks pure conversational narration without reading out code.
    """
    if not text:
        return ""

    import re
    s = text

    # 1. Remove entire fenced code blocks (```shell ... ```)
    s = re.sub(r"```[\s\S]*?```", "", s)

    # 2. Remove inline code snippets (`...`)
    s = re.sub(r"`[^`]*`", "", s)

    # 3. Remove HTML tags
    s = re.sub(r"<[^>]+>", "", s)

    # 4. Remove URLs
    s = re.sub(r"https?://\S+", "", s)

    # 5. Remove long file paths (e.g. C:/Users/... or /home/...)
    s = re.sub(r"[A-Za-z]:[\\/][^\s,]+", "berkas terkait", s)
    s = re.sub(r"/(?:[a-zA-Z0-9_\-]+/)+[a-zA-Z0-9_\-\.]+", "berkas terkait", s)

    # 6. Remove markdown formatting markers (*, #, _, ~, [ ])
    s = re.sub(r"[*_~#]", "", s)
    s = re.sub(r"\[[ xX]\]", "", s)
    s = re.sub(r"^[ \t]*[-•][ \t]*", "", s, flags=re.MULTILINE)

    # 7. Normalize excess whitespace and line breaks
    s = re.sub(r"\n+", ". ", s)
    s = re.sub(r"\s+", " ", s).strip()

    if not s or len(s) < 3:
        return "Tindakan teknis telah selesai diproses."

    return s


async def synthesize_speech_audio(
    text: str,
    output_path: Optional[str] = None,
    voice: str = "id-ID-GadisNeural"
) -> Optional[str]:
    """
    Synthesizes conversational text into high-quality audio file for Telegram voice notes,
    WhatsApp PTT, Discord, and Slack (Hermes Parity).
    Uses Edge-TTS Neural Voice (free, natural Indonesian) with automatic failover.
    """
    clean = filter_tts_speech_text(text)
    if not clean or len(clean) < 2:
        return None

    import os
    import uuid
    from pathlib import Path
    from constants import get_anara_cache_dir

    if not output_path:
        cache_dir = get_anara_cache_dir("voice_notes")
        cache_dir.mkdir(parents=True, exist_ok=True)
        out_f = cache_dir / f"anara_voice_{uuid.uuid4().hex[:8]}.mp3"
        target_path = str(out_f)
    else:
        target_path = os.path.abspath(os.path.expanduser(output_path))
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

    # 1. Edge-TTS Primary Synthesizer
    try:
        import edge_tts
        communicate = edge_tts.Communicate(clean, voice)
        await communicate.save(target_path)
        if os.path.isfile(target_path) and os.path.getsize(target_path) > 500:
            return target_path
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"[TTS] Edge-TTS error: {e}")

    # 2. Google GenAI / Gemini Speech Synthesizer Failover
    try:
        from core import key_manager
        client = key_manager.get_client()
        if client:
            from google.genai import types
            audio_resp = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"Ucapkan kalimat ini secara alami dalam bahasa Indonesia: {clean}",
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
                        )
                    )
                )
            )
            for part in audio_resp.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    with open(target_path, "wb") as fh:
                        fh.write(part.inline_data.data)
                    return target_path
    except Exception as e_genai:
        import logging
        logging.getLogger(__name__).debug(f"[TTS] Google Audio failover notice: {e_genai}")

    return None




