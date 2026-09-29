import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

from .constants import PROVIDER_METADATA, _DYNAMIC_CACHE, _DYNAMIC_CACHE_LOCK

logger = logging.getLogger(__name__)

_ROTATION_LOCK = threading.RLock()
_PROVIDER_ROTATION_INDEX: Dict[str, int] = {}


def _sanitize_account_for_client(acc: Dict[str, Any]) -> Dict[str, Any]:
    """Anara Enterprise Architecture: Masks raw API key before sending account data to client."""
    safe = dict(acc)
    raw_key = safe.pop("api_key", None)
    if raw_key:
        if len(raw_key) > 8:
            safe["masked_key"] = f"{raw_key[:4]}...{raw_key[-4:]}"
        else:
            safe["masked_key"] = "••••••••"
    else:
        safe["masked_key"] = "(none)"
    return safe


def disconnect_provider_api_key(provider: str) -> bool:
    """Explicitly disconnects a provider, deleting its accounts and disabling it."""
    from memory import memory_engine
    prov = provider.strip().lower()
    
    memory_engine.delete_ai_accounts_by_provider(prov)
    
    setting_key_map = {
        "gemini": "gemini_api_key",
        "anthropic": "anthropic_api_key",
        "codex": "codex_api_key",
        "openai": "openai_api_key",
        "openrouter": "openrouter_api_key",
        "groq": "groq_api_key",
        "deepseek": "deepseek_api_key",
        "xai": "xai_api_key",
    }
    db_key_name = setting_key_map.get(prov)
    if db_key_name:
        with memory_engine._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM app_settings WHERE key = ?", (db_key_name,))
            conn.commit()

    memory_engine.set_app_setting(f"provider_disconnected_{prov}", "true")

    with _DYNAMIC_CACHE_LOCK:
        _DYNAMIC_CACHE.pop(prov, None)
        _DYNAMIC_CACHE.pop("custom_providers", None)
    logger.info(f"[ModelRouter] Disconnected provider '{prov}' and marked as disconnected")
    
    if prov == "gemini":
        from core import key_manager
        key_manager.reload_keys()
    return True


def get_provider_key(provider: str) -> Optional[str]:
    """Resolves provider active API key with round-robin pool rotation, cooldown awareness, and fallback."""
    from memory import memory_engine
    prov = provider.strip().lower()
    
    if memory_engine.get_app_setting(f"provider_disconnected_{prov}") == "true":
        return None

    accounts = memory_engine.get_ai_accounts(prov)
    if not accounts and prov == "codex":
        accounts = memory_engine.get_ai_accounts("openai")
    if not accounts and prov == "openai":
        accounts = memory_engine.get_ai_accounts("codex")

    enabled_accounts = [a for a in accounts if a.get("is_enabled", 1) == 1]
    if enabled_accounts:
        now = time.time()
        healthy_accounts = [
            a for a in enabled_accounts
            if a.get("status") != "invalid" and (a.get("cooldown_until") or 0.0) <= now
        ]
        if healthy_accounts:
            with _ROTATION_LOCK:
                idx = _PROVIDER_ROTATION_INDEX.get(prov, 0)
                selected = healthy_accounts[idx % len(healthy_accounts)]
                _PROVIDER_ROTATION_INDEX[prov] = (idx + 1) % len(healthy_accounts)
            return selected["api_key"]

        # All accounts in cooldown — select key recovering soonest if within 60s
        soonest = min(enabled_accounts, key=lambda a: a.get("cooldown_until") or 0.0)
        if (soonest.get("cooldown_until") or 0.0) - now <= 60.0:
            return soonest["api_key"]
        return None
    elif accounts:
        return None

    # Check custom providers table
    try:
        custom_nodes = memory_engine.get_custom_providers()
        for c in custom_nodes:
            if c.get("prefix", "").lower() == prov and c.get("is_active", 1):
                k = c.get("api_key")
                if k and k.strip():
                    return k.strip()
    except Exception:
        pass

    setting_key_map = {
        "gemini": "gemini_api_key",
        "anthropic": "anthropic_api_key",
        "codex": "codex_api_key",
        "openai": "openai_api_key",
        "openrouter": "openrouter_api_key",
        "groq": "groq_api_key",
        "deepseek": "deepseek_api_key",
        "xai": "xai_api_key",
    }
    db_key_name = setting_key_map.get(prov)
    if db_key_name:
        val = memory_engine.get_app_setting(db_key_name)
        if val and val.strip():
            return val.strip()

    env_key_map = {
        "gemini": "GEMINI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "codex": "OPENAI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "groq": "GROQ_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "xai": "XAI_API_KEY",
    }
    env_name = env_key_map.get(prov)
    if env_name:
        env_val = os.environ.get(env_name, "").strip()
        if env_val:
            return env_val
    return None


