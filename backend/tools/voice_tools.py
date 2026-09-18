"""
voice_tools.py — Voice Biometrics & Speaker Identification Tools for Project Anara.
Allows Anara to identify who is speaking, list enrolled speaker profiles,
and enroll/calibrate user voiceprints into SQLite memory.
"""

import base64
import logging
import os
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
        speakers = memory_engine.get_all_speakers() if hasattr(memory_engine, "get_all_speakers") else []
        summary = [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "sample_count": s.get("sample_count", 1),
                "last_seen": s.get("last_seen")
            }
            for s in speakers
        ]
        last_active = memory_engine.get_last_active_speaker_name() if hasattr(memory_engine, "get_last_active_speaker_name") else None
        return {
            "status": "success",
            "last_active_speaker": last_active,
            "total_speakers": len(summary),
            "speakers": summary
        }

    # Helper to resolve audio bytes
    audio_bytes: Optional[bytes] = None
    if audio_base64:
        try:
            audio_bytes = base64.b64decode(audio_base64.strip())
        except Exception:
            return {"status": "error", "message": "Gagal mendekode audio_base64."}
    elif audio_file_path and os.path.isfile(audio_file_path):
        try:
            with open(audio_file_path, "rb") as f:
                audio_bytes = f.read()
        except Exception as e:
            return {"status": "error", "message": f"Gagal membaca berkas audio: {e}"}

    if act == "identify":
        if not audio_bytes:
            return {
                "status": "error",
                "message": "Diperlukan parameter 'audio_file_path' atau 'audio_base64' untuk identifikasi sidik suara."
            }
        match_res = memory_engine.identify_speaker_from_voice(audio_bytes) if hasattr(memory_engine, "identify_speaker_from_voice") else None
        if match_res and match_res.get("identified"):
            conf = match_res.get("confidence")
            conf_str = f"{float(conf):.2f}" if conf is not None else "N/A"
            return {
                "status": "success",
                "identified": True,
                "speaker_name": match_res.get("name"),
                "confidence": conf,
                "message": f"Suara teridentifikasi sebagai: {match_res.get('name')} (kepercayaan: {conf_str})"
            }
        return {
            "status": "warning",
            "identified": False,
            "message": "Sidik suara tidak cocok dengan profil terdaftar yang ada."
        }

    elif act in ("enroll", "calibrate"):
        if not speaker_name:
            return {"status": "error", "message": "Parameter 'speaker_name' wajib diisi untuk pendaftaran sidik suara."}
        res = memory_engine.enroll_or_update_speaker(speaker_name, audio_pcm=audio_bytes) if hasattr(memory_engine, "enroll_or_update_speaker") else {}
        return {
            "status": "success",
            "speaker_name": speaker_name,
            "result": res,
            "message": f"Profil suara '{speaker_name}' berhasil didaftarkan/diperbarui di basis data biometrik Anara."
        }

    return {
        "status": "error",
        "message": f"Aksi '{act}' tidak dikenal. Pilih dari: 'list', 'identify', 'enroll'."
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
            "message": f"Wake word listener {'aktif' if wake_word_detector.is_active() else 'tidak aktif'} dengan kata kunci '{wake_word_detector.phrase}'."
        }

    elif act == "start":
        wake_word_detector.start_background_capture()
        return {
            "status": "success",
            "is_listening": True,
            "phrase": wake_word_detector.phrase,
            "message": f"Wake word listener diaktifkan. Panggil '{wake_word_detector.phrase}' untuk berinteraksi hands-free."
        }

    elif act == "stop":
        wake_word_detector.stop()
        return {
            "status": "success",
            "is_listening": False,
            "message": "Wake word listener dinonaktifkan."
        }

    elif act in ("set_phrase", "change"):
        if not phrase:
            return {"status": "error", "message": "Parameter 'phrase' wajib diisi (misal 'Hey Anara', 'Halo Anara')."}
        wake_word_detector.set_phrase(phrase)
        return {
            "status": "success",
            "phrase": wake_word_detector.phrase,
            "message": f"Kata kunci panggilan berhasil diubah menjadi: '{wake_word_detector.phrase}'."
        }

    return {"status": "error", "message": f"Aksi '{act}' tidak dikenal. Pilih: 'status', 'start', 'stop', 'set_phrase'."}

