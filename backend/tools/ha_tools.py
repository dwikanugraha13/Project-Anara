"""
ha_tools.py — Home Assistant & Smart Home IoT Tools for Project Anara.
Anara Standard homeassistant toolset: allows Anara to monitor
and control IoT smart devices, lights, switches, scenes, and climate sensors.
"""

import logging
import os
from typing import Any, Dict, List, Optional
import httpx

from .events import _emit_agent_event

logger = logging.getLogger(__name__)


def _get_ha_config() -> tuple[str, str]:
    """Retrieves Home Assistant base URL and bearer token from environment or SQLite settings."""
    from memory import memory_engine

    base_url = (
        os.getenv("HASS_URL")
        or os.getenv("HOMEASSISTANT_URL")
        or memory_engine.get_app_setting("homeassistant_url")
        or "http://localhost:8123"
    ).rstrip("/")

    token = (
        os.getenv("HASS_TOKEN")
        or os.getenv("HOMEASSISTANT_TOKEN")
        or memory_engine.get_app_setting("homeassistant_token")
        or ""
    ).strip()

    return base_url, token


async def _tool_ha_list_entities(domain: Optional[str] = None) -> Dict[str, Any]:
    """
    Lists smart home entities and their states from Home Assistant.
    domain: Optional filter like 'light', 'switch', 'sensor', 'climate', 'media_player'.
    """
    base_url, token = _get_ha_config()

    _emit_agent_event("agent_action_start", {
        "tool_name": "ha_list_entities",
        "action_title": "Smart Home: Cek Perangkat",
        "detail": f"Domain: {domain or 'Semua entitas'}",
        "icon": "home"
    })

    if not token:
        return {
            "status": "warning",
            "configured": False,
            "message": "Home Assistant is not configured. Set HASS_URL and HASS_TOKEN in .env file or Settings to enable IoT control.",
            "entities": []
        }

    url = f"{base_url}/api/states"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                all_states = res.json()
                if domain:
                    clean_dom = domain.strip().lower()
                    filtered = [s for s in all_states if s.get("entity_id", "").startswith(f"{clean_dom}.")]
                else:
                    filtered = all_states[:50]  # Limit if no filter

                summary = [
                    {
                        "entity_id": s.get("entity_id"),
                        "state": s.get("state"),
                        "friendly_name": s.get("attributes", {}).get("friendly_name", s.get("entity_id")),
                    }
                    for s in filtered
                ]
                return {
                    "status": "success",
                    "configured": True,
                    "total_found": len(summary),
                    "entities": summary
                }
            else:
                return {
                    "status": "error",
                    "configured": True,
                    "message": f"Home Assistant API returned status {res.status_code}: {res.text}"
                }
    except Exception as e:
        logger.warning(f"[HomeAssistant] Connection failed: {e}")
        return {
            "status": "error",
            "configured": True,
            "message": f"Failed to connect to Home Assistant at {base_url}: {str(e)}"
        }


async def _tool_ha_get_state(entity_id: str) -> Dict[str, Any]:
    """Retrieves detailed attributes and state for a specific Home Assistant entity."""
    clean_id = (entity_id or "").strip()
    if not clean_id:
        return {"status": "error", "message": "Parameter 'entity_id' is required (e.g. 'light.living_room')."}

    base_url, token = _get_ha_config()
    if not token:
        return {
            "status": "warning",
            "configured": False,
            "message": "Home Assistant is not configured (HASS_TOKEN not set)."
        }

    url = f"{base_url}/api/states/{clean_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                data = res.json()
                return {
                    "status": "success",
                    "entity_id": clean_id,
                    "state": data.get("state"),
                    "attributes": data.get("attributes", {}),
                    "last_updated": data.get("last_updated")
                }
            elif res.status_code == 404:
                return {"status": "error", "message": f"Entity '{clean_id}' not found in Home Assistant."}
            else:
                return {"status": "error", "message": f"API error {res.status_code}: {res.text}"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to read entity {clean_id}: {str(e)}"}


async def _tool_ha_call_service(
    domain: str,
    service: str,
    entity_id: Optional[str] = None,
    service_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calls a Home Assistant service (e.g. domain='light', service='turn_on', entity_id='light.bedroom').
    """
    clean_domain = (domain or "").strip().lower()
    clean_service = (service or "").strip().lower()
    base_url, token = _get_ha_config()

    _emit_agent_event("agent_action_start", {
        "tool_name": "ha_call_service",
        "action_title": f"Smart Home: {clean_domain}.{clean_service}",
        "detail": f"Target: {entity_id or 'Global'}",
        "icon": "zap"
    })

    if not token:
        return {
            "status": "warning",
            "configured": False,
            "message": "Home Assistant is not configured. Set HASS_TOKEN to enable IoT control."
        }

    url = f"{base_url}/api/services/{clean_domain}/{clean_service}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload: Dict[str, Any] = {}
    if service_data and isinstance(service_data, dict):
        payload.update(service_data)
    if entity_id:
        payload["entity_id"] = entity_id.strip()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code in (200, 201):
                return {
                    "status": "success",
                    "domain": clean_domain,
                    "service": clean_service,
                    "target": entity_id,
                    "message": f"Service '{clean_domain}.{clean_service}' executed successfully on Home Assistant."
                }
            else:
                return {"status": "error", "message": f"Failed to execute service: HTTP {res.status_code}: {res.text}"}
    except Exception as e:
        return {"status": "error", "message": f"Connection error to Home Assistant: {str(e)}"}
