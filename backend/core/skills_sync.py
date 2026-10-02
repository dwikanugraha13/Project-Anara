"""
skills_sync.py — Manifest-based Seeding & Synchronization for Bundled Skills.
Anara Standard (tools/skills_sync.py):
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
import stat
import threading
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from constants import get_anara_skills_dir, get_bundled_skills_dir

logger = logging.getLogger("anara.skills.sync")

MANIFEST_FILENAME = ".bundled_manifest"
_SYNC_LOCK = threading.Lock()
IGNORED_PATTERNS = {"__pycache__", ".git", ".pytest_cache", ".DS_Store", "desktop.ini"}


def _rmtree_writable(path: Path) -> None:
    """Removes a directory tree, resetting read-only attributes on Windows if needed (Anara Standard)."""
    def _on_error(func, fpath, exc_info):
        try:
            os.chmod(fpath, stat.S_IRWXU)
            func(fpath)
        except Exception:
            pass

    try:
        shutil.rmtree(path, onerror=_on_error)
    except Exception:
        shutil.rmtree(path, ignore_errors=True)


def _dir_hash(directory: Path) -> str:
    """Calculates deterministic MD5 hash of skill directory content excluding runtime caches."""
    hasher = hashlib.md5()
    if not directory.is_dir():
        return ""

    for root, dirs, files in os.walk(directory):
        dirs[:] = sorted([d for d in dirs if d not in IGNORED_PATTERNS and not d.endswith(".bak")])
        for f in sorted(files):
            if f in IGNORED_PATTERNS or f.endswith((".pyc", ".pyo", ".tmp")):
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
    """Reads .bundled_manifest format '{slug}:{hash}' into a dictionary, stripping UTF-8 BOM."""
    if not manifest_path.is_file():
        return {}
    entries: Dict[str, str] = {}
    try:
        lines = manifest_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
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
    """Writes sorted entries atomically to .bundled_manifest."""
    try:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"{k}:{v}\n" for k, v in sorted(entries.items())]
        tmp_path = manifest_path.with_suffix(".tmp")
        tmp_path.write_text("".join(lines), encoding="utf-8", errors="replace")
        os.replace(tmp_path, manifest_path)
    except Exception as e:
        logger.warning(f"[SkillsSync] Failed to write manifest {manifest_path}: {e}")


def sync_bundled_skills() -> Dict[str, int]:
    """
    Synchronizes in-tree bundled skills into active user runtime skills (Anara Standard).
    Preserves user customizations and agent-learned skills.
    Thread-safe and race-condition free.
    """
    with _SYNC_LOCK:
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

        # Discover all bundled skills (directories containing SKILL.md) recursively
        bundled_skills: List[Tuple[str, Path]] = []
        for skill_md in bundled_dir.rglob("SKILL.md"):
            skill_folder = skill_md.parent
            if any(part in IGNORED_PATTERNS for part in skill_folder.parts):
                continue
            slug = skill_folder.name
            bundled_skills.append((slug, skill_folder))

        stats["total_bundled"] = len(bundled_skills)

        for slug, source_path in bundled_skills:
            b_hash = _dir_hash(source_path)
            target_path = runtime_dir / slug

            if not target_path.exists():
                # If skill was previously tracked in manifest, user deliberately deleted it -> respect user choice!
                if slug in manifest:
                    stats["unchanged"] += 1
                    continue

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
                        # Upstream was updated -> Safe to apply update via .bak staging (Anara Standard)
                        bak_path = target_path.with_suffix(".bak")
                        try:
                            if bak_path.exists():
                                _rmtree_writable(bak_path)
                            shutil.move(str(target_path), str(bak_path))
                            shutil.copytree(source_path, target_path, ignore=shutil.ignore_patterns(*IGNORED_PATTERNS))
                            updated_manifest[slug] = b_hash
                            stats["updated"] += 1
                            _rmtree_writable(bak_path)
                        except Exception as e:
                            if bak_path.exists() and not target_path.exists():
                                shutil.move(str(bak_path), str(target_path))
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
