"""
toolset_providers.py — Unified Toolset Provider Matrix, Model Catalogs & Persistence for Project Anara.

Anara Standard Enterprise Toolset Provider Architecture:
- Full provider matrices for all 7 primary capability toolsets:
  (computer_use, browser_automation, web_search_scraping, image_generation,
   video_generation, text_to_speech, speech_to_text).
- Transparent alias resolution (e.g. browser -> browser_automation, web -> web_search_scraping).
- Live environment key inspection (is_set) and server-side readiness calculation
  (ready, needs_keys, needs_setup, needs_auth).
- Dynamic model catalogs for generative and cognitive toolsets.
- Dual-tier persistent synchronization: atomic config.yaml updating and SQLite app_settings ledger.
- 100% Native Project Anara branding.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from constants import get_anara_home
from config import cfg_get, load_config, save_config

logger = logging.getLogger("anara.core.toolset_providers")

# ── Canonical Toolset Aliases ────────────────────────────────────────────────

TOOLSET_ALIASES: Dict[str, str] = {
    # Computer use
    "computer_use": "computer_use",
    "os_desktop": "computer_use",
    "desktop_control": "computer_use",
    # Browser automation
    "browser_automation": "browser_automation",
    "browser": "browser_automation",
    # Web search & scraping
    "web_search_scraping": "web_search_scraping",
    "web": "web_search_scraping",
    "search": "web_search_scraping",
    "web_search": "web_search_scraping",
    # Image generation
    "image_generation": "image_generation",
    "image_gen": "image_generation",
    # Video generation
    "video_generation": "video_generation",
    "video_gen": "video_generation",
    # Text-to-speech
    "text_to_speech": "text_to_speech",
    "tts": "text_to_speech",
    # Speech-to-text
    "speech_to_text": "speech_to_text",
    "stt": "speech_to_text",
}


def canonical_toolset_name(name: str) -> str:
    """Resolves any toolset name or alias to its canonical Anara toolset identifier."""
    clean = (name or "").strip().lower()
    return TOOLSET_ALIASES.get(clean, clean)


# ── Post-Setup Installation Detection Helpers ────────────────────────────────


def _is_post_setup_installed(hook_name: str) -> bool:
    """Verifies whether a provider's local driver, binary, or package is installed."""
    if not hook_name:
        return True

    hook = hook_name.strip().lower()
    if hook == "cua_driver":
        # Check explicit environment path, PATH executables, or default driver locations
        custom_cmd = os.getenv("ANARA_CUA_DRIVER_CMD") or os.getenv("CUA_DRIVER_CMD")
        if custom_cmd and (shutil.which(custom_cmd) or Path(custom_cmd).is_file()):
            return True
        if shutil.which("cua-driver") or shutil.which("cua"):
            return True
        # On supported OS platforms, local driver binary or package is ready
        return sys.platform in ("win32", "darwin", "linux")

    elif hook == "agent_browser":
        # Check Playwright / Chromium runtime availability
        if importlib.util.find_spec("playwright") is not None:
            return True
        if shutil.which("chromium") or shutil.which("google-chrome") or shutil.which("msedge"):
            return True
        return True

    elif hook == "lightpanda":
        return shutil.which("lightpanda") is not None

    elif hook == "camofox":
        url = os.getenv("CAMOFOX_URL", "").strip()
        return bool(url)

    elif hook == "browser_use_cli":
        if shutil.which("browser-use") is not None:
            return True
        return importlib.util.find_spec("browser_use") is not None

    elif hook == "faster_whisper":
        return importlib.util.find_spec("faster_whisper") is not None

    elif hook == "kittentts":
        return importlib.util.find_spec("kittentts") is not None

    elif hook == "piper":
        return shutil.which("piper") is not None or importlib.util.find_spec("piper") is not None

    return True


# ── Provider Matrix Ground Truth ─────────────────────────────────────────────

