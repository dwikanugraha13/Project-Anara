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
    supports_native_tools: bool = True
    supports_prompt_caching: bool = False
    supports_thinking: bool = False

    def is_available(self) -> bool:
        """Returns True if provider keys or credentials are configured."""
        return True

    def format_tools(self, tools: List[Dict[str, Any]]) -> List[Any]:
        """Transforms platform tools into provider-specific wire schemas."""
        return tools

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
        progress_cb: Optional[Callable[[Dict[str, Any]], Any]] = None,
        token_cb: Optional[Callable[[str], Any]] = None,
        intercept_mutating_tools: bool = False,
        platform: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """Executes a full multi-turn conversational or ReAct tool turn (Anara Standard)."""
        pass
