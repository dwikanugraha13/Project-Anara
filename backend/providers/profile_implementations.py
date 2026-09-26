"""
profile_implementations.py — Concrete Provider Profiles for Project Anara.
Anara Standard provider adapters:
Decouples inference execution into polymorphic provider profiles.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Set, Tuple
import httpx
from config import cfg_get

from .base_profile import BaseProviderProfile
from .accounts import get_provider_key
from .discovery import refresh_codex_oauth_token_if_needed

logger = logging.getLogger(__name__)


class GeminiProviderProfile(BaseProviderProfile):
    name = "gemini"

    def can_handle(self, model_id: str) -> bool:
        clean = model_id.lower()
        return clean.startswith("gemini") or clean.startswith("gemma") or clean.startswith("models/")

    async def stream_chat(
        self,
        model_id: str,
        user_prompt: str,
        system_instruction: str = "",
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        usage_out: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        from core import key_manager
        from google import genai
        from google.genai import types

        gemini_model_name = model_id.replace("models/", "")

        cfg_kwargs: Dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None and max_tokens > 0:
            cfg_kwargs["max_output_tokens"] = max_tokens
        if system_instruction and system_instruction.strip():
            cfg_kwargs["system_instruction"] = system_instruction.strip()

        cfg = types.GenerateContentConfig(**cfg_kwargs)
        active_key = key_manager.get_active_key()
        if not active_key:
            return

        client = genai.Client(api_key=active_key)
        try:
            stream_res = client.aio.models.generate_content_stream(
                model=gemini_model_name,
                contents=user_prompt,
                config=cfg,
            )
            async for chunk in await stream_res:
                if chunk.text:
                    yield chunk.text
                if usage_out is not None and hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    u = chunk.usage_metadata
                    p_t = getattr(u, "prompt_token_count", 0) or 0
                    c_t = getattr(u, "candidates_token_count", 0) or 0
                    usage_out["prompt_tokens"] = p_t
                    usage_out["completion_tokens"] = c_t
                    usage_out["total_tokens"] = p_t + c_t
                    usage_out["source"] = "actual"
        except Exception as e:
            logger.warning(f"[GeminiProfile] Streaming error: {e}")
            raise e

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
        from .caller import _make_gemini_raw_call, _execute_json_agent_loop

        gemini_model_name = model_id.replace("models/", "")
        active_target_model = gemini_model_name

        # 1. Native Structured Tool-Use API Path (Hermes & Gemini Parity)
        try:
            from tools.catalog import get_agent_tools
            from tools.toolsets import PlatformToolRegistry
            from google.genai import types
            from .caller import _make_gemini_native_turn, _execute_native_agent_loop

            target_platform = platform or "web_studio"
            active_tool_names = set(PlatformToolRegistry.get_pruned_tools_for_execution(
                target_platform, user_task=user_prompt, read_only=read_only
            ))
            gemini_tools = get_agent_tools(read_only=read_only, enabled_set=active_tool_names)

            async def _gemini_native_turn_caller(contents: List[Any]) -> Any:
                return await _make_gemini_native_turn(
                    model_name=active_target_model,
                    contents=contents,
                    tools=gemini_tools,
                    system_instruction=system_instruction,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    on_chunk=token_cb,
                )

            def _record_gemini_results(contents: List[Any], turn_result: Any, executed_results: List[Tuple[Any, str, bool]]) -> None:
                if turn_result.raw_response:
                    contents.append(turn_result.raw_response)
                resp_parts = []
                for call_obj, output_str, is_err in executed_results:
                    resp_parts.append(
                        types.Part.from_function_response(
                            name=call_obj.name,
                            response={"result": output_str, "status": "error" if is_err else "ok"}
                        )
                    )
                contents.append(types.Content(role="user", parts=resp_parts))

            initial_contents = [types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)])]
            return await _execute_native_agent_loop(
                native_turn_caller=_gemini_native_turn_caller,
                record_results_fn=_record_gemini_results,
                initial_history=initial_contents,
                user_prompt=user_prompt,
                read_only=read_only,
                progress_cb=progress_cb,
                token_cb=token_cb,
                intercept_mutating_tools=intercept_mutating_tools,
                model_id=model_id,
            )
        except Exception as e_native:
            logger.info(f"[GeminiProfile] Native tool call fallback to JSON loop: {e_native}")

        # 2. Universal JSON ReAct Loop Fallback
        async def _gemini_call(msgs: List[Dict[str, str]], on_chunk: Optional[Callable[[str], Any]] = None) -> str:
            return await _make_gemini_raw_call(
                model_name=active_target_model,
                msgs=msgs,
                temperature=temperature,
                max_tokens=max_tokens,
                on_chunk=on_chunk,
            )

        return await _execute_json_agent_loop(
            provider_caller=_gemini_call,
            user_prompt=user_prompt,
            system_instruction=system_instruction,
            read_only=read_only,
            progress_cb=progress_cb,
            token_cb=token_cb,
            intercept_mutating_tools=intercept_mutating_tools,
            platform=platform,
            model_id=model_id,
        )


def _parse_openai_compatible_native_payload(
    raw_text: str,
    token_cb: Optional[Callable[[str], Any]] = None,
) -> Any:
    """
    Parses OpenAI-compatible chat completion responses supporting BOTH
    Server-Sent Events (SSE) data streams (e.g. 9Router, vLLM, OpenRouter)
    and standard JSON payloads.
    Hermes & Claude Code Parity: Assembles streaming delta tool_calls robustly.
    """
    from .native_turn import NativeToolCall, NativeTurnResult

    raw_s = (raw_text or "").strip()
    if not raw_s:
        return NativeTurnResult(text="")

    if raw_s.startswith("data:"):
        text_parts: List[str] = []
        tool_calls_map: Dict[int, Dict[str, Any]] = {}
        finish_reason: Optional[str] = None
        for line in raw_s.splitlines():
            line_s = line.strip()
            if not line_s or not line_s.startswith("data:"):
                continue
            d_str = line_s[5:].strip()
            if d_str == "[DONE]":
                break
            try:
                chunk = json.loads(d_str)
                choices = chunk.get("choices") or []
                if choices:
                    ch0 = choices[0]
                    if ch0.get("finish_reason"):
                        finish_reason = ch0["finish_reason"]
                    delta = ch0.get("delta") or ch0.get("message") or {}
                    if delta.get("content"):
                        c_txt = delta["content"]
                        text_parts.append(c_txt)
                        if token_cb:
                            r = token_cb(c_txt)
                            if asyncio.iscoroutine(r):
                                asyncio.create_task(r)
                    for tc in delta.get("tool_calls") or []:
                        t_idx = tc.get("index", len(tool_calls_map))
                        if t_idx not in tool_calls_map:
                            tool_calls_map[t_idx] = {
                                "id": tc.get("id") or f"call_{t_idx}",
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments": "",
                            }
                        fn_info = tc.get("function") or {}
                        if fn_info.get("name"):
                            tool_calls_map[t_idx]["name"] = fn_info["name"]
                        if fn_info.get("arguments"):
                            tool_calls_map[t_idx]["arguments"] += fn_info["arguments"]
            except Exception:
                pass

        tool_calls: List[NativeToolCall] = []
        for _, tc_item in sorted(tool_calls_map.items()):
            arg_s = tc_item["arguments"]
            try:
                p_args = json.loads(arg_s) if arg_s else {}
            except Exception:
                p_args = {}
            tool_calls.append(NativeToolCall(
                call_id=tc_item["id"],
                name=tc_item["name"],
                arguments=p_args if isinstance(p_args, dict) else {},
            ))

        full_txt = "".join(text_parts)
        raw_msg: Dict[str, Any] = {"role": "assistant", "content": full_txt}
        if tool_calls:
            raw_msg["tool_calls"] = [
                {"id": c.call_id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                for c in tool_calls
            ]
        return NativeTurnResult(
            text=full_txt,
            tool_calls=tool_calls,
            raw_response=raw_msg,
            finish_reason=finish_reason,
        )
    else:
        try:
            data = json.loads(raw_s)
        except Exception:
            return NativeTurnResult(text=raw_s)

        choices = data.get("choices") or []
        if not choices:
            return NativeTurnResult(text="")
        choice = choices[0]
        msg = choice.get("message", {})
        text = msg.get("content") or ""
        if token_cb and text:
            r = token_cb(text)
            if asyncio.iscoroutine(r):
                asyncio.create_task(r)

        tool_calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            fn_args_str = fn.get("arguments", "{}")
            try:
                parsed_args = json.loads(fn_args_str) if isinstance(fn_args_str, str) else fn_args_str
            except Exception:
                parsed_args = {}
            tool_calls.append(NativeToolCall(
                call_id=tc.get("id", f"call_{len(tool_calls)}"),
                name=fn.get("name", ""),
                arguments=parsed_args if isinstance(parsed_args, dict) else {}
            ))

        return NativeTurnResult(
            text=text,
            tool_calls=tool_calls,
            raw_response=msg,
            finish_reason=choice.get("finish_reason"),
        )


class CodexOpenAIProviderProfile(BaseProviderProfile):
    name = "codex_openai"

    def can_handle(self, model_id: str) -> bool:
        clean = model_id.lower()
        return clean.startswith("codex/") or clean.startswith("openai/") or clean.startswith("gpt-") or clean.startswith("o1") or clean.startswith("o3")

    async def stream_chat(
        self,
        model_id: str,
        user_prompt: str,
        system_instruction: str = "",
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        usage_out: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        from memory import memory_engine
        accounts = memory_engine.get_ai_accounts("codex") or memory_engine.get_ai_accounts("openai")
        keys_to_try = [a["api_key"] for a in accounts if a.get("api_key")]
        if not keys_to_try:
            k = get_provider_key("codex") or get_provider_key("openai")
            if k:
                keys_to_try.append(k)
        if not keys_to_try:
            return

        target_model = model_id.replace("codex/", "").replace("openai/", "")
        active_key = keys_to_try[0]
        acc_id = accounts[0]["id"] if accounts else None
        is_oauth_jwt = active_key.startswith("eyJ")

        if is_oauth_jwt:
            headers = {
                "Authorization": f"Bearer {active_key}",
                "Content-Type": "application/json",
                "originator": "codex_cli_rs",
                "User-Agent": "codex_cli_rs/0.136.0",
            }
            payload = {
                "model": target_model,
                "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": user_prompt}]}],
                "instructions": system_instruction,
                "store": False,
                "stream": True,
            }
            endpoint_url = "https://chatgpt.com/backend-api/codex/responses"
        else:
            headers = {
                "Authorization": f"Bearer {active_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": target_model,
                "stream": True,
                "stream_options": {"include_usage": True},
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
            }
            if max_tokens is not None and max_tokens > 0:
                payload["max_tokens"] = max_tokens
            if target_model.startswith("o1") or target_model.startswith("o3"):
                payload.pop("temperature", None)
                payload["messages"] = [{"role": "user", "content": f"{system_instruction}\n\n{user_prompt}"}]
                if "max_tokens" in payload:
                    payload["max_completion_tokens"] = payload.pop("max_tokens")
            endpoint_url = "https://api.openai.com/v1/chat/completions"

        gen_timeout = float(cfg_get("agent.generation.timeout", 45.0))
        async with httpx.AsyncClient(timeout=gen_timeout) as client:
            async with client.stream("POST", endpoint_url, headers=headers, json=payload) as response:
                if response.status_code == 401 and is_oauth_jwt:
                    new_tok = await refresh_codex_oauth_token_if_needed(acc_id)
                    if new_tok:
                        headers["Authorization"] = f"Bearer {new_tok}"
                        async with client.stream("POST", endpoint_url, headers=headers, json=payload) as retry_res:
                            if retry_res.status_code == 200:
                                async for line in retry_res.aiter_lines():
                                    if not line:
                                        continue
                                    data = line[5:].strip() if line.startswith("data:") else line.strip()
                                    if data == "[DONE]":
                                        break
                                    try:
                                        obj = json.loads(data)
                                        if usage_out is not None and obj.get("usage"):
                                            u = obj["usage"]
                                            usage_out["prompt_tokens"] = u.get("prompt_tokens", 0)
                                            usage_out["completion_tokens"] = u.get("completion_tokens", 0)
                                            usage_out["total_tokens"] = u.get("total_tokens", 0)
                                            usage_out["source"] = "actual"
                                        content = ""
                                        if obj.get("type") == "response.text.delta":
                                            content = obj.get("delta", "")
                                        elif obj.get("choices"):
                                            choice = obj["choices"][0] or {}
                                            content = (choice.get("delta") or {}).get("content", "") or choice.get("text", "")
                                        if content:
                                            yield content
                                    except json.JSONDecodeError:
                                        pass
                    return

                if response.status_code == 200:
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = line[5:].strip() if line.startswith("data:") else line.strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                            if usage_out is not None and obj.get("usage"):
                                u = obj["usage"]
                                usage_out["prompt_tokens"] = u.get("prompt_tokens", 0)
                                usage_out["completion_tokens"] = u.get("completion_tokens", 0)
                                usage_out["total_tokens"] = u.get("total_tokens", 0)
                                usage_out["source"] = "actual"
                            content = ""
                            if obj.get("type") == "response.text.delta":
                                content = obj.get("delta", "")
                            elif obj.get("choices"):
                                choice = obj["choices"][0] or {}
                                content = (choice.get("delta") or {}).get("content", "") or choice.get("text", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            pass
                else:
                    logger.warning(f"[Stream] OpenAI Codex error HTTP {response.status_code}")

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
        from memory import memory_engine
        from .caller import _execute_json_agent_loop
        accounts = memory_engine.get_ai_accounts("codex") or memory_engine.get_ai_accounts("openai")
        keys_to_try = [a["api_key"] for a in accounts if a.get("api_key")]
        if not keys_to_try:
            k = get_provider_key("codex") or get_provider_key("openai")
            if k:
                keys_to_try.append(k)

        if not keys_to_try:
            raise ValueError("OpenAI Codex API Key / OAuth Token not configured. Add an account in the Providers tab.")

        target_model = model_id.replace("codex/", "").replace("openai/", "")

        # 1. Native Structured Tool-Use API Path for standard OpenAI keys (Hermes Parity)
        standard_keys = [k for k in keys_to_try if not k.startswith("eyJ")]
        if standard_keys:
            try:
                from tools.catalog import get_native_tools_openai
                from tools.toolsets import PlatformToolRegistry
                from .caller import _execute_native_agent_loop
                from .native_turn import NativeToolCall, NativeTurnResult

                target_platform = platform or "web_studio"
                active_tool_names = set(PlatformToolRegistry.get_pruned_tools_for_execution(
                    target_platform, user_task=user_prompt, read_only=read_only
                ))
                openai_tools = get_native_tools_openai(read_only=read_only, enabled_set=active_tool_names)
                active_key = standard_keys[0]

                async def _openai_native_turn_caller(history: List[Dict[str, Any]]) -> NativeTurnResult:
                    headers = {
                        "Authorization": f"Bearer {active_key}",
                        "Content-Type": "application/json",
                    }
                    payload: Dict[str, Any] = {
                        "model": target_model,
                        "messages": history,
                    }
                    is_reasoning_model = target_model.startswith("o1") or target_model.startswith("o3")
                    if not is_reasoning_model:
                        payload["temperature"] = temperature
                    if openai_tools:
                        payload["tools"] = openai_tools
                    if max_tokens is not None and max_tokens > 0:
                        if is_reasoning_model:
                            payload["max_completion_tokens"] = max_tokens
                        else:
                            payload["max_tokens"] = max_tokens

                    gen_timeout = float(cfg_get("agent.generation.timeout", 45.0))
                    async with httpx.AsyncClient(timeout=gen_timeout) as client:
                        resp = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                        if resp.status_code == 200:
                            return _parse_openai_compatible_native_payload(resp.text, token_cb=token_cb)
                        else:
                            raise RuntimeError(f"OpenAI error {resp.status_code}: {resp.text[:200]}")

                def _record_openai_results(history: List[Any], turn_result: Any, executed_results: List[Tuple[Any, str, bool]]) -> None:
                    history.append(turn_result.raw_response)
                    for call_obj, output_str, is_err in executed_results:
                        history.append({
                            "role": "tool",
                            "tool_call_id": call_obj.call_id,
                            "content": output_str
                        })

                is_reasoning_model = target_model.startswith("o1") or target_model.startswith("o3")
                sys_role = "developer" if is_reasoning_model else "system"
                initial_history = [
                    {"role": sys_role, "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ]
                return await _execute_native_agent_loop(
                    native_turn_caller=_openai_native_turn_caller,
                    record_results_fn=_record_openai_results,
                    initial_history=initial_history,
                    user_prompt=user_prompt,
                    read_only=read_only,
                    progress_cb=progress_cb,
                    token_cb=token_cb,
                    intercept_mutating_tools=intercept_mutating_tools,
                    model_id=model_id,
                )
            except Exception as e_native:
                logger.info(f"[CodexProfile] Native tool call fallback to JSON loop: {e_native}")

        # 2. Universal JSON ReAct Loop Fallback
        async def _codex_call(msgs: List[Dict[str, str]], on_chunk: Optional[Callable[[str], Any]] = None) -> str:
            sys_msg = next((m["content"] for m in msgs if m["role"] == "system"), "")
            chat_msgs = [m for m in msgs if m["role"] != "system"]
            for idx, key in enumerate(keys_to_try):
                is_oauth_jwt = key.startswith("eyJ")
                if is_oauth_jwt:
                    headers = {
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    }
                    endpoint_url = "https://chatgpt.com/backend-api/lat/r"
                    payload = {
                        "model": target_model,
                        "messages": [{"role": "system", "content": sys_msg}] + chat_msgs,
                        "temperature": temperature,
                        "stream": True,
                    }
                    if max_tokens is not None and max_tokens > 0:
                        payload["max_tokens"] = max_tokens

                    gen_timeout = float(cfg_get("agent.generation.timeout", 45.0))
                    async with httpx.AsyncClient(timeout=gen_timeout) as client:
                        resp = await client.post(endpoint_url, headers=headers, json=payload)
                        if resp.status_code == 200:
                            chunks = []
                            async for line in resp.aiter_lines():
                                if not line or not line.startswith("data:"):
                                    continue
                                d_str = line[5:].strip()
                                if d_str == "[DONE]":
                                    break
                                try:
                                    o = json.loads(d_str)
                                    val = ""
                                    if o.get("type") == "response.text.delta":
                                        val = o.get("delta", "")
                                    elif "choices" in o and o["choices"]:
                                        val = o["choices"][0].get("delta", {}).get("content", "")
                                    if val:
                                        chunks.append(val)
                                        if on_chunk:
                                            res = on_chunk(val)
                                            if asyncio.iscoroutine(res):
                                                await res
                                except Exception:
                                    pass
                            if idx < len(accounts):
                                memory_engine.increment_ai_account_usage(accounts[idx]["id"])
                            return "".join(chunks)
                else:
                    headers = {
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    }
                    endpoint_url = "https://api.openai.com/v1/chat/completions"
                    payload = {
                        "model": target_model,
                        "messages": [{"role": "system", "content": sys_msg}] + chat_msgs,
                        "temperature": temperature,
                        "stream": True,
                        "stream_options": {"include_usage": True},
                    }
                    if max_tokens is not None and max_tokens > 0:
                        payload["max_tokens"] = max_tokens

                    gen_timeout = float(cfg_get("agent.generation.timeout", 45.0))
                    async with httpx.AsyncClient(timeout=gen_timeout) as client:
                        async with client.stream("POST", endpoint_url, headers=headers, json=payload) as resp:
                            if resp.status_code == 200:
                                 chunks = []
                                 reasoning_chunks = []
                                 async for line in resp.aiter_lines():
                                     if not line or not line.startswith("data:"):
                                         continue
                                     d_str = line[5:].strip()
                                     if d_str == "[DONE]":
                                         break
                                     try:
                                         o = json.loads(d_str)
                                         u = o.get("usage")
                                         if u:
                                             memory_engine.record_token_usage(
                                                 model_id=model_id,
                                                 provider="codex",
                                                 prompt_tokens=u.get("prompt_tokens", 0),
                                                 completion_tokens=u.get("completion_tokens", 0)
                                             )
                                         delta_obj = o.get("choices", [{}])[0].get("delta", {}) or {}
                                         val = delta_obj.get("content", "")
                                         r_val = delta_obj.get("reasoning_content") or delta_obj.get("thought") or ""
                                         if val:
                                             chunks.append(val)
                                             if on_chunk:
                                                 res = on_chunk(val)
                                                 if asyncio.iscoroutine(res):
                                                    await res
                                         elif r_val:
                                             reasoning_chunks.append(r_val)
                                     except Exception:
                                         pass
                                 if idx < len(accounts):
                                     memory_engine.increment_ai_account_usage(accounts[idx]["id"])
                                 res_text = "".join(chunks)
                                 if not res_text.strip() and reasoning_chunks:
                                     res_text = "".join(reasoning_chunks)
                                 return res_text
            return ""

        return await _execute_json_agent_loop(
            _codex_call,
            user_prompt,
            system_instruction,
            read_only=read_only,
            progress_cb=progress_cb,
            token_cb=token_cb,
            intercept_mutating_tools=intercept_mutating_tools,
            platform=platform,
            model_id=model_id,
        )


class AnthropicProviderProfile(BaseProviderProfile):
    name = "anthropic"

    def can_handle(self, model_id: str) -> bool:
        clean = model_id.lower()
        return clean.startswith("anthropic/") or clean.startswith("claude-")

    async def stream_chat(
        self,
        model_id: str,
        user_prompt: str,
        system_instruction: str = "",
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        usage_out: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Claude Code & Hermes Parity: True Native SSE Token Streaming for Anthropic.
        Parses Server-Sent Events (SSE) line-by-line and yields text_delta tokens in real time.
        """
        from memory import memory_engine
        from config import cfg_get

        accounts = memory_engine.get_ai_accounts("anthropic")
        keys_to_try = [a["api_key"] for a in accounts if a.get("api_key")]
        if not keys_to_try:
            k = get_provider_key("anthropic")
            if k:
                keys_to_try.append(k)

        if not keys_to_try:
            res = await self.generate_chat(
                model_id=model_id,
                user_prompt=user_prompt,
                system_instruction=system_instruction,
                max_tokens=max_tokens,
                temperature=temperature,
                read_only=False,
            )
            if res:
                yield str(res)
            return

        target_model = model_id.replace("anthropic/", "")
        anthropic_max = max_tokens if (max_tokens is not None and max_tokens > 0) else (64000 if "3-7" in target_model else 8192)

        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": anthropic_max,
            "temperature": temperature,
            "stream": True,
        }
        if system_instruction and system_instruction.strip():
            payload["system"] = system_instruction.strip()

        gen_timeout = float(cfg_get("agent.generation.timeout", 30.0))
        streamed_any = False
        prompt_tokens = 0
        completion_tokens = 0

        for idx, key in enumerate(keys_to_try):
            headers = {
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "X-Timeout": "15",
                "Content-Type": "application/json"
            }
            try:
                async with httpx.AsyncClient(timeout=gen_timeout) as client:
                    async with client.stream("POST", "https://api.anthropic.com/v1/messages", headers=headers, json=payload) as resp:
                        if resp.status_code == 200:
                            async for line in resp.aiter_lines():
                                if not line or not line.startswith("data:"):
                                    continue
                                d_str = line[5:].strip()
                                if d_str == "[DONE]":
                                    break
                                try:
                                    event = json.loads(d_str)
                                    ev_type = event.get("type", "")

                                    if ev_type == "message_start":
                                        msg_usage = event.get("message", {}).get("usage", {})
                                        if msg_usage:
                                            prompt_tokens = msg_usage.get("input_tokens", 0)

                                    elif ev_type == "content_block_delta":
                                        delta = event.get("delta", {})
                                        if delta.get("type") == "text_delta":
                                            chunk = delta.get("text", "")
                                            if chunk:
                                                streamed_any = True
                                                yield chunk

                                    elif ev_type == "message_delta":
                                        delta_usage = event.get("usage", {})
                                        if delta_usage:
                                            completion_tokens = delta_usage.get("output_tokens", 0)

                                except Exception:
                                    pass

                            if usage_out is not None:
                                usage_out["prompt_tokens"] = prompt_tokens
                                usage_out["completion_tokens"] = completion_tokens
                                usage_out["total_tokens"] = prompt_tokens + completion_tokens
                                usage_out["source"] = "actual"

                            if prompt_tokens or completion_tokens:
                                memory_engine.record_token_usage(
                                    model_id=model_id,
                                    provider="anthropic",
                                    prompt_tokens=prompt_tokens,
                                    completion_tokens=completion_tokens
                                )
                            if idx < len(accounts):
                                memory_engine.increment_ai_account_usage(accounts[idx]["id"])

                            return

                        elif resp.status_code in [429, 403, 401] and len(keys_to_try) > 1:
                            if idx < len(accounts):
                                memory_engine.set_ai_account_cooldown(accounts[idx]["id"], 120.0)
                            continue
                        else:
                            err_body = await resp.aread()
                            logger.warning(f"[AnthropicProfile] Stream HTTP {resp.status_code}: {err_body.decode('utf-8', errors='replace')[:200]}")
                            break
            except Exception as e_stream:
                logger.warning(f"[AnthropicProfile] Streaming connection error: {e_stream}")
                if idx == len(keys_to_try) - 1:
                    break

        if not streamed_any:
            logger.info("[AnthropicProfile] Falling back to generate_chat for stream response.")
            res = await self.generate_chat(
                model_id=model_id,
                user_prompt=user_prompt,
                system_instruction=system_instruction,
                max_tokens=max_tokens,
                temperature=temperature,
                read_only=False,
            )
            if res:
                yield str(res)

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
        from memory import memory_engine
        from .caller import _execute_json_agent_loop

        accounts = memory_engine.get_ai_accounts("anthropic")
        keys_to_try = [a["api_key"] for a in accounts if a.get("api_key")]
        if not keys_to_try:
            k = get_provider_key("anthropic")
            if k:
                keys_to_try.append(k)

        if not keys_to_try:
            raise ValueError("Anthropic API Key not configured. Add an account in the Providers tab.")

        target_model = model_id.replace("anthropic/", "")

        # 1. Native Structured Tool-Use API Path (Claude Code Parity)
        try:
            from tools.catalog import get_native_tools_anthropic
            from tools.toolsets import PlatformToolRegistry
            from .caller import _execute_native_agent_loop
            from .native_turn import NativeToolCall, NativeTurnResult

            target_platform = platform or "web_studio"
            active_tool_names = set(PlatformToolRegistry.get_pruned_tools_for_execution(
                target_platform, user_task=user_prompt, read_only=read_only
            ))
            anthropic_tools = get_native_tools_anthropic(read_only=read_only, enabled_set=active_tool_names)

            async def _anthropic_native_turn_caller(history: List[Dict[str, Any]]) -> NativeTurnResult:
                for idx, key in enumerate(keys_to_try):
                    headers = {
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01",
                        "X-Timeout": "15",
                        "Content-Type": "application/json"
                    }
                    anthropic_max = max_tokens if (max_tokens is not None and max_tokens > 0) else (64000 if "3-7" in target_model else 8192)
                    payload: Dict[str, Any] = {
                        "model": target_model,
                        "messages": history,
                        "max_tokens": anthropic_max,
                        "temperature": temperature,
                    }
                    if system_instruction and system_instruction.strip():
                        # Anthropic Prompt Caching Parity (Claude Code & Hermes Parity)
                        payload["system"] = [
                            {
                                "type": "text",
                                "text": system_instruction.strip(),
                                "cache_control": {"type": "ephemeral"}
                            }
                        ]
                    if anthropic_tools:
                        # Cache the tools catalog block on the last tool
                        cached_tools = []
                        for t_idx, t in enumerate(anthropic_tools):
                            t_copy = dict(t)
                            if t_idx == len(anthropic_tools) - 1:
                                t_copy["cache_control"] = {"type": "ephemeral"}
                            cached_tools.append(t_copy)
                        payload["tools"] = cached_tools

                    gen_timeout = float(cfg_get("agent.generation.timeout", 30.0))
                    try:
                        async with httpx.AsyncClient(timeout=gen_timeout) as client:
                            res = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
                            if res.status_code == 200:
                                data = res.json()
                                u = data.get("usage")
                                if u:
                                    memory_engine.record_token_usage(
                                        model_id=model_id,
                                        provider="anthropic",
                                        prompt_tokens=u.get("input_tokens", 0),
                                        completion_tokens=u.get("output_tokens", 0)
                                    )
                                if idx < len(accounts):
                                    memory_engine.increment_ai_account_usage(accounts[idx]["id"])

                                text_parts = []
                                tool_calls = []
                                for block in data.get("content", []):
                                    if block.get("type") == "text":
                                        txt = block.get("text", "")
                                        text_parts.append(txt)
                                        if token_cb and txt:
                                            r = token_cb(txt)
                                            if asyncio.iscoroutine(r):
                                                await r
                                    elif block.get("type") == "tool_use":
                                        tool_calls.append(NativeToolCall(
                                            call_id=block.get("id", ""),
                                            name=block.get("name", ""),
                                            arguments=block.get("input", {}) or {},
                                        ))

                                return NativeTurnResult(
                                    text="".join(text_parts),
                                    tool_calls=tool_calls,
                                    raw_response=data,
                                    finish_reason=data.get("stop_reason"),
                                )
                            elif res.status_code in [429, 403, 401] and len(keys_to_try) > 1:
                                if idx < len(accounts):
                                    memory_engine.set_ai_account_cooldown(accounts[idx]["id"], 120.0)
                                continue
                            else:
                                raise RuntimeError(f"Anthropic HTTP {res.status_code}: {res.text}")
                    except Exception as e:
                        if idx == len(keys_to_try) - 1:
                            raise e
                return NativeTurnResult(text="")

            def _record_anthropic_results(history: List[Any], turn_result: Any, executed_results: List[Tuple[Any, str, bool]]) -> None:
                # Assistant message with raw content blocks
                raw_content = turn_result.raw_response.get("content", []) if isinstance(turn_result.raw_response, dict) else []
                history.append({"role": "assistant", "content": raw_content})
                # User message with tool_result blocks
                results_blocks = []
                for call_obj, output_str, is_err in executed_results:
                    block: Dict[str, Any] = {
                        "type": "tool_result",
                        "tool_use_id": call_obj.call_id,
                        "content": output_str,
                    }
                    if is_err:
                        block["is_error"] = True
                    results_blocks.append(block)
                history.append({"role": "user", "content": results_blocks})

            initial_history = [{"role": "user", "content": user_prompt}]
            return await _execute_native_agent_loop(
                native_turn_caller=_anthropic_native_turn_caller,
                record_results_fn=_record_anthropic_results,
                initial_history=initial_history,
                user_prompt=user_prompt,
                read_only=read_only,
                progress_cb=progress_cb,
                token_cb=token_cb,
                intercept_mutating_tools=intercept_mutating_tools,
                model_id=model_id,
            )
        except Exception as e_native:
            logger.info(f"[AnthropicProfile] Native tool call fallback to JSON loop: {e_native}")

        # 2. Universal JSON ReAct Loop Fallback
        async def _anthropic_call(msgs: List[Dict[str, str]]) -> str:
            sys_msg = next((m["content"] for m in msgs if m["role"] == "system"), "")
            chat_msgs = [m for m in msgs if m["role"] != "system"]
            for idx, key in enumerate(keys_to_try):
                headers = {
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "X-Timeout": "15",
                    "Content-Type": "application/json"
                }
                anthropic_max = max_tokens if (max_tokens is not None and max_tokens > 0) else (64000 if "3-7" in target_model else 8192)
                payload = {
                    "model": target_model,
                    "system": sys_msg,
                    "messages": chat_msgs,
                    "max_tokens": anthropic_max,
                    "temperature": temperature,
                }
                gen_timeout = float(cfg_get("agent.generation.timeout", 30.0))
                try:
                    async with httpx.AsyncClient(timeout=gen_timeout) as client:
                        res = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
                        if res.status_code == 200:
                            data = res.json()
                            u = data.get("usage")
                            if u:
                                memory_engine.record_token_usage(
                                    model_id=model_id,
                                    provider="anthropic",
                                    prompt_tokens=u.get("input_tokens", 0),
                                    completion_tokens=u.get("output_tokens", 0)
                                )
                            if idx < len(accounts):
                                memory_engine.increment_ai_account_usage(accounts[idx]["id"])
                            return data["content"][0]["text"]
                        elif res.status_code in [429, 403, 401] and len(keys_to_try) > 1:
                            if idx < len(accounts):
                                memory_engine.set_ai_account_cooldown(accounts[idx]["id"], 120.0)
                            continue
                        else:
                            raise RuntimeError(f"Anthropic HTTP {res.status_code}: {res.text}")
                except Exception as e:
                    if idx == len(keys_to_try) - 1:
                        raise e
            return ""

        return await _execute_json_agent_loop(
            _anthropic_call,
            user_prompt,
            system_instruction,
            read_only=read_only,
            progress_cb=progress_cb,
            token_cb=token_cb,
            intercept_mutating_tools=intercept_mutating_tools,
            platform=platform,
            model_id=model_id,
        )


