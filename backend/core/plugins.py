"""
plugins.py — Project Anara Native Modular Plugin Engine.
Provides discovery, state persistence, lifecycle management, and catalog for Anara Plugins.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BUILTIN_PLUGINS: List[Dict[str, Any]] = [
    {
        "id": "disk-cleanup",
        "name": "disk-cleanup",
        "title": "Disk Cleanup & Scratch Purge",
        "version": "1.2.0",
        "category": "system",
        "author": "Anara Core",
        "description": "System utility for purging stale scratch cache, orphan temp files, and build artifacts.",
        "default_enabled": True,
        "entrypoint": "plugins.disk_cleanup",
    },
    {
        "id": "security-guidance",
        "name": "security-guidance",
        "title": "Security Guidance & Policy Sentinel",
        "version": "1.0.4",
        "category": "security",
        "author": "Anara Core",
        "description": "Real-time command interception, credential leak scanning, and execution guardrail auditing.",
        "default_enabled": True,
        "entrypoint": "plugins.security_guidance",
    },
    {
        "id": "anara-bots",
        "name": "anara-bots",
        "title": "Omnichannel Bots Orchestrator",
        "version": "2.1.0",
        "category": "omnichannel",
        "author": "Anara Intelligence",
        "description": "Multi-agent bot personas, webhook routing, and background channel listeners across Telegram and chat surfaces.",
        "default_enabled": True,
        "entrypoint": "plugins.bots",
    },
    {
        "id": "kanban",
        "name": "kanban",
        "title": "Interactive Kanban Workspace",
        "version": "1.1.0",
        "category": "productivity",
        "author": "Anara Productivity",
        "description": "Visual task tracking, agile lane progression, and autonomous task breakdown boards.",
        "default_enabled": False,
        "entrypoint": "plugins.kanban",
    },
    {
        "id": "radio-media",
        "name": "radio-media",
        "title": "Ambient Studio Synthesizer",
        "version": "1.0.2",
        "category": "media",
        "author": "Anara Audio Lab",
        "description": "Procedural ambient soundscapes, focus audio generation, and background sonic feedback.",
        "default_enabled": False,
        "entrypoint": "plugins.radio",
    },
    {
        "id": "homeassistant",
        "name": "homeassistant",
        "title": "Home Assistant IoT Telemetry",
        "version": "0.9.5",
        "category": "smart-home",
        "author": "Community",
        "description": "Local smart home automation, sensor telemetry querying, and device state controls.",
        "default_enabled": False,
        "entrypoint": "plugins.homeassistant",
    },
]


class AnaraPluginManager:
    """Manages active plugin states, persistence, and discovery in Project Anara."""

    def __init__(self):
        self._plugins: Dict[str, Dict[str, Any]] = {p["id"]: dict(p) for p in BUILTIN_PLUGINS}

    def _get_saved_states(self) -> Dict[str, bool]:
        from memory import memory_engine
        raw = memory_engine.get_app_setting("plugins_enabled_map")
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _save_states(self, states: Dict[str, bool]) -> None:
        from memory import memory_engine
        memory_engine.set_app_setting("plugins_enabled_map", json.dumps(states))

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Returns all registered plugins with live enabled/disabled toggle states."""
        states = self._get_saved_states()
        result = []
        for pid, p in self._plugins.items():
            item = dict(p)
            item["enabled"] = states.get(pid, p.get("default_enabled", False))
            result.append(item)
        return sorted(result, key=lambda x: (not x["enabled"], x["title"]))

    def toggle_plugin(self, plugin_id: str, enabled: Optional[bool] = None) -> Optional[Dict[str, Any]]:
        """Toggles plugin on or off and persists state to SQLite."""
        clean_id = (plugin_id or "").strip().lower()
        if clean_id not in self._plugins:
            return None

        states = self._get_saved_states()
        current = states.get(clean_id, self._plugins[clean_id].get("default_enabled", False))
        new_state = (not current) if enabled is None else bool(enabled)
        states[clean_id] = new_state
        self._save_states(states)

        item = dict(self._plugins[clean_id])
        item["enabled"] = new_state
        logger.info(f"[PluginManager] Toggled plugin '{clean_id}' -> {'ENABLED' if new_state else 'DISABLED'}")
        return item


plugin_manager = AnaraPluginManager()
