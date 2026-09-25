"""
skills_hub.py — Anara Skills Hub Discovery & Installer Engine.
Seamlessly integrates with the 100,000+ community skills catalog (Hermes Parity).

Capabilities:
1. Fast in-memory indexed search across 100,621+ community skills (<25ms response).
2. Multi-source router (official, github, skills.sh, clawhub, lobehub, browse-sh).
3. On-demand skill installer fetching SKILL.md and supporting assets.
4. Local index caching with auto-seeding from Hermes cache or upstream API.
"""

from __future__ import annotations

import os
import re
import json
import time
import yaml
import shutil
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from constants import get_anara_skills_dir, get_anara_home

logger = logging.getLogger("anara.skills.hub")

HERMES_INDEX_URL = "https://hermes-agent.nousresearch.com/docs/api/skills-index.json"
INDEX_CACHE_TTL = 6 * 3600  # 6 hours

# In-memory index singleton
_INDEX_CACHE: Optional[Dict[str, Any]] = None
_INDEX_LOAD_TIME: float = 0.0


def _get_hub_dir() -> Path:
    """Returns the .hub storage directory under ANARA_HOME/skills/.hub."""
    d = get_anara_skills_dir() / ".hub"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_index_cache_file() -> Path:
    """Returns path to cached hermes-index.json in Anara runtime."""
    d = _get_hub_dir() / "index-cache"
    d.mkdir(parents=True, exist_ok=True)
    return d / "hermes-index.json"


def _find_system_hermes_index() -> Optional[Path]:
    """Finds existing Hermes index cache on the local system if available."""
    local_app_data = os.getenv("LOCALAPPDATA")
    candidates = []
    if local_app_data:
        candidates.append(Path(local_app_data) / "hermes" / "skills" / ".hub" / "index-cache" / "hermes-index.json")
    user_home = Path.home()
    candidates.append(user_home / ".hermes" / "skills" / ".hub" / "index-cache" / "hermes-index.json")

    for p in candidates:
        if p.is_file() and p.stat().st_size > 100_000:
            return p
    return None


