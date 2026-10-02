"""
voice_tools.py — Voice Biometrics & Speaker Identification Tools for Project Anara.
Allows Anara to identify who is speaking, list enrolled speaker profiles,
and enroll/calibrate user voiceprints into SQLite memory.
"""

import asyncio
import base64
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .events import _emit_agent_event

logger = logging.getLogger(__name__)


async def _tool_voice_biometrics_manage(
    action: str,
    speaker_name: Optional[str] = None,
    audio_file_path: Optional[str] = None,
    audio_base64: Optional[str] = None
) -> Dict[str, Any]:
    """
    Manages voice biometrics and speaker recognition.
    action: 'list' (list enrolled speakers), 'identify' (match voice to speaker), 'enroll' (save voiceprint)
    speaker_name: name of the person (required for 'enroll')
    audio_file_path: local path to WAV/PCM audio sample file
    audio_base64: raw PCM16/WAV audio data in base64 string
    """
    from memory import memory_engine

    act = (action or "list").strip().lower()

    _emit_agent_event("agent_action_start", {
        "tool_name": "voice_biometrics_manage",
        "action_title": f"Voice Biometrics ({act.upper()})",
        "detail": f"Speaker: {speaker_name or 'N/A'}",
        "icon": "mic"
    })

    if act == "list":
        speakers = await asyncio.to_thread(memory_engine.get_all_speakers) if hasattr(memory_engine, "get_all_speakers") else []
        summary = [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "sample_count": s.get("sample_count", 1),
                "last_seen": s.get("last_seen")
            }
            for s in speakers
        ]
        last_active = await asyncio.to_thread(memory_engine.get_last_active_speaker_name) if hasattr(memory_engine, "get_last_active_speaker_name") else None
        return {
            "status": "success",
            "last_active_speaker": last_active,
            "total_speakers": len(summary),
            "speakers": summary
        }

    # Helper to resolve audio bytes safely
    audio_bytes: Optional[bytes] = None
    if audio_base64:
        try:
            audio_bytes = base64.b64decode(audio_base64.strip())
        except Exception:
            return {"status": "error", "message": "Failed to decode audio_base64."}
    elif audio_file_path:
        clean_p = audio_file_path.strip().strip("'\"")
        p = Path(clean_p).resolve()
        # Security: block sensitive repository and system files
        forbidden = {".env", "anara_brain.db", "id_rsa", "id_ed25519"}
        if p.name.lower() in forbidden or any(part.startswith(".env") for part in p.parts):
            return {"status": "error", "message": "Access to restricted file blocked."}
        if not p.is_file():
            return {"status": "error", "message": f"Audio file not found: {clean_p}"}
        try:
            def _read_file() -> bytes:
                with open(p, "rb") as f:
                    return f.read()
            audio_bytes = await asyncio.to_thread(_read_file)
        except Exception as e:
            return {"status": "error", "message": f"Failed to read audio file: {e}"}

    if act == "identify":
        if not audio_bytes:
            return {
                "status": "error",
                "message": "Parameter 'audio_file_path' or 'audio_base64' is required for speaker identification."
            }
        speaker_name = None
        conf = 0.0
        if hasattr(memory_engine, "identify_speaker"):
            name, score, _ = await asyncio.to_thread(memory_engine.identify_speaker, audio_bytes)
            if name:
                speaker_name = name
                conf = score
        elif hasattr(memory_engine, "identify_speaker_from_voice"):
            match_res = await asyncio.to_thread(getattr(memory_engine, "identify_speaker_from_voice"), audio_bytes)
            if match_res and match_res.get("identified"):
                speaker_name = match_res.get("name")
                conf = match_res.get("confidence") or 0.0

        if speaker_name:
            conf_str = f"{float(conf):.2f}" if conf is not None else "N/A"
            return {
                "status": "success",
                "identified": True,
                "speaker_name": speaker_name,
                "confidence": conf,
                "message": f"Voice identified as: {speaker_name} (confidence: {conf_str})"
            }
        return {
            "status": "warning",
            "identified": False,
            "message": "Voice print did not match any registered biometric profile."
        }

    elif act in ("enroll", "calibrate"):
        if not speaker_name:
            return {"status": "error", "message": "Parameter 'speaker_name' is required for voice enrollment."}
        res = await asyncio.to_thread(memory_engine.enroll_or_update_speaker, speaker_name, audio_pcm=audio_bytes) if hasattr(memory_engine, "enroll_or_update_speaker") else {}
        return {
            "status": "success",
            "speaker_name": speaker_name,
            "result": res,
            "message": f"Voice profile '{speaker_name}' registered successfully in biometrics registry."
        }

    return {
        "status": "error",
        "message": f"Unknown voice action '{act}'. Choose from: 'list', 'identify', 'enroll'."
    }


async def _tool_wake_word_manage(
    action: str = "status",
    phrase: Optional[str] = None
) -> Dict[str, Any]:
    """
    Controls hands-free background wake-word ('Hey Anara') listener.
    action: 'status' (check if listening), 'start' (begin listening), 'stop' (turn off), 'set_phrase' (change trigger phrase).
    """
    from cognition.wake_word import wake_word_detector

    act = (action or "status").strip().lower()

    _emit_agent_event("agent_action_start", {
        "tool_name": "wake_word_manage",
        "action_title": f"Wake Word ({act.upper()})",
        "detail": f"Hotword: '{wake_word_detector.phrase}'",
        "icon": "volume-2"
    })

    if act == "status":
        return {
            "status": "success",
            "is_listening": wake_word_detector.is_active(),
            "phrase": wake_word_detector.phrase,
            "sensitivity": wake_word_detector.sensitivity,
            "message": f"Wake word listener is {'active' if wake_word_detector.is_active() else 'inactive'} with phrase '{wake_word_detector.phrase}'."
        }

    elif act == "start":
        wake_word_detector.start_background_capture()
        return {
            "status": "success",
            "is_listening": True,
            "phrase": wake_word_detector.phrase,
            "message": f"Wake word listener activated. Call '{wake_word_detector.phrase}' to interact hands-free."
        }

    elif act == "stop":
        wake_word_detector.stop()
        return {
            "status": "success",
            "is_listening": False,
            "message": "Wake word listener deactivated."
        }

    elif act in ("set_phrase", "change"):
        if not phrase:
            return {"status": "error", "message": "Parameter 'phrase' is required (e.g. 'Hey Anara')."}
        wake_word_detector.set_phrase(phrase)
        return {
            "status": "success",
            "phrase": wake_word_detector.phrase,
            "message": f"Wake word trigger phrase changed to: '{wake_word_detector.phrase}'."
        }

    return {"status": "error", "message": f"Unknown action '{act}'. Choose: 'status', 'start', 'stop', 'set_phrase'."}

