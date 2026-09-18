"""
vision_tools.py — Autonomous Multimodal Vision & Video Analysis for Project Anara.
Anara Standard Vision & Video Understanding Engine:
1. Inspects, describes, and reasons over visual images (screenshots, diagrams, photos, OCR)
   from either local PC disk paths or web URLs.
2. Analyzes video recordings (.mp4, .webm, .mov) with scene understanding and question answering.
3. Automatically integrates with Gemini Vision and OpenAI/Claude multimodal backends.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, Optional
import httpx

from .events import _emit_agent_event

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
SUPPORTED_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv", ".avi"}


def _resolve_vision_model() -> str:
    """
    Dynamically determines the best vision model without static hardcoding:
    1. Reads user-configured model from config.yaml (model.vision).
    2. Checks if active model supports vision via ModelCapabilityRegistry.
    3. Gracefully falls back to primary multimodal engine model.
    """
    try:
        from config import cfg_get
        from core.capabilities import ModelCapabilityRegistry
        from providers.accounts import get_active_model_id

        configured = cfg_get("model.vision")
        if configured and str(configured).strip():
            return str(configured).strip()

        active = get_active_model_id()
        if active and ModelCapabilityRegistry.supports_vision(active):
            clean_mid = active.replace("models/", "")
            if "live-preview" not in clean_mid:
                return clean_mid

        if "gemini" in (active or "").lower():
            return "gemini-2.5-flash"
    except Exception as e:
        logger.debug(f"[VisionTools] Dynamic model resolution note: {e}")

    return "gemini-2.5-flash"


def _resolve_fallback_vision_model() -> str:
    """Dynamically resolves fallback multimodal model for OpenAI/Claude/OpenRouter."""
    try:
        from config import cfg_get
        configured = cfg_get("model.vision_fallback")
        if configured and str(configured).strip():
            return str(configured).strip()
    except Exception:
        pass
    return "gpt-4o-mini"


def _resolve_mime_type(file_path: str, is_video: bool = False) -> str:
    """Infers MIME type from file extension."""
    mime, _ = mimetypes.guess_type(file_path)
    if mime:
        return mime
    ext = os.path.splitext(file_path)[1].lower()
    if not is_video:
        if ext in (".jpg", ".jpeg"):
            return "image/jpeg"
        elif ext == ".png":
            return "image/png"
        elif ext == ".webp":
            return "image/webp"
        return "image/jpeg"
    else:
        if ext == ".mp4":
            return "video/mp4"
        elif ext == ".webm":
            return "video/webm"
        elif ext == ".mov":
            return "video/quicktime"
        return "video/mp4"


async def _tool_vision_analyze(
    image_path: str,
    question: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analisis visual mendalam terhadap gambar atau foto dari path berkas lokal di PC atau URL internet.
    Mampu membaca teks (OCR), mendeteksi error pada tangkapan layar, bagan arsitektur, wajah, dan objek.
    :param image_path: Path lokal berkas gambar di komputer (contoh: 'C:/Users/.../foto.jpg') atau URL http/https.
    :param question: Pertanyaan spesifik atau fokus analisis visual (opsional).
    """
    clean_target = (image_path or "").strip().strip('"\'')
    if not clean_target:
        return {"status": "error", "message": "Path gambar atau URL tidak boleh kosong."}

    user_query = (question or "").strip() or "Deskripsikan isi gambar ini secara detail dan jelaskan teks, objek, konteks, serta elemen penting di dalamnya."

    _emit_agent_event("agent_action_start", {
        "tool_name": "vision_analyze",
        "action_title": "Menganalisis Gambar / Foto",
        "detail": f"Target: {os.path.basename(clean_target)}",
        "icon": "eye"
    })

    img_bytes: Optional[bytes] = None
    mime_type = "image/jpeg"

    # 1. Fetch from HTTP URL or Read from local disk
    if clean_target.startswith(("http://", "https://")):
        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                res = await client.get(clean_target)
                if res.status_code == 200:
                    img_bytes = res.content
                    mime_type = res.headers.get("content-type") or _resolve_mime_type(clean_target)
                else:
                    return {"status": "error", "message": f"Gagal mengunduh gambar dari URL: HTTP {res.status_code}"}
        except Exception as e:
            return {"status": "error", "message": f"Koneksi gagal saat mengunduh gambar: {e}"}
    else:
        norm_path = os.path.abspath(os.path.expanduser(clean_target))
        if not os.path.isfile(norm_path):
            return {"status": "error", "message": f"Berkas gambar tidak ditemukan di sistem: {clean_target}"}
        try:
            with open(norm_path, "rb") as f:
                img_bytes = f.read()
            mime_type = _resolve_mime_type(norm_path)
        except Exception as e:
            return {"status": "error", "message": f"Gagal membaca berkas gambar: {e}"}

    if not img_bytes:
        return {"status": "error", "message": "Data gambar kosong."}

    # 2. Multimodal Analysis via Primary Engine (Google GenAI)
    try:
        from core import key_manager
        from google.genai import types

        async def _analyze_with_gemini(client: Any) -> str:
            image_part = types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
            prompt = (
                f"Kamu adalah modul penglihatan visual (Vision Engine) Project Anara.\n"
                f"Tugas: {user_query}\n"
                "Analisis gambar berikut secara cermat, akurat, dan jelas. Berikan jawaban komprehensif."
            )
            v_model = _resolve_vision_model()
            response = await client.aio.models.generate_content(
                model=v_model,
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=2048)
            )
            return response.text or "Tidak ada teks yang dapat dideskripsikan."

        analysis_text = await key_manager.execute_with_failover(_analyze_with_gemini)

        _emit_agent_event("agent_action_complete", {
            "tool_name": "vision_analyze",
            "action_title": "Analisis Visual Selesai",
            "summary": analysis_text[:120] + "...",
            "icon": "eye"
        })

        return {
            "status": "success",
            "image_target": clean_target,
            "mime_type": mime_type,
            "question": user_query,
            "analysis": analysis_text
        }
    except Exception as e:
        logger.warning(f"[VisionTools] Gemini multimodal failed, attempting auxiliary fallback: {e}")

    # 3. Fallback to OpenAI / Claude base64 multimodal API
    try:
        from providers.accounts import get_provider_key
        api_key = get_provider_key("openai") or get_provider_key("codex") or os.getenv("OPENAI_API_KEY")
        if api_key:
            b64_str = base64.b64encode(img_bytes).decode("ascii")
            data_url = f"data:{mime_type};base64,{b64_str}"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            fallback_m = _resolve_fallback_vision_model()
            payload = {
                "model": fallback_m,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_query},
                            {"type": "image_url", "image_url": {"url": data_url}}
                        ]
                    }
                ],
                "max_tokens": 1500
            }
            async with httpx.AsyncClient(timeout=45.0) as client:
                res = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                if res.status_code == 200:
                    analysis_text = res.json()["choices"][0]["message"]["content"]
                    return {
                        "status": "success",
                        "image_target": clean_target,
                        "mime_type": mime_type,
                        "question": user_query,
                        "analysis": analysis_text
                    }
    except Exception as fb_err:
        logger.error(f"[VisionTools] Fallback vision error: {fb_err}")

    return {
        "status": "error",
        "message": "Gagal menganalisis gambar melalui provider vision aktif. Pastikan API Key Gemini atau OpenAI valid."
    }