class OpenAICompatibleProviderProfile(BaseProviderProfile):
    name = "openai_compatible"

    NATIVE_OPEN_ENDPOINTS = {
        "openrouter": "https://openrouter.ai/api/v1",
        "groq": "https://api.groq.com/openai/v1",
        "deepseek": "https://api.deepseek.com",
        "xai": "https://api.x.ai/v1",
    }

    async def _try_native_agent_loop(
        self,
        endpoint_url: str,
        target_model: str,
        headers: Dict[str, str],
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
    ) -> Optional[Any]:
        """
        Hermes & Claude Code Parity: Native Structured Tool-Use API for OpenAI-Compatible Endpoints.
        Sends tools schema in request, extracts tool_calls from choice.message,
        and executes through _execute_native_agent_loop with full safety guards.
        """
        from tools.catalog import get_native_tools_openai
        from tools.toolsets import PlatformToolRegistry
        from .caller import _execute_native_agent_loop
        from .native_turn import NativeToolCall, NativeTurnResult

        target_platform = platform or "web_studio"
        active_tool_names = set(PlatformToolRegistry.get_pruned_tools_for_execution(
            target_platform, user_task=user_prompt, read_only=read_only
        ))
        openai_tools = get_native_tools_openai(read_only=read_only, enabled_set=active_tool_names)

        async def _openai_native_turn_caller(history: List[Dict[str, Any]]) -> NativeTurnResult:
            payload: Dict[str, Any] = {
                "model": target_model,
                "messages": history,
                "temperature": temperature,
            }
            if openai_tools:
                payload["tools"] = openai_tools
            if max_tokens is not None and max_tokens > 0:
                payload["max_tokens"] = max_tokens

            custom_timeout = float(cfg_get("agent.generation.custom_timeout", 120.0))
            async with httpx.AsyncClient(timeout=custom_timeout) as client:
                resp = await client.post(endpoint_url, headers=headers, json=payload)
                if resp.status_code == 200:
                    return _parse_openai_compatible_native_payload(resp.text, token_cb=token_cb)
                else:
                    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

        def _record_openai_results(history: List[Any], turn_result: Any, executed_results: List[Tuple[Any, str, bool]]) -> None:
            history.append(turn_result.raw_response)
            for call_obj, output_str, is_err in executed_results:
                history.append({
                    "role": "tool",
                    "tool_call_id": call_obj.call_id,
                    "content": output_str
                })

        initial_history = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt}
        ]
        return await _execute_native_agent_loop(
            native_turn_caller=_openai_native_turn_caller,
            record_results_fn=_record_openai_results,
            initial_history=initial_history,
            user_prompt=user_prompt,
            read_only=read_only,
            progress_cb=progress_cb,
            token_cb=token_cb,
            intercept_mutating_tools=intercept_mutating_tools,
            model_id=model_id,
        )

    def can_handle(self, model_id: str) -> bool:
        clean = model_id.lower()
        if any(clean.startswith(f"{prov}/") for prov in self.NATIVE_OPEN_ENDPOINTS):
            return True
        if clean.startswith("9router/") or clean.startswith("ag/"):
            return True
        from memory import memory_engine
        try:
            custom_nodes = memory_engine.get_custom_providers()
            for c in custom_nodes:
                if clean.startswith(f"{c['prefix'].lower()}/"):
                    return True
        except Exception:
            pass
        return False

    async def stream_chat(
        self,
        model_id: str,
        user_prompt: str,
        system_instruction: str = "",
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        usage_out: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        q: asyncio.Queue[Optional[str]] = asyncio.Queue()

        def _on_token(token: str):
            if token:
                q.put_nowait(token)

        async def _run_task():
            try:
                await self.generate_chat(
                    model_id=model_id,
                    user_prompt=user_prompt,
                    system_instruction=system_instruction,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    read_only=False,
                    token_cb=_on_token,
                )
            except Exception as e:
                logger.error(f"[OpenAICompatible] stream_chat error: {e}")
            finally:
                q.put_nowait(None)

        task = asyncio.create_task(_run_task())
        while True:
            chunk = await q.get()
            if chunk is None:
                break
            yield chunk
        await task

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
        from memory import memory_engine
        from .caller import _execute_json_agent_loop

        for prov_name, base_url in self.NATIVE_OPEN_ENDPOINTS.items():
            if model_id.startswith(f"{prov_name}/"):
                target_model = model_id.replace(f"{prov_name}/", "")
                api_key = get_provider_key(prov_name) or ""
                if not api_key:
                    raise ValueError(f"API Key for {prov_name.upper()} not configured.")

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                if prov_name == "openrouter":
                    headers["HTTP-Referer"] = "https://project-anara.local"
                    headers["X-Title"] = "Project Anara"

                # 1. Native Structured Tool-Use API Path (Hermes Parity)
                try:
                    native_res = await self._try_native_agent_loop(
                        endpoint_url=f"{base_url}/chat/completions",
                        target_model=target_model,
                        headers=headers,
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
                    )
                    if native_res is not None:
                        return native_res
                except Exception as e_native:
                    logger.info(f"[OpenAICompatibleProfile] Native tool call fallback for {prov_name}: {e_native}")

                # 2. Universal JSON ReAct Loop Fallback
                async def _open_call(msgs: List[Dict[str, str]], on_chunk: Optional[Callable[[str], Any]] = None) -> str:
                    sys_msg = next((m["content"] for m in msgs if m["role"] == "system"), "")
                    chat_msgs = [m for m in msgs if m["role"] != "system"]
                    payload = {
                        "model": target_model,
                        "messages": [{"role": "system", "content": sys_msg}] + chat_msgs,
                        "temperature": temperature,
                        "stream": True,
                        "stream_options": {"include_usage": True},
                    }
                    if max_tokens is not None and max_tokens > 0:
                        payload["max_tokens"] = max_tokens
                    endpoint = f"{base_url}/chat/completions"
                    custom_timeout = float(cfg_get("agent.generation.custom_timeout", 120.0))

                    async with httpx.AsyncClient(timeout=custom_timeout) as client:
                        async with client.stream("POST", endpoint, headers=headers, json=payload) as resp:
                            if resp.status_code != 200:
                                err_body = await resp.aread()
                                raise RuntimeError(f"{prov_name.upper()} error: HTTP {resp.status_code}: {err_body.decode('utf-8', errors='replace')[:200]}")

                            full_content = []
                            full_reasoning = []
                            async for line in resp.aiter_lines():
                                if not line or not line.startswith("data:"):
                                    continue
                                d_str = line[5:].strip()
                                if d_str == "[DONE]":
                                    break
                                try:
                                    chunk_json = json.loads(d_str)
                                    usage = chunk_json.get("usage")
                                    if usage:
                                        memory_engine.record_token_usage(
                                            model_id=model_id,
                                            provider=prov_name,
                                            prompt_tokens=usage.get("prompt_tokens", 0),
                                            completion_tokens=usage.get("completion_tokens", 0)
                                        )
                                    choices = chunk_json.get("choices") or []
                                    if choices and isinstance(choices, list):
                                        choice = choices[0] or {}
                                        delta_obj = choice.get("delta") or {}
                                        delta = delta_obj.get("content") or choice.get("message", {}).get("content") or choice.get("text") or ""
                                        reasoning_piece = delta_obj.get("reasoning_content") or delta_obj.get("thought") or choice.get("message", {}).get("reasoning_content") or ""
                                        if delta:
                                            full_content.append(delta)
                                            if on_chunk:
                                                res = on_chunk(delta)
                                                if asyncio.iscoroutine(res):
                                                    await res
                                        elif reasoning_piece:
                                            full_reasoning.append(reasoning_piece)
                                except Exception:
                                    pass

                            text_out = "".join(full_content)
                            if not text_out.strip() and full_reasoning:
                                joined_reasoning = "".join(full_reasoning)
                                if '"action": "tool_call"' in joined_reasoning or '"action":"tool_call"' in joined_reasoning or "<tool_call>" in joined_reasoning:
                                    text_out = joined_reasoning
                                else:
                                    text_out = joined_reasoning.strip()
                            return text_out

                return await _execute_json_agent_loop(
                    _open_call,
                    user_prompt,
                    system_instruction,
                    read_only=read_only,
                    progress_cb=progress_cb,
                    token_cb=token_cb,
                    intercept_mutating_tools=intercept_mutating_tools,
                    platform=platform,
                    model_id=model_id,
                )

        # Check custom nodes (including 9Router)
        custom_nodes = memory_engine.get_custom_providers()
        for c_node in custom_nodes:
            c_prefix = c_node["prefix"]
            if model_id.startswith(f"{c_prefix}/") or (c_prefix == "9router" and model_id.startswith("ag/")):
                target_model = model_id.replace(f"{c_prefix}/", "")
                base_url = c_node["base_url"].rstrip("/")
                api_key = c_node.get("api_key") or ""

                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                # 1. Native Structured Tool-Use API Path (Hermes Parity)
                try:
                    native_res = await self._try_native_agent_loop(
                        endpoint_url=f"{base_url}/chat/completions",
                        target_model=target_model,
                        headers=headers,
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
                    )
                    if native_res is not None:
                        return native_res
                except Exception as e_native:
                    logger.info(f"[OpenAICompatibleProfile] Native tool call fallback for custom node {c_prefix}: {e_native}")

                # 2. Universal JSON ReAct Loop Fallback
                async def _custom_call(msgs: List[Dict[str, str]], on_chunk: Optional[Callable[[str], Any]] = None) -> str:
                    sys_msg = next((m["content"] for m in msgs if m["role"] == "system"), "")
                    chat_msgs = [m for m in msgs if m["role"] != "system"]

                    payload = {
                        "model": target_model,
                        "messages": [{"role": "system", "content": sys_msg}] + chat_msgs,
                        "temperature": temperature,
                        "stream": True,
                    }
                    if max_tokens is not None and max_tokens > 0:
                        payload["max_tokens"] = max_tokens
                    endpoint = f"{base_url}/chat/completions"
                    custom_timeout = float(cfg_get("agent.generation.custom_timeout", 120.0))

                    async with httpx.AsyncClient(timeout=custom_timeout) as client:
                        async with client.stream("POST", endpoint, headers=headers, json=payload) as resp:
                            if resp.status_code != 200:
                                err_body = await resp.aread()
                                raise RuntimeError(f"Custom provider error: HTTP {resp.status_code}: {err_body.decode('utf-8', errors='replace')[:200]}")

                            full_content = []
                            full_reasoning = []
                            async for line in resp.aiter_lines():
                                if not line or not line.startswith("data:"):
                                    continue
                                d_str = line[5:].strip()
                                if d_str == "[DONE]":
                                    break
                                try:
                                    chunk_json = json.loads(d_str)
                                    usage = chunk_json.get("usage")
                                    if usage:
                                        memory_engine.record_token_usage(
                                            model_id=model_id,
                                            provider=c_prefix,
                                            prompt_tokens=usage.get("prompt_tokens", 0),
                                            completion_tokens=usage.get("completion_tokens", 0)
                                        )
                                    choices = chunk_json.get("choices") or []
                                    if choices and isinstance(choices, list):
                                        choice = choices[0] or {}
                                        delta_obj = choice.get("delta") or {}
                                        delta = delta_obj.get("content") or choice.get("message", {}).get("content") or choice.get("text") or ""
                                        reasoning_piece = delta_obj.get("reasoning_content") or delta_obj.get("thought") or choice.get("message", {}).get("reasoning_content") or ""
                                        if delta:
                                            full_content.append(delta)
                                            if on_chunk:
                                                res = on_chunk(delta)
                                                if asyncio.iscoroutine(res):
                                                    await res
                                        elif reasoning_piece:
                                            full_reasoning.append(reasoning_piece)
                                except Exception:
                                    pass

                            text_out = "".join(full_content)
                            if not text_out.strip() and full_reasoning:
                                joined_reasoning = "".join(full_reasoning)
                                if '"action": "tool_call"' in joined_reasoning or '"action":"tool_call"' in joined_reasoning or "<tool_call>" in joined_reasoning:
                                    text_out = joined_reasoning
                                else:
                                    text_out = joined_reasoning.strip()
                            return text_out

                return await _execute_json_agent_loop(
                    _custom_call,
                    user_prompt,
                    system_instruction,
                    read_only=read_only,
                    progress_cb=progress_cb,
                    token_cb=token_cb,
                    intercept_mutating_tools=intercept_mutating_tools,
                    platform=platform,
                    model_id=model_id,
                )

        raise ValueError(f"No configured provider could handle model: {model_id}")