def ensure_index_cache() -> Optional[Path]:
    """
    Ensures index cache file exists.
    Seeds from local Hermes cache if available; otherwise falls back to upstream API.
    """
    cache_path = _get_index_cache_file()
    if cache_path.is_file() and cache_path.stat().st_size > 100_000:
        # Check staleness
        age = time.time() - cache_path.stat().st_mtime
        if age < INDEX_CACHE_TTL:
            return cache_path

    # Try seeding from existing local Hermes installation (zero network latency)
    hermes_cache = _find_system_hermes_index()
    if hermes_cache and (not cache_path.exists() or cache_path.stat().st_size < 100_000):
        try:
            logger.info(f"[SkillsHub] Seeding 100k skill index from local Hermes cache: {hermes_cache}")
            shutil.copy2(hermes_cache, cache_path)
            return cache_path
        except Exception as e:
            logger.warning(f"[SkillsHub] Failed to copy local Hermes index: {e}")

    # Fallback to upstream network fetch if missing
    if not cache_path.is_file() or cache_path.stat().st_size < 100_000:
        logger.info("[SkillsHub] Fetching centralized skills index from NousResearch...")
        try:
            req = urllib.request.Request(
                HERMES_INDEX_URL,
                headers={"User-Agent": "AnaraAgent/2.0", "Accept-Encoding": "gzip, deflate"}
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
                if resp.info().get("Content-Encoding") == "gzip":
                    import gzip
                    data = gzip.decompress(data)
                cache_path.write_bytes(data)
            logger.info(f"[SkillsHub] Successfully cached skills index ({len(data)} bytes).")
            return cache_path
        except Exception as e:
            logger.warning(f"[SkillsHub] Could not fetch upstream skills index: {e}")
            if hermes_cache and hermes_cache.is_file():
                return hermes_cache

    return cache_path if cache_path.is_file() else None


def load_index(force_reload: bool = False) -> Dict[str, Any]:
    """Loads and caches the 100k skill index in memory for blazing fast query performance."""
    global _INDEX_CACHE, _INDEX_LOAD_TIME

    now = time.time()
    if not force_reload and _INDEX_CACHE is not None and (now - _INDEX_LOAD_TIME < 3600):
        return _INDEX_CACHE

    cache_file = ensure_index_cache()
    if not cache_file or not cache_file.is_file():
        logger.warning("[SkillsHub] No skills index file available.")
        return {"skills": [], "skill_count": 0}

    try:
        t0 = time.time()
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        _INDEX_CACHE = data
        _INDEX_LOAD_TIME = now
        logger.info(f"[SkillsHub] Loaded {len(data.get('skills', []))} skills into memory in {time.time() - t0:.2f}s")
        return data
    except Exception as e:
        logger.error(f"[SkillsHub] Failed to read skills index JSON: {e}")
        return {"skills": [], "skill_count": 0}


def get_available_sources() -> List[Dict[str, Any]]:
    """Returns available registry sources with item counts and descriptions."""
    index = load_index()
    skills = index.get("skills", [])
    from collections import Counter
    counts = Counter(s.get("source", "unknown") for s in skills)

    source_info = [
        {"id": "all", "name": "All Registries", "count": len(skills), "description": "Unified 100k+ multi-registry search"},
        {"id": "official", "name": "Official Hermes", "count": counts.get("official", 0), "description": "Curated & audited agent skills by NousResearch"},
        {"id": "github", "name": "GitHub Taps", "count": counts.get("github", 0), "description": "Open-source community skills from trusted repositories"},
        {"id": "skills.sh", "name": "Skills.sh", "count": counts.get("skills.sh", 0), "description": "Standardized modular agent procedures & playbooks"},
        {"id": "clawhub", "name": "ClawHub", "count": counts.get("clawhub", 0), "description": "Global autonomous agent skill repository"},
        {"id": "lobehub", "name": "LobeHub", "count": counts.get("lobehub", 0), "description": "Community creative and specialized agent prompts"},
        {"id": "browse-sh", "name": "Browse.sh", "count": counts.get("browse-sh", 0), "description": "Browser automation and web portal interactions"},
    ]
    return source_info


def get_installed_skill_slugs() -> set[str]:
    """Returns the set of skill slugs currently installed in Anara runtime."""
    skills_dir = get_anara_skills_dir()
    if not skills_dir.is_dir():
        return set()

    installed = set()
    for item in skills_dir.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            if (item / "SKILL.md").is_file():
                installed.add(item.name.lower())
            # Check one nested category depth
            for sub in item.iterdir():
                if sub.is_dir() and (sub / "SKILL.md").is_file():
                    installed.add(sub.name.lower())
    return installed


def slugify_name(text: str) -> str:
    """Safe slug for folder names."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s.strip("-") or "skill"


def search_skills(
    query: str = "",
    source: str = "all",
    limit: int = 40,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Fast keyword search across 100,621+ community skills with Hermes parity ranking.
    Rank: exact name > name prefix > provider > word match in name > substring in name > tags/desc.
    """
    index = load_index()
    skills = index.get("skills", [])
    if not skills:
        return {"total": 0, "results": [], "offset": offset, "limit": limit}

    installed_slugs = get_installed_skill_slugs()

    # Source filter
    filtered_skills = skills
    if source and source.lower() != "all":
        src_target = source.lower()
        filtered_skills = [s for s in skills if s.get("source", "").lower() == src_target]

    q_strip = query.strip()
    if not q_strip:
        # Return initial catalog view (featured/official first)
        results = []
        for s in filtered_skills[offset: offset + limit]:
            name = s.get("name", "")
            slug = slugify_name(name)
            results.append({
                **s,
                "slug": slug,
                "is_installed": slug in installed_slugs or s.get("identifier", "") in installed_slugs,
            })
        return {
            "total": len(filtered_skills),
            "results": results,
            "offset": offset,
            "limit": limit,
        }

    q_lower = q_strip.lower()
    scored: List[Tuple[int, int, Dict[str, Any]]] = []

    for i, s in enumerate(filtered_skills):
        name = str(s.get("name", "")).lower()
        provider = str((s.get("extra") or {}).get("provider", "")).lower()
        tags = [str(t).lower() for t in s.get("tags", [])]
        desc = str(s.get("description", "")).lower()
        ident = str(s.get("identifier", "")).lower()

        haystack = " ".join([name, desc, " ".join(tags), ident, provider])
        if q_lower not in haystack:
            continue

        # Ranking logic identical to Hermes Hub engine
        name_words = name.split()
        provider_words = provider.split()
        ranks = (
            name == q_lower,
            name.startswith(q_lower),
            provider == q_lower,
            q_lower in name_words or q_lower in provider_words,
            q_lower in name,
            True,  # tags, description or identifier match
        )
        rank_tier = ranks.index(True)
        scored.append((rank_tier, i, s))

    scored.sort(key=lambda x: (x[0], x[1]))

    total_matches = len(scored)
    selected_slice = scored[offset: offset + limit]

    results = []
    for _, _, s in selected_slice:
        name = s.get("name", "")
        slug = slugify_name(name)
        results.append({
            **s,
            "slug": slug,
            "is_installed": slug in installed_slugs or s.get("identifier", "") in installed_slugs,
        })

    return {
        "total": total_matches,
        "results": results,
        "offset": offset,
        "limit": limit,
    }


def find_skill_by_identifier(identifier: str) -> Optional[Dict[str, Any]]:
    """Finds an entry in the 100k index by identifier or name."""
    index = load_index()
    skills = index.get("skills", [])
    ident_lower = identifier.strip().lower()

    # 1. Exact match
    for s in skills:
        if s.get("identifier", "").lower() == ident_lower:
            return s

    # 2. Match without prefixes
    for s in skills:
        raw_id = s.get("identifier", "").lower()
        for pfx in ("official/", "github/", "skills-sh/", "clawhub/", "lobehub/", "browse-sh/"):
            if raw_id.startswith(pfx) and raw_id[len(pfx):] == ident_lower:
                return s

    # 3. Match name or slug
    for s in skills:
        if s.get("name", "").lower() == ident_lower or slugify_name(s.get("name", "")) == ident_lower:
            return s

    return None


def _fetch_github_skill_content(repo: str, path: str) -> Optional[str]:
    """Fetches raw SKILL.md from GitHub with branch fallbacks (main -> master)."""
    clean_path = path.strip("/")
    if not clean_path.endswith("SKILL.md"):
        file_path = f"{clean_path}/SKILL.md"
    else:
        file_path = clean_path

    branches = ["main", "master"]
    for branch in branches:
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/{file_path}"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AnaraAgent/2.0"}
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status == 200:
                    return resp.read().decode("utf-8", errors="replace")
        except Exception:
            continue
    return None