def is_provider_configured(provider: str) -> bool:
    """Checks if a provider has active credentials and is not disconnected."""
    from memory import memory_engine
    prov = provider.strip().lower()
    
    if memory_engine.get_app_setting(f"provider_disconnected_{prov}") == "true":
        return False

    try:
        custom_nodes = memory_engine.get_custom_providers()
        for c in custom_nodes:
            if c["prefix"].lower() == prov and c.get("is_active", 1):
                return True
    except Exception:
        pass

    if prov == "gemini":
        from core import key_manager
        return key_manager.total_keys > 0 or bool(get_provider_key("gemini"))
    
    if prov in ["codex", "openai"]:
        return bool(get_provider_key("codex") or get_provider_key("openai"))

    return bool(get_provider_key(prov))


def has_any_active_provider() -> bool:
    """Checks whether ANY provider (standard or custom) is configured and ready to use."""
    from memory import memory_engine
    for prov in PROVIDER_METADATA.keys():
        if is_provider_configured(prov):
            return True
    try:
        custom_nodes = memory_engine.get_custom_providers()
        if any(c.get("is_active", 1) for c in custom_nodes):
            return True
    except Exception:
        pass
    return False


def sync_env_to_accounts() -> None:
    """
    Universal .env -> SQLite Account Synchronizer (Anara Standard):
    Ensures that any keys or custom providers specified by any user in their .env
    are automatically discovered, loaded, and registered into SQLite (ai_accounts & custom_providers).
    Allows ANY user to simply provide a .env and have Anara work immediately out of the box.
    """
    from memory import memory_engine

    # 1. Standard provider keys
    env_keys = {
        "gemini": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        "openai": os.getenv("OPENAI_API_KEY"),
        "anthropic": os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY"),
        "groq": os.getenv("GROQ_API_KEY"),
        "deepseek": os.getenv("DEEPSEEK_API_KEY"),
        "openrouter": os.getenv("OPENROUTER_API_KEY"),
        "xai": os.getenv("XAI_API_KEY"),
    }

    for prov, key_val in env_keys.items():
        if not key_val or not key_val.strip():
            continue
        # Do not resurrect explicitly disconnected providers upon restart
        if memory_engine.get_app_setting(f"provider_disconnected_{prov}") == "true":
            continue
        clean_key = key_val.strip()
        existing = memory_engine.get_ai_accounts(prov)
        has_key = any(a.get("api_key") == clean_key for a in existing)
        if not has_key:
            add_provider_account(prov, f"{prov.capitalize()} (.env)", clean_key)
            logger.info(f"[AccountSync] Automatically registered {prov} key from .env into SQLite.")

    # 2. Custom provider (9Router, OpenRouter, etc.)
    c_url = os.getenv("CUSTOM_PROVIDER_BASE_URL", "").strip()
    if c_url:
        c_name = os.getenv("CUSTOM_PROVIDER_NAME", "Custom Router").strip()
        c_prefix = os.getenv("CUSTOM_PROVIDER_PREFIX", "custom").strip()
        c_key = os.getenv("CUSTOM_PROVIDER_API_KEY", "").strip()

        existing_custom = memory_engine.get_custom_providers()
        match = next((cp for cp in existing_custom if cp.get("base_url") == c_url or cp.get("prefix") == c_prefix), None)
        if not match:
            memory_engine.add_custom_provider(
                name=c_name,
                base_url=c_url,
                api_key=c_key,
                prefix=c_prefix,
                api_type="chat_completions"
            )
            logger.info(f"[AccountSync] Automatically registered custom provider '{c_name}' ({c_prefix}) from .env into SQLite.")

    # 3. Local Ollama provider if specified
    ollama_url = os.getenv("OLLAMA_BASE_URL", "").strip()
    if ollama_url:
        existing_custom = memory_engine.get_custom_providers()
        match = next((cp for cp in existing_custom if "ollama" in cp.get("prefix", "").lower() or cp.get("base_url") == ollama_url), None)
        if not match:
            memory_engine.add_custom_provider(
                name="Ollama Local",
                base_url=ollama_url,
                api_key="ollama",
                prefix="ollama",
                api_type="chat_completions"
            )
            logger.info(f"[AccountSync] Automatically registered Ollama from .env into SQLite.")

    # 4. Default active model override from .env
    active_env_model = os.getenv("DEFAULT_AI_MODEL") or os.getenv("ACTIVE_MODEL")
    if active_env_model and active_env_model.strip():
        curr = get_active_model_id()
        if not curr or curr == "gemini-2.5-flash" or curr.startswith("models/"):
            set_active_model_id(active_env_model.strip())


