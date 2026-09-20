"""
image_tools.py — Creative Image Generation Engine for Project Anara.
Parity with Anara Agent image_generate: supports high-speed creative visual generation
via free Pollinations.ai Flux endpoint (zero API key needed) and OpenAI DALL-E 3 fallback.
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

STAGING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "staging", "images")
os.makedirs(STAGING_DIR, exist_ok=True)


async def _tool_image_generate(
    prompt: str,
    aspect_ratio: str = "1:1",
    style: Optional[str] = None,
    save_to_disk: bool = True
) -> Dict[str, Any]:
    """
    Generates a creative digital image from a descriptive prompt.
    aspect_ratio: '1:1' (square), '16:9' (landscape), '9:16' (portrait), '4:3'
    style: optional style hint like 'photorealistic', 'anime', 'digital-art', 'cyberpunk', 'cinematic'
    """
    clean_prompt = (prompt or "").strip()
    if not clean_prompt:
        return {"status": "error", "message": "Prompt pembuatan gambar tidak boleh kosong."}

    full_prompt = clean_prompt
    if style:
        full_prompt = f"{clean_prompt}, in {style} style, masterpiece, 8k resolution, highly detailed"

    _emit_agent_event("agent_action_start", {
        "tool_name": "image_generate",
        "action_title": "Membuat Gambar Digital",
        "detail": f"Prompt: '{clean_prompt[:60]}...'",
        "icon": "image"
    })

    # Aspect ratio mapping to width & height
    ratio_map = {
        "1:1": (1024, 1024),
        "16:9": (1280, 720),
        "9:16": (720, 1280),
        "4:3": (1024, 768),
        "3:4": (768, 1024)
    }
    width, height = ratio_map.get(aspect_ratio, (1024, 1024))

    # Check for OpenAI API key for DALL-E 3
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            url = "https://api.openai.com/v1/images/generations"
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            payload = {
                "model": "dall-e-3",
                "prompt": full_prompt,
                "n": 1,
                "size": "1024x1024" if aspect_ratio == "1:1" else ("1792x1024" if "16:9" in aspect_ratio else "1024x1792")
            }
            async with httpx.AsyncClient(timeout=45.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    d = res.json()
                    img_url = d["data"][0]["url"]
                    local_filename = f"img_{int(time.time())}_{hashlib.md5(full_prompt.encode()).hexdigest()[:8]}.png"
                    local_path = os.path.join(STAGING_DIR, local_filename)

                    # Download local copy if requested
                    if save_to_disk:
                        dl = await client.get(img_url)
                        if dl.status_code == 200:
                            with open(local_path, "wb") as f:
                                f.write(dl.content)

                    # Project HUD card
                    _emit_agent_event("hud_project", {
                        "type": "image",
                        "title": f"AI Image: {clean_prompt[:40]}",
                        "image_url": img_url,
                        "local_path": local_path if save_to_disk else None,
                        "aspect_ratio": aspect_ratio
                    })

                    return {
                        "status": "success",
                        "provider": "openai-dall-e-3",
                        "image_url": img_url,
                        "local_file": local_path if save_to_disk else None,
                        "prompt": full_prompt,
                        "message": "Image generated successfully via DALL-E 3 and projected to HUD."
                    }
        except Exception as e:
            logger.warning(f"[ImageTools] OpenAI DALL-E generation failed, falling back to Pollinations: {e}")

    # Fallback to Pollinations.ai (Flux engine, ultra high quality, free & fast)
    encoded_prompt = urllib.parse.quote(full_prompt)
    seed = int(time.time() * 1000) % 999999
    pollinations_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&model=flux&seed={seed}&nologo=true&enhance=true"

    local_filename = f"img_flux_{int(time.time())}_{hashlib.md5(full_prompt.encode()).hexdigest()[:8]}.jpg"
    local_path = os.path.join(STAGING_DIR, local_filename)

    if save_to_disk:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(pollinations_url)
                if resp.status_code == 200:
                    with open(local_path, "wb") as f:
                        f.write(resp.content)
        except Exception as err:
            logger.warning(f"[ImageTools] Download failed, returning direct URL: {err}")

    # Project HUD visual
    _emit_agent_event("hud_project", {
        "type": "image",
        "title": f"AI Image: {clean_prompt[:40]}",
        "image_url": pollinations_url,
        "local_path": local_path if os.path.isfile(local_path) else None,
        "aspect_ratio": aspect_ratio
    })

    return {
        "status": "success",
        "provider": "pollinations-flux",
        "image_url": pollinations_url,
        "local_file": local_path if os.path.isfile(local_path) else None,
        "prompt": full_prompt,
        "aspect_ratio": aspect_ratio,
        "message": f"Image generated successfully via Pollinations Flux and projected to HUD: {pollinations_url}"
    }