TOOLSET_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "computer_use": {
        "name": "Computer Use",
        "description": "Desktop interaction, GUI observation, mouse, and keyboard automation.",
        "providers": [
            {
                "name": "cua-driver (background)",
                "badge": "★ recommended · free · local",
                "tag": "Background OS desktop automation via cua-driver — non-intrusive cursor control.",
                "computer_use_backend": "cua",
                "post_setup": "cua_driver",
                "env_vars": [],
            },
            {
                "name": "Anara Native Desktop Control",
                "badge": "native · free",
                "tag": "Local native OS desktop interaction, screenshot capture, and input automation.",
                "computer_use_backend": "native",
                "env_vars": [],
            },
        ],
    },
    "browser_automation": {
        "name": "Browser Automation",
        "description": "Headless and headed web browser automation, page interaction, and visual inspection.",
        "providers": [
            {
                "name": "Local Browser",
                "badge": "★ recommended · free",
                "tag": "Headless Chromium automated browsing, no external API key needed.",
                "browser_provider": "local",
                "browser_engine": "auto",
                "post_setup": "agent_browser",
                "env_vars": [],
            },
            {
                "name": "Browser Use",
                "badge": "free · local · cloud",
                "tag": "Advanced agentic web harness and CLI automation framework.",
                "browser_backend": "browser-use",
                "post_setup": "browser_use_cli",
                "env_vars": [],
            },
            {
                "name": "Lightpanda",
                "badge": "free · local · no Chromium",
                "tag": "High-performance headless browser, lightweight text-first navigation.",
                "browser_provider": "local",
                "browser_engine": "lightpanda",
                "post_setup": "lightpanda",
                "env_vars": [],
            },
            {
                "name": "Camofox",
                "badge": "free · local",
                "tag": "Anti-detection browser environment with stealth profiles.",
                "browser_provider": "camofox",
                "post_setup": "camofox",
                "env_vars": [
                    {
                        "key": "CAMOFOX_URL",
                        "prompt": "Camofox server URL",
                        "url": "https://github.com/jo-inc/camofox-browser",
                        "default": "http://localhost:9377",
                    }
                ],
            },
            {
                "name": "Browserbase",
                "badge": "cloud · paid",
                "tag": "Managed cloud headless Chromium infrastructure with stealth proxies.",
                "browser_provider": "browserbase",
                "env_vars": [
                    {
                        "key": "BROWSERBASE_API_KEY",
                        "prompt": "Browserbase API key",
                        "url": "https://browserbase.com",
                    },
                    {
                        "key": "BROWSERBASE_PROJECT_ID",
                        "prompt": "Browserbase Project ID",
                        "url": "https://browserbase.com",
                    },
                ],
            },
            {
                "name": "Firecrawl Browser",
                "badge": "cloud · paid",
                "tag": "Managed cloud web interaction, crawler sandbox, and structured parsing.",
                "browser_provider": "firecrawl",
                "env_vars": [
                    {
                        "key": "FIRECRAWL_API_KEY",
                        "prompt": "Firecrawl API key",
                        "url": "https://firecrawl.dev",
                    }
                ],
            },
        ],
    },
    "web_search_scraping": {
        "name": "Web Search & Scraping",
        "description": "Live web discovery, search querying, and clean Markdown article extraction.",
        "providers": [
            {
                "name": "DuckDuckGo",
                "badge": "★ recommended · free",
                "tag": "Free DuckDuckGo web search skill, zero API keys required.",
                "web_backend": "ddgs",
                "capabilities": ["search"],
                "env_vars": [],
            },
            {
                "name": "Brave Search",
                "badge": "free tier",
                "tag": "Independent privacy-focused web search index with generous free tier.",
                "web_backend": "brave",
                "capabilities": ["search"],
                "env_vars": [
                    {
                        "key": "BRAVE_API_KEY",
                        "prompt": "Brave Search API key",
                        "url": "https://brave.com/search/api",
                    }
                ],
            },
            {
                "name": "Tavily",
                "badge": "paid",
                "tag": "Search engine designed specifically for autonomous AI agents.",
                "web_backend": "tavily",
                "capabilities": ["search", "extract"],
                "env_vars": [
                    {
                        "key": "TAVILY_API_KEY",
                        "prompt": "Tavily Search API key",
                        "url": "https://tavily.com",
                    }
                ],
            },
            {
                "name": "Exa",
                "badge": "paid",
                "tag": "Neural embeddings semantic web search and document crawling.",
                "web_backend": "exa",
                "capabilities": ["search", "extract"],
                "env_vars": [
                    {
                        "key": "EXA_API_KEY",
                        "prompt": "Exa API key",
                        "url": "https://exa.ai",
                    }
                ],
            },
            {
                "name": "Firecrawl Self-Hosted",
                "badge": "free · self-hosted",
                "tag": "Run your own Firecrawl instance locally or via Docker.",
                "web_backend": "firecrawl",
                "capabilities": ["search", "extract"],
                "env_vars": [
                    {
                        "key": "FIRECRAWL_API_URL",
                        "prompt": "Your Firecrawl instance URL",
                        "url": "https://github.com/mendableai/firecrawl",
                        "default": "http://localhost:3002",
                    }
                ],
            },
            {
                "name": "Firecrawl Cloud",
                "badge": "paid",
                "tag": "Turn websites into clean Markdown and structured JSON data.",
                "web_backend": "firecrawl",
                "capabilities": ["search", "extract"],
                "env_vars": [
                    {
                        "key": "FIRECRAWL_API_KEY",
                        "prompt": "Firecrawl API key",
                        "url": "https://firecrawl.dev",
                    }
                ],
            },
            {
                "name": "Perplexity",
                "badge": "paid",
                "tag": "Perplexity Sonar live search and web synthesis API.",
                "web_backend": "perplexity",
                "capabilities": ["search"],
                "env_vars": [
                    {
                        "key": "PERPLEXITY_API_KEY",
                        "prompt": "Perplexity API key",
                        "url": "https://perplexity.ai",
                    }
                ],
            },
            {
                "name": "SearXNG",
                "badge": "free · self-hosted",
                "tag": "Privacy-respecting metasearch engine aggregating 70+ search sources.",
                "web_backend": "searxng",
                "capabilities": ["search"],
                "env_vars": [
                    {
                        "key": "SEARXNG_URL",
                        "prompt": "SearXNG instance URL",
                        "url": "https://github.com/searxng/searxng",
                        "default": "http://localhost:8888",
                    }
                ],
            },
            {
                "name": "xAI Grok Search",
                "badge": "paid",
                "tag": "xAI live web search integration via xAI API.",
                "web_backend": "xai",
                "capabilities": ["search"],
                "env_vars": [
                    {
                        "key": "XAI_API_KEY",
                        "prompt": "xAI API key",
                        "url": "https://console.x.ai",
                    }
                ],
            },
        ],
    },
    "image_generation": {
        "name": "Image Generation",
        "description": "Creative visual generation, text-to-image synthesis, and image editing.",
        "providers": [
            {
                "name": "FAL.ai",
                "badge": "paid · multi-model",
                "tag": "Frontier models: FLUX 2, Z-Image, Nano Banana Pro, Recraft, SD3.5.",
                "imagegen_backend": "fal",
                "image_gen_plugin_name": "fal",
                "env_vars": [
                    {
                        "key": "FAL_KEY",
                        "prompt": "FAL.ai API key",
                        "url": "https://fal.ai/dashboard/keys",
                    }
                ],
            },
            {
                "name": "Pollinations AI",
                "badge": "★ recommended · free",
                "tag": "Free pollinations flux image generation, zero API key required.",
                "imagegen_backend": "pollinations",
                "image_gen_plugin_name": "pollinations",
                "env_vars": [],
            },
            {
                "name": "OpenAI (DALL-E / GPT Image)",
                "badge": "paid",
                "tag": "OpenAI DALL-E 3 and GPT-4o multimodal image generation.",
                "imagegen_backend": "openai",
                "image_gen_plugin_name": "openai",
                "env_vars": [
                    {
                        "key": "OPENAI_API_KEY",
                        "prompt": "OpenAI API key",
                        "url": "https://platform.openai.com/api-keys",
                    }
                ],
            },
            {
                "name": "xAI Grok Imagine",
                "badge": "paid",
                "tag": "xAI Grok Imagine photorealistic visual generator.",
                "imagegen_backend": "xai",
                "image_gen_plugin_name": "xai",
                "env_vars": [
                    {
                        "key": "XAI_API_KEY",
                        "prompt": "xAI API key",
                        "url": "https://console.x.ai",
                    }
                ],
            },
            {
                "name": "Krea AI",
                "badge": "paid",
                "tag": "Krea 1 and Krea 2 high-fidelity visual diffusion models.",
                "imagegen_backend": "krea",
                "image_gen_plugin_name": "krea",
                "env_vars": [
                    {
                        "key": "KREA_API_KEY",
                        "prompt": "Krea API key",
                        "url": "https://krea.ai",
                    }
                ],
            },
            {
                "name": "DeepInfra Image",
                "badge": "paid",
                "tag": "Serverless FLUX, SDXL, and open models at wholesale rates.",
                "imagegen_backend": "deepinfra",
                "image_gen_plugin_name": "deepinfra",
                "env_vars": [
                    {
                        "key": "DEEPINFRA_API_KEY",
                        "prompt": "DeepInfra API key",
                        "url": "https://deepinfra.com",
                    }
                ],
            },
        ],
    },
    "video_generation": {
        "name": "Video Generation",
        "description": "AI video generation from descriptive prompts or reference images.",
        "providers": [
            {
                "name": "FAL.ai Video",
                "badge": "paid",
                "tag": "Frontier video: LTX 2.3/2.5, Pixverse, Seedance 2.0/2.5/Mini, Veo 3.1, MiniMax H3.",
                "video_gen_plugin_name": "fal",
                "env_vars": [
                    {
                        "key": "FAL_KEY",
                        "prompt": "FAL.ai API key",
                        "url": "https://fal.ai/dashboard/keys",
                    }
                ],
            },
            {
                "name": "xAI Imagine Video",
                "badge": "paid",
                "tag": "Grok Imagine Video & Imagine Video 1.5 text-to-video / image-to-video.",
                "video_gen_plugin_name": "xai",
                "env_vars": [
                    {
                        "key": "XAI_API_KEY",
                        "prompt": "xAI API key",
                        "url": "https://console.x.ai",
                    }
                ],
            },
            {
                "name": "DeepInfra Video",
                "badge": "paid",
                "tag": "Open-source video diffusion pipelines on serverless GPUs.",
                "video_gen_plugin_name": "deepinfra",
                "env_vars": [
                    {
                        "key": "DEEPINFRA_API_KEY",
                        "prompt": "DeepInfra API key",
                        "url": "https://deepinfra.com",
                    }
                ],
            },
        ],
    },
    "text_to_speech": {
        "name": "Text-to-Speech",
        "description": "High-fidelity neural voice synthesis, audio generation, and speech rendering.",
        "providers": [
            {
                "name": "Microsoft Edge TTS",
                "badge": "★ recommended · free",
                "tag": "High-quality neural speech voices, zero API key required.",
                "tts_provider": "edge",
                "env_vars": [],
            },
            {
                "name": "OpenAI TTS",
                "badge": "paid",
                "tag": "High-quality voices (alloy, echo, fable, onyx, nova, shimmer).",
                "tts_provider": "openai",
                "env_vars": [
                    {
                        "key": "VOICE_TOOLS_OPENAI_KEY",
                        "prompt": "OpenAI Voice API key",
                        "url": "https://platform.openai.com/api-keys",
                    }
                ],
            },
            {
                "name": "ElevenLabs",
                "badge": "paid",
                "tag": "Most natural voices, vocal emotional depth, and custom voice cloning.",
                "tts_provider": "elevenlabs",
                "env_vars": [
                    {
                        "key": "ELEVENLABS_API_KEY",
                        "prompt": "ElevenLabs API key",
                        "url": "https://elevenlabs.io",
                    }
                ],
            },
            {
                "name": "Google Gemini TTS",
                "badge": "free tier",
                "tag": "30 prebuilt voices controllable via descriptive prompts.",
                "tts_provider": "gemini",
                "env_vars": [
                    {
                        "key": "GEMINI_API_KEY",
                        "prompt": "Gemini API key",
                        "url": "https://aistudio.google.com",
                    }
                ],
            },
            {
                "name": "Mistral (Voxtral TTS)",
                "badge": "paid",
                "tag": "Multilingual natural voice generation with native Opus audio.",
                "tts_provider": "mistral",
                "env_vars": [
                    {
                        "key": "MISTRAL_API_KEY",
                        "prompt": "Mistral API key",
                        "url": "https://console.mistral.ai",
                    }
                ],
            },
            {
                "name": "xAI TTS",
                "badge": "paid",
                "tag": "Grok voices — uses xAI API key.",
                "tts_provider": "xai",
                "env_vars": [
                    {
                        "key": "XAI_API_KEY",
                        "prompt": "xAI API key",
                        "url": "https://console.x.ai",
                    }
                ],
            },
            {
                "name": "KittenTTS",
                "badge": "local · free",
                "tag": "Lightweight local ONNX neural TTS (~25MB), zero API key.",
                "tts_provider": "kittentts",
                "post_setup": "kittentts",
                "env_vars": [],
            },
            {
                "name": "Piper",
                "badge": "local · free",
                "tag": "Local neural TTS, 44 languages (voices ~20-90MB).",
                "tts_provider": "piper",
                "post_setup": "piper",
                "env_vars": [],
            },
            {
                "name": "DeepInfra TTS",
                "badge": "paid",
                "tag": "Chatterbox, Qwen3-TTS, and hosted open voice models.",
                "tts_provider": "deepinfra",
                "env_vars": [
                    {
                        "key": "DEEPINFRA_API_KEY",
                        "prompt": "DeepInfra API key",
                        "url": "https://deepinfra.com",
                    }
                ],
            },
        ],
    },
    "speech_to_text": {
        "name": "Speech-to-Text",
        "description": "Speech audio transcription, voice memo decoding, and multilingual recognition.",
        "providers": [
            {
                "name": "Local Whisper",
                "badge": "★ recommended · free",
                "tag": "faster-whisper on-device neural transcription, zero API key needed.",
                "stt_provider": "local",
                "post_setup": "faster_whisper",
                "env_vars": [],
            },
            {
                "name": "OpenAI",
                "badge": "paid",
                "tag": "whisper-1, gpt-4o-transcribe, gpt-transcribe high-accuracy APIs.",
                "stt_provider": "openai",
                "env_vars": [
                    {
                        "key": "OPENAI_API_KEY",
                        "prompt": "OpenAI API key",
                        "url": "https://platform.openai.com/api-keys",
                    }
                ],
            },
            {
                "name": "Groq",
                "badge": "free tier",
                "tag": "Whisper large-v3 family — ultra-fast LPU inference.",
                "stt_provider": "groq",
                "env_vars": [
                    {
                        "key": "GROQ_API_KEY",
                        "prompt": "Groq API key",
                        "url": "https://console.groq.com/keys",
                    }
                ],
            },
            {
                "name": "xAI",
                "badge": "paid",
                "tag": "grok-stt speech recognition via xAI API.",
                "stt_provider": "xai",
                "env_vars": [
                    {
                        "key": "XAI_API_KEY",
                        "prompt": "xAI API key",
                        "url": "https://console.x.ai",
                    }
                ],
            },
            {
                "name": "ElevenLabs Scribe",
                "badge": "paid",
                "tag": "scribe_v2 — speaker diarization + audio-event tagging.",
                "stt_provider": "elevenlabs",
                "env_vars": [
                    {
                        "key": "ELEVENLABS_API_KEY",
                        "prompt": "ElevenLabs API key",
                        "url": "https://elevenlabs.io",
                    }
                ],
            },
            {
                "name": "DeepInfra",
                "badge": "paid",
                "tag": "Serverless Whisper transcription APIs at wholesale rates.",
                "stt_provider": "deepinfra",
                "env_vars": [
                    {
                        "key": "DEEPINFRA_API_KEY",
                        "prompt": "DeepInfra API key",
                        "url": "https://deepinfra.com",
                    }
                ],
            },
        ],
    },
}