def get_active_model_id() -> str:
    """Returns the currently selected model ID."""
    from memory import memory_engine
    saved = memory_engine.get_app_setting("active_ai_model")
    if saved and saved.strip():
        return saved.strip()
    try:
        from config import cfg_get
        conf = cfg_get("model.default")
        if conf and str(conf).strip():
            return str(conf).strip()
    except Exception:
        pass
    return "gemini-2.5-flash"


def get_fallback_model_id() -> str:
    """
    Returns the fallback model ID dynamically configured in config or settings.
    Anara Standard: Multi-tier fallback ladder across healthy configured providers.
    """
    from memory import memory_engine
    saved = memory_engine.get_app_setting("fallback_ai_model")
    if saved and saved.strip():
        return saved.strip()
    try:
        from config import cfg_get
        conf = cfg_get("model.fallback")
        if conf and str(conf).strip():
            return str(conf).strip()
    except Exception:
        pass

    active_mid = get_active_model_id()
    ladder_candidates = [
        ("anthropic", "claude-3-5-sonnet-latest"),
        ("gemini", "gemini-2.5-flash"),
        ("openai", "gpt-4o"),
        ("groq", "groq/llama-3.3-70b-versatile"),
        ("deepseek", "deepseek/deepseek-chat"),
    ]
    for p_id, default_m in ladder_candidates:
        if is_provider_configured(p_id) and default_m != active_mid:
            return default_m

    return active_mid


def set_active_model_id(model_id: str) -> bool:
    """Sets and persists the active model ID."""
    from memory import memory_engine
    clean_id = model_id.strip()
    if clean_id.startswith("ag/"):
        clean_id = f"9router/{clean_id}"
    memory_engine.set_app_setting("active_ai_model", clean_id)
    logger.info(f"[ModelRouter] Switched active model to: {clean_id}")
    return True


