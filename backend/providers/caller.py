import asyncio
import json
import logging
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional
import httpx

from .accounts import (
    get_provider_key,
)
from .discovery import refresh_codex_oauth_token_if_needed

logger = logging.getLogger(__name__)


async def stream_universal_chat_model(
    model_id: str,
    user_prompt: str,
    system_instruction: str = "",
    max_tokens: Optional[int] = None,
    temperature: float = 0.7,
    usage_out: Optional[Dict[str, Any]] = None,
):
    """
    Async generator that streams model text chunks in real-time. Yields str fragments.
    Uncapped native generation by default — allows models to output full deep blueprints and code without artificial throttling.
    """
    if model_id.startswith("gemini") or model_id.startswith("gemma") or model_id.startswith("models/"):
        from core import key_manager
        from google import genai
        from google.genai import types
        gemini_model_name = model_id.replace("models/", "")
        if "live-preview" in gemini_model_name or "native-audio" in gemini_model_name:
            gemini_model_name = "gemini-3.5-flash-lite"
        cfg_kwargs: Dict[str, Any] = {
            "temperature": temperature,
        }
        if max_tokens is not None and max_tokens > 0:
            cfg_kwargs["max_output_tokens"] = max_tokens
        if system_instruction and system_instruction.strip():
            cfg_kwargs["system_instruction"] = system_instruction.strip()
        cfg = types.GenerateContentConfig(**cfg_kwargs)
        active_key = key_manager.get_active_key()
        if active_key:
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
                return
            except Exception as g_err:
                logger.warning(f"[Stream] Gemini streaming error, falling back: {g_err}")

    if model_id.startswith("codex/") or model_id.startswith("openai/"):
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
                "input": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": user_prompt}],
                    }
                ],
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
                payload["messages"] = [
                    {"role": "user", "content": f"{system_instruction}\n\n{user_prompt}"}
                ]
                if "max_tokens" in payload:
                    payload["max_completion_tokens"] = payload.pop("max_tokens")
            endpoint_url = "https://api.openai.com/v1/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
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
                        return
                    else:
                        logger.warning(f"[Stream] OpenAI Codex error HTTP {response.status_code}")
        except Exception as e:
            logger.warning(f"[Stream] OpenAI Codex stream error: {e}")

    # Fallback to full non-streaming call
    full = await call_universal_chat_model(
        model_id=model_id,
        user_prompt=user_prompt,
        system_instruction=system_instruction,
        max_tokens=max_tokens,
        temperature=temperature,
        read_only=False,
    )
    if full:
        yield full


