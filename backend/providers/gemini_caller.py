"""
gemini_caller.py — Google GenAI Native SDK & Live Turn Caller for Project Anara.
Handles raw streaming text generation and structured function calling with deep dictionary mapping.
"""

from __future__ import annotations

import asyncio
import collections.abc
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("anara.gemini_caller")


async def _make_gemini_raw_call(
    model_name: str,
    msgs: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    on_chunk: Optional[Callable[[str], Any]] = None,
) -> str:
    """OpenAI-to-Gemini raw provider adapter (Anara Agent gemini_native_adapter Parity)."""
    from core import key_manager
    from google.genai import types

    sys_msg = next((m["content"] for m in msgs if m["role"] == "system"), "")
    cfg_kwargs: Dict[str, Any] = {"temperature": temperature}
    if max_tokens is not None and max_tokens > 0:
        cfg_kwargs["max_output_tokens"] = max_tokens
    if sys_msg:
        cfg_kwargs["system_instruction"] = sys_msg.strip()
    config = types.GenerateContentConfig(**cfg_kwargs)

    contents = []
    for m in msgs:
        r = m.get("role", "")
        c = m.get("content", "")
        if r == "system":
            continue
        role = "user" if r == "user" else "model"
        if contents and contents[-1].role == role:
            contents[-1].parts.append(types.Part.from_text(text=c))
        else:
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=c)]))

    if not contents:
        contents = [types.Content(role="user", parts=[types.Part.from_text(text="Continue.")])]

    async def _exec(client):
        chunks = []
        try:
            stream = await client.aio.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=config,
            )
            async for chunk in stream:
                txt = chunk.text or ""
                if txt:
                    chunks.append(txt)
                    if on_chunk:
                        res = on_chunk(txt)
                        if asyncio.iscoroutine(res):
                            await res
            return "".join(chunks)
        except Exception:
            res = await client.aio.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
            txt = res.text or ""
            if on_chunk and txt:
                r = on_chunk(txt)
                if asyncio.iscoroutine(r):
                    await r
            return txt

    return await key_manager.execute_with_failover(_exec)


async def _make_gemini_native_turn(
    model_name: str,
    contents: List[Any],
    tools: List[Any],
    system_instruction: str = "",
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    on_chunk: Optional[Callable[[str], Any]] = None,
    reasoning_effort: Optional[str] = None,
) -> Any:
    """Executes a single native tool-calling turn via Google GenAI SDK (Anara Architecture)."""
    from core.key_manager import key_manager
    from google.genai import types
    from providers.native_turn import NativeToolCall, NativeTurnResult

    def _deep_to_dict(obj: Any) -> Any:
        if isinstance(obj, collections.abc.Mapping) or hasattr(obj, "items"):
            return {k: _deep_to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, collections.abc.Sequence) and not isinstance(obj, (str, bytes)):
            return [_deep_to_dict(v) for v in obj]
        return obj

    cfg_kwargs: Dict[str, Any] = {
        "temperature": temperature,
        "tools": tools,
    }
    if max_tokens is not None and max_tokens > 0:
        cfg_kwargs["max_output_tokens"] = max_tokens
    if system_instruction and system_instruction.strip():
        cfg_kwargs["system_instruction"] = system_instruction.strip()
    if reasoning_effort:
        try:
            from core.reasoning_effort import to_gemini_thinking
            t_conf = to_gemini_thinking(reasoning_effort, model_name)
            if "thinking_config" in t_conf:
                cfg_kwargs["thinking_config"] = t_conf["thinking_config"]
        except Exception as e_think:
            logger.debug(f"[GeminiNativeTurn] thinking_config setup warning: {e_think}")

    config = types.GenerateContentConfig(**cfg_kwargs)

    async def _exec(client):
        res = await client.aio.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )
        text_parts = []
        tool_calls = []

        if res.candidates and len(res.candidates) > 0:
            cand = res.candidates[0]
            if cand.content and cand.content.parts:
                for idx, part in enumerate(cand.content.parts):
                    if getattr(part, "text", None):
                        text_parts.append(part.text)
                        if on_chunk:
                            r = on_chunk(part.text)
                            if asyncio.iscoroutine(r):
                                await r
                    if getattr(part, "function_call", None):
                        fc = part.function_call
                        call_id = f"call_{fc.name}_{idx}"
                        args_dict = _deep_to_dict(fc.args) if fc.args else {}
                        tool_calls.append(NativeToolCall(
                            call_id=call_id,
                            name=fc.name,
                            arguments=args_dict
                        ))

        full_text = "".join(text_parts)
        cand_content = res.candidates[0].content if (res.candidates and res.candidates[0].content) else None
        finish_reason = None
        usage_res = None
        if res.candidates:
            finish_reason = getattr(res.candidates[0], "finish_reason", None)
            if finish_reason is not None:
                finish_reason = str(finish_reason)
        if hasattr(res, "usage_metadata") and res.usage_metadata:
            u = res.usage_metadata
            usage_res = {
                "prompt_tokens": getattr(u, "prompt_token_count", 0) or 0,
                "completion_tokens": getattr(u, "candidates_token_count", 0) or 0,
                "total_tokens": getattr(u, "total_token_count", 0) or 0,
            }
        return NativeTurnResult(
            text=full_text,
            tool_calls=tool_calls,
            raw_response=cand_content,
            finish_reason=finish_reason,
            usage=usage_res,
        )

    return await key_manager.execute_with_failover(_exec)
