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
    """Transcribes an audio file (.ogg, .mp3, .wav) using Gemini / multimodal failover."""
    import os
    import logging
    _log = logging.getLogger(__name__)

    if not audio_path or not os.path.isfile(audio_path):
        return None
    try:
        from core import key_manager
        from google.genai import types

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        ext = os.path.splitext(audio_path)[1].lower()
        mime_map = {".ogg": "audio/ogg", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4"}
        mime = mime_map.get(ext, "audio/ogg")

        async def _transcribe_call(client: Any) -> str:
            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime)
            prompt = "Transkripsikan isi rekaman suara ini secara akurat kata per kata dalam teks. Jangan tambahkan komentar atau penjelasan, cukup kembalikan teks hasil transkripsi ucapan."
            from tools.vision_tools import _resolve_vision_model
            response = await client.aio.models.generate_content(
                model=_resolve_vision_model(),
                contents=[audio_part, prompt],
                config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=1024)
            )
            return response.text or ""

        text = await key_manager.execute_with_failover(_transcribe_call)
        clean = text.strip() if text else ""
        if clean and not is_stt_hallucination(clean):
            return clean
        return clean or None
    except Exception as e:
        _log.warning(f"[AudioSTT] Audio transcription error: {e}")
        return None