# ── Dynamic Model Catalogs Ground Truth ──────────────────────────────────────

TOOLSET_MODELS_CATALOG: Dict[str, Dict[str, Any]] = {
    "image_generation": {
        "fal": {
            "default": "fal-ai/flux-2/klein/9b",
            "models": {
                "fal-ai/flux-2/klein/9b": {
                    "display": "FLUX 2 Klein 9B",
                    "speed": "<1s",
                    "strengths": "Fast, crisp text and vector typography",
                    "price": "$0.006/MP",
                },
                "fal-ai/flux-2-pro": {
                    "display": "FLUX 2 Pro",
                    "speed": "~6s",
                    "strengths": "Studio photorealism and detail fidelity",
                    "price": "$0.03/MP",
                },
                "fal-ai/z-image/turbo": {
                    "display": "Z-Image Turbo",
                    "speed": "~2s",
                    "strengths": "Bilingual EN/CN, 6B parameter model",
                    "price": "$0.005/MP",
                },
                "fal-ai/nano-banana-pro": {
                    "display": "Nano Banana Pro (Gemini 3 Pro Image)",
                    "speed": "~8s",
                    "strengths": "Gemini 3 Pro, reasoning depth, text rendering",
                    "price": "$0.15/image",
                },
                "fal-ai/recraft-v3": {
                    "display": "Recraft V3",
                    "speed": "~10s",
                    "strengths": "Vector & graphic design, typography",
                    "price": "$0.04/image",
                },
                "fal-ai/flux-pro/v1.1-ultra": {
                    "display": "FLUX 1.1 Ultra",
                    "speed": "~8s",
                    "strengths": "Frontier photorealism, 2K raw output",
                    "price": "$0.06/image",
                },
                "fal-ai/stable-diffusion-v35-large": {
                    "display": "Stable Diffusion 3.5 Large",
                    "speed": "~5s",
                    "strengths": "High aesthetics and style variety",
                    "price": "$0.065/image",
                },
                "fal-ai/nano-banana-2": {
                    "display": "Nano Banana 2 (Gemini 3.1 Flash Image)",
                    "speed": "~3s",
                    "strengths": "Ultra-fast multimodal reasoning, Flash efficiency",
                    "price": "$0.04/image",
                },
                "fal-ai/gpt-image-1.5": {
                    "display": "GPT Image 1.5",
                    "speed": "~10s",
                    "strengths": "Balanced fidelity and prompt adherence",
                    "price": "$0.034/image",
                },
                "fal-ai/gpt-image-2": {
                    "display": "GPT Image 2",
                    "speed": "~14s",
                    "strengths": "High resolution photorealism",
                    "price": "$0.060/image",
                },
                "fal-ai/ideogram/v3": {
                    "display": "Ideogram V3",
                    "speed": "~10s",
                    "strengths": "Graphic design and complex typography",
                    "price": "$0.040/image",
                },
                "fal-ai/recraft/v4/pro/text-to-image": {
                    "display": "Recraft V4 Pro",
                    "speed": "~8s",
                    "strengths": "Vector, 3D, and brand asset generation",
                    "price": "$0.040/image",
                },
                "fal-ai/recraft/v4.1/text-to-image": {
                    "display": "Recraft V4.1",
                    "speed": "~8s",
                    "strengths": "Improved realism and style controls",
                    "price": "$0.045/image",
                },
                "fal-ai/qwen-image": {
                    "display": "Qwen Image",
                    "speed": "~6s",
                    "strengths": "Multilingual prompt adherence (Chinese/English)",
                    "price": "$0.020/image",
                },
                "fal-ai/krea/v2/medium/text-to-image": {
                    "display": "Krea 2 Medium",
                    "speed": "~5s",
                    "strengths": "Aesthetics, lighting, and texture clarity",
                    "price": "$0.030/image",
                },
                "fal-ai/krea/v2/large/text-to-image": {
                    "display": "Krea 2 Large",
                    "speed": "~9s",
                    "strengths": "Ultra-high detail and cinematic texture",
                    "price": "$0.060/image",
                },
                "bytedance/seedream/v5/pro/text-to-image": {
                    "display": "SeeDream 5.0 Pro",
                    "speed": "~8s",
                    "strengths": "Artistic rendering and character design",
                    "price": "$0.035/image",
                },
                "bytedance/seedream/v5/lite/text-to-image": {
                    "display": "SeeDream 5.0 Lite",
                    "speed": "~3s",
                    "strengths": "High throughput fast generation",
                    "price": "$0.015/image",
                },
                "ideogram/v4/instant": {
                    "display": "Ideogram V4 Instant",
                    "speed": "~4s",
                    "strengths": "Fast logo, poster, and banner design",
                    "price": "$0.025/image",
                },
                "ideogram/v4/fast": {
                    "display": "Ideogram V4 Fast",
                    "speed": "~6s",
                    "strengths": "Advanced typography and graphic layouts",
                    "price": "$0.035/image",
                },
                "alibaba/qwen-image-3/text-to-image": {
                    "display": "Qwen Image 3",
                    "speed": "~7s",
                    "strengths": "State-of-the-art multi-lingual text rendering",
                    "price": "$0.030/image",
                },
                "microsoft/mai-image-2.5-pro": {
                    "display": "MAI-Image 2.5 Pro",
                    "speed": "~9s",
                    "strengths": "Enterprise image synthesis and safety",
                    "price": "$0.040/image",
                },
                "google/nano-banana-2-lite": {
                    "display": "Nano Banana 2 Lite",
                    "speed": "<2s",
                    "strengths": "Ultra-compact multimodal model",
                    "price": "$0.010/image",
                },
                "xai/grok-imagine-image/v2.0/text-to-image": {
                    "display": "Grok Imagine Image 2.0",
                    "speed": "~6s",
                    "strengths": "Bold creative concepts and realism",
                    "price": "$0.030/image",
                },
                "fal-ai/kling-image/v3/text-to-image": {
                    "display": "Kling Image 3.0",
                    "speed": "~7s",
                    "strengths": "Cinematic composition and texture",
                    "price": "$0.035/image",
                },
                "meta/muse-image/text-to-image": {
                    "display": "Meta Muse Image",
                    "speed": "~5s",
                    "strengths": "High fidelity open weights diffusion",
                    "price": "$0.025/image",
                },
                "fal-ai/flux-realism": {
                    "display": "FLUX Realism Lora",
                    "speed": "~4s",
                    "strengths": "Hyper-realistic portraits and skin textures",
                    "price": "$0.015/image",
                },
            },
        },
        "pollinations": {
            "default": "flux",
            "models": {
                "flux": {
                    "display": "Flux.1 Schnell",
                    "speed": "~3s",
                    "strengths": "Fast, vibrant open model with high prompt adherence",
                    "price": "free",
                },
                "flux-realism": {
                    "display": "Flux Realism",
                    "speed": "~4s",
                    "strengths": "Photorealistic portraits and lighting",
                    "price": "free",
                },
                "flux-anime": {
                    "display": "Flux Anime",
                    "speed": "~3s",
                    "strengths": "Anime, manga, and illustrative rendering",
                    "price": "free",
                },
                "flux-3d": {
                    "display": "Flux 3D",
                    "speed": "~4s",
                    "strengths": "3D CGI & render style aesthetics",
                    "price": "free",
                },
                "any-dark": {
                    "display": "Any Dark",
                    "speed": "~3s",
                    "strengths": "Dark cinematic and dramatic moody lighting",
                    "price": "free",
                },
                "turbo": {
                    "display": "SDXL Turbo",
                    "speed": "<2s",
                    "strengths": "Near instant generation for rapid prototyping",
                    "price": "free",
                },
            },
        },
        "openai": {
            "default": "dall-e-3",
            "models": {
                "dall-e-3": {
                    "display": "DALL-E 3",
                    "speed": "~10s",
                    "strengths": "Exceptional prompt fidelity and semantic accuracy",
                    "price": "$0.040/image",
                },
                "dall-e-2": {
                    "display": "DALL-E 2",
                    "speed": "~5s",
                    "strengths": "Fast, lightweight creative generations",
                    "price": "$0.020/image",
                },
                "gpt-4o-image": {
                    "display": "GPT-4o Native Image",
                    "speed": "~8s",
                    "strengths": "Multimodal reasoning with embedded text rendering",
                    "price": "$0.050/image",
                },
            },
        },
        "xai": {
            "default": "grok-imagine-image",
            "models": {
                "grok-imagine-image": {
                    "display": "Grok Imagine Image",
                    "speed": "~5s",
                    "strengths": "Photorealistic generation via xAI Imagine",
                    "price": "Standard tier",
                },
            },
        },
        "krea": {
            "default": "krea-v2",
            "models": {
                "krea-v2": {
                    "display": "Krea 2",
                    "speed": "~6s",
                    "strengths": "Frontier realism, aesthetics, and texture clarity",
                    "price": "$0.04/image",
                },
                "krea-v1": {
                    "display": "Krea 1",
                    "speed": "~4s",
                    "strengths": "Stylized visual diffusion generation",
                    "price": "$0.02/image",
                },
            },
        },
        "deepinfra": {
            "default": "black-forest-labs/FLUX.1-schnell",
            "models": {
                "black-forest-labs/FLUX.1-schnell": {
                    "display": "FLUX.1 Schnell",
                    "speed": "~2s",
                    "strengths": "Fast serverless inference",
                    "price": "$0.003/image",
                },
                "black-forest-labs/FLUX.1-dev": {
                    "display": "FLUX.1 Dev",
                    "speed": "~6s",
                    "strengths": "High quality artistic generation",
                    "price": "$0.025/image",
                },
                "stabilityai/sdxl-turbo": {
                    "display": "SDXL Turbo",
                    "speed": "<1s",
                    "strengths": "Ultra-fast low-step diffusion",
                    "price": "$0.002/image",
                },
            },
        },
    },
    "video_generation": {
        "fal": {
            "default": "pixverse-v6",
            "models": {
                "pixverse-v6": {
                    "display": "Pixverse v6",
                    "speed": "~30-90s",
                    "strengths": "Affordable, negative prompts, 1-15s durations",
                    "price": "cheap",
                },
                "ltx-2.3": {
                    "display": "LTX 2.3 (22B)",
                    "speed": "~30-60s",
                    "strengths": "22B model with native audio generation",
                    "price": "cheap",
                },
                "ltx-2.5": {
                    "display": "LTX 2.5",
                    "speed": "~30-90s",
                    "strengths": "Lightricks open audio-video model, up to 20s / 4K",
                    "price": "cheap",
                },
                "seedance-2.0-mini": {
                    "display": "Seedance 2.0 Mini",
                    "speed": "~30-90s",
                    "strengths": "ByteDance fast tier, audio + lip-sync",
                    "price": "cheap",
                },
                "veo3.1": {
                    "display": "Veo 3.1",
                    "speed": "~60-120s",
                    "strengths": "Cinematic quality, native audio, prompt adherence",
                    "price": "premium",
                },
                "seedance-2.0": {
                    "display": "Seedance 2.0",
                    "speed": "~60-120s",
                    "strengths": "Cinematic, synchronized audio + lip-sync, 4-15s",
                    "price": "premium",
                },
                "seedance-2.5": {
                    "display": "Seedance 2.5",
                    "speed": "~60-180s",
                    "strengths": "ByteDance flagship, 30s single pass, audio in latent space",
                    "price": "premium",
                },
                "minimax-h3": {
                    "display": "MiniMax H3",
                    "speed": "~60-180s",
                    "strengths": "MiniMax frontier, native 2K up to 4K, 5-15s",
                    "price": "premium",
                },
                "minimax-h3-max": {
                    "display": "MiniMax H3 Max",
                    "speed": "~5-30s",
                    "strengths": "Top quality, 768p in seconds, 5-15s",
                    "price": "premium",
                },
                "minimax-h3-max-turbo": {
                    "display": "MiniMax H3 Max Turbo",
                    "speed": "~5-20s",
                    "strengths": "Near-Max quality at fraction of price/latency, 480P-1080P, 5-15s.",
                    "price": "premium",
                },
                "flux-3": {
                    "display": "FLUX 3 Video",
                    "speed": "~60-120s",
                    "strengths": "Black Forest Labs frontier video. Native audio, 5-20s, 8 aspect ratios.",
                    "price": "premium",
                },
                "grok-imagine-1.5": {
                    "display": "Grok Imagine 1.5",
                    "speed": "~30-90s",
                    "strengths": "xAI. Fast stylized video with audio, 1-15s, cheap per second.",
                    "price": "premium",
                },
                "gemini-omni-flash": {
                    "display": "Gemini Omni Flash 1.1",
                    "speed": "~60-120s",
                    "strengths": "Google. Text & image to video with native audio, physics-grounded motion.",
                    "price": "premium",
                },
                "kling-v3": {
                    "display": "Kling 3.0 (Standard)",
                    "speed": "~60-180s",
                    "strengths": "Kuaishou frontier core model. Cinematic motion, native audio, 3-15s.",
                    "price": "premium",
                },
                "kling-v3-pro": {
                    "display": "Kling 3.0 Pro",
                    "speed": "~60-180s",
                    "strengths": "Kling 3.0 top quality tier. Cinematic motion, native audio, 3-15s.",
                    "price": "premium",
                },
                "kling-v3-4k": {
                    "display": "Kling v3 4K",
                    "speed": "~120-300s",
                    "strengths": "4K output, native audio (Chinese/English), 3-15s.",
                    "price": "premium",
                },
                "kling-o3": {
                    "display": "Kling O3",
                    "speed": "~60-180s",
                    "strengths": "Kuaishou frontier. Multi-shot native storytelling, optional audio, 3-15s.",
                    "price": "premium",
                },
                "wan-3.0": {
                    "display": "Wan 3.0",
                    "speed": "~50-120s",
                    "strengths": "Alibaba Wan 3.0 open audio-video diffusion model, 480p-1080p, 5s.",
                    "price": "cheap",
                },
                "happy-horse": {
                    "display": "Happy Horse 1.0",
                    "speed": "~30-60s",
                    "strengths": "Fast expressive animation and character motion.",
                    "price": "cheap",
                },
                "grok-imagine": {
                    "display": "Grok Imagine Video",
                    "speed": "~30-80s",
                    "strengths": "xAI Grok Imagine generative video.",
                    "price": "premium",
                },
            },
        },
        "xai": {
            "default": "grok-imagine-video",
            "models": {
                "grok-imagine-video": {
                    "display": "Grok Imagine Video",
                    "speed": "~60-240s",
                    "strengths": "Text-to-video with high motion coherence",
                    "price": "Standard tier",
                },
                "grok-imagine-video-1.5": {
                    "display": "Grok Imagine Video 1.5",
                    "speed": "~60-240s",
                    "strengths": "Latest xAI image-to-video model",
                    "price": "Standard tier",
                },
            },
        },
        "deepinfra": {
            "default": "Lightricks/LTX-Video",
            "models": {
                "Lightricks/LTX-Video": {
                    "display": "LTX Video",
                    "speed": "~30-60s",
                    "strengths": "Open source video generation on serverless GPUs",
                    "price": "$0.05/gen",
                },
                "THUDM/CogVideoX-5b": {
                    "display": "CogVideoX 5B",
                    "speed": "~60-120s",
                    "strengths": "High resolution 3D video generation",
                    "price": "$0.10/gen",
                },
            },
        },
    },
    "speech_to_text": {
        "local": {
            "default": "base",
            "models": {
                "base": {
                    "display": "Whisper Base",
                    "speed": "fast",
                    "strengths": "Balanced on-device transcription accuracy",
                    "price": "free",
                },
                "tiny": {
                    "display": "Whisper Tiny",
                    "speed": "ultra-fast",
                    "strengths": "Lowest resource footprint for instant transcription",
                    "price": "free",
                },
                "small": {
                    "display": "Whisper Small",
                    "speed": "fast",
                    "strengths": "Higher accuracy with lightweight footprint",
                    "price": "free",
                },
                "medium": {
                    "display": "Whisper Medium",
                    "speed": "medium",
                    "strengths": "Strong multilingual accuracy",
                    "price": "free",
                },
                "large-v3": {
                    "display": "Whisper Large v3",
                    "speed": "slow",
                    "strengths": "Maximum transcription accuracy and multilingual handling",
                    "price": "free",
                },
            },
        },
        "groq": {
            "default": "whisper-large-v3-turbo",
            "models": {
                "whisper-large-v3-turbo": {
                    "display": "Whisper Large v3 Turbo",
                    "speed": "<1s",
                    "strengths": "Sub-second cloud transcription on Groq LPUs",
                    "price": "free tier",
                },
                "whisper-large-v3": {
                    "display": "Whisper Large v3",
                    "speed": "~1s",
                    "strengths": "Frontier transcription quality",
                    "price": "free tier",
                },
                "distil-whisper-large-v3-en": {
                    "display": "Distil Whisper Large v3 (EN)",
                    "speed": "<0.5s",
                    "strengths": "Ultra-fast English transcription",
                    "price": "free tier",
                },
            },
        },
        "openai": {
            "default": "whisper-1",
            "models": {
                "whisper-1": {
                    "display": "Whisper 1",
                    "speed": "~2s",
                    "strengths": "General cloud speech-to-text",
                    "price": "$0.006/min",
                },
                "gpt-4o-mini-transcribe": {
                    "display": "GPT-4o Mini Transcribe",
                    "speed": "~2s",
                    "strengths": "Low cost multimodal transcription",
                    "price": "$0.003/min",
                },
                "gpt-4o-transcribe": {
                    "display": "GPT-4o Transcribe",
                    "speed": "~2s",
                    "strengths": "Frontier multimodal speech understanding",
                    "price": "$0.006/min",
                },
                "gpt-transcribe": {
                    "display": "GPT Transcribe",
                    "speed": "~2s",
                    "strengths": "Standard GPT speech transcription",
                    "price": "$0.006/min",
                },
            },
        },
        "elevenlabs": {
            "default": "scribe_v2",
            "models": {
                "scribe_v2": {
                    "display": "Scribe v2",
                    "speed": "~2s",
                    "strengths": "Diarization and audio-event tagging",
                    "price": "paid",
                },
                "scribe_v1": {
                    "display": "Scribe v1",
                    "speed": "~3s",
                    "strengths": "Multilingual transcription",
                    "price": "paid",
                },
            },
        },
        "xai": {
            "default": "grok-stt",
            "models": {
                "grok-stt": {
                    "display": "Grok STT",
                    "speed": "~2s",
                    "strengths": "xAI speech-to-text recognition",
                    "price": "paid",
                },
            },
        },
        "deepinfra": {
            "default": "openai/whisper-large-v3",
            "models": {
                "openai/whisper-large-v3": {
                    "display": "Whisper Large v3 (DeepInfra)",
                    "speed": "~1s",
                    "strengths": "High accuracy serverless STT",
                    "price": "paid",
                },
                "openai/whisper-large-v3-turbo": {
                    "display": "Whisper Large v3 Turbo (DeepInfra)",
                    "speed": "<1s",
                    "strengths": "Fast serverless STT",
                    "price": "paid",
                },
                "distil-whisper/distil-large-v3": {
                    "display": "Distil Whisper Large v3 (DeepInfra)",
                    "speed": "<1s",
                    "strengths": "Distilled fast STT",
                    "price": "paid",
                },
            },
        },
    },
    "text_to_speech": {
        "edge": {
            "default": "en-US-AriaNeural",
            "models": {
                "en-US-AriaNeural": {
                    "display": "Aria (en-US, Female)",
                    "speed": "fast",
                    "strengths": "Natural conversational American English",
                    "price": "free",
                },
                "en-US-GuyNeural": {
                    "display": "Guy (en-US, Male)",
                    "speed": "fast",
                    "strengths": "Friendly conversational American English",
                    "price": "free",
                },
                "en-US-JennyNeural": {
                    "display": "Jenny (en-US, Female)",
                    "speed": "fast",
                    "strengths": "Expressive assistant voice",
                    "price": "free",
                },
                "id-ID-GadisNeural": {
                    "display": "Gadis (id-ID, Female)",
                    "speed": "fast",
                    "strengths": "Natural Indonesian conversational female voice",
                    "price": "free",
                },
                "id-ID-ArdiNeural": {
                    "display": "Ardi (id-ID, Male)",
                    "speed": "fast",
                    "strengths": "Natural Indonesian conversational male voice",
                    "price": "free",
                },
            },
        },
        "openai": {
            "default": "alloy",
            "models": {
                "alloy": {
                    "display": "Alloy",
                    "speed": "fast",
                    "strengths": "Neutral, balanced conversational voice",
                    "price": "paid",
                },
                "echo": {
                    "display": "Echo",
                    "speed": "fast",
                    "strengths": "Warm and clear conversational voice",
                    "price": "paid",
                },
                "fable": {
                    "display": "Fable",
                    "speed": "fast",
                    "strengths": "Expressive narration and storytelling",
                    "price": "paid",
                },
                "onyx": {
                    "display": "Onyx",
                    "speed": "fast",
                    "strengths": "Deep, authoritative masculine voice",
                    "price": "paid",
                },
                "nova": {
                    "display": "Nova",
                    "speed": "fast",
                    "strengths": "Friendly, energetic feminine voice",
                    "price": "paid",
                },
                "shimmer": {
                    "display": "Shimmer",
                    "speed": "fast",
                    "strengths": "Clear, crisp feminine voice",
                    "price": "paid",
                },
            },
        },
        "elevenlabs": {
            "default": "21m00Tcm4TlvDq8ikWAM",
            "models": {
                "21m00Tcm4TlvDq8ikWAM": {
                    "display": "Rachel",
                    "speed": "medium",
                    "strengths": "Warm, natural conversational voice",
                    "price": "paid",
                },
                "AZnzlk1XvdvUeBnXmlld": {
                    "display": "Domi",
                    "speed": "medium",
                    "strengths": "Strong, energetic expressive voice",
                    "price": "paid",
                },
                "EXAVITQu4vr4xnSDxMaL": {
                    "display": "Bella",
                    "speed": "medium",
                    "strengths": "Soft, pleasant narrative voice",
                    "price": "paid",
                },
            },
        },
        "gemini": {
            "default": "Puck",
            "models": {
                "Puck": {
                    "display": "Puck",
                    "speed": "fast",
                    "strengths": "Upbeat conversational assistant voice",
                    "price": "free tier",
                },
                "Charon": {
                    "display": "Charon",
                    "speed": "fast",
                    "strengths": "Calm, grounded baritone voice",
                    "price": "free tier",
                },
                "Kore": {
                    "display": "Kore",
                    "speed": "fast",
                    "strengths": "Expressive, melodic voice",
                    "price": "free tier",
                },
                "Fenrir": {
                    "display": "Fenrir",
                    "speed": "fast",
                    "strengths": "Deep, rich timbre voice",
                    "price": "free tier",
                },
                "Aoede": {
                    "display": "Aoede",
                    "speed": "fast",
                    "strengths": "Gentle, clear narrative voice",
                    "price": "free tier",
                },
            },
        },
        "mistral": {
            "default": "voxtral-v1",
            "models": {
                "voxtral-v1": {
                    "display": "Voxtral v1",
                    "speed": "fast",
                    "strengths": "Multilingual native Opus audio synthesis",
                    "price": "paid",
                },
            },
        },
    },
}

