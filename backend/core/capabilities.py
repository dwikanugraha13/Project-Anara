"""
model_capabilities.py

Capability-Aware Model Registry:
- Fetches model metadata from Google Gemini SDK list_models and provider router.
- Determines whether a model supports:
  * Voice/Audio (native real-time multimodal: Live API / Realtime)
  * Vision (image input)
  * Text (output text modality)
- Caches results in memory for 1 hour to avoid hammering external APIs.

This module is read-only (no file I/O, no DB writes). All cache lives in process RAM.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# --- Public constants (canonical Gemini Live Preview model ids) ---------------
# These are the ONLY model ids known to support bidiGenerateContent (native voice).
# Auto-discovered entries from list_models() are merged in at runtime.
NATIVE_VOICE_MODEL_IDS: set = {
    "gemini-2.0-flash-live-preview",
    "gemini-2.5-flash-live-preview",
    "gemini-3.0-flash-live-preview",
    "gemini-3.1-flash-live-preview",
    "models/gemini-2.0-flash-live-preview",
    "models/gemini-2.5-flash-live-preview",
    "models/gemini-3.0-flash-live-preview",
    "models/gemini-3.1-flash-live-preview",
}

# Heuristic substring used as fallback when API metadata is unavailable
# or the model id format is not yet known to us.
_VOICE_HEURISTIC_KEYWORDS: tuple = (
    "live-preview",
    "realtime",
    "audio-preview",
    "voice-preview",
)


class ModelCapabilityRegistry:
    """
    In-memory cache of model capability metadata fetched from provider APIs.
    - `cache` maps canonical model_id -> capability dict.
    - `last_refresh` is the epoch seconds of the last successful refresh.
    - `ttl` is the cache lifetime in seconds (default 1 hour).
    """

    _cache: Dict[str, Dict[str, Any]] = {}
    _last_refresh: float = 0.0
    _ttl: int = 3600
    _lock: Optional[asyncio.Lock] = None

    # --- Public API -----------------------------------------------------------

    @classmethod
    def get(cls, model_id: str) -> Optional[Dict[str, Any]]:
        """Returns the cached capability dict for a model, or None if not cached."""
        return cls._cache.get(model_id)

    @classmethod
    def supports_voice(cls, model_id: str) -> bool:
        """Returns True if the model is known to support native real-time voice."""
        info = cls._cache.get(model_id)
        if info is not None:
            return bool(info.get("supports_voice", False))
        # Fallback heuristic when not yet cached
        mid = (model_id or "").lower()
        if any(kw in mid for kw in _VOICE_HEURISTIC_KEYWORDS):
            # Only Gemini/Google models have native Live API right now.
            return ("gemini" in mid) or ("google" in mid)
        return False

    @classmethod
    def supports_text(cls, model_id: str) -> bool:
        """Returns True if the model can produce text output."""
        info = cls._cache.get(model_id)
        if info is None:
            # Default assumption: unknown models are text-capable.
            return True
        return "text" in (info.get("output_modalities") or [])

    @classmethod
    def supports_vision(cls, model_id: str) -> bool:
        """Returns True if the model accepts image input."""
        info = cls._cache.get(model_id)
        if info is not None:
            return bool(info.get("supports_vision", False))
        mid = (model_id or "").lower()
        return any(kw in mid for kw in ["vision", "flash", "gpt-4o", "4o", "claude-3-7", "claude-3-5"])

    @classmethod
    def normalize_id(cls, model_id: str) -> str:
        """Strips the 'models/' prefix that the Gemini SDK adds to model names."""
        if not model_id:
            return ""
        return model_id[7:] if model_id.startswith("models/") else model_id

    # --- Cache management -----------------------------------------------------

    @classmethod
    async def _get_lock(cls) -> asyncio.Lock:
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    async def refresh(cls, force: bool = False) -> None:
        """Fetch capabilities from providers in parallel, throttled by TTL."""
        if not force and cls._cache and (time.time() - cls._last_refresh) < cls._ttl:
            return
        lock = await cls._get_lock()
        async with lock:
            if not force and cls._cache and (time.time() - cls._last_refresh) < cls._ttl:
                return
            logger.info("[Capabilities] Refreshing model capability cache...")
            await asyncio.gather(
                cls._fetch_gemini_models(),
                return_exceptions=True,
            )
            cls._last_refresh = time.time()
            logger.info(f"[Capabilities] Cache refreshed: {len(cls._cache)} models indexed.")

    @classmethod
    async def _fetch_gemini_models(cls) -> None:
        """Enumerate models exposed by the Google Gemini SDK."""
        try:
            # Import lazily so missing dependency does not break unrelated flows.
            import google.generativeai as genai  # type: ignore

            def _list_models() -> list:
                try:
                    return list(genai.list_models())
                except Exception as inner:
                    logger.warning(f"[Capabilities] genai.list_models() failed: {inner}")
                    return []

            models = await asyncio.to_thread(_list_models)
            for m in models:
                # m.name like 'models/gemini-2.5-flash'
                raw = getattr(m, "name", "") or ""
                mid = cls.normalize_id(raw)
                if not mid:
                    continue
                methods = set(getattr(m, "supported_generation_methods", []) or [])
                # Gemini Live Preview supports real-time audio via bidiGenerateContent.
                supports_voice = (
                    "bidiGenerateContent" in methods
                    or mid in NATIVE_VOICE_MODEL_IDS
                )
                cls._cache[mid] = {
                    "name": getattr(m, "display_name", mid) or mid,
                    "input_modalities": _gemini_input_modalities(mid),
                    "output_modalities": ["text"],  # All current Gemini chat models emit text
                    "supports_voice": supports_voice,
                    "supports_vision": "vision" in mid.lower() or "flash" in mid.lower(),
                    "provider": "google",
                }
        except Exception as e:
            logger.warning(f"[Capabilities] Gemini fetch error: {e}")

    @classmethod
    def seed_live_voice_from_key_manager(cls) -> int:
        """
        Inspect the active Gemini key pool via key_manager and register
        Live Preview model entries (with voice=true) so the UI exposes them
        immediately, even before a successful network fetch.

        Returns the number of new live-voice entries seeded.
        """
        try:
            from core.key_manager import key_manager  # local import: avoids circular at startup
        except Exception as e:
            logger.debug(f"[Capabilities] key_manager unavailable: {e}")
            return 0
        if key_manager.total_keys <= 0:
            return 0
        seeded = 0
        for mid in NATIVE_VOICE_MODEL_IDS:
            if mid in cls._cache:
                # Upgrade existing entry if supports_voice is missing/False
                if not cls._cache[mid].get("supports_voice"):
                    cls._cache[mid]["supports_voice"] = True
                    if "audio" not in cls._cache[mid].get("input_modalities", []):
                        cls._cache[mid].setdefault("input_modalities", []).append("audio")
                    if "audio" not in cls._cache[mid].get("output_modalities", []):
                        cls._cache[mid].setdefault("output_modalities", []).append("audio")
                    seeded += 1
                continue
            cls._cache[mid] = {
                "name": cls.normalize_id(mid),
                "input_modalities": ["text", "audio"],
                "output_modalities": ["text", "audio"],
                "supports_voice": True,
                "supports_text": True,
                "supports_vision": False,
                "provider": "google",
                "is_live_preview": True,
            }
            seeded += 1
        return seeded


def _gemini_input_modalities(model_id: str) -> List[str]:
    """Infer supported Gemini input modalities from model id naming conventions."""
    mid = model_id.lower()
    mods: List[str] = ["text"]
    if "vision" in mid or "flash" in mid or "pro" in mid or "ultra" in mid:
        mods.append("image")
    if "audio" in mid or "live" in mid or "realtime" in mid:
        mods.append("audio")
    return mods
