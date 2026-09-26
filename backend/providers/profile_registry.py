"""
profile_registry.py — Provider Profile Registry & Resolver for Project Anara.
Anara Enterprise Architecture: Thread-safe, lazy-initialized, deduplicated
profile registration with graceful fallback and diagnostic logging.
"""

import logging
import threading
from typing import List, Optional
from .base_profile import BaseProviderProfile

logger = logging.getLogger(__name__)

_LOCK = threading.RLock()
_REGISTERED_PROFILES: List[BaseProviderProfile] = []
_DEFAULT_FALLBACK_PROFILE: Optional[BaseProviderProfile] = None


def _init_default_profiles_if_needed() -> None:
    """Lazy initialization of standard profiles to prevent circular import cascades."""
    global _DEFAULT_FALLBACK_PROFILE
    with _LOCK:
        if not _REGISTERED_PROFILES:
            from .profile_implementations import (
                GeminiProviderProfile,
                CodexOpenAIProviderProfile,
                AnthropicProviderProfile,
                OpenAICompatibleProviderProfile,
            )
            fallback = OpenAICompatibleProviderProfile()
            _REGISTERED_PROFILES.extend([
                GeminiProviderProfile(),
                CodexOpenAIProviderProfile(),
                AnthropicProviderProfile(),
                fallback,
            ])
            _DEFAULT_FALLBACK_PROFILE = fallback


def get_registered_profiles() -> List[BaseProviderProfile]:
    """Returns all active provider profile handlers."""
    _init_default_profiles_if_needed()
    with _LOCK:
        return list(_REGISTERED_PROFILES)


def register_provider_profile(profile: BaseProviderProfile) -> None:
    """Dynamically registers or updates a provider profile thread-safely."""
    if not isinstance(profile, BaseProviderProfile):
        raise TypeError(f"Expected BaseProviderProfile instance, got {type(profile).__name__}")
    _init_default_profiles_if_needed()
    with _LOCK:
        _REGISTERED_PROFILES[:] = [p for p in _REGISTERED_PROFILES if p.name != profile.name]
        _REGISTERED_PROFILES.insert(0, profile)
    logger.info(f"[ProfileRegistry] Registered provider profile: {profile.name}")


def unregister_provider_profile(name: str) -> bool:
    """Removes a provider profile by name."""
    _init_default_profiles_if_needed()
    with _LOCK:
        initial_len = len(_REGISTERED_PROFILES)
        _REGISTERED_PROFILES[:] = [p for p in _REGISTERED_PROFILES if p.name != name]
        return len(_REGISTERED_PROFILES) < initial_len


def normalize_model_id(model_id: str) -> str:
    """Normalizes model IDs removing leading/trailing whitespaces and prefixes."""
    return (model_id or "").strip()


def resolve_provider_profile(model_id: str) -> BaseProviderProfile:
    """Resolves and returns the appropriate ProviderProfile for a given model ID."""
    _init_default_profiles_if_needed()
    clean_id = normalize_model_id(model_id)
    with _LOCK:
        for profile in _REGISTERED_PROFILES:
            if profile.can_handle(clean_id):
                return profile

        if _DEFAULT_FALLBACK_PROFILE is not None:
            logger.debug(
                f"[ProfileRegistry] Model '{model_id}' did not match any registered provider; "
                f"falling back to '{_DEFAULT_FALLBACK_PROFILE.name}'."
            )
            return _DEFAULT_FALLBACK_PROFILE

        if _REGISTERED_PROFILES:
            logger.debug(
                f"[ProfileRegistry] Model '{model_id}' unmatched and default fallback unset; "
                f"falling back to '{_REGISTERED_PROFILES[-1].name}'."
            )
            return _REGISTERED_PROFILES[-1]

    raise RuntimeError(f"[ProfileRegistry] No provider profiles registered to handle '{model_id}'.")