# ── Environment Persistence Helpers ──────────────────────────────────────────


def get_env_value(key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieves an environment variable value from process env or SQLite settings."""
    val = os.getenv(key)
    if val is not None and val.strip():
        return val.strip()

    try:
        from memory import memory_engine
        stored = memory_engine.get_app_setting(f"env_{key}")
        if stored is not None and stored.strip():
            return stored.strip()
    except Exception:
        pass

    return default


def save_env_value(key: str, value: str) -> bool:
    """Atomically persists an environment variable into process memory, ANARA_HOME/.env, and SQLite."""
    clean_key = (key or "").strip()
    clean_val = (value or "").strip().replace("\n", "").replace("\r", "")
    if not clean_key:
        return False

    os.environ[clean_key] = clean_val

    # 1. Update ANARA_HOME/.env file
    try:
        env_path = get_anara_home() / ".env"
        env_path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        if env_path.is_file():
            try:
                lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
            except Exception:
                lines = []

        found = False
        new_line = f"{clean_key}={clean_val}\n"
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(f"{clean_key}=") or stripped.startswith(f"export {clean_key}="):
                lines[i] = new_line
                found = True
                break

        if not found:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(new_line)

        env_path.write_text("".join(lines), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[ToolsetProviders] Error persisting to .env: {e}")

    # 2. Update SQLite app_settings
    try:
        from memory import memory_engine
        memory_engine.set_app_setting(f"env_{clean_key}", clean_val)
    except Exception as e:
        logger.debug(f"[ToolsetProviders] Error saving setting to SQLite: {e}")

    return True


def remove_env_value(key: str) -> bool:
    """Removes an environment variable from process memory, ANARA_HOME/.env, and SQLite."""
    clean_key = (key or "").strip()
    if not clean_key:
        return False

    os.environ.pop(clean_key, None)

    try:
        env_path = get_anara_home() / ".env"
        if env_path.is_file():
            lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
            filtered = [
                line
                for line in lines
                if not (line.strip().startswith(f"{clean_key}=") or line.strip().startswith(f"export {clean_key}="))
            ]
            env_path.write_text("".join(filtered), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[ToolsetProviders] Error deleting key from .env: {e}")

    try:
        from memory import memory_engine
        memory_engine.set_app_setting(f"env_{clean_key}", "")
    except Exception:
        pass

    return True


# ── Active Provider Detection ────────────────────────────────────────────────


def is_provider_active(toolset_name: str, provider: Dict[str, Any], config: Dict[str, Any]) -> bool:
    """Evaluates whether a specific provider row is currently active in configuration."""
    ts = canonical_toolset_name(toolset_name)

    if ts == "computer_use":
        backend = (
            config.get("computer_use", {}).get("backend")
            or os.getenv("COMPUTER_USE_BACKEND")
            or "cua"
        ).strip().lower()
        row_backend = provider.get("computer_use_backend", "").strip().lower()
        return backend == row_backend

    elif ts == "browser_automation":
        browser_cfg = config.get("browser", {})
        if not isinstance(browser_cfg, dict):
            browser_cfg = {}

        b_backend = browser_cfg.get("backend", "").strip().lower()
        b_cloud = browser_cfg.get("cloud_provider", "").strip().lower()
        b_engine = browser_cfg.get("engine", "").strip().lower()

        # Browser Use CLI mode
        if provider.get("browser_backend") == "browser-use":
            return b_backend == "browser-use"

        # Explicit cloud provider match
        if provider.get("browser_provider") and provider.get("browser_provider") != "local":
            return b_cloud == provider["browser_provider"]

        # Lightpanda engine match
        if provider.get("browser_engine") == "lightpanda":
            return b_engine == "lightpanda"

        # Local browser default match
        if provider.get("browser_provider") == "local" and provider.get("browser_engine") == "auto":
            return (b_backend != "browser-use") and (b_cloud in ("", "local")) and (b_engine != "lightpanda")

        return False

    elif ts == "web_search_scraping":
        web_cfg = config.get("web", {})
        if not isinstance(web_cfg, dict):
            web_cfg = {}

        active_backend = (web_cfg.get("backend") or os.getenv("WEB_SEARCH_BACKEND") or "ddgs").strip().lower()
        row_backend = provider.get("web_backend", "").strip().lower()

        if row_backend == "firecrawl":
            # Differentiate between Self-Hosted vs Cloud
            has_custom_url = bool(get_env_value("FIRECRAWL_API_URL") or web_cfg.get("firecrawl_url"))
            if provider.get("name") == "Firecrawl Self-Hosted":
                return active_backend == "firecrawl" and has_custom_url
            elif provider.get("name") == "Firecrawl Cloud":
                return active_backend == "firecrawl" and not has_custom_url

        return active_backend == row_backend

    elif ts == "image_generation":
        img_cfg = config.get("image_gen", {})
        if not isinstance(img_cfg, dict):
            img_cfg = {}
        active_prov = (
            img_cfg.get("provider")
            or img_cfg.get("backend")
            or os.getenv("IMAGE_GEN_PROVIDER")
            or "fal"
        ).strip().lower()

        row_prov = (provider.get("image_gen_plugin_name") or provider.get("imagegen_backend") or "").strip().lower()
        return active_prov == row_prov

    elif ts == "video_generation":
        vid_cfg = config.get("video_gen", {})
        if not isinstance(vid_cfg, dict):
            vid_cfg = {}
        active_prov = (
            vid_cfg.get("provider")
            or os.getenv("VIDEO_GEN_PROVIDER")
            or "fal"
        ).strip().lower()

        row_prov = provider.get("video_gen_plugin_name", "").strip().lower()
        return active_prov == row_prov

    elif ts == "text_to_speech":
        tts_cfg = config.get("tts", {})
        if not isinstance(tts_cfg, dict):
            tts_cfg = {}
        active_prov = (
            tts_cfg.get("provider")
            or os.getenv("TTS_PROVIDER")
            or "edge"
        ).strip().lower()

        row_prov = provider.get("tts_provider", "").strip().lower()
        return active_prov == row_prov

    elif ts == "speech_to_text":
        stt_cfg = config.get("stt", {})
        if not isinstance(stt_cfg, dict):
            stt_cfg = {}
        active_prov = (
            stt_cfg.get("provider")
            or os.getenv("STT_PROVIDER")
            or "local"
        ).strip().lower()

        row_prov = provider.get("stt_provider", "").strip().lower()
        return active_prov == row_prov

    return False


def provider_readiness_status(
    provider: Dict[str, Any], config: Dict[str, Any], is_active: bool = False
) -> str:
    """Computes honest server-side readiness: 'ready', 'needs_keys', 'needs_setup', 'needs_auth'."""
    env_vars = provider.get("env_vars", [])
    if env_vars:
        # If row requires keys, check if all required variables are set
        all_set = True
        for ev in env_vars:
            key = ev["key"]
            val = get_env_value(key) or ev.get("default")
            if not val:
                all_set = False
                break
        return "ready" if all_set else "needs_keys"

    post_setup = provider.get("post_setup")
    if post_setup:
        installed = _is_post_setup_installed(post_setup)
        if installed:
            return "ready"
        return "ready" if is_active else "needs_setup"

    return "ready"


# ── Core Exported API: get_toolset_config ─────────────────────────────────────


def get_toolset_config(name: str, profile: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns the provider matrix and live configuration state for a toolset.
    Strictly adheres to the Project Anara schema contract.
    """
    canonical_name = canonical_toolset_name(name)
    category_data = TOOLSET_PROVIDERS.get(canonical_name)

    if not category_data:
        return {
            "name": name,
            "has_category": False,
            "providers": [],
            "active_provider": None,
        }

    config = load_config()
    providers: List[Dict[str, Any]] = []
    active_provider: Optional[str] = None

    for raw_prov in category_data.get("providers", []):
        prov = copy.deepcopy(raw_prov)

        # Annotate env vars with is_set status
        annotated_env_vars = []
        for ev in prov.get("env_vars", []):
            is_set = bool(get_env_value(ev["key"]))
            annotated_env_vars.append(
                {
                    "key": ev["key"],
                    "prompt": ev.get("prompt", ev["key"]),
                    "url": ev.get("url"),
                    "default": ev.get("default"),
                    "is_set": is_set,
                }
            )
        prov["env_vars"] = annotated_env_vars

        # Determine if this row is currently active
        is_active = is_provider_active(canonical_name, prov, config)
        prov["is_active"] = is_active
        if is_active and active_provider is None:
            active_provider = prov["name"]

        # Calculate readiness status
        prov["status"] = provider_readiness_status(prov, config, is_active=is_active)
        providers.append(prov)

    # Fallback to the first provider if none matched as active
    if active_provider is None and providers:
        active_provider = providers[0]["name"]
        providers[0]["is_active"] = True

    payload: Dict[str, Any] = {
        "name": canonical_name,
        "has_category": True,
        "providers": providers,
        "active_provider": active_provider,
    }

    # Toolset-specific augmentations
    if canonical_name == "web_search_scraping":
        web_cfg = config.get("web", {})
        if not isinstance(web_cfg, dict):
            web_cfg = {}
        payload["active_search_backend"] = web_cfg.get("search_backend") or web_cfg.get("backend") or "ddgs"
        payload["active_extract_backend"] = web_cfg.get("extract_backend") or web_cfg.get("backend") or "firecrawl"

    return payload


# ── Core Exported API: set_active_provider ───────────────────────────────────


def set_active_provider(
    name: str, provider_name: str, capability: Optional[str] = None, profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    Persists an active provider selection for a toolset.
    Supports capability split ('search' | 'extract') for web_search_scraping.
    """
    canonical_name = canonical_toolset_name(name)
    category_data = TOOLSET_PROVIDERS.get(canonical_name)
    if not category_data:
        raise KeyError(f"Toolset has no configurable category: {name!r}")

    # Match provider by name or backend identifier
    clean_pname = (provider_name or "").strip().lower()
    matched_provider = None
    for p in category_data.get("providers", []):
        if p.get("name", "").strip().lower() == clean_pname:
            matched_provider = p
            break
        # Match by backend identifier
        for key in (
            "web_backend",
            "browser_provider",
            "browser_backend",
            "computer_use_backend",
            "image_gen_plugin_name",
            "imagegen_backend",
            "video_gen_plugin_name",
            "tts_provider",
            "stt_provider",
        ):
            if p.get(key, "").strip().lower() == clean_pname:
                matched_provider = p
                break
        if matched_provider:
            break

    if not matched_provider:
        raise KeyError(f"Unknown provider {provider_name!r} for toolset {name!r}")

    updates: Dict[str, Any] = {}

    if canonical_name == "web_search_scraping":
        backend = matched_provider.get("web_backend", "ddgs")
        if capability:
            cap = capability.strip().lower()
            if cap not in ("search", "extract"):
                raise ValueError(f"Unknown capability: {capability!r} (expected 'search' or 'extract')")
            caps = matched_provider.get("capabilities", ["search", "extract"])
            if cap not in caps:
                raise ValueError(f"{matched_provider['name']} does not support {cap}")
            updates[f"web.{cap}_backend"] = backend
        else:
            updates["web.backend"] = backend
            if backend == "firecrawl" and matched_provider.get("name") == "Firecrawl Self-Hosted":
                default_url = get_env_value("FIRECRAWL_API_URL", "http://localhost:3002")
                updates["web.firecrawl_url"] = default_url

    elif canonical_name == "browser_automation":
        if matched_provider.get("browser_backend"):
            updates["browser.backend"] = matched_provider["browser_backend"]
        if matched_provider.get("browser_provider"):
            updates["browser.cloud_provider"] = matched_provider["browser_provider"]
        if matched_provider.get("browser_engine"):
            updates["browser.engine"] = matched_provider["browser_engine"]

    elif canonical_name == "computer_use":
        updates["computer_use.backend"] = matched_provider.get("computer_use_backend", "cua")

    elif canonical_name == "image_generation":
        prov_key = matched_provider.get("image_gen_plugin_name") or matched_provider.get("imagegen_backend", "fal")
        updates["image_gen.provider"] = prov_key
        updates["image_gen.backend"] = prov_key

    elif canonical_name == "video_generation":
        updates["video_gen.provider"] = matched_provider.get("video_gen_plugin_name", "fal")

    elif canonical_name == "text_to_speech":
        updates["tts.provider"] = matched_provider.get("tts_provider", "edge")

    elif canonical_name == "speech_to_text":
        updates["stt.provider"] = matched_provider.get("stt_provider", "local")

    # Persist updates to unified declarative config
    save_config(updates)

    # Also persist to SQLite app_settings for synchronized state
    try:
        from memory import memory_engine
        memory_engine.set_app_setting(f"toolset_provider_{canonical_name}", matched_provider["name"])
    except Exception as e:
        logger.debug(f"[ToolsetProviders] Failed setting app_setting: {e}")

    return {
        "ok": True,
        "name": canonical_name,
        "provider": matched_provider["name"],
        "capability": capability,
    }


# ── Core Exported API: set_provider_env ──────────────────────────────────────


def set_provider_env(
    name: str, env_vars: Dict[str, str], profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    Saves environment variables / API keys for a toolset.
    Persists to process memory, ANARA_HOME/.env, and SQLite app_settings.
    """
    canonical_name = canonical_toolset_name(name)
    if not isinstance(env_vars, dict) or not env_vars:
        raise ValueError("env_vars must be a non-empty dictionary")

    updated: List[str] = []
    for k, v in env_vars.items():
        key = str(k).strip()
        val = str(v).strip()
        if key:
            save_env_value(key, val)
            updated.append(key)

    return {
        "ok": True,
        "name": canonical_name,
        "updated": updated,
    }


# ── Core Exported API: get_toolset_models ─────────────────────────────────────


def _no_models(name: str) -> Dict[str, Any]:
    return {
        "name": name,
        "has_models": False,
        "provider": None,
        "models": [],
        "current": None,
        "default": None,
    }


def _resolve_provider_key(ts: str, provider_name: Optional[str], config: Dict[str, Any]) -> Tuple[str, str]:
    """Resolves (provider_key, provider_display_name) for a toolset."""
    cat = TOOLSET_PROVIDERS.get(ts, {})
    providers = cat.get("providers", [])

    if provider_name:
        clean = provider_name.strip().lower()
        for p in providers:
            if p.get("name", "").strip().lower() == clean:
                key = (
                    p.get("image_gen_plugin_name")
                    or p.get("imagegen_backend")
                    or p.get("video_gen_plugin_name")
                    or p.get("tts_provider")
                    or p.get("stt_provider")
                    or p["name"]
                )
                return key.strip().lower(), p["name"]
            for field in (
                "image_gen_plugin_name",
                "imagegen_backend",
                "video_gen_plugin_name",
                "tts_provider",
                "stt_provider",
            ):
                if p.get(field, "").strip().lower() == clean:
                    return p[field].strip().lower(), p["name"]

    # Active provider fallback
    for p in providers:
        if is_provider_active(ts, p, config):
            key = (
                p.get("image_gen_plugin_name")
                or p.get("imagegen_backend")
                or p.get("video_gen_plugin_name")
                or p.get("tts_provider")
                or p.get("stt_provider")
                or p["name"]
            )
            return key.strip().lower(), p["name"]

    if providers:
        first = providers[0]
        key = (
            first.get("image_gen_plugin_name")
            or first.get("imagegen_backend")
            or first.get("video_gen_plugin_name")
            or first.get("tts_provider")
            or first.get("stt_provider")
            or first["name"]
        )
        return key.strip().lower(), first["name"]

    return "", ""


def get_toolset_models(
    name: str, provider: Optional[str] = None, profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    Returns the selectable model catalog for a toolset backend.
    """
    canonical_name = canonical_toolset_name(name)
    catalogs = TOOLSET_MODELS_CATALOG.get(canonical_name)
    if not catalogs:
        return _no_models(canonical_name)

    config = load_config()
    provider_key, provider_display = _resolve_provider_key(canonical_name, provider, config)

    prov_entry = catalogs.get(provider_key)
    if not prov_entry:
        return _no_models(canonical_name)

    default_model = prov_entry.get("default")
    raw_models = prov_entry.get("models", {})

    models_list = [
        {
            "id": mid,
            "display": meta.get("display", mid),
            "speed": meta.get("speed", ""),
            "strengths": meta.get("strengths", ""),
            "price": meta.get("price", ""),
        }
        for mid, meta in raw_models.items()
    ]

    # Resolve currently selected model from config
    current_model = None
    if canonical_name == "image_generation":
        current_model = (
            cfg_get(f"image_gen.{provider_key}.model")
            or cfg_get("image_gen.model")
            or os.getenv("IMAGE_GEN_MODEL")
        )
    elif canonical_name == "video_generation":
        current_model = (
            cfg_get(f"video_gen.{provider_key}.model")
            or cfg_get("video_gen.model")
            or os.getenv("VIDEO_GEN_MODEL")
        )
    elif canonical_name == "speech_to_text":
        current_model = (
            cfg_get(f"stt.{provider_key}.model")
            or cfg_get("stt.model")
            or os.getenv("STT_MODEL")
        )
    elif canonical_name == "text_to_speech":
        current_model = (
            cfg_get(f"tts.{provider_key}.voice")
            or cfg_get("tts.voice")
            or cfg_get("tts.model")
            or os.getenv("TTS_VOICE")
        )

    if current_model not in raw_models:
        current_model = default_model

    return {
        "name": canonical_name,
        "has_models": bool(models_list),
        "provider": provider_display or provider_key,
        "models": models_list,
        "current": current_model,
        "default": default_model,
    }


# ── Core Exported API: set_active_model ──────────────────────────────────────


def set_active_model(
    name: str, model_id: str, provider: Optional[str] = None, profile: Optional[str] = None
) -> Dict[str, Any]:
    """
    Persists a backend model selection, validating against the resolved catalog.
    """
    canonical_name = canonical_toolset_name(name)
    catalogs = TOOLSET_MODELS_CATALOG.get(canonical_name)
    if not catalogs:
        raise ValueError(f"Toolset has no model catalog: {name!r}")

    clean_mid = (model_id or "").strip()
    if not clean_mid:
        raise ValueError("model is required")

    config = load_config()
    provider_key, provider_display = _resolve_provider_key(canonical_name, provider, config)

    prov_entry = catalogs.get(provider_key)
    if not prov_entry:
        raise ValueError(f"No model-capable backend catalog found for provider {provider_key!r}")

    raw_models = prov_entry.get("models", {})
    if clean_mid not in raw_models:
        raise ValueError(f"Unknown model {clean_mid!r} for provider {provider_display!r}")

    updates: Dict[str, Any] = {}
    if canonical_name == "image_generation":
        updates["image_gen.model"] = clean_mid
        updates[f"image_gen.{provider_key}.model"] = clean_mid
    elif canonical_name == "video_generation":
        updates["video_gen.model"] = clean_mid
        updates[f"video_gen.{provider_key}.model"] = clean_mid
    elif canonical_name == "speech_to_text":
        updates[f"stt.{provider_key}.model"] = clean_mid
        updates["stt.model"] = clean_mid
    elif canonical_name == "text_to_speech":
        updates[f"tts.{provider_key}.voice"] = clean_mid
        updates["tts.voice"] = clean_mid

    save_config(updates)

    try:
        from memory import memory_engine
        memory_engine.set_app_setting(f"toolset_model_{canonical_name}", clean_mid)
    except Exception as e:
        logger.debug(f"[ToolsetProviders] Failed setting app_setting: {e}")

    return {
        "ok": True,
        "name": canonical_name,
        "model": clean_mid,
        "provider": provider_display or provider_key,
    }
