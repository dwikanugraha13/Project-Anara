"""
skills_hub_tools.py — Skills Hub Management Tool for Project Anara.
Allows the agent and user to search, download, list, and uninstall community skills.
"""

import logging
from typing import Any, Dict, List, Optional

from .events import _emit_agent_event

logger = logging.getLogger(__name__)


async def _tool_skills_hub_manage(
    action: str = "list",
    query: Optional[str] = None,
    skill_name: Optional[str] = None,
    custom_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Manages community skills (searching, installing from GitHub/ClawHub, listing, uninstalling).
    action: 'search', 'install', 'list', 'uninstall'.
    query: search term for finding skills (e.g. 'docker', 'kubernetes', 'nextjs', 'security').
    skill_name: identifier of the skill to install or uninstall.
    custom_url: direct GitHub raw URL to download a custom SKILL.md.
    """
    from core.skills_hub import skills_hub

    act = (action or "list").strip().lower()

    _emit_agent_event("agent_action_start", {
        "tool_name": "skills_hub_manage",
        "action_title": f"Skills Hub ({act.upper()})",
        "detail": f"{skill_name or query or 'All installed'}",
        "icon": "download-cloud"
    })

    if act == "search":
        results = skills_hub.search_skills(query or "")
        return {
            "status": "success",
            "query": query,
            "total_found": len(results),
            "skills": results
        }

    elif act == "install":
        target = skill_name or query
        if not target:
            return {"status": "error", "message": "Parameter 'skill_name' wajib diisi untuk menginstal skill."}
        return await skills_hub.install_skill(target, custom_url=custom_url)

    elif act in ("list", "installed"):
        installed = skills_hub.list_installed_community_skills()
        return {
            "status": "success",
            "total_installed": len(installed),
            "installed_skills": installed
        }

    elif act in ("uninstall", "remove", "delete"):
        target = skill_name or query
        if not target:
            return {"status": "error", "message": "Parameter 'skill_name' wajib diisi untuk menghapus skill."}
        ok = skills_hub.uninstall_skill(target)
        return {
            "status": "success" if ok else "error",
            "message": f"Skill '{target}' {'berhasil dihapus.' if ok else 'tidak ditemukan.'}"
        }

    return {"status": "error", "message": f"Aksi '{act}' tidak dikenal. Gunakan: 'search', 'install', 'list', 'uninstall'."}
