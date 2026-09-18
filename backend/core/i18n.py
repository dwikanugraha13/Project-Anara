"""
i18n.py — Enterprise Localization Engine for Project Anara.
Anara Standard agent/i18n.py & locales/*.yaml:
Provides dotted-key string lookups (t("greetings.morning", name="User")),
language resolution cascade, and missing-key fallback.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

from config import cfg_get

logger = logging.getLogger(__name__)

_LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"
_CATALOG_CACHE: Dict[str, Dict[str, Any]] = {}


def _load_catalog(lang: str) -> Dict[str, Any]:
    """Loads and caches localized strings from backend/locales/<lang>.yaml."""
    clean_lang = (lang or "id").strip().lower()
    if clean_lang in _CATALOG_CACHE:
        return _CATALOG_CACHE[clean_lang]

    catalog_file = _LOCALES_DIR / f"{clean_lang}.yaml"
    if not catalog_file.is_file():
        # Fallback to id.yaml or en.yaml
        catalog_file = _LOCALES_DIR / "id.yaml" if (_LOCALES_DIR / "id.yaml").is_file() else _LOCALES_DIR / "en.yaml"

    try:
        with open(catalog_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            _CATALOG_CACHE[clean_lang] = data
            return data
    except Exception as e:
        logger.debug(f"[i18n] Error loading catalog {catalog_file}: {e}")
        return {}


def resolve_language(requested_lang: Optional[str] = None) -> str:
    """
    Resolves the active language following the hierarchy:
    1. Explicit requested language parameter
    2. ANARA_LANGUAGE environment variable
    3. config.yaml -> display.language or location.language
    4. Default fallback: 'id'
    """
    if requested_lang and requested_lang.strip():
        return requested_lang.strip().lower()

    env_lang = os.getenv("ANARA_LANGUAGE", "").strip().lower()
    if env_lang:
        return env_lang

    cfg_lang = str(cfg_get("display.language") or cfg_get("location.language") or "").strip().lower()
    if cfg_lang:
        return cfg_lang

    return "id"


def t(key: str, lang: Optional[str] = None, **kwargs) -> str:
    """
    Translates a dotted key into a localized string with keyword interpolation (Anara Standard).
    Example: t("briefing.header", name="Agnan", date_str="Senin, 17 September 2026")
    """
    target_lang = resolve_language(lang)
    catalog = _load_catalog(target_lang)

    parts = key.strip().split(".")
    curr: Any = catalog
    for p in parts:
        if isinstance(curr, dict) and p in curr:
            curr = curr[p]
        else:
            # Try fallback language catalog
            fallback_catalog = _load_catalog("id") if target_lang != "id" else _load_catalog("en")
            fb_curr: Any = fallback_catalog
            for fbp in parts:
                if isinstance(fb_curr, dict) and fbp in fb_curr:
                    fb_curr = fb_curr[fbp]
                else:
                    return key
            curr = fb_curr
            break

    if not isinstance(curr, str):
        return key

    try:
        return curr.format(**kwargs) if kwargs else curr
    except Exception:
        return curr
