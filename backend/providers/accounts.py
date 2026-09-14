import logging
import os
import time
from typing import Any, Dict, List, Optional

from .constants import PROVIDER_METADATA, _DYNAMIC_CACHE

logger = logging.getLogger(__name__)


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
    }
    db_key_name = setting_key_map.get(prov)
    if db_key_name:
        with memory_engine._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM app_settings WHERE key = ?", (db_key_name,))
            conn.commit()

    memory_engine.set_app_setting(f"provider_disconnected_{prov}", "true")

    _DYNAMIC_CACHE.pop(prov, None)
    _DYNAMIC_CACHE.pop("custom_providers", None)
    logger.info(f"[ModelRouter] Disconnected provider '{prov}' and marked as disconnected")
    
    if prov == "gemini":
        from core import key_manager
        key_manager.reload_keys()
    return True


def get_provider_key(provider: str) -> Optional[str]:
    """Resolves provider active API key from SQLite ai_accounts pool, then app_settings/env."""
    from memory import memory_engine
    prov = provider.strip().lower()
    
    if memory_engine.get_app_setting(f"provider_disconnected_{prov}") == "true":
        return None

    accounts = memory_engine.get_ai_accounts(prov)
    if not accounts and prov == "codex":
        accounts = memory_engine.get_ai_accounts("openai")
    enabled_accounts = [a for a in accounts if a.get("is_enabled", 1) == 1]
    if enabled_accounts:
        now = time.time()
        for acc in enabled_accounts:
            if acc.get("status") != "invalid" and (acc.get("cooldown_until") or 0.0) <= now:
                return acc["api_key"]
        return enabled_accounts[0]["api_key"]
    elif accounts:
        return None

    setting_key_map = {
        "gemini": "gemini_api_key",
        "anthropic": "anthropic_api_key",
        "codex": "codex_api_key",
        "openai": "openai_api_key",
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


def get_active_model_id() -> str:
    """Returns the currently selected model ID."""
    from memory import memory_engine
    saved = memory_engine.get_app_setting("active_ai_model")
    if saved and saved.strip():
        return saved.strip()
    return "gemini-3.5-flash-lite"


def set_active_model_id(model_id: str) -> bool:
    """Sets and persists the active model ID."""
    from memory import memory_engine
    memory_engine.set_app_setting("active_ai_model", model_id.strip())
    logger.info(f"[ModelRouter] Switched active model to: {model_id}")
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
    add_provider_account(prov, f"{prov.capitalize()} Account", clean_key)
    return True


async def get_providers_status_list_async(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Returns all standard & custom providers with live connection status, account list, credits, and models."""
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
            "accounts": accounts,
            "models": prov_models,
            "credit_info": None,
            "is_custom": False,
        })

    # 2. Custom Providers (OpenAI & Anthropic Compatible)
    custom_nodes = memory_engine.get_custom_providers()
    for c_node in custom_nodes:
        c_prefix = c_node["prefix"]
        prov_models = [m for m in all_models if m["provider"] == c_prefix]
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
            "custom_data": c_node,
        })

    return result
