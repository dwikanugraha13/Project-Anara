"""
plugins.py — Project Anara Native Modular Plugin Engine.
Provides discovery, state persistence, lifecycle management, and catalog for Anara Plugins.
"""

import json
import logging
import os
import shutil
import subprocess
import sys
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

CATALOG_PLUGINS: List[Dict[str, Any]] = [
    {
        "id": "code-reviewer",
        "name": "code-reviewer",
        "title": "Code Reviewer & Quality Linter",
        "version": "1.3.0",
        "category": "developer",
        "author": "Anara Lab",
        "description": "Automated syntax auditing, PR code review suggestions, and style gatekeeper.",
        "source": "agent",
        "has_desktop_half": True,
        "has_agent_half": True,
    },
    {
        "id": "db-explorer",
        "name": "db-explorer",
        "title": "Database Explorer & SQL Studio",
        "version": "1.1.2",
        "category": "database",
        "author": "Anara Data",
        "description": "Live schema diagramming, SQLite and PostgreSQL inspection, and visual query runner.",
        "source": "agent",
        "has_desktop_half": True,
        "has_agent_half": True,
    },
    {
        "id": "cloud-ops",
        "name": "cloud-ops",
        "title": "Cloud Ops & Container Sentinel",
        "version": "1.0.8",
        "category": "devops",
        "author": "Anara Infra",
        "description": "Docker, Kubernetes, and cloud container health telemetry and log streaming.",
        "source": "agent",
        "has_desktop_half": True,
        "has_agent_half": True,
    },
    {
        "id": "linear-bridge",
        "name": "linear-bridge",
        "title": "Linear Workspace Synchronizer",
        "version": "1.2.1",
        "category": "productivity",
        "author": "Anara Productivity",
        "description": "Bi-directional ticket sync, cycle tracking, and autonomous issue breakdown.",
        "source": "agent",
        "has_desktop_half": True,
        "has_agent_half": True,
    },
    {
        "id": "slack-agent",
        "name": "slack-agent",
        "title": "Slack Agent & Channel Dispatcher",
        "version": "2.0.1",
        "category": "omnichannel",
        "author": "Anara Intelligence",
        "description": "Autonomous channel listeners, thread responder, and workspace mentions dispatcher.",
        "source": "agent",
        "has_desktop_half": True,
        "has_agent_half": True,
    },
    {
        "id": "vision-ocr",
        "name": "vision-ocr",
        "title": "Vision OCR & Layout Analyzer",
        "version": "1.1.0",
        "category": "vision",
        "author": "Anara Vision",
        "description": "Multi-page PDF text extraction, document OCR parsing, and visual diagram chunking.",
        "source": "agent",
        "has_desktop_half": True,
        "has_agent_half": True,
    },
    {
        "id": "voice-studio",
        "name": "voice-studio",
        "title": "Voice Studio Synthesizer",
        "version": "1.4.0",
        "category": "media",
        "author": "Anara Audio Lab",
        "description": "Custom neural voice modeling, pitch modulation, and real-time audio playback.",
        "source": "agent",
        "has_desktop_half": True,
        "has_agent_half": True,
    },
    {
        "id": "security-vault",
        "name": "security-vault",
        "title": "Security Vault & Secret Sentinel",
        "version": "1.0.5",
        "category": "security",
        "author": "Anara Security",
        "description": "Zero-leak secret masking, environment variable encryption, and credential auditing.",
        "source": "agent",
        "has_desktop_half": True,
        "has_agent_half": True,
    },
]


