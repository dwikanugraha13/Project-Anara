import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional
import httpx

from .constants import (
    _DYNAMIC_CACHE,
    _CACHE_TTL_SECONDS,
    _infer_model_badge_and_category,
)
from .accounts import (
    is_provider_configured,
    get_provider_key,
    get_active_model_id,
)

logger = logging.getLogger(__name__)


async def fetch_gemini_models(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Discovers live models available on Google AI Studio if API key is configured."""
    from core import key_manager
    from google import genai
    
    if not is_provider_configured("gemini"):
        return []

    cache_key = "gemini"
    now = time.time()
    if not force_refresh and cache_key in _DYNAMIC_CACHE:
        entry = _DYNAMIC_CACHE[cache_key]
        if now - entry["timestamp"] < _CACHE_TTL_SECONDS:
            return entry["models"]

    models_list = []
    live_models = [
        {
            "id": "gemini-3.1-flash-live-preview",
            "name": "Gemini 3.1 Flash Live",
            "provider": "gemini",
            "category": "voice_native",
            "badge": "Live Audio",
            "description": "Ultra-fast Gen 3.1 bidirectional real-time audio with natural voice expressions.",
            "icon": "gemini",
            "supports_voice": True,
        },
        {
            "id": "gemini-2.5-flash-live-preview",
            "name": "Gemini 2.5 Flash Live",
            "provider": "gemini",
            "category": "voice_native",
            "badge": "Live Audio",
            "description": "Stable Gen 2.5 low-latency bidirectional streaming audio.",
            "icon": "gemini",
            "supports_voice": True,
        },
        {
            "id": "gemini-2.0-flash-live-preview",
            "name": "Gemini 2.0 Flash Live",
            "provider": "gemini",
            "category": "voice_native",
            "badge": "Live Audio",
            "description": "Classic Gen 2.0 bidirectional audio.",
            "icon": "gemini",
            "supports_voice": True,
        },
    ]
    models_list.extend(live_models)
    live_ids = set(m["id"] for m in live_models)

    fetch_ok = False
    try:
        active_key = get_provider_key("gemini")
        if active_key:
            client = genai.Client(api_key=active_key.split(",")[0].strip())
            def _list():
                return list(client.models.list())
            
            try:
                raw_models = await asyncio.wait_for(asyncio.to_thread(_list), timeout=8.0)
            except asyncio.TimeoutError:
                logger.warning("[ModelRouter] Gemini models.list timed out after 8s — using live_models fallback")
                raw_models = []
                raise TimeoutError("Gemini list timeout")
            for m in raw_models:
                m_name = m.name or ""
                clean_id = m_name.replace("models/", "")
                if clean_id in live_ids:
                    continue
                
                methods = getattr(m, "supported_generation_methods", getattr(m, "supported_actions", [])) or []
                if "generateContent" in methods:
                    disp_name = getattr(m, "display_name", "") or clean_id
                    badge, category, icon = _infer_model_badge_and_category(clean_id, disp_name, "gemini")
                    desc = getattr(m, "description", "") or f"Google Gemini model: {disp_name}"
                    
                    models_list.append({
                        "id": clean_id,
                        "name": disp_name,
                        "provider": "gemini",
                        "category": category,
                        "badge": badge,
                        "description": desc,
                        "icon": icon,
                        "supports_voice": True,
                    })
            fetch_ok = True
        else:
            fetch_ok = True
    except Exception as e:
        if not isinstance(e, TimeoutError):
            logger.warning(f"[ModelRouter] Failed to fetch live Gemini models: {e}")
        if cache_key in _DYNAMIC_CACHE and _DYNAMIC_CACHE[cache_key].get("models"):
            logger.info("[ModelRouter] Gemini fetch failed — returning stale cache")
            return _DYNAMIC_CACHE[cache_key]["models"]

    if fetch_ok:
        _DYNAMIC_CACHE[cache_key] = {"timestamp": now, "models": models_list}
    else:
        _DYNAMIC_CACHE[cache_key] = {"timestamp": now - (_CACHE_TTL_SECONDS - 30), "models": models_list}
    return models_list


async def fetch_codex_models(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Discovers live OpenAI Codex & reasoning models (o3-mini, o1, GPT-4o) when credentials are configured."""
    if not is_provider_configured("codex"):
        return []

    cache_key = "codex"
    now = time.time()
    if not force_refresh and cache_key in _DYNAMIC_CACHE:
        entry = _DYNAMIC_CACHE[cache_key]
        if now - entry["timestamp"] < _CACHE_TTL_SECONDS:
            return entry["models"]

    models_list = []
    fetch_ok = False
    codex_defaults = [
        ("codex/o3-mini", "OpenAI o3-mini (Codex Reasoning)", "High Reasoning", "Latest generation coding & logic reasoning model with advanced intelligence."),
        ("codex/o1", "OpenAI o1 (Codex Deep)", "Deep Reasoning", "OpenAI deep reasoning model for complex architecture and algorithm reasoning."),
        ("codex/o1-mini", "OpenAI o1-mini (Codex Fast)", "Fast Reasoning", "Fast reasoning version of o1 for script generation and code optimization."),
        ("codex/gpt-4o", "GPT-4o Omnimodal", "Omnimodal", "OpenAI flagship multimodal model with high speed and broad reasoning."),
        ("codex/gpt-4o-mini", "GPT-4o Mini", "Fast General", "Ultra-fast efficient model for daily coding tasks and text analysis."),
        ("codex/chatgpt-4o-latest", "ChatGPT-4o Dynamic", "Flagship", "Latest dynamic ChatGPT-4o research model."),
        ("codex/gpt-5.3-codex", "OpenAI Codex 5.3", "Code & Logic", "Official Codex CLI model for script generation, architecture, and code execution."),
    ]
    for mid, mname, mbadge, mdesc in codex_defaults:
        models_list.append({
            "id": mid,
            "name": mname,
            "provider": "codex",
            "category": "deep_reasoning" if "o" in mid or "5.3" in mid else "fast_general",
            "badge": mbadge,
            "description": mdesc,
            "icon": "openai",
            "supports_voice": False,
            "supports_text": True,
        })
    default_ids = set(m["id"] for m in models_list)

    codex_key = get_provider_key("codex") or get_provider_key("openai")
    if codex_key and codex_key.startswith("sk-"):
        try:
            headers = {"Authorization": f"Bearer {codex_key}"}
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.get("https://api.openai.com/v1/models", headers=headers)
                if res.status_code == 200:
                    data = res.json().get("data", [])
                    for item in data:
                        raw_id = item.get("id", "")
                        if not raw_id:
                            continue
                        r_low = raw_id.lower()
                        if not any(k in r_low for k in ["gpt-4", "gpt-3.5", "o1", "o3", "codex"]):
                            continue
                        full_id = f"codex/{raw_id}"
                        if full_id in default_ids:
                            continue
                        badge, category, icon = _infer_model_badge_and_category(raw_id, raw_id, "codex")
                        models_list.append({
                            "id": full_id,
                            "name": f"{raw_id} (OpenAI)",
                            "provider": "codex",
                            "category": category,
                            "badge": badge,
                            "description": f"Official OpenAI model {raw_id}.",
                            "icon": "openai",
                            "supports_voice": False,
                            "supports_text": True,
                        })
            fetch_ok = True
        except Exception as e:
            logger.warning(f"[ModelRouter] Failed to fetch live OpenAI Codex models: {e}")
            if cache_key in _DYNAMIC_CACHE and _DYNAMIC_CACHE[cache_key].get("models"):
                return _DYNAMIC_CACHE[cache_key]["models"]
    else:
        fetch_ok = True

    if fetch_ok:
        _DYNAMIC_CACHE[cache_key] = {"timestamp": now, "models": models_list}
    else:
        _DYNAMIC_CACHE[cache_key] = {"timestamp": now - (_CACHE_TTL_SECONDS - 30), "models": models_list}
    return models_list


async def refresh_codex_oauth_token_if_needed(account_id: Optional[int] = None) -> Optional[str]:
    """Refreshes an expired Codex OAuth access token using stored refresh_token."""
    from memory import memory_engine
    refresh_token = ""
    if account_id:
        refresh_token = memory_engine.get_app_setting(f"codex_refresh_token_{account_id}") or ""
    if not refresh_token:
        refresh_token = memory_engine.get_app_setting("codex_latest_refresh_token") or ""

    if not refresh_token:
        return None

    payload = {
        "grant_type": "refresh_token",
        "client_id": "app_EMoamEEZ73f0CkXaXp7hrann",
        "refresh_token": refresh_token,
        "scope": "openid profile email offline_access",
        "redirect_uri": "http://localhost:1455/auth/callback",
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post("https://auth.openai.com/oauth/token", data=payload, headers=headers)
            if res.status_code == 200:
                token_data = res.json()
                new_access = token_data.get("access_token")
                new_refresh = token_data.get("refresh_token")
                if new_access:
                    with memory_engine._get_connection() as conn:
                        cursor = conn.cursor()
                        if account_id:
                            cursor.execute("UPDATE ai_accounts SET api_key = ? WHERE id = ?", (new_access, account_id))
                        else:
                            cursor.execute("UPDATE ai_accounts SET api_key = ? WHERE provider = 'codex'", (new_access,))
                        conn.commit()
                    if new_refresh and account_id:
                        memory_engine.set_app_setting(f"codex_refresh_token_{account_id}", new_refresh)
                    if new_refresh:
                        memory_engine.set_app_setting("codex_latest_refresh_token", new_refresh)
                    logger.info(f"[CodexOAuth] Successfully refreshed OAuth access token (Account #{account_id})")
                    return new_access
            else:
                logger.warning(f"[CodexOAuth] Token refresh returned HTTP {res.status_code}: {res.text}")
    except Exception as e:
        logger.warning(f"[CodexOAuth] Token refresh exception: {e}")
    return None


async def fetch_anthropic_models(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Discovers models from Anthropic API ONLY when Anthropic key is configured."""
    if not is_provider_configured("anthropic"):
        return []

    cache_key = "anthropic"
    now = time.time()
    if not force_refresh and cache_key in _DYNAMIC_CACHE:
        entry = _DYNAMIC_CACHE[cache_key]
        if now - entry["timestamp"] < _CACHE_TTL_SECONDS:
            return entry["models"]

    models_list = []
    fetch_ok = False
    anthropic_key = get_provider_key("anthropic")
    if anthropic_key:
        try:
            headers = {
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01"
            }
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get("https://api.anthropic.com/v1/models", headers=headers)
                if res.status_code == 200:
                    data = res.json().get("data", [])
                    for item in data:
                        raw_id = item.get("id", "")
                        disp_name = item.get("display_name") or raw_id
                        full_id = f"anthropic/{raw_id}"
                        badge, category, icon = _infer_model_badge_and_category(raw_id, disp_name, "anthropic")
                        models_list.append({
                            "id": full_id,
                            "name": f"{disp_name} (Anthropic Direct)",
                            "provider": "anthropic",
                            "category": category,
                            "badge": badge,
                            "description": f"Official Anthropic model: {disp_name}.",
                            "icon": icon,
                            "supports_voice": True,
                        })
            fetch_ok = True
        except Exception as e:
            logger.warning(f"[ModelRouter] Failed to fetch live Anthropic models: {e}")
            if cache_key in _DYNAMIC_CACHE and _DYNAMIC_CACHE[cache_key].get("models"):
                return _DYNAMIC_CACHE[cache_key]["models"]

    if not models_list and anthropic_key:
        anthropic_defaults = [
            ("anthropic/claude-3-7-sonnet-20250219", "Claude 3.7 Sonnet (Anthropic Direct)", "Hybrid Reasoning"),
            ("anthropic/claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet (Anthropic Direct)", "Advanced Logic"),
            ("anthropic/claude-3-5-haiku-20241022", "Claude 3.5 Haiku (Anthropic Direct)", "Ultra Fast"),
        ]
        for mid, mname, mbadge in anthropic_defaults:
            models_list.append({
                "id": mid,
                "name": mname,
                "provider": "anthropic",
                "category": "deep_reasoning",
                "badge": mbadge,
                "description": "Official Anthropic API access using sk-ant-... key.",
                "icon": "anthropic",
                "supports_voice": True,
            })
        fetch_ok = True

    if fetch_ok:
        _DYNAMIC_CACHE[cache_key] = {"timestamp": now, "models": models_list}
    else:
        _DYNAMIC_CACHE[cache_key] = {"timestamp": now - (_CACHE_TTL_SECONDS - 30), "models": models_list}
    return models_list


async def fetch_custom_providers_models(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Discovers models from all registered custom OpenAI/Anthropic compatible endpoints with in-memory caching."""
    from memory import memory_engine
    custom_nodes = memory_engine.get_custom_providers()
    if not custom_nodes:
        return []

    cache_key = "custom_providers"
    now = time.time()
    if not force_refresh and cache_key in _DYNAMIC_CACHE:
        entry = _DYNAMIC_CACHE[cache_key]
        if now - entry["timestamp"] < _CACHE_TTL_SECONDS:
            return entry["models"]

    async def _fetch_one(node: Dict[str, Any]) -> List[Dict[str, Any]]:
        prefix = node["prefix"]
        base_url = node["base_url"].rstrip("/")
        api_key = node.get("api_key") or ""
        headers: Dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        discovered: List[Dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.get(f"{base_url}/models", headers=headers)
                if res.status_code == 200:
                    d_json = res.json()
                    raw_data = d_json.get("data") if isinstance(d_json, dict) else (d_json if isinstance(d_json, list) else [])
                    for item in (raw_data or []):
                        m_id = item.get("id") if isinstance(item, dict) else str(item)
                        if m_id:
                            full_mid = f"{prefix}/{m_id}"
                            badge, cat, icon = _infer_model_badge_and_category(m_id, m_id, prefix)
                            discovered.append({
                                "id": full_mid,
                                "name": f"{m_id} ({node['name']})",
                                "provider": prefix,
                                "category": cat,
                                "badge": node["name"],
                                "description": f"Custom model via {node['name']} ({base_url})",
                                "icon": "custom",
                                "supports_voice": False,
                                "supports_text": True,
                            })
        except Exception as e:
            logger.debug(f"[CustomProvider] Error fetching /models for {node['name']}: {e}")
        if not discovered and node.get("default_model"):
            m_id = node["default_model"]
            full_mid = f"{prefix}/{m_id}"
            badge, cat, icon = _infer_model_badge_and_category(m_id, m_id, prefix)
            discovered.append({
                "id": full_mid,
                "name": f"{m_id} ({node['name']})",
                "provider": prefix,
                "category": cat,
                "badge": node["name"],
                "description": f"Default custom model via {node['name']}",
                "icon": "custom",
                "supports_voice": False,
                "supports_text": True,
            })
        return discovered

    active_nodes = [n for n in custom_nodes if n.get("is_active", 1)]
    if not active_nodes:
        _DYNAMIC_CACHE[cache_key] = {"timestamp": now, "models": []}
        return []

    results = await asyncio.gather(*[_fetch_one(node) for node in active_nodes], return_exceptions=True)
    all_custom_models: List[Dict[str, Any]] = []
    fetch_ok = False
    for r in results:
        if isinstance(r, list):
            all_custom_models.extend(r)
            if len(r) > 0:
                fetch_ok = True
        elif isinstance(r, Exception):
            logger.debug(f"[CustomProvider] parallel fetch error: {r}")

    if not fetch_ok and len(active_nodes) > 0:
        if cache_key in _DYNAMIC_CACHE and _DYNAMIC_CACHE[cache_key].get("models"):
            logger.info("[ModelRouter] Custom providers fetch all failed — returning stale cache")
            return _DYNAMIC_CACHE[cache_key]["models"]
        _DYNAMIC_CACHE[cache_key] = {"timestamp": now - (_CACHE_TTL_SECONDS - 30), "models": all_custom_models}
    else:
        _DYNAMIC_CACHE[cache_key] = {"timestamp": now, "models": all_custom_models}
    return all_custom_models


async def get_all_dynamic_models(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Fetches all models ONLY from connected providers and prunes hidden models."""
    from memory import memory_engine
    gemini_task = fetch_gemini_models(force_refresh)
    anthropic_task = fetch_anthropic_models(force_refresh)
    codex_task = fetch_codex_models(force_refresh)
    custom_task = fetch_custom_providers_models(force_refresh)

    results = await asyncio.gather(
        gemini_task, anthropic_task, codex_task, custom_task,
        return_exceptions=True
    )

    all_models: List[Dict[str, Any]] = []
    for r in results:
        if isinstance(r, list):
            all_models.extend(r)

    hidden_items = memory_engine.get_hidden_models()
    hidden_ids = set(item["model_id"] for item in hidden_items)
    if hidden_ids:
        all_models = [m for m in all_models if m["id"] not in hidden_ids]

    active_id = get_active_model_id()
    unique_provs = set(m["provider"] for m in all_models)
    prov_configured_map = {p: is_provider_configured(p) for p in unique_provs}

    for m in all_models:
        prov = m["provider"]
        m["is_configured"] = prov_configured_map.get(prov, False)
        m["is_active"] = (m["id"] == active_id)
        m_id_lower = m["id"].lower()
        m["supports_voice"] = (
            "live-preview" in m_id_lower
            or "realtime" in m_id_lower
            or "audio" in m_id_lower
        )
        m["supports_text"] = True

    try:
        from core import ModelCapabilityRegistry
        for m in all_models:
            mid = m["id"]
            info = {
                "name": m.get("name", mid),
                "input_modalities": ["audio"] if m.get("supports_voice") else ["text"],
                "output_modalities": ["text"],
                "supports_voice": m.get("supports_voice", False),
                "supports_text": m.get("supports_text", True),
                "supports_vision": "vision" in mid.lower() or "flash" in mid.lower(),
                "provider": m.get("provider", "unknown"),
                "is_configured": m.get("is_configured", False),
            }
            ModelCapabilityRegistry._cache[mid] = info
        ModelCapabilityRegistry.seed_live_voice_from_key_manager()
    except Exception as e:
        logger.debug(f"[Models] Cache seed skipped: {e}")

    return all_models