async def _execute_json_agent_loop(
    provider_caller: Callable[..., Awaitable[str]],
    user_prompt: str,
    system_instruction: str,
    read_only: bool = False,
    progress_cb: Optional[Callable[[Dict[str, Any]], Any]] = None,
    token_cb: Optional[Callable[[str], Any]] = None,
) -> str:
    """Universal multi-turn JSON tool loop for OpenAI Codex, Claude, and Custom Providers."""
    from tools import dispatch_tool_call, READ_ONLY_TOOL_NAMES
    from tools.catalog import is_safe_read_only_cli_command
    
    tool_spec_doc = (
        "\n\n[UNIVERSAL AUTONOMOUS AGENT PROTOCOL — CLAUDE CODE / OPENCODE / HERMES STANDARD]\n"
        "Kamu adalah Autonomous AI Agent cerdas, berdaya cipta tinggi, dan solutif.\n"
        "Untuk membaca kode, menjelajahi proyek, mengedit berkas, menjalankan perintah terminal, atau membuat artefak:\n"
        "BALAS HANYA DENGAN SATU BLOK JSON VALID BERIKUT:\n"
        "```json\n"
        '{\n  "action": "tool_call",\n  "tool": "interactive_question" | "edit_file" | "read_local_file" | "write_local_file" | "glob_find_files" | "grep_search_code" | "execute_cli_command" | "create_zip_archive" | "web_search" | "fetch_webpage" | "delegate_subagent" | "generate_file_artifact" | "scan_workspace_folder" | "list_directory",\n  "arguments": { ... }\n}\n'
        "```\n"
        "Katalog Pemanggilan Alat Otonom:\n"
        "- 'interactive_question': Menampilkan kartu kuesioner bertahap (Wizard Card) ke layar user untuk meminta preferensi / mengklarifikasi ide proyek yang luas di Plan Mode. Argumen: {\"questions\": [{\"header\": \"Kategori\", \"question\": \"Pertanyaan...\", \"options\": [{\"label\": \"Opsi A (Recommended)\", \"description\": \"Penjelasan\"}]}]}.\n"
        "- 'edit_file': Menyunting berkas secara in-place (hemat token & anti-rusak). Argumen: {\"file_path\": \"...\", \"old_string\": \"teks_lama\", \"new_string\": \"teks_baru\"}.\n"
        "- 'read_local_file': Membaca berkas dengan nomor baris. Argumen: {\"file_path\": \"...\", \"offset\": 1, \"limit\": 200}.\n"
        "- 'write_local_file': Membuat berkas baru atau menulis ulang. Argumen: {\"file_path\": \"...\", \"content\": \"...\"}.\n"
        "- 'glob_find_files': Mencari file berdasarkan pola. Argumen: {\"pattern\": \"**/*.tsx\"}.\n"
        "- 'grep_search_code': Mencari kode/teks via regex di seluruh workspace. Argumen: {\"pattern\": \"regex_atau_kata\", \"include\": \"*.py\"}.\n"
        "- 'execute_cli_command': Menjalankan perintah terminal lokal (npm run build, pytest, git diff). Argumen: {\"command\": \"...\"}.\n"
        "- 'create_zip_archive': Mengompresi seluruh proyek ke ZIP untuk diunduh pengguna. Argumen: {\"archive_name\": \"project.zip\"}.\n"
        "- 'web_search': Mencari informasi terkini di internet. Argumen: {\"query\": \"...\"}.\n"
        "- 'fetch_webpage': Membaca isi web dari URL. Argumen: {\"url\": \"...\"}.\n"
        "- 'delegate_subagent': Mendelegasikan tugas berat ke pekerja latar belakang. Argumen: {\"title\": \"...\", \"mission_prompt\": \"...\"}.\n\n"
        "DISIPLIN KERJA (SELF-VERIFICATION LOOP):\n"
        "1. Selalu baca berkas (read_local_file) atau cari (glob/grep) sebelum melakukan perubahan.\n"
        "2. Gunakan 'edit_file' untuk modifikasi spesifik agar tidak merusak baris lain.\n"
        "3. Setelah menulis/mengedit kode penting, lakukan verifikasi mandiri dengan 'execute_cli_command' (misal build atau test) jika relevan.\n"
        "4. Setelah seluruh alat selesai dieksekusi dan tujuan tercapai, berikan penjelasan akhir yang cerdas, tuntas, dan ramah MURNI dengan gayamu sendiri."
    )
    
    messages = [
        {"role": "system", "content": f"{system_instruction}{tool_spec_doc}"},
        {"role": "user", "content": user_prompt}
    ]
    
    last_response = ""
    for step in range(25):
        if len(messages) > 12:
            for m_idx in range(2, len(messages) - 4):
                if messages[m_idx].get("role") == "user" and len(messages[m_idx].get("content", "")) > 600:
                    c = messages[m_idx]["content"]
                    messages[m_idx]["content"] = c[:300] + "\n[... output observasi lama dipangkas demi efisiensi konteks ...]\n" + c[-150:]

        buffered_chunks = []
        is_tool_candidate = None  # None: undetermined, True: looks like JSON tool call, False: narrative streaming
        accumulated_narrative = []

        async def _chunk_dispatcher(delta: str):
            nonlocal is_tool_candidate
            if not delta:
                return

            if is_tool_candidate is False:
                accumulated_narrative.append(delta)
                if token_cb:
                    res = token_cb("".join(accumulated_narrative))
                    if asyncio.iscoroutine(res):
                        await res
                return

            buffered_chunks.append(delta)
            joined = "".join(buffered_chunks)
            trimmed = joined.strip()

            if len(trimmed) < 7:
                if trimmed and not any(trimmed.startswith(p) for p in ["`", "{"]):
                    is_tool_candidate = False
                    accumulated_narrative.extend(buffered_chunks)
                    if token_cb:
                        res = token_cb("".join(accumulated_narrative))
                        if asyncio.iscoroutine(res):
                            await res
                return

            if trimmed.startswith("```json") or trimmed.startswith("```") or (trimmed.startswith("{") and ('"action"' in trimmed or '"tool"' in trimmed)):
                is_tool_candidate = True
            else:
                is_tool_candidate = False
                accumulated_narrative.extend(buffered_chunks)
                if token_cb:
                    res = token_cb("".join(accumulated_narrative))
                    if asyncio.iscoroutine(res):
                        await res

        try:
            raw_out = await provider_caller(messages, on_chunk=_chunk_dispatcher)
        except TypeError:
            raw_out = await provider_caller(messages)

        if not raw_out or not raw_out.strip():
            break
        last_response = raw_out.strip()
        
        json_match = re.search(r"```(?:json)?\s*(\{\s*\"action\"\s*:\s*\"tool_call\".*?\})\s*```", raw_out, re.DOTALL)
        if not json_match:
            if raw_out.strip().startswith("{") and '"action"' in raw_out and '"tool"' in raw_out:
                try:
                    payload = json.loads(raw_out.strip())
                except Exception:
                    payload = None
            else:
                payload = None
        else:
            try:
                payload = json.loads(json_match.group(1))
            except Exception:
                payload = None
                
        if not payload or payload.get("action") != "tool_call":
            if token_cb and not accumulated_narrative and last_response:
                res = token_cb(last_response)
                if asyncio.iscoroutine(res):
                    await res
            return last_response
            
        tool_name = payload.get("tool", "")
        tool_args = payload.get("arguments", {}) or {}
        
        if progress_cb:
            try:
                res_cb = progress_cb({"tool_name": tool_name, "status": "running"})
                if asyncio.iscoroutine(res_cb):
                    await res_cb
            except Exception:
                pass
        
        is_safe_cli = (tool_name == "execute_cli_command" and is_safe_read_only_cli_command(tool_args.get("command", "")))
        if read_only and tool_name not in READ_ONLY_TOOL_NAMES and not is_safe_cli:
            tool_res = {"status": "error", "message": f"Tool '{tool_name}' dinonaktifkan di Plan Mode (Read-Only)."}
        else:
            tool_res = await dispatch_tool_call(tool_name, tool_args, read_only=read_only)

        if tool_name == "interactive_question" and isinstance(tool_res, dict) and tool_res.get("dismissed"):
            dismiss_notice = "Pertanyaan ditutup."
            if token_cb:
                res = token_cb(dismiss_notice)
                if asyncio.iscoroutine(res):
                    await res
            return dismiss_notice
        
        if progress_cb:
            try:
                res_cb = progress_cb({
                    "tool_name": tool_name,
                    "status": "done",
                    "summary": (tool_res.get("message") or tool_res.get("summary") or "")[:160] if isinstance(tool_res, dict) else str(tool_res)[:160]
                })
                if asyncio.iscoroutine(res_cb):
                    await res_cb
            except Exception:
                pass
            
        messages.append({"role": "assistant", "content": raw_out})
        messages.append({
            "role": "user",
            "content": f"[TOOL RESULT for {tool_name}]:\n{json.dumps(tool_res, ensure_ascii=False)}\n\nLanjutkan tugas berikutnya atau berikan penjelasan akhir yang cerdas dan lengkap jika semua langkah telah selesai."
        })

        if progress_cb:
            try:
                res_cb = progress_cb({
                    "tool_name": "agent",
                    "status": "thinking",
                    "summary": "Merumuskan cetak biru arsitektur & analisis..." if read_only else "Menyusun perubahan kode & langkah implementasi..."
                })
                if asyncio.iscoroutine(res_cb):
                    await res_cb
            except Exception:
                pass
        
    return last_response