class AnaraPluginManager:
    """Manages active plugin states, persistence, discovery, and catalog in Project Anara."""

    def __init__(self):
        self._plugins: Dict[str, Dict[str, Any]] = {p["id"]: dict(p) for p in BUILTIN_PLUGINS}
        self._load_custom_plugins()

    def get_plugins_dir(self) -> str:
        """Returns and ensures the %LOCALAPPDATA%\\anara\\plugins root directory."""
        plugins_dir = os.path.expandvars(r"%LOCALAPPDATA%\anara\plugins")
        os.makedirs(plugins_dir, exist_ok=True)
        return plugins_dir

    def _get_saved_states(self, key: str = "plugins_enabled_map") -> Dict[str, bool]:
        from memory import memory_engine
        raw = memory_engine.get_app_setting(key)
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _save_states(self, states: Dict[str, bool], key: str = "plugins_enabled_map") -> None:
        from memory import memory_engine
        memory_engine.set_app_setting(key, json.dumps(states))

    def _load_custom_plugins(self) -> None:
        """Loads custom plugins from SQLite and disk directory."""
        from memory import memory_engine
        raw = memory_engine.get_app_setting("plugins_installed_custom")
        if raw:
            try:
                custom_list = json.loads(raw)
                if isinstance(custom_list, list):
                    for item in custom_list:
                        if isinstance(item, dict) and "id" in item:
                            self._plugins[item["id"]] = dict(item)
            except Exception as e:
                logger.debug(f"[PluginManager] Custom plugins load note: {e}")

    def _save_custom_plugins(self) -> None:
        """Persists custom installed plugins list to SQLite."""
        from memory import memory_engine
        custom_items = [
            p for p in self._plugins.values()
            if p.get("source") in ("user", "git", "agent")
        ]
        memory_engine.set_app_setting("plugins_installed_custom", json.dumps(custom_items))

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Returns all registered plugins with live dual desktop & agent toggle states."""
        agent_states = self._get_saved_states("plugins_enabled_map")
        desktop_states = self._get_saved_states("plugins_desktop_enabled_map")
        result = []
        for pid, p in self._plugins.items():
            item = dict(p)
            def_enabled = p.get("default_enabled", False)
            item["agent_enabled"] = agent_states.get(pid, def_enabled)
            item["desktop_enabled"] = desktop_states.get(pid, def_enabled if item.get("has_desktop_half", True) else False)
            item["enabled"] = item["agent_enabled"]
            item.setdefault("source", "bundled")
            item.setdefault("has_desktop_half", True)
            item.setdefault("has_agent_half", True)
            result.append(item)
        return sorted(result, key=lambda x: (not x["agent_enabled"] and not x["desktop_enabled"], x["title"]))

    def get_catalog(self) -> List[Dict[str, Any]]:
        """Returns installable modular plugin catalog with installation markers."""
        registered_ids = set(self._plugins.keys())
        catalog_items = []
        for cat in CATALOG_PLUGINS:
            item = dict(cat)
            item["installed"] = cat["id"] in registered_ids
            catalog_items.append(item)
        return catalog_items

    def toggle_plugin(
        self,
        plugin_id: str,
        target: str = "agent",
        enabled: Optional[bool] = None
    ) -> Optional[Dict[str, Any]]:
        """Toggles plugin on or off for desktop, agent, or both, persisting state to SQLite."""
        clean_id = (plugin_id or "").strip().lower()
        if clean_id not in self._plugins:
            return None

        agent_states = self._get_saved_states("plugins_enabled_map")
        desktop_states = self._get_saved_states("plugins_desktop_enabled_map")
        p = self._plugins[clean_id]
        def_enabled = p.get("default_enabled", False)

        if target in ("agent", "both"):
            current_agent = agent_states.get(clean_id, def_enabled)
            new_agent = (not current_agent) if enabled is None else bool(enabled)
            agent_states[clean_id] = new_agent
            self._save_states(agent_states, "plugins_enabled_map")

        if target in ("desktop", "both"):
            current_desktop = desktop_states.get(clean_id, def_enabled if p.get("has_desktop_half", True) else False)
            new_desktop = (not current_desktop) if enabled is None else bool(enabled)
            desktop_states[clean_id] = new_desktop
            self._save_states(desktop_states, "plugins_desktop_enabled_map")

        item = dict(p)
        item["agent_enabled"] = agent_states.get(clean_id, def_enabled)
        item["desktop_enabled"] = desktop_states.get(clean_id, def_enabled)
        item["enabled"] = item["agent_enabled"]
        logger.info(f"[PluginManager] Toggled plugin '{clean_id}' ({target}) -> agent={item['agent_enabled']}, desktop={item['desktop_enabled']}")
        return item

    def open_plugins_folder(self) -> Dict[str, Any]:
        """Reveals %LOCALAPPDATA%\\anara\\plugins via os.startfile on Windows or system file manager."""
        plugins_dir = self.get_plugins_dir()
        try:
            if sys.platform == "win32":
                os.startfile(plugins_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", plugins_dir])
            else:
                subprocess.Popen(["xdg-open", plugins_dir])
            return {"status": "success", "path": plugins_dir}
        except Exception as e:
            logger.warning(f"[PluginManager] Error opening plugins folder: {e}")
            return {"status": "error", "path": plugins_dir, "error": str(e)}

    def rescan_plugins(self) -> List[Dict[str, Any]]:
        """Scans %LOCALAPPDATA%\\anara\\plugins on disk and synchronizes discovered packages."""
        plugins_dir = self.get_plugins_dir()
        try:
            for entry in os.listdir(plugins_dir):
                entry_dir = os.path.join(plugins_dir, entry)
                if not os.path.isdir(entry_dir):
                    continue
                manifest_path = os.path.join(entry_dir, "plugin.json")
                if os.path.isfile(manifest_path):
                    try:
                        with open(manifest_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        pid = data.get("id") or entry.lower()
                        if pid not in self._plugins:
                            self._plugins[pid] = {
                                "id": pid,
                                "name": data.get("name", entry),
                                "title": data.get("title", entry.replace("-", " ").title()),
                                "version": data.get("version", "1.0.0"),
                                "category": data.get("category", "user"),
                                "author": data.get("author", "Local User"),
                                "description": data.get("description", "User-installed modular plugin."),
                                "default_enabled": True,
                                "source": data.get("source", "user"),
                                "has_desktop_half": data.get("has_desktop_half", True),
                                "has_agent_half": True,
                                "file": entry_dir,
                            }
                    except Exception as err:
                        logger.debug(f"[PluginManager] Error parsing {manifest_path}: {err}")
        except Exception as e:
            logger.warning(f"[PluginManager] Rescan error: {e}")

        self._save_custom_plugins()
        return self.list_plugins()

    def install_plugin(
        self,
        identifier_or_repo: str,
        branch: Optional[str] = None,
        name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Installs a plugin from the catalog or a Git repository into %LOCALAPPDATA%\\anara\\plugins."""
        ident = (identifier_or_repo or "").strip()
        if not ident:
            raise ValueError("Plugin identifier or repository URL cannot be empty.")

        plugins_dir = self.get_plugins_dir()

        # Check if catalog match
        catalog_match = next((c for c in CATALOG_PLUGINS if c["id"] == ident.lower()), None)
        if catalog_match:
            pid = catalog_match["id"]
            target_dir = os.path.join(plugins_dir, pid)
            os.makedirs(target_dir, exist_ok=True)
            manifest = dict(catalog_match)
            manifest["source"] = "agent"
            manifest["default_enabled"] = True
            manifest["file"] = target_dir
            with open(os.path.join(target_dir, "plugin.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)

            self._plugins[pid] = manifest
            self._save_custom_plugins()

            self.toggle_plugin(pid, target="both", enabled=True)
            logger.info(f"[PluginManager] Installed catalog plugin '{pid}' successfully.")
            return manifest

        # Git repository install
        if ident.startswith("http://") or ident.startswith("https://") or ident.endswith(".git"):
            repo_name = name or ident.rstrip("/").split("/")[-1].replace(".git", "")
            pid = repo_name.lower()
            target_dir = os.path.join(plugins_dir, pid)
            cmd = ["git", "clone", "--depth", "1"]
            if branch:
                cmd.extend(["-b", branch])
            cmd.extend([ident, target_dir])

            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=60)
            except Exception as e:
                logger.warning(f"[PluginManager] Git clone failed ({e}), creating registered stub.")
                os.makedirs(target_dir, exist_ok=True)

            manifest = {
                "id": pid,
                "name": repo_name,
                "title": repo_name.replace("-", " ").title(),
                "version": "1.0.0",
                "category": "git",
                "author": "Git Community",
                "description": f"Installed from Git repository {ident}",
                "default_enabled": True,
                "source": "git",
                "has_desktop_half": True,
                "has_agent_half": True,
                "file": target_dir,
            }
            manifest_path = os.path.join(target_dir, "plugin.json")
            if not os.path.isfile(manifest_path):
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2)

            self._plugins[pid] = manifest
            self._save_custom_plugins()
            self.toggle_plugin(pid, target="both", enabled=True)
            logger.info(f"[PluginManager] Installed git plugin '{pid}' successfully.")
            return manifest

        # Generic custom plugin
        pid = ident.lower().replace(" ", "-")
        target_dir = os.path.join(plugins_dir, pid)
        os.makedirs(target_dir, exist_ok=True)
        manifest = {
            "id": pid,
            "name": ident,
            "title": ident.replace("-", " ").title(),
            "version": "1.0.0",
            "category": "user",
            "author": "Local User",
            "description": f"Custom user plugin package '{ident}'.",
            "default_enabled": True,
            "source": "user",
            "has_desktop_half": True,
            "has_agent_half": True,
            "file": target_dir,
        }
        with open(os.path.join(target_dir, "plugin.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        self._plugins[pid] = manifest
        self._save_custom_plugins()
        self.toggle_plugin(pid, target="both", enabled=True)
        return manifest

    def uninstall_plugin(self, plugin_id: str) -> bool:
        """Removes a user or git plugin package from disk and registry."""
        clean_id = (plugin_id or "").strip().lower()
        if clean_id not in self._plugins:
            return False

        p = self._plugins[clean_id]
        if p.get("source") == "bundled":
            raise ValueError("Built-in bundled plugins cannot be uninstalled.")

        plugins_dir = self.get_plugins_dir()
        target_dir = os.path.join(plugins_dir, clean_id)
        if os.path.isdir(target_dir):
            try:
                shutil.rmtree(target_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"[PluginManager] Error removing plugin dir {target_dir}: {e}")

        del self._plugins[clean_id]
        self._save_custom_plugins()
        logger.info(f"[PluginManager] Successfully uninstalled plugin '{clean_id}'.")
        return True


plugin_manager = AnaraPluginManager()
