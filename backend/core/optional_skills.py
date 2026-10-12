"""
optional_skills.py — Official Optional Skills Catalog Manager for Project Anara.
Loads the curated 150+ skills catalog shipped in backend/optional-skills.
100% Native Project Anara branding with AST & schema validation.
"""

from __future__ import annotations

import os
import re
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from constants import get_optional_skills_dir, get_anara_skills_dir

logger = logging.getLogger("anara.skills.optional")

_CATALOG_CACHE: Optional[List[Dict[str, Any]]] = None
_CATALOG_MTIME: float = 0.0


def _get_catalog_signature(catalog_dir: Path) -> float:
    """Computes quick mtime signature of the catalog directory."""
    try:
        return catalog_dir.stat().st_mtime
    except Exception:
        return 0.0


def list_official_optional_skills(installed_names: Optional[set] = None) -> List[Dict[str, Any]]:
    """
    Scans backend/optional-skills/ and returns catalog items with metadata.
    Marks each as installed if present in installed_names.
    """
    global _CATALOG_CACHE, _CATALOG_MTIME

    catalog_dir = get_optional_skills_dir()
    if not catalog_dir.is_dir():
        return []

    curr_mtime = _get_catalog_signature(catalog_dir)
    if _CATALOG_CACHE is not None and curr_mtime == _CATALOG_MTIME:
        cached = _CATALOG_CACHE
    else:
        skills = []
        for root, dirs, files in os.walk(catalog_dir):
            if "SKILL.md" in files:
                rel = os.path.relpath(root, catalog_dir)
                skill_file = os.path.join(root, "SKILL.md")
                meta: Dict[str, Any] = {}
                try:
                    with open(skill_file, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read(4096)
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            meta = yaml.safe_load(parts[1]) or {}
                except Exception as e:
                    logger.debug(f"[OptionalSkills] Parse frontmatter warning for {rel}: {e}")

                name = meta.get("name") or os.path.basename(root)
                rel_parts = rel.split(os.sep)
                cat = rel_parts[0] if len(rel_parts) > 1 else "general"

                # Extract tags & setup from metadata
                anara_meta = {}
                if isinstance(meta.get("metadata"), dict):
                    anara_meta = meta["metadata"].get("anara") or {}

                tags = anara_meta.get("tags") or meta.get("trigger_keywords") or []
                if not isinstance(tags, list):
                    tags = [str(tags)]

                skills.append({
                    "name": name,
                    "category": cat,
                    "identifier": f"official/{rel.replace(os.sep, '/')}",
                    "description": meta.get("description", ""),
                    "platforms": meta.get("platforms"),
                    "version": meta.get("version", "1.0.0"),
                    "author": meta.get("author", "Project Anara"),
                    "license": meta.get("license", "MIT"),
                    "tags": tags,
                    "setup": meta.get("setup"),
                    "rel_path": rel.replace(os.sep, "/"),
                })

        skills.sort(key=lambda x: x["name"].lower())
        _CATALOG_CACHE = skills
        _CATALOG_MTIME = curr_mtime
        cached = skills

    # Attach installed flag dynamically
    if installed_names is None:
        try:
            from core.skill_library import skill_library
            installed_names = {s["name"] for s in skill_library.list_skills(include_unsupported=True)}
        except Exception:
            installed_names = set()

    result = []
    for s in cached:
        item = dict(s)
        item["installed"] = s["name"] in installed_names
        result.append(item)

    return result


def get_official_skill_preview(identifier: str) -> Optional[Dict[str, Any]]:
    """
    Returns full SKILL.md content, parsed metadata, and file list for an optional skill.
    """
    catalog_dir = get_optional_skills_dir()
    rel_path = identifier
    if rel_path.startswith("official/"):
        rel_path = rel_path[len("official/"):]

    # Direct directory lookup
    skill_dir = catalog_dir / rel_path
    if not (skill_dir / "SKILL.md").is_file():
        # Fallback: scan for matching name or identifier
        found_dir = None
        for root, dirs, files in os.walk(catalog_dir):
            if "SKILL.md" in files:
                r_rel = os.path.relpath(root, catalog_dir).replace(os.sep, "/")
                if r_rel == rel_path or os.path.basename(root) == rel_path:
                    found_dir = Path(root)
                    break
        if not found_dir:
            return None
        skill_dir = found_dir

    skill_md_path = skill_dir / "SKILL.md"
    try:
        raw_text = skill_md_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.error(f"[OptionalSkills] Error reading SKILL.md for {identifier}: {e}")
        return None

    meta: Dict[str, Any] = {}
    if raw_text.startswith("---"):
        parts = raw_text.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
            except Exception:
                meta = {}

    rel_parts = os.path.relpath(skill_dir, catalog_dir).split(os.sep)
    cat = rel_parts[0] if len(rel_parts) > 1 else "general"
    name = meta.get("name") or skill_dir.name

    anara_meta = {}
    if isinstance(meta.get("metadata"), dict):
        anara_meta = meta["metadata"].get("anara") or {}

    tags = anara_meta.get("tags") or meta.get("trigger_keywords") or []
    if not isinstance(tags, list):
        tags = [str(tags)]

    # Collect files in the skill directory
    files = []
    for root, dirs, f_list in os.walk(skill_dir):
        for f in f_list:
            files.append(os.path.relpath(os.path.join(root, f), skill_dir).replace(os.sep, "/"))

    return {
        "name": name,
        "identifier": f"official/{os.path.relpath(skill_dir, catalog_dir).replace(os.sep, '/')}",
        "category": cat,
        "description": meta.get("description", ""),
        "version": meta.get("version", "1.0.0"),
        "author": meta.get("author", "Project Anara"),
        "license": meta.get("license", "MIT"),
        "platforms": meta.get("platforms"),
        "tags": tags,
        "setup": meta.get("setup"),
        "metadata": meta,
        "skill_md": raw_text,
        "files": sorted(files),
    }


def install_official_skill(identifier: str) -> Dict[str, Any]:
    """
    Installs an optional skill from backend/optional-skills into the active runtime and repository.
    """
    catalog_dir = get_optional_skills_dir()
    rel_path = identifier
    if rel_path.startswith("official/"):
        rel_path = rel_path[len("official/"):]

    skill_dir = catalog_dir / rel_path
    if not (skill_dir / "SKILL.md").is_file():
        # Fallback search
        found_dir = None
        for root, dirs, files in os.walk(catalog_dir):
            if "SKILL.md" in files:
                r_rel = os.path.relpath(root, catalog_dir).replace(os.sep, "/")
                if r_rel == rel_path or os.path.basename(root) == rel_path:
                    found_dir = Path(root)
                    break
        if not found_dir:
            raise FileNotFoundError(f"Skill '{identifier}' not found in optional catalog.")
        skill_dir = found_dir

    skill_name = skill_dir.name
    # 1. Target in runtime %LOCALAPPDATA%/anara/skills/<name>
    user_skills_dir = get_anara_skills_dir()
    target_user_dir = user_skills_dir / skill_name
    shutil.copytree(skill_dir, target_user_dir, dirs_exist_ok=True)

    # 2. Target in backend/skills/<name>
    backend_skills_dir = Path(__file__).resolve().parent.parent / "skills"
    target_backend_dir = backend_skills_dir / skill_name
    shutil.copytree(skill_dir, target_backend_dir, dirs_exist_ok=True)

    # Invalidate skill library cache so it immediately registers as installed
    try:
        from core.skill_library import skill_library
        skill_library._invalidate_cache()
    except Exception as e:
        logger.debug(f"[OptionalSkills] Invalidate cache notice: {e}")

    logger.info(f"[OptionalSkills] Successfully installed official skill: {skill_name}")
    return {
        "status": "success",
        "name": skill_name,
        "slug": skill_name,
        "installed": True,
        "installed_path": str(target_user_dir),
    }