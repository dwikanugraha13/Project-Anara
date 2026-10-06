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

# Fallback root to optional MCP bundles if present in local runtime
OPTIONAL_MCPS_DIR = os.path.expandvars(r"%LOCALAPPDATA%\hermes\hermes-agent\optional-mcps")


def sanitize_text(text: Optional[str]) -> str:
    """Removes any external framework branding to maintain 100% pure Anara identity."""
    if not text:
        return ""
    res = text.replace("Hermes", "Anara").replace("hermes", "anara")
    return res


def load_connectors_catalog() -> List[Dict[str, Any]]:
    """Loads all available MCP and SaaS Connectors for Anara Brain Console."""
    items: List[Dict[str, Any]] = []

    if os.path.isdir(OPTIONAL_MCPS_DIR):
        try:
            for entry in sorted(os.listdir(OPTIONAL_MCPS_DIR)):
                entry_dir = os.path.join(OPTIONAL_MCPS_DIR, entry)
                if not os.path.isdir(entry_dir):
                    continue
                mf_path = os.path.join(entry_dir, "manifest.yaml")
                if os.path.isfile(mf_path):
                    try:
                        with open(mf_path, "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f) or {}
                        slug = data.get("connector_slug") or data.get("name") or entry
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
            logger.warning(f"[ConnectorsCatalog] Error scanning optional-mcps: {e}")

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
