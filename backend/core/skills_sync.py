"""
skills_sync.py — Manifest-based Seeding & Synchronization for Bundled Skills.
Hermes Agent Parity (tools/skills_sync.py):
1. In-tree repository skills (backend/skills/) act as pristine master templates.
2. Active user runtime skills (ANARA_HOME/skills/) are decoupled from Git.
3. Tracks origin hashes in .bundled_manifest:
   - Newly discovered bundled skills are seeded to runtime.
   - Upstream updates overwrite only if user copy is unmodified (matching origin hash).
   - User-customized and agent-learned skills are strictly preserved and never overwritten.
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from constants import get_anara_skills_dir, get_bundled_skills_dir

logger = logging.getLogger("anara.skills.sync")

MANIFEST_FILENAME = ".bundled_manifest"
IGNORED_PATTERNS = {"__pycache__", ".git", ".pytest_cache", ".DS_Store", "desktop.ini"}


def _dir_hash(directory: Path) -> str:
    """Calculates MD5 hash of skill directory content excluding runtime caches."""
    hasher = hashlib.md5()
    if not directory.is_dir():
        return ""

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in IGNORED_PATTERNS]
        for f in sorted(files):
            if f in IGNORED_PATTERNS:
                continue
            fpath = Path(root) / f
            rel_p = str(fpath.relative_to(directory)).replace("\\", "/")
            hasher.update(rel_p.encode("utf-8"))
            try:
                hasher.update(fpath.read_bytes())
            except Exception:
                pass
    return hasher.hexdigest()


def _read_manifest(manifest_path: Path) -> Dict[str, str]:
    """Reads .bundled_manifest format '{slug}:{hash}' into a dictionary."""
    if not manifest_path.is_file():
        return {}
    entries: Dict[str, str] = {}
    try:
        lines = manifest_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                name, _, h = line.partition(":")
                entries[name.strip()] = h.strip()
            else:
                entries[line] = ""
    except Exception as e:
        logger.warning(f"[SkillsSync] Failed to read manifest {manifest_path}: {e}")
    return entries


def _write_manifest(manifest_path: Path, entries: Dict[str, str]) -> None:
    """Writes sorted entries to .bundled_manifest."""
    try:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"{k}:{v}\n" for k, v in sorted(entries.items())]
        manifest_path.write_text("".join(lines), encoding="utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"[SkillsSync] Failed to write manifest {manifest_path}: {e}")


def sync_bundled_skills() -> Dict[str, int]:
    """
    Synchronizes in-tree bundled skills into active user runtime skills (Hermes Parity).
    Preserves user customizations and agent-learned skills.
    """
    bundled_dir = get_bundled_skills_dir()
    runtime_dir = get_anara_skills_dir()
    manifest_file = runtime_dir / MANIFEST_FILENAME

    stats = {
        "seeded": 0,
        "updated": 0,
        "preserved": 0,
        "unchanged": 0,
        "total_bundled": 0,
        "total_runtime": 0,
    }

    if not bundled_dir.is_dir():
        logger.debug(f"[SkillsSync] Bundled directory '{bundled_dir}' not found. Skipping sync.")
        return stats

    manifest = _read_manifest(manifest_file)
    updated_manifest = dict(manifest)

    # Discover all bundled skills (directories containing SKILL.md)
    bundled_skills: List[Tuple[str, Path]] = []
    for item in bundled_dir.iterdir():
        if item.is_dir() and (item / "SKILL.md").is_file():
            bundled_skills.append((item.name, item))

    stats["total_bundled"] = len(bundled_skills)

    for slug, source_path in bundled_skills:
        b_hash = _dir_hash(source_path)
        target_path = runtime_dir / slug

        if not target_path.exists():
            # Case 1: Skill does not exist in runtime -> Seed it
            try:
                shutil.copytree(source_path, target_path, ignore=shutil.ignore_patterns(*IGNORED_PATTERNS))
                updated_manifest[slug] = b_hash
                stats["seeded"] += 1
            except Exception as e:
                logger.warning(f"[SkillsSync] Failed to seed skill '{slug}': {e}")
        else:
            # Case 2: Target exists in runtime -> Check for user customizations
            user_hash = _dir_hash(target_path)
            origin_hash = manifest.get(slug, "")

            if not origin_hash:
                # First migration from pre-manifest runtime: record current hash
                updated_manifest[slug] = user_hash
                stats["unchanged"] += 1
            elif user_hash == origin_hash:
                # User has NOT modified the skill
                if b_hash != origin_hash:
                    # Upstream was updated -> Safe to apply update
                    try:
                        shutil.rmtree(target_path, ignore_errors=True)
                        shutil.copytree(source_path, target_path, ignore=shutil.ignore_patterns(*IGNORED_PATTERNS))
                        updated_manifest[slug] = b_hash
                        stats["updated"] += 1
                    except Exception as e:
                        logger.warning(f"[SkillsSync] Failed to update skill '{slug}': {e}")
                else:
                    stats["unchanged"] += 1
            else:
                # User or agent modified the skill in runtime -> Strictly PRESERVE
                stats["preserved"] += 1

    _write_manifest(manifest_file, updated_manifest)

    # Count all active runtime skills
    stats["total_runtime"] = sum(
        1 for p in runtime_dir.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()
    )

    if stats["seeded"] > 0 or stats["updated"] > 0:
        logger.info(
            f"[SkillsSync] Synced skills to runtime: {stats['seeded']} seeded, "
            f"{stats['updated']} updated, {stats['preserved']} user-customized preserved "
            f"(Total runtime skills: {stats['total_runtime']})"
        )

    return stats
