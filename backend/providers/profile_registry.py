"""
profile_registry.py — Provider Profile Registry & Resolver for Project Anara.
Anara Standard providers architecture.
"""

import logging
from typing import List, Optional
from .base_profile import BaseProviderProfile
from .profile_implementations import (
    GeminiProviderProfile,
    CodexOpenAIProviderProfile,
    AnthropicProviderProfile,
    OpenAICompatibleProviderProfile,
)

logger = logging.getLogger(__name__)

_REGISTERED_PROFILES: List[BaseProviderProfile] = [
    GeminiProviderProfile(),
    CodexOpenAIProviderProfile(),
    AnthropicProviderProfile(),
    OpenAICompatibleProviderProfile(),
]


def get_registered_profiles() -> List[BaseProviderProfile]:
    """Returns all active provider profile handlers."""
    return list(_REGISTERED_PROFILES)


def register_provider_profile(profile: BaseProviderProfile) -> None:
    """Dynamically registers a new provider profile."""
    _REGISTERED_PROFILES.insert(0, profile)
    logger.info(f"[ProfileRegistry] Registered provider profile: {profile.name}")


def resolve_provider_profile(model_id: str) -> BaseProviderProfile:
    """Resolves and returns the appropriate ProviderProfile for a given model ID."""
    clean_id = (model_id or "").strip()
    for profile in _REGISTERED_PROFILES:
        if profile.can_handle(clean_id):
            return profile

    # Default fallback profile
    return _REGISTERED_PROFILES[-1]