async def _tool_video_analyze(
    video_path: str,
    question: Optional[str] = None
) -> Dict[str, Any]:
    """
    Menganalisis berkas rekaman video lokal (.mp4, .webm, .mov) di komputer.
    Mengekstrak informasi visual, adegan utama, teks, dan menjawab pertanyaan terkait video.
    :param video_path: Path lokal berkas video di komputer (contoh: 'C:/Users/.../video.mp4').
    :param question: Pertanyaan spesifik atau instruksi analisis video (opsional).
    """
    clean_target = (video_path or "").strip().strip('"\'')
    if not clean_target:
        return {"status": "error", "message": "Path video tidak boleh kosong."}

    norm_path = os.path.abspath(os.path.expanduser(clean_target))
    if not os.path.isfile(norm_path):
        return {"status": "error", "message": f"Berkas video tidak ditemukan di komputer: {clean_target}"}

    file_size_mb = os.path.getsize(norm_path) / (1024 * 1024)
    if file_size_mb > 50.0:
        return {"status": "error", "message": f"Ukuran video ({file_size_mb:.1f} MB) melebihi batas maksimal 50 MB."}

    user_query = (question or "").strip() or "Jelaskan ringkasan adegan, peristiwa, dan konten visual di dalam video ini secara kronologis."

    _emit_agent_event("agent_action_start", {
        "tool_name": "video_analyze",
        "action_title": "Menganalisis Berkas Video",
        "detail": f"{os.path.basename(norm_path)} ({file_size_mb:.1f} MB)",
        "icon": "video"
    })

    try:
        from core import key_manager
        from google.genai import types

        with open(norm_path, "rb") as f:
            video_bytes = f.read()

        mime_type = _resolve_mime_type(norm_path, is_video=True)

        async def _analyze_video(client: Any) -> str:
            video_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
            prompt = (
                f"Kamu adalah modul analisis video Project Anara.\n"
                f"Tugas: {user_query}\n"
                "Analisis rekaman video berikut secara objektif, detail, dan runtut."
            )
            v_model = _resolve_vision_model()
            response = await client.aio.models.generate_content(
                model=v_model,
                contents=[video_part, prompt],
                config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=2048)
            )
            return response.text or "Tidak ada hasil analisis video."

        analysis_text = await key_manager.execute_with_failover(_analyze_video)

        _emit_agent_event("agent_action_complete", {
            "tool_name": "video_analyze",
            "action_title": "Analisis Video Selesai",
            "summary": analysis_text[:120] + "...",
            "icon": "video"
        })

        return {
            "status": "success",
            "video_path": norm_path,
            "size_mb": round(file_size_mb, 2),
            "mime_type": mime_type,
            "question": user_query,
            "analysis": analysis_text
        }
    except Exception as e:
        logger.error(f"[VisionTools] Video analysis error: {e}")
        return {"status": "error", "message": f"Gagal menganalisis video: {str(e)}"}
