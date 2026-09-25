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
    Dynamically determines the vision model following Model Sovereignty (Hermes Parity):
    1. Reads user-configured model from config.yaml (model.vision).
    2. Uses the user's actively selected chat model directly.
    Zero static hardcoding to arbitrary models.
    """
    try:
        from config import cfg_get
        from providers.accounts import get_active_model_id

        configured = cfg_get("model.vision")
        if configured and str(configured).strip():
            return str(configured).strip()

        active = get_active_model_id()
        if active and str(active).strip():
            return str(active).strip()
    except Exception as e:
        logger.debug(f"[VisionTools] Dynamic model resolution note: {e}")

    from providers.accounts import get_active_model_id
    return get_active_model_id() or "gpt-4o"


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
    Deep visual analysis of images or photos from local file paths on PC or internet URLs.
    Capable of reading text (OCR), detecting errors in screenshots, architecture diagrams, faces, and objects.
    :param image_path: Local image file path on computer (e.g. 'C:/Users/.../photo.jpg') or http/https URL.
    :param question: Specific question or visual analysis focus (optional).
    """
    clean_target = (image_path or "").strip().strip('"\'')
    if not clean_target:
        return {"status": "error", "message": "Image path or URL cannot be empty."}

    user_query = (question or "").strip() or "Describe the contents of this image in detail, explaining text, objects, context, and key elements."

    _emit_agent_event("agent_action_start", {
        "tool_name": "vision_analyze",
        "action_title": "Analyzing Image",
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
                    return {"status": "error", "message": f"Failed to download image from URL: HTTP {res.status_code}"}
        except Exception as e:
            return {"status": "error", "message": f"Connection failed while downloading image: {e}"}
    else:
        norm_path = os.path.abspath(os.path.expanduser(clean_target))
        if not os.path.isfile(norm_path):
            return {"status": "error", "message": f"Image file not found on disk: {clean_target}"}
        try:
            with open(norm_path, "rb") as f:
                img_bytes = f.read()
            mime_type = _resolve_mime_type(norm_path)
        except Exception as e:
            return {"status": "error", "message": f"Failed to read image file: {e}"}

    if not img_bytes:
        return {"status": "error", "message": "Image data is empty."}

    # 2. Check if active/configured vision model is from a Custom Provider (e.g. 9Router, OpenRouter)
    v_model = _resolve_vision_model()
    try:
        from memory import memory_engine
        custom_nodes = memory_engine.get_custom_providers()
        for c_node in custom_nodes:
            c_prefix = c_node.get("prefix", "")
            if c_prefix and v_model.startswith(f"{c_prefix}/"):
                target_model = v_model.replace(f"{c_prefix}/", "")
                base_url = (c_node.get("base_url") or "").rstrip("/")
                api_key = c_node.get("api_key") or ""
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                b64_str = base64.b64encode(img_bytes).decode("ascii")
                data_url = f"data:{mime_type};base64,{b64_str}"
                payload = {
                    "model": target_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": user_query},
                                {"type": "image_url", "image_url": {"url": data_url}}
                            ]
                        }
                    ],
                    "max_tokens": 2048,
                    "stream": False
                }
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        analysis_text = ""
                        # Dual Parser: Handle both standard JSON object and SSE line stream
                        try:
                            d = resp.json()
                            if isinstance(d, dict) and d.get("choices"):
                                c0 = d["choices"][0]
                                analysis_text = (c0.get("message") or {}).get("content") or (c0.get("delta") or {}).get("content") or ""
                        except Exception:
                            pass

                        if not analysis_text:
                            # Stream reconstruction fallback
                            stream_parts = []
                            for line in resp.text.splitlines():
                                line_str = line.strip()
                                if line_str.startswith("data:"):
                                    d_raw = line_str[5:].strip()
                                    if d_raw == "[DONE]":
                                        break
                                    try:
                                        chunk = json.loads(d_raw)
                                        choices = chunk.get("choices") or []
                                        if choices:
                                            delta = (choices[0].get("delta") or {}).get("content") or (choices[0].get("message") or {}).get("content") or ""
                                            if delta:
                                                stream_parts.append(delta)
                                    except Exception:
                                        continue
                            if stream_parts:
                                analysis_text = "".join(stream_parts).strip()

                        if analysis_text:
                            _emit_agent_event("agent_action_complete", {
                                "tool_name": "vision_analyze",
                                "action_title": "Visual Analysis Complete",
                                "summary": analysis_text[:120] + "...",
                                "icon": "eye"
                            })
                            return {
                                "status": "success",
                                "image_target": clean_target,
                                "mime_type": mime_type,
                                "question": user_query,
                                "analysis": analysis_text,
                                "provider": c_prefix,
                                "model": target_model
                            }
    except Exception as c_err:
        logger.warning(f"[VisionTools] Custom provider vision check note: {c_err}")

    # 3. Multimodal Analysis via Primary Engine (Google GenAI)
    try:
        from core import key_manager
        from google.genai import types

        async def _analyze_with_gemini(client: Any) -> str:
            image_part = types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
            from core.prompt_loader import load_prompt
            prompt = load_prompt("vision/image_analysis", user_query=user_query)
            # Ensure model name sent to Google GenAI SDK does not contain foreign provider prefixes
            clean_g_model = v_model.split("/")[-1] if ("/" in v_model and not v_model.startswith("models/")) else v_model
            if not clean_g_model.startswith("gemini"):
                clean_g_model = "gemini-2.5-flash"
            response = await client.aio.models.generate_content(
                model=clean_g_model,
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=2048)
            )
            return response.text or ""

        analysis_text = await key_manager.execute_with_failover(_analyze_with_gemini)

        _emit_agent_event("agent_action_complete", {
            "tool_name": "vision_analyze",
            "action_title": "Visual Analysis Complete",
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
        "message": "Failed to analyze image via active vision provider. Ensure valid API key is configured."
    }


async def _tool_video_analyze(
    video_path: str,
    question: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyzes local video files (.mp4, .webm, .mov) on host machine.
    Extracts visual information, scene dynamics, text, and answers questions regarding video content.
    """
    clean_target = (video_path or "").strip().strip('"\'')
    if not clean_target:
        return {"status": "error", "message": "Video path cannot be empty."}

    norm_path = os.path.abspath(os.path.expanduser(clean_target))
    if not os.path.isfile(norm_path):
        return {"status": "error", "message": f"Video file not found on disk: {clean_target}"}

    file_size_mb = os.path.getsize(norm_path) / (1024 * 1024)
    if file_size_mb > 50.0:
        return {"status": "error", "message": f"Video size ({file_size_mb:.1f} MB) exceeds maximum 50 MB limit."}

    user_query = (question or "").strip() or "Provide a chronological analysis of the scenes, events, and visual details in this video."

    _emit_agent_event("agent_action_start", {
        "tool_name": "video_analyze",
        "action_title": "Analyzing Video File",
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
            from core.prompt_loader import load_prompt
            prompt = load_prompt("vision/video_analysis", user_query=user_query)
            v_model = _resolve_vision_model()
            clean_v_model = v_model.split("/")[-1] if ("/" in v_model and not v_model.startswith("models/")) else v_model
            if not clean_v_model.startswith("gemini"):
                clean_v_model = "gemini-2.5-flash"
            response = await client.aio.models.generate_content(
                model=clean_v_model,
                contents=[video_part, prompt],
                config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=2048)
            )
            return response.text or "No video analysis results returned."

        analysis_text = await key_manager.execute_with_failover(_analyze_video)

        _emit_agent_event("agent_action_complete", {
            "tool_name": "video_analyze",
            "action_title": "Video Analysis Complete",
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
        return {"status": "error", "message": f"Failed to analyze video: {str(e)}"}
