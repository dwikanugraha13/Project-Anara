from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from providers.think_scrubber import (
    StreamingThinkScrubber,
    THINK_TAG_NAMES,
    THINK_OPEN_TAGS,
    THINK_CLOSE_TAGS,
)


async def stream_universal_chat_model(
    model_id: str,
    user_prompt: str,
    system_instruction: str = "",
    max_tokens: Optional[int] = None,
    temperature: float = 0.7,
    usage_out: Optional[Dict[str, Any]] = None,
):
    """
    Polymorphic streaming entrypoint (Anara Enterprise Architecture).
    Routes dynamically through ProfileRegistry with integrated StreamingThinkScrubber.
    Zero static hardcoded model shortcuts: 100% Open-Closed Principle compliant.
    """
    scrubber = StreamingThinkScrubber()

    # 1. Polymorphic Profile Streaming
    try:
        from .profile_registry import resolve_provider_profile
        profile = resolve_provider_profile(model_id)
        has_yielded = False
        async for chunk in profile.stream_chat(
            model_id=model_id,
            user_prompt=user_prompt,
            system_instruction=system_instruction,
            max_tokens=max_tokens,
            temperature=temperature,
            usage_out=usage_out,
        ):
            if chunk:
                cleaned = scrubber.feed(chunk)
                if cleaned:
                    has_yielded = True
                    yield cleaned
        tail = scrubber.flush()
        if tail:
            has_yielded = True
            yield tail
        if has_yielded:
            return
    except Exception as e_prof:
        logger.warning(f"[Stream] Profile stream error for '{model_id}': {e_prof}")

    # 2. Fallback: Full non-streaming call on primary model
    try:
        full = await call_universal_chat_model(
            model_id=model_id,
            user_prompt=user_prompt,
            system_instruction=system_instruction,
            max_tokens=max_tokens,
            temperature=temperature,
            read_only=False,
        )
        if full:
            cleaned_full = _strip_think_blocks(full)
            if cleaned_full:
                yield cleaned_full
                return
    except Exception as e_call:
        logger.warning(f"[Stream] Non-streaming primary call error for '{model_id}': {e_call}")

    # 3. Fallback: Multi-tier fallback model ladder (Anara Standard)
    from .accounts import get_fallback_model_id
    fallback_model = get_fallback_model_id()
    if fallback_model and fallback_model != model_id:
        logger.info(f"[Stream] Primary model '{model_id}' failed; engaging fallback ladder to '{fallback_model}'...")
        try:
            from .profile_registry import resolve_provider_profile
            fb_profile = resolve_provider_profile(fallback_model)
            scrubber.reset()
            has_yielded = False
            async for chunk in fb_profile.stream_chat(
                model_id=fallback_model,
                user_prompt=user_prompt,
                system_instruction=system_instruction,
                max_tokens=max_tokens,
                temperature=temperature,
                usage_out=usage_out,
            ):
                if chunk:
                    cleaned = scrubber.feed(chunk)
                    if cleaned:
                        has_yielded = True
                        yield cleaned
            tail = scrubber.flush()
            if tail:
                has_yielded = True
                yield tail
            if has_yielded:
                return
        except Exception as e_fb:
            logger.warning(f"[Stream] Fallback ladder stream error for '{fallback_model}': {e_fb}")


from providers.payload_parser import (
    _robust_parse_json,
    _sanitize_lead_narration,
    _format_empty_model_notice,
    _strip_think_blocks,
    _clean_model_chat_text,
    _extract_json_balanced,
    _extract_and_parse_tool_calls,
    _extract_and_parse_tool_call,
    _build_closing_history,
)


from providers.agent_loops import (
    _execute_native_agent_loop,
    _execute_json_agent_loop,
)



from providers.gemini_caller import (
    _make_gemini_raw_call,
    _make_gemini_native_turn,
)


async def call_universal_chat_model(
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
    reasoning_effort: Optional[str] = None,
) -> Any:
    """
    Polymorphic universal model caller (Anara Standard).
    Dynamically resolves provider profile via ProfileRegistry and executes through the unified ReAct loop.
    Incorporates multi-tier fallback ladder if primary model is unavailable or encounters fatal failure.
    Zero static hardcoded model shortcuts: Open-Closed Principle compliant.
    """
    from .profile_registry import resolve_provider_profile
    from .accounts import get_fallback_model_id

    try:
        profile = resolve_provider_profile(model_id)
        return await profile.generate_chat(
            model_id=model_id,
            user_prompt=user_prompt,
            system_instruction=system_instruction,
            max_tokens=max_tokens,
            temperature=temperature,
            read_only=read_only,
            progress_cb=progress_cb,
            token_cb=token_cb,
            intercept_mutating_tools=intercept_mutating_tools,
            platform=platform,
            reasoning_effort=reasoning_effort,
        )
    except Exception as e_prim:
        from core.error_classifier import classify_api_error
        classified = classify_api_error(e_prim, attempt=1, provider=model_id)

        # Smart Retry Ladder: If error is transient (e.g. 429 rate limit or 503 overload), perform quick jittered backoff retry
        if classified.retryable and not classified.should_fallback and classified.backoff_seconds <= 6.0:
            logger.info(f"[ModelCaller] Primary model error is transient ({classified.reason.value}). Retrying after {classified.backoff_seconds:.1f}s backoff...")
            await asyncio.sleep(classified.backoff_seconds)
            try:
                profile = resolve_provider_profile(model_id)
                return await profile.generate_chat(
                    model_id=model_id,
                    user_prompt=user_prompt,
                    system_instruction=system_instruction,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    read_only=read_only,
                    progress_cb=progress_cb,
                    token_cb=token_cb,
                    intercept_mutating_tools=intercept_mutating_tools,
                    platform=platform,
                    reasoning_effort=reasoning_effort,
                )
            except Exception as e_retry:
                logger.warning(f"[ModelCaller] Primary retry after backoff also failed: {e_retry}")
                e_prim = e_retry

        fallback_model = get_fallback_model_id()
        if fallback_model and fallback_model != model_id:
            logger.warning(
                f"[ModelCaller] Primary model '{model_id}' failed ({e_prim}); engaging fallback ladder to '{fallback_model}'..."
            )
            if progress_cb:
                try:
                    res_diag = progress_cb({
                        "tool_name": "agent",
                        "status": "warning",
                        "summary": f"Primary model '{model_id}' unavailable ({type(e_prim).__name__}). Engaging fallback to '{fallback_model}'..."
                    })
                    if asyncio.iscoroutine(res_diag):
                        await res_diag
                except Exception:
                    pass
            try:
                fb_profile = resolve_provider_profile(fallback_model)
                return await fb_profile.generate_chat(
                    model_id=fallback_model,
                    user_prompt=user_prompt,
                    system_instruction=system_instruction,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    read_only=read_only,
                    progress_cb=progress_cb,
                    token_cb=token_cb,
                    intercept_mutating_tools=intercept_mutating_tools,
                    platform=platform,
                    reasoning_effort=reasoning_effort,
                )
            except Exception as e_fb:
                logger.error(f"[ModelCaller] Fallback model '{fallback_model}' also failed: {e_fb}")
                raise RuntimeError(
                    f"Both primary model '{model_id}' ({type(e_prim).__name__}: {e_prim}) "
                    f"and fallback model '{fallback_model}' ({type(e_fb).__name__}: {e_fb}) failed."
                ) from e_fb
        raise e_prim
