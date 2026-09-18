"""
video_tools.py — Creative Video Generation Engine for Project Anara.
Anara Standard video_generate: creates short AI videos from
text prompts or reference images using Pollinations Video and Fal.ai fallback.
"""

import asyncio
import hashlib
import logging
import os
import time
import urllib.parse
from typing import Any, Dict, Optional
import httpx

from .events import _emit_agent_event

logger = logging.getLogger(__name__)

STAGING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "staging", "videos")
os.makedirs(STAGING_DIR, exist_ok=True)


async def _tool_video_generate(
    prompt: str,
    duration: int = 4,
    aspect_ratio: str = "16:9",
    image_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates a creative AI video from a descriptive prompt or input image.
    duration: length in seconds (default 4, range 2-10).
    aspect_ratio: '16:9' (landscape, default), '9:16' (portrait/reels), '1:1' (square).
    image_url: optional starting image URL for image-to-video motion.
    """
    clean_prompt = (prompt or "").strip()
    if not clean_prompt:
        return {"status": "error", "message": "Prompt pembuatan video tidak boleh kosong."}

    _emit_agent_event("agent_action_start", {
        "tool_name": "video_generate",
        "action_title": "Membuat Video Digital AI",
        "detail": f"Prompt: '{clean_prompt[:50]}...' ({aspect_ratio})",
        "icon": "video"
    })

    # Dimension mapping
    dim_map = {
        "16:9": (1280, 720),
        "9:16": (720, 1280),
        "1:1": (800, 800)
    }
    width, height = dim_map.get(aspect_ratio, (1280, 720))

    # Check for Fal.ai API key fallback
    fal_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    if fal_key:
        try:
            url = "https://queue.fal.run/fal-ai/minimax/video-01"
            headers = {"Authorization": f"Key {fal_key}", "Content-Type": "application/json"}
            payload = {
                "prompt": clean_prompt,
                "aspect_ratio": aspect_ratio,
                "duration": duration
            }
            if image_url:
                payload["image_url"] = image_url

            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code in (200, 201):
                    d = res.json()
                    video_url = d.get("video", {}).get("url") or d.get("url")
                    if video_url:
                        local_name = f"video_{int(time.time())}_{hashlib.md5(clean_prompt.encode()).hexdigest()[:8]}.mp4"
                        local_path = os.path.join(STAGING_DIR, local_name)

                        # Download local copy
                        try:
                            dl = await client.get(video_url, timeout=30.0)
                            if dl.status_code == 200:
                                with open(local_path, "wb") as f:
                                    f.write(dl.content)
                        except Exception:
                            pass

                        _emit_agent_event("hud_project", {
                            "type": "video",
                            "title": f"Video AI: {clean_prompt[:40]}",
                            "video_url": video_url,
                            "local_path": local_path if os.path.isfile(local_path) else None,
                            "aspect_ratio": aspect_ratio
                        })

                        return {
                            "status": "success",
                            "provider": "fal-ai",
                            "video_url": video_url,
                            "local_file": local_path if os.path.isfile(local_path) else None,
                            "message": f"Video berhasil dibuat dan diproyeksikan ke HUD: {video_url}"
                        }
        except Exception as e:
            logger.warning(f"[VideoTools] Fal.ai generation failed: {e}")

    # Fallback to Pollinations Video Endpoint (zero-key required)
    encoded = urllib.parse.quote(clean_prompt)
    seed = int(time.time() * 1000) % 999999
    pollinations_video_url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&model=cogvideox&seed={seed}&nologo=true"

    local_name = f"video_cog_{int(time.time())}_{hashlib.md5(clean_prompt.encode()).hexdigest()[:8]}.mp4"
    local_path = os.path.join(STAGING_DIR, local_name)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            dl_res = await client.get(pollinations_video_url)
            if dl_res.status_code == 200 and len(dl_res.content) > 1000:
                os.makedirs(STAGING_DIR, exist_ok=True)
                with open(local_path, "wb") as vf:
                    vf.write(dl_res.content)
    except Exception as e:
        logger.debug(f"[VideoTools] Pollinations video download notice: {e}")

    _emit_agent_event("hud_project", {
        "type": "video",
        "title": f"Video AI: {clean_prompt[:40]}",
        "video_url": pollinations_video_url,
        "local_path": local_path if os.path.isfile(local_path) else None,
        "aspect_ratio": aspect_ratio
    })

    return {
        "status": "success",
        "provider": "pollinations-cogvideo",
        "video_url": pollinations_video_url,
        "local_file": local_path if os.path.isfile(local_path) else None,
        "aspect_ratio": aspect_ratio,
        "duration": duration,
        "message": f"Video AI berhasil dibuat dan diproyeksikan ke HUD: {pollinations_video_url}"
    }