def add_provider_account(provider: str, account_label: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Adds a new labeled account to the provider pool and enables the provider."""
    from memory import memory_engine
    prov = provider.strip().lower()
    clean_key = (api_key or "").strip()
    if not clean_key:
        return None

    with memory_engine._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM app_settings WHERE key = ?", (f"provider_disconnected_{prov}",))
        conn.commit()

    res = memory_engine.add_ai_account(provider=prov, account_label=account_label, api_key=clean_key)
    with _DYNAMIC_CACHE_LOCK:
        _DYNAMIC_CACHE.pop(prov, None)
        _DYNAMIC_CACHE.pop("custom_providers", None)
    
    if prov == "gemini":
        from core import key_manager
        key_manager.reload_keys()
    
    return res


def toggle_provider_account(provider: str, account_id: int) -> Optional[int]:
    """Toggles an account's enabled state in the pool."""
    from memory import memory_engine
    prov = provider.strip().lower()
    res = memory_engine.toggle_ai_account(account_id)
    with _DYNAMIC_CACHE_LOCK:
        _DYNAMIC_CACHE.pop(prov, None)
        _DYNAMIC_CACHE.pop("custom_providers", None)
    if prov == "gemini":
        from core import key_manager
        key_manager.reload_keys()
    return res


def delete_provider_account(provider: str, account_id: int) -> bool:
    """Deletes an account from the pool by ID."""
    from memory import memory_engine
    prov = provider.strip().lower()
    ok = memory_engine.delete_ai_account(account_id)
    with _DYNAMIC_CACHE_LOCK:
        _DYNAMIC_CACHE.pop(prov, None)
        _DYNAMIC_CACHE.pop("custom_providers", None)
    
    if prov == "gemini":
        from core import key_manager
        key_manager.reload_keys()
        
    return ok


def save_provider_api_key(provider: str, api_key: str) -> bool:
    """Saves provider API key safely and enables the provider."""
    prov = provider.strip().lower()
    clean_key = (api_key or "").strip()
    if not clean_key:
        return False
    res = add_provider_account(prov, f"{prov.capitalize()} Account", clean_key)
    return bool(res)


async def get_providers_status_list_async(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Returns all standard & custom providers with live connection status, sanitized account list, credits, and models."""
    from memory import memory_engine
    from .discovery import get_all_dynamic_models
    all_models = await get_all_dynamic_models(force_refresh)
    
    result = []
    # 1. Standard Built-in Providers
    for pid, pinfo in PROVIDER_METADATA.items():
        configured = is_provider_configured(pid)
        prov_models = [m for m in all_models if m["provider"] == pid] if configured else []
        accounts = memory_engine.get_ai_accounts(pid)

        result.append({
            **pinfo,
            "is_connected": configured,
            "models_count": len(prov_models),
            "accounts_count": len(accounts),
            "accounts": [_sanitize_account_for_client(a) for a in accounts],
            "models": prov_models,
            "credit_info": None,
            "is_custom": False,
        })

    # 2. Custom Providers (OpenAI & Anthropic Compatible)
    custom_nodes = memory_engine.get_custom_providers()
    for c_node in custom_nodes:
        c_prefix = c_node["prefix"]
        prov_models = [m for m in all_models if m["provider"] == c_prefix]
        c_safe = dict(c_node)
        c_safe.pop("api_key", None)
        c_safe["api_key"] = c_node.get("masked_key", "(none)")
        result.append({
            "id": c_prefix,
            "name": c_node["name"],
            "badge": "OpenAI / Anthropic Comp",
            "icon": "custom",
            "description": f"Custom API: {c_node['base_url']} ({c_node.get('api_type', 'chat_completions')})",
            "auth_type": "custom",
            "is_connected": bool(c_node.get("is_active", 1)),
            "models_count": len(prov_models),
            "accounts_count": 1 if c_node.get("api_key") else 0,
            "accounts": [{
                "id": c_node["id"],
                "account_label": c_node["name"],
                "masked_key": c_node.get("masked_key", "(none)"),
                "status": "active",
                "is_enabled": 1,
            }] if c_node.get("api_key") else [],
            "models": prov_models,
            "is_custom": True,
            "custom_data": c_safe,
        })

    return result