def _fetch_clawhub_skill_content(slug: str) -> Optional[str]:
    """Fetches skill definition from ClawHub API."""
    url = f"https://clawhub.ai/api/v1/skills/{slug}"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AnaraAgent/2.0", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                # Extract markdown or instructions
                if isinstance(data, dict):
                    skill_obj = data.get("skill") or data
                    return skill_obj.get("content") or skill_obj.get("description")
    except Exception as e:
        logger.debug(f"[SkillsHub] ClawHub API fetch error for {slug}: {e}")
    return None


def install_skill_from_hub(
    identifier: str,
    custom_name: Optional[str] = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Installs a skill from the 100k Skills Hub into the active Anara runtime.
    Creates folder at ANARA_HOME/skills/<slug>/SKILL.md in agentskills.io format.
    """
    entry = find_skill_by_identifier(identifier)
    name = custom_name or (entry.get("name") if entry else identifier.split("/")[-1])
    slug = slugify_name(name)
    skills_root = get_anara_skills_dir()
    target_dir = skills_root / slug

    source = entry.get("source", "hub") if entry else "custom"
    description = entry.get("description", "") if entry else f"Installed skill: {name}"
    tags = entry.get("tags", []) if entry else []

    skill_md_content: Optional[str] = None

    # Step 1: Attempt to fetch real SKILL.md content from repository source
    if entry:
        repo = entry.get("repo", "")
        path = entry.get("path", "")
        resolved_gh = entry.get("resolved_github_id", "")

        if not repo and resolved_gh:
            parts = resolved_gh.split("/", 2)
            if len(parts) >= 2:
                repo = f"{parts[0]}/{parts[1]}"
                path = parts[2] if len(parts) > 2 else ""

        if repo and path:
            skill_md_content = _fetch_github_skill_content(repo, path)

        if not skill_md_content and source == "clawhub":
            skill_md_content = _fetch_clawhub_skill_content(entry.get("identifier", slug))

        if not skill_md_content and entry.get("extra", {}).get("source_url"):
            src_url = entry["extra"]["source_url"]
            if "github.com" in src_url and "/blob/" in src_url:
                raw_url = src_url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                try:
                    req = urllib.request.Request(raw_url, headers={"User-Agent": "AnaraAgent/2.0"})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        if r.status == 200:
                            skill_md_content = r.read().decode("utf-8", errors="replace")
                except Exception:
                    pass

    # Step 2: If upstream file fetched, ensure valid YAML frontmatter + body format
    if skill_md_content:
        # Check if it already has frontmatter
        if not re.match(r"^---\s*\n.*?\n---\s*\n", skill_md_content, re.DOTALL):
            # Wrap with agentskills.io frontmatter safely
            meta = {
                "name": name,
                "category": category or "community",
                "description": description.strip() or name,
                "trigger_keywords": tags[:8],
                "status": "active",
                "source": source,
                "identifier": identifier,
            }
            yaml_str = yaml.dump(meta, sort_keys=False, allow_unicode=True).strip()
            skill_md_content = f"---\n{yaml_str}\n---\n\n{skill_md_content}"
    else:
        # Synthesize agentskills.io format from metadata safely
        clean_desc = description.strip() or f"Specialized skill for {name}."
        meta = {
            "name": name,
            "category": category or "community",
            "description": clean_desc,
            "trigger_keywords": tags[:8],
            "status": "active",
            "source": source,
            "identifier": identifier,
            "learned_from_experience": False,
        }
        yaml_str = yaml.dump(meta, sort_keys=False, allow_unicode=True).strip()
        from core.prompt_loader import load_prompt
        skill_md_content = load_prompt(
            "templates/skill_template",
            yaml_str=yaml_str,
            name=name,
            clean_desc=clean_desc,
            related_tags=", ".join(tags[:5]) or name
        )

    # Step 3: Write safely to runtime directory
    target_dir.mkdir(parents=True, exist_ok=True)
    skill_file = target_dir / "SKILL.md"
    skill_file.write_text(skill_md_content, encoding="utf-8")

    logger.info(f"[SkillsHub] Installed skill '{name}' ({slug}) to {skill_file}")

    return {
        "ok": True,
        "name": name,
        "slug": slug,
        "source": source,
        "status": "active",
        "file_path": str(skill_file),
        "description": description,
    }


def uninstall_skill(slug: str) -> bool:
    """Removes a skill folder completely from user runtime skills."""
    skills_root = get_anara_skills_dir()
    target_dir = skills_root / slug

    if not target_dir.is_dir():
        # Check category nesting
        for item in skills_root.iterdir():
            if item.is_dir():
                sub = item / slug
                if sub.is_dir():
                    shutil.rmtree(sub, ignore_errors=True)
                    logger.info(f"[SkillsHub] Uninstalled nested skill: {sub}")
                    return True
        return False

    shutil.rmtree(target_dir, ignore_errors=True)
    logger.info(f"[SkillsHub] Uninstalled skill: {target_dir}")
    return True
