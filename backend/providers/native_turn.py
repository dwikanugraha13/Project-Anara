"""
native_turn.py — Uniform DTOs for Native Structured Tool-Use (Anara Enterprise Architecture).

Provides a provider-agnostic representation for single-turn model responses containing
native tool calls, narrative content, reasoning signatures, and usage across
Anthropic, Gemini, OpenAI, Codex, and custom providers.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class TurnUsage:
    """Canonical token usage accounting with prompt caching and reasoning support (Anara Enterprise Architecture)."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens or (self.prompt_tokens + self.completion_tokens),
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "reasoning_tokens": self.reasoning_tokens,
        }


@dataclass
class NativeToolCall:
    """Represents a single native tool call emitted by an LLM."""
    call_id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    raw_arguments: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "call_id": self.call_id,
            "name": self.name,
            "arguments": self.arguments,
        }
        if self.raw_arguments is not None:
            d["raw_arguments"] = self.raw_arguments
        return d


@dataclass
class NativeTurnResult:
    """Uniform container for a single LLM response turn in the Native ReAct loop (Anara Enterprise Architecture)."""
    text: Optional[str] = None
    tool_calls: List[NativeToolCall] = field(default_factory=list)
    reasoning: Optional[str] = None
    thinking_signature: Optional[str] = None
    thinking_blocks: Optional[List[Dict[str, Any]]] = None
    finish_reason: Optional[str] = None
    raw_response: Any = None
    usage: Optional[Union[TurnUsage, Dict[str, int]]] = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def clean_text(self) -> str:
        return (self.text or "").strip()

    @property
    def is_tool_call_stop(self) -> bool:
        fr = (self.finish_reason or "").lower()
        return self.has_tool_calls or fr in ("tool_calls", "tool_use", "function_call")

    @property
    def is_length_truncated(self) -> bool:
        fr = (self.finish_reason or "").lower()
        return fr in ("length", "max_tokens", "max_token")

    def get_canonical_usage(self) -> TurnUsage:
        if isinstance(self.usage, TurnUsage):
            return self.usage
        if isinstance(self.usage, dict):
            return TurnUsage(
                prompt_tokens=self.usage.get("prompt_tokens") or self.usage.get("input_tokens", 0),
                completion_tokens=self.usage.get("completion_tokens") or self.usage.get("output_tokens", 0),
                total_tokens=self.usage.get("total_tokens", 0),
                cache_read_tokens=self.usage.get("cache_read_tokens") or self.usage.get("cache_read_input_tokens", 0),
                cache_write_tokens=self.usage.get("cache_write_tokens") or self.usage.get("cache_creation_input_tokens", 0),
                reasoning_tokens=self.usage.get("reasoning_tokens", 0),
            )
        return TurnUsage()

