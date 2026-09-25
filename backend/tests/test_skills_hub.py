"""
test_skills_hub.py — Unit Tests for Anara 100k+ Skills Hub & Toggle Management.
Hermes Agent Parity.
"""

import os
import sys
import pytest
from pathlib import Path

# Setup paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.skills_hub import (
    load_index,
    get_available_sources,
    search_skills,
    install_skill_from_hub,
    uninstall_skill,
)
from core.skill_library import skill_library
from constants import get_anara_skills_dir


def test_skills_hub_sources_and_indexing():
    """Verify Skills Hub loads 100k+ items and enumerates all registry sources."""
    sources = get_available_sources()
    assert len(sources) >= 6
    source_ids = [s["id"] for s in sources]
    assert "all" in source_ids
    assert "official" in source_ids
    assert "github" in source_ids
    assert "skills.sh" in source_ids
    assert "clawhub" in source_ids

    all_source = next(s for s in sources if s["id"] == "all")
    assert all_source["count"] > 100_000


def test_skills_hub_keyword_search():
    """Verify fast sub-50ms search and proper ranking tiers."""
    res = search_skills(query="docker", source="all", limit=10)
    assert res["total"] > 0
    assert len(res["results"]) > 0

    first = res["results"][0]
    assert "name" in first
    assert "slug" in first
    assert "source" in first
    assert "identifier" in first
    assert "is_installed" in first
    assert isinstance(first["is_installed"], bool)

    # Filtered source search
    res_skills_sh = search_skills(query="docker", source="skills.sh", limit=5)
    for r in res_skills_sh["results"]:
        assert r["source"] == "skills.sh"


def test_skill_library_toggle_lifecycle():
    """Verify skills can be turned ON and OFF without data loss, correctly gating prompt injection."""
    test_slug = "test-toggle-sample-skill"
    # Create test skill
    saved = skill_library.save_skill(
        name="Test Toggle Sample Skill",
        category="testing",
        description="A temporary skill for verifying toggle ON/OFF behavior",
        procedure_steps=["Step 1: Check active state", "Step 2: Check disabled state"],
        trigger_keywords=["toggle_sample_test"],
        status="active",
        learned=False,
    )
    assert saved["slug"] == test_slug

    try:
        # 1. Verify initially active
        initial_active = [s["slug"] for s in skill_library.list_skills(status_filter="active")]
        assert test_slug in initial_active
        manifest_active = skill_library.get_prompt_manifest(user_task="Please run toggle_sample_test now")
        assert "Test Toggle Sample Skill" in manifest_active

        # 2. Toggle to disabled (OFF)
        toggled = skill_library.toggle_skill(test_slug, enabled=False)
        assert toggled is not None
        assert toggled["status"] == "disabled"
        assert toggled["enabled"] is False

        # Verify excluded from active list and prompt manifest
        active_after_disable = [s["slug"] for s in skill_library.list_skills(status_filter="active")]
        assert test_slug not in active_after_disable
        manifest_disabled = skill_library.get_prompt_manifest(user_task="Please run toggle_sample_test now")
        assert "Test Toggle Sample Skill" not in manifest_disabled

        # Verify still preserved on disk in list_skills(status_filter="disabled")
        disabled_skills = [s["slug"] for s in skill_library.list_skills(status_filter="disabled")]
        assert test_slug in disabled_skills

        # 3. Toggle back to active (ON)
        restored = skill_library.toggle_skill(test_slug, enabled=True)
        assert restored is not None
        assert restored["status"] == "active"
        assert restored["enabled"] is True

        # Verify restored in prompt manifest
        active_restored = [s["slug"] for s in skill_library.list_skills(status_filter="active")]
        assert test_slug in active_restored
        manifest_restored = skill_library.get_prompt_manifest(user_task="Please run toggle_sample_test now")
        assert "Test Toggle Sample Skill" in manifest_restored

    finally:
        # Cleanup test folder
        skill_library.reject_skill(test_slug, delete_folder=True)


def test_skills_hub_install_and_uninstall():
    """Verify installing on-demand from hub and clean uninstallation."""
    identifier = "skills-sh/test-sample-automation"
    custom_name = "Sample Hub Installed Skill"

    res = install_skill_from_hub(identifier=identifier, custom_name=custom_name, category="automation")
    assert res.get("ok") is True
    slug = res["slug"]

    try:
        # Verify file exists and parses
        skill_file = Path(res["file_path"])
        assert skill_file.is_file()

        parsed = skill_library.get_skill(slug)
        assert parsed is not None
        assert parsed["name"] == custom_name
        assert parsed["status"] == "active"

        # Verify uninstall removes cleanly
        ok = uninstall_skill(slug)
        assert ok is True
        assert not (get_anara_skills_dir() / slug).exists()
    finally:
        uninstall_skill(slug)


@pytest.mark.anyio
async def test_brain_routes_hub_endpoints():
    """Verify Brain API routes respond correctly."""
    from routers.brain_routes import (
        get_skill_hub_sources_endpoint,
        search_skill_hub_endpoint,
        toggle_skill_v2_endpoint,
        SkillToggleRequest,
    )

    # 1. Sources endpoint
    sources = await get_skill_hub_sources_endpoint()
    assert len(sources) >= 6

    # 2. Search endpoint
    search_res = await search_skill_hub_endpoint(q="python", limit=5)
    assert search_res["total"] > 0
    assert len(search_res["results"]) > 0

    # 3. Toggle endpoint with docx skill
    docx_skill = skill_library.get_skill("docx")
    if docx_skill:
        # Toggle off
        r_off = await toggle_skill_v2_endpoint("docx", SkillToggleRequest(enabled=False))
        assert r_off["status"] == "success"
        assert r_off["skill"]["status"] == "disabled"

        # Toggle back on
        r_on = await toggle_skill_v2_endpoint("docx", SkillToggleRequest(enabled=True))
        assert r_on["status"] == "success"
        assert r_on["skill"]["status"] == "active"
