"""
native_turn.py — Uniform DTOs for Native Structured Tool-Use (Hermes & Claude Code Parity).

Provides a provider-agnostic representation for single-turn model responses containing
native tool calls and narrative content across Anthropic, Gemini, OpenAI, and custom providers.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class NativeToolCall:
    """Represents a single native tool call emitted by an LLM."""
    call_id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "name": self.name,
            "arguments": self.arguments,
        }


@dataclass
class NativeTurnResult:
    """Uniform container for a single LLM response turn in the Native ReAct loop."""
    text: Optional[str] = None
    tool_calls: List[NativeToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None
    raw_response: Any = None
    usage: Optional[Dict[str, int]] = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def clean_text(self) -> str:
        return (self.text or "").strip()
