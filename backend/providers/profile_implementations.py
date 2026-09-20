"""
profile_implementations.py — Concrete Provider Profiles for Project Anara.
Anara Standard provider adapters:
Decouples inference execution into polymorphic provider profiles.
"""

import asyncio
import json
import logging
import os
import re
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional
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
        if "live-preview" in gemini_model_name or "native-audio" in gemini_model_name:
            from .accounts import get_fallback_model_id
            gemini_model_name = get_fallback_model_id()

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
        if "live-preview" in gemini_model_name or "native-audio" in gemini_model_name:
            from .accounts import get_fallback_model_id
            gemini_model_name = get_fallback_model_id()

        active_target_model = gemini_model_name

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
            raise ValueError("API Key / OAuth Token OpenAI Codex belum diatur. Tambahkan akun di tab Providers.")

        target_model = model_id.replace("codex/", "").replace("openai/", "")

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
                                        val = o.get("choices", [{}])[0].get("delta", {}).get("content", "")
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
            raise ValueError("API Key Anthropic belum diatur. Tambahkan akun di tab Providers.")

        target_model = model_id.replace("anthropic/", "")

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
        )


class OpenAICompatibleProviderProfile(BaseProviderProfile):
    name = "openai_compatible"

    NATIVE_OPEN_ENDPOINTS = {
        "openrouter": "https://openrouter.ai/api/v1",
        "groq": "https://api.groq.com/openai/v1",
        "deepseek": "https://api.deepseek.com",
        "xai": "https://api.x.ai/v1",
    }

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

        for prov_name, base_url in self.NATIVE_OPEN_ENDPOINTS.items():
            if model_id.startswith(f"{prov_name}/"):
                target_model = model_id.replace(f"{prov_name}/", "")
                api_key = get_provider_key(prov_name) or ""
                if not api_key:
                    raise ValueError(f"API Key {prov_name.upper()} belum diatur.")

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                if prov_name == "openrouter":
                    headers["HTTP-Referer"] = "https://project-anara.local"
                    headers["X-Title"] = "Project Anara"

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
                                    delta = chunk_json.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                    if delta:
                                        full_content.append(delta)
                                        if on_chunk:
                                            res = on_chunk(delta)
                                            if asyncio.iscoroutine(res):
                                                await res
                                except Exception:
                                    pass

                            return "".join(full_content)

                return await _execute_json_agent_loop(
                    _open_call,
                    user_prompt,
                    system_instruction,
                    read_only=read_only,
                    progress_cb=progress_cb,
                    token_cb=token_cb,
                    intercept_mutating_tools=intercept_mutating_tools,
                    platform=platform,
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
                                    delta = chunk_json.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                    if delta:
                                        full_content.append(delta)
                                        if on_chunk:
                                            res = on_chunk(delta)
                                            if asyncio.iscoroutine(res):
                                                await res
                                except Exception:
                                    pass

                            return "".join(full_content)

                return await _execute_json_agent_loop(
                    _custom_call,
                    user_prompt,
                    system_instruction,
                    read_only=read_only,
                    progress_cb=progress_cb,
                    token_cb=token_cb,
                    intercept_mutating_tools=intercept_mutating_tools,
                    platform=platform,
                )

        raise ValueError(f"No configured provider could handle model: {model_id}")
