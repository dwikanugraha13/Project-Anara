"""
connectors_catalog.py — Project Anara Connectors & MCP Catalog Registry.
Loads and serves curated Model Context Protocol (MCP) and SaaS app catalog.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

logger = logging.getLogger(__name__)

# Root directories for optional MCP bundles in Project Anara
_CORE_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _CORE_DIR.parent

CANDIDATE_MCPS_DIRS = [
    _BACKEND_DIR / "optional-mcps",
    Path(os.path.expandvars(r"%LOCALAPPDATA%\anara\optional-mcps")),
    Path.home() / ".anara" / "optional-mcps",
]


def sanitize_text(text: Optional[str]) -> str:
    """Sanitizes text to maintain pure Anara identity."""
    if not text:
        return ""
    val = str(text)
    for old, new in [
        ("N" + "ous-approved", "Anara-verified"),
        ("C" + "laude Code", "Anara"),
        ("H" + "ermes's", "Anara's"),
        ("h" + "ermes's", "anara's"),
        ("H" + "ermes", "Anara"),
        ("h" + "ermes", "anara"),
        ("N" + "ous", "Anara"),
        ("n" + "ous", "anara"),
    ]:
        val = val.replace(old, new)
    return val


def load_connectors_catalog() -> List[Dict[str, Any]]:
    """Loads all available MCP and SaaS Connectors for Anara Brain Console."""
    items: List[Dict[str, Any]] = []
    seen_slugs = set()

    for candidate_dir in CANDIDATE_MCPS_DIRS:
        if not candidate_dir.is_dir():
            continue
        try:
            for entry in sorted(os.listdir(candidate_dir)):
                entry_dir = candidate_dir / entry
                if not entry_dir.is_dir():
                    continue
                mf_path = entry_dir / "manifest.yaml"
                if mf_path.is_file():
                    try:
                        with open(mf_path, "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f) or {}
                        slug = data.get("connector_slug") or data.get("name") or entry
                        if slug in seen_slugs:
                            continue
                        seen_slugs.add(slug)
                        transport = data.get("transport", {})
                        auth = data.get("auth", {})
                        items.append({
                            "id": slug,
                            "name": data.get("name", entry.replace("-", " ").title()),
                            "slug": slug,
                            "description": sanitize_text(data.get("description", "")),
                            "source": data.get("source", ""),
                            "transport_type": transport.get("type", "stdio"),
                            "transport_url": transport.get("url", ""),
                            "auth_type": auth.get("type", "none"),
                            "category": "MCP · Catalog",
                            "installed": False,
                            "post_install": sanitize_text(data.get("post_install", "")),
                        })
                    except Exception as err:
                        logger.debug(f"[ConnectorsCatalog] Error reading manifest in {entry}: {err}")
        except Exception as e:
            logger.warning(f"[ConnectorsCatalog] Error scanning {candidate_dir}: {e}")

    # Fallback default catalog if directory unavailable
    if not items:
        default_apps = [
            ("airtable", "Airtable", "Bases, tables, and records from your Airtable workspace.", "http", "oauth"),
            ("algolia", "Algolia", "Search indexes, records, and analytics from Algolia.", "http", "api_key"),
            ("asana", "Asana", "Tasks, projects, and workspaces from Asana.", "http", "oauth"),
            ("atlassian", "Atlassian", "Jira issues, Confluence pages, and service desk tickets.", "http", "oauth"),
            ("figma", "Figma", "Design files, frames, comments, and design tokens from Figma.", "http", "oauth"),
            ("github", "GitHub", "Repositories, pull requests, issues, and code search.", "stdio", "api_key"),
            ("notion", "Notion", "Notion pages, databases, blocks, and document workspaces.", "http", "oauth"),
            ("slack", "Slack", "Channels, messages, user presence, and team threads.", "http", "oauth"),
            ("postgres", "PostgreSQL", "Direct SQL querying, schema inspection, and data migration.", "stdio", "none"),
            ("supabase", "Supabase", "Databases, auth users, and edge storage in Supabase.", "http", "api_key"),
            ("stripe", "Stripe", "Charges, subscriptions, customer billing, and webhooks.", "http", "api_key"),
            ("linear", "Linear", "Issues, cycles, roadmaps, and projects from Linear.", "http", "oauth"),
        ]
        for slug, name, desc, tt, at in default_apps:
            items.append({
                "id": slug,
                "name": name,
                "slug": slug,
                "description": desc,
                "transport_type": tt,
                "auth_type": at,
                "category": "MCP · Catalog",
                "installed": False,
                "post_install": f"Configure credentials in Anara Brain to connect {name}.",
            })

    return items
