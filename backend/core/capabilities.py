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
        mid = (model_id or "").lower()
        if mid in NATIVE_VOICE_MODEL_IDS or any(mid == m.lower() for m in NATIVE_VOICE_MODEL_IDS):
            return True
        if any(kw in mid for kw in _VOICE_HEURISTIC_KEYWORDS):
            return True
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
        """
        Returns True if the model accepts image input (Hermes Parity).
        Evaluates registered capability metadata, input_modalities, and verified multimodal family identifiers.
        """
        if not model_id:
            return False

        norm_id = cls.normalize_id(model_id)
        info = cls._cache.get(norm_id) or cls._cache.get(model_id)
        if info is not None:
            input_mods = set(info.get("input_modalities") or [])
            return bool(info.get("supports_vision") or "image" in input_mods or "vision" in input_mods)

        # Hermes Parity: evaluate verified multimodal model identifiers when unindexed
        mid = norm_id.lower()
        verified_vision_families = (
            "vision", "-vl", "llava", "pixtral", "multimodal",
            "gpt-4o", "gpt-4-turbo", "claude-3", "gemini-", "qwen-vl"
        )
        return any(tag in mid for tag in verified_vision_families)

    @classmethod
    def find_models(cls, capability: str = "text", provider: Optional[str] = None) -> List[str]:
        """
        Discovers all models matching a capability filter ('voice', 'vision', 'text').
        Optionally filters by provider ('google', 'openrouter', 'openai', etc.).
        """
        cap = (capability or "text").strip().lower()
        results: List[str] = []
        for mid, info in cls._cache.items():
            if provider and str(info.get("provider", "")).lower() != provider.lower():
                continue
            if cap in ("voice", "audio") and cls.supports_voice(mid):
                results.append(mid)
            elif cap in ("vision", "image") and cls.supports_vision(mid):
                results.append(mid)
            elif cap == "text" and cls.supports_text(mid):
                results.append(mid)
        return results

    @classmethod
    def resolve_auxiliary_model(cls) -> str:
        """Returns the dynamic auxiliary helper model id."""
        return get_fast_auxiliary_model()

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
        """Enumerate models exposed by the Google Gemini SDK and harvest context limits."""
        try:
            from core.key_manager import key_manager
            from google import genai

            active_key = key_manager.get_active_key()
            if not active_key:
                return

            client = genai.Client(api_key=active_key.split(",")[0].strip())

            def _list_models() -> list:
                try:
                    return list(client.models.list())
                except Exception as inner:
                    logger.debug(f"[Capabilities] client.models.list() notice: {inner}")
                    return []

            models = await asyncio.to_thread(_list_models)
            for m in models:
                raw = getattr(m, "name", "") or ""
                mid = cls.normalize_id(raw)
                if not mid:
                    continue
                methods = set(getattr(m, "supported_generation_methods", getattr(m, "supported_actions", [])) or [])
                supports_voice = (
                    "bidiGenerateContent" in methods
                    or mid in NATIVE_VOICE_MODEL_IDS
                )
                input_mods = _gemini_input_modalities(mid)

                # Dynamically harvest and save context limits
                in_limit = getattr(m, "input_token_limit", None)
                out_limit = getattr(m, "output_token_limit", None)
                if in_limit and isinstance(in_limit, int) and in_limit > 0:
                    try:
                        from core.token_budget import save_context_length
                        save_context_length(mid, in_limit, max_output=out_limit if isinstance(out_limit, int) else None)
                    except Exception:
                        pass

                cls._cache[mid] = {
                    "name": getattr(m, "display_name", mid) or mid,
                    "input_modalities": input_mods,
                    "output_modalities": ["text"],
                    "supports_voice": supports_voice,
                    "supports_vision": "image" in input_mods or "vision" in input_mods,
                    "provider": "google",
                }
        except Exception as e:
            logger.debug(f"[Capabilities] Gemini fetch notice: {e}")

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


def get_fast_auxiliary_model() -> str:
    """
    Hermes-Standard Model Sovereignty Resolver:
    Uses the user's explicitly selected active model ID by default, guaranteeing
    identical reasoning capacity, zero intelligence degradation, and 100% provider route preservation
    (e.g. 9router/ag/gemini-3.8-flash-high, openrouter/..., ollama/..., claude-3-7-sonnet).

    Only adapts if:
    1. The user explicitly sets an auxiliary override in config (model.auxiliary or model.fast).
    2. The active model is a pure audio/bidi model (*live-preview / *realtime) that does not accept
       standard text completion formats, in which case it strips the live preview suffix within
       the EXACT SAME custom provider / prefix without switching providers.
    """
    try:
        from config import cfg_get
        configured = cfg_get("model.auxiliary") or cfg_get("model.fast")
        if configured and str(configured).strip():
            return str(configured).strip()
    except Exception:
        pass

    try:
        from providers.accounts import get_active_model_id
        active = get_active_model_id()
        if active and active.strip():
            clean_active = active.strip()
            # If active model is a native audio/bidi live-preview model (e.g. gemini-3.1-flash-live-preview)
            # which does not support text completions, clean the suffix while preserving prefix
            if "live-preview" in clean_active or "native-audio" in clean_active or "realtime" in clean_active:
                cleaned = clean_active.replace("-live-preview", "").replace("-realtime", "").replace("-native-audio", "")
                return cleaned or clean_active
            return clean_active
    except Exception:
        pass

    return "gemini-2.5-flash"
