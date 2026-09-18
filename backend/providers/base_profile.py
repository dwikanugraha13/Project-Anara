"""
base_profile.py — Unified Abstract Provider Profile Interface for Project Anara.
Anara Standard providers/base.py:
Decouples inference execution into polymorphic provider profiles.
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional


class BaseProviderProfile(ABC):
    """Abstract base class for all LLM providers in Project Anara."""

    name: str

    @abstractmethod
    def can_handle(self, model_id: str) -> bool:
        """Returns True if this provider can serve the given model_id."""
        pass

    @abstractmethod
    async def stream_chat(
        self,
        model_id: str,
        user_prompt: str,
        system_instruction: str = "",
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        usage_out: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """Streams text chunks in real-time."""
        pass

    @abstractmethod
    async def generate_chat(
        self,
        model_id: str,
        user_prompt: str,
        system_instruction: str = "",
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        read_only: bool = False,
        usage_out: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Executes a single non-streaming conversational generation turn."""
        pass