async def call_universal_chat_model(
    model_id: str,
    user_prompt: str,
    system_instruction: str = "",
    max_tokens: Optional[int] = None,
    temperature: float = 0.7,
    read_only: bool = False,
    progress_cb: Optional[Callable[[Dict[str, Any]], Any]] = None,
    token_cb: Optional[Callable[[str], Any]] = None,
) -> Optional[str]:
    """
    Executes a chat generation turn with any dynamically selected model.
    Uncapped native generation by default to support complete multi-phase blueprints and large codebases.
    """
    if model_id.startswith("gemini") or model_id.startswith("gemma") or model_id.startswith("models/"):
        from core import key_manager
        from tools import generate_text_response_with_tools

        gemini_model_name = model_id.replace("models/", "")
        if "live-preview" in gemini_model_name or "native-audio" in gemini_model_name:
            gemini_model_name = "gemini-3.5-flash-lite"

        active_target_model = gemini_model_name

        async def _call(client):
            return await generate_text_response_with_tools(
                client=client,
                model=active_target_model,
                user_prompt=user_prompt,
                system_instruction=system_instruction,
                max_tokens=max_tokens,
                temperature=temperature,
                read_only=read_only,
                progress_cb=progress_cb,
                token_cb=token_cb,
            )

        return await key_manager.execute_with_failover(_call)

    if model_id.startswith("codex/") or model_id.startswith("openai/"):
        from memory import memory_engine
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
                acc_id = accounts[idx]["id"] if idx < len(accounts) else None

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

                    async with httpx.AsyncClient(timeout=45.0) as client:
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
                    }
                    if max_tokens is not None and max_tokens > 0:
                        payload["max_tokens"] = max_tokens

                    async with httpx.AsyncClient(timeout=45.0) as client:
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

        return await _execute_json_agent_loop(_codex_call, user_prompt, system_instruction, read_only=read_only, progress_cb=progress_cb, token_cb=token_cb)

    if model_id.startswith("anthropic/"):
        from memory import memory_engine
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
                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        res = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
                        if res.status_code == 200:
                            data = res.json()
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

        return await _execute_json_agent_loop(_anthropic_call, user_prompt, system_instruction, read_only=read_only, progress_cb=progress_cb, token_cb=token_cb)

    from memory import memory_engine
    custom_nodes = memory_engine.get_custom_providers()
    for c_node in custom_nodes:
        c_prefix = c_node["prefix"]
        if model_id.startswith(f"{c_prefix}/"):
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

                async with httpx.AsyncClient(timeout=120.0) as client:
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

            return await _execute_json_agent_loop(_custom_call, user_prompt, system_instruction, read_only=read_only, progress_cb=progress_cb, token_cb=token_cb)

    from core import key_manager
    from tools import generate_text_response_with_tools
    client = key_manager.get_client()
    return await generate_text_response_with_tools(
        client=client,
        model="gemini-3.5-flash-lite",
        user_prompt=user_prompt,
        system_instruction=system_instruction,
        max_tokens=max_tokens,
        temperature=temperature,
        progress_cb=progress_cb,
        token_cb=token_cb,
    )
