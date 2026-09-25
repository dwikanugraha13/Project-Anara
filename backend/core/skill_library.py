"""
skill_library.py — Folder-based Skill Library Engine v2 (agentskills.io format).
Implements FR-15, FR-16, FR-17, FR-18, and FR-19 from prd-general-agent.md.

Standard:
- Each skill is stored in its own folder: backend/skills/<slug>/SKILL.md
- YAML frontmatter specifies metadata (name, description, category, credentials, status).
- Body markdown defines Overview, When to Use, and Steps.
- Progressive disclosure: index summary enters system prompt; full steps load when relevant.
- Approval workflow: agent-extracted skills start as 'pending' and require user approval.
"""
import os
import re
import yaml
import shutil
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

from constants import get_anara_skills_dir, get_bundled_skills_dir
from core.skills_sync import sync_bundled_skills


def _resolve_skills_root() -> str:
    """
    Resolves the active user runtime skills directory with auto-seeding (Hermes Parity).
    Pristine bundled templates in Git (backend/skills/) are mirrored to runtime (ANARA_HOME/skills/).
    """
    try:
        sync_bundled_skills()
        return str(get_anara_skills_dir())
    except Exception as e:
        logger.warning(f"[SkillLibrary] Runtime skills sync notice: {e}")
        return str(get_bundled_skills_dir())


SKILLS_DIR = _resolve_skills_root()


def slugify(text: str) -> str:
    """Creates a filesystem-safe folder slug from skill name."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s.strip("-") or "skill"


class SkillLibraryManager:
    """Manages the agentskills.io folder-based skill repository with progressive disclosure (Hermes Parity)."""

    def __init__(self, root_dir: Optional[str] = None):
        self._root_dir = root_dir

    @property
    def root_dir(self) -> str:
        if self._root_dir:
            return self._root_dir
        return str(get_anara_skills_dir())

    @root_dir.setter
    def root_dir(self, val: str):
        self._root_dir = val

    def parse_skill_file(self, skill_md_path: str) -> Optional[Dict[str, Any]]:
        """Parses frontmatter and body markdown from a SKILL.md file."""
        if not os.path.isfile(skill_md_path):
            return None
        try:
            with open(skill_md_path, "r", encoding="utf-8") as f:
                content = f.read()

            fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
            if not fm_match:
                return None

            raw_yaml, raw_body = fm_match.group(1), fm_match.group(2)
            meta = yaml.safe_load(raw_yaml) or {}

            slug = os.path.basename(os.path.dirname(skill_md_path))
            status = str(meta.get("status", "active")).lower()
            return {
                "slug": slug,
                "name": meta.get("name", slug),
                "category": meta.get("category", "coding"),
                "description": meta.get("description", ""),
                "trigger_keywords": meta.get("trigger_keywords", []),
                "required_environment_variables": meta.get("required_environment_variables", []),
                "required_credential_files": meta.get("required_credential_files", []),
                "status": status,  # 'active' | 'disabled' | 'pending' | 'rejected'
                "enabled": status == "active",
                "learned_from_experience": bool(meta.get("learned_from_experience", False)),
                "created_at": meta.get("created_at", ""),
                "body": raw_body.strip(),
                "file_path": skill_md_path,
            }
        except Exception as e:
            logger.warning(f"[SkillLibrary] Error reading {skill_md_path}: {e}")
            return None

    def save_skill(
        self,
        name: str,
        category: str,
        description: str,
        procedure_steps: List[str],
        trigger_keywords: Optional[List[str]] = None,
        status: str = "pending",
        learned: bool = True,
        required_env: Optional[List[str]] = None,
        required_creds: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Creates or updates a skill folder with SKILL.md in agentskills.io format.
        """
        slug = slugify(name)
        folder = os.path.join(self.root_dir, slug)
        os.makedirs(folder, exist_ok=True)

        now_iso = datetime.now().isoformat()
        triggers = [t.strip().lower() for t in (trigger_keywords or []) if t.strip()]

        frontmatter = {
            "name": name.strip(),
            "category": category.strip().lower() or "coding",
            "description": description.strip(),
            "trigger_keywords": triggers,
            "required_environment_variables": required_env or [],
            "required_credential_files": required_creds or [],
            "status": status,
            "learned_from_experience": learned,
            "created_at": now_iso,
            "updated_at": now_iso,
        }

        steps_md = "\n".join([f"{idx + 1}. {s.lstrip('0123456789. ')}" for idx, s in enumerate(procedure_steps)])

        body = f"""# {name}

## Overview
{description}

## When to Use
Use this skill when requested or when detecting tasks with keywords: {', '.join(triggers) or name}.

## Steps
{steps_md}
"""

        yaml_str = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
        full_content = f"---\n{yaml_str}\n---\n\n{body}"

        skill_file = os.path.join(folder, "SKILL.md")
        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(full_content)

        logger.info(f"[SkillLibrary] Saved skill '{name}' ({status}) to {skill_file}")

        # Mirror to SQLite database if legacy table exists (Hermes Parity)
        try:
            from memory import memory_engine
            if hasattr(memory_engine, "add_agent_skill"):
                memory_engine.add_agent_skill(
                    name=name,
                    category=category,
                    description=description,
                    trigger_keywords=triggers,
                    procedure_steps=procedure_steps,
                    learned_from_experience=learned,
                )
        except Exception:
            pass

        return {
            "slug": slug,
            "name": name,
            "category": category,
            "description": description,
            "status": status,
            "folder": folder,
            "file_path": skill_file,
        }

    def list_skills(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scans all folders and subfolders in runtime skills directory and parses their SKILL.md."""
        results = []
        if not os.path.isdir(self.root_dir):
            return results

        from pathlib import Path
        for skill_path in Path(self.root_dir).rglob("SKILL.md"):
            # Exclude hidden directories (like .hub, .git)
            if any(part.startswith(".") for part in skill_path.parts):
                continue
            parsed = self.parse_skill_file(str(skill_path))
            if parsed:
                if status_filter and status_filter != "all":
                    if parsed.get("status") != status_filter:
                        continue
                results.append(parsed)

        return sorted(results, key=lambda s: s.get("name", ""))

    def get_skill(self, name_or_slug: str) -> Optional[Dict[str, Any]]:
        """Retrieves a skill by name or slug."""
        clean = name_or_slug.strip().lower()
        for s in self.list_skills():
            if s["slug"].lower() == clean or s["name"].lower() == clean or slugify(s["name"]) == clean:
                return s
        return None

    def toggle_skill(self, slug: str, enabled: Optional[bool] = None) -> Optional[Dict[str, Any]]:
        """
        Toggles a skill between 'active' and 'disabled' (Hermes Parity).
        Disabled skills remain safely on disk but are hidden from the agent prompt manifest.
        """
        skill = self.get_skill(slug)
        if not skill:
            return None

        skill_file = skill["file_path"]
        current_status = skill.get("status", "active")

        if enabled is not None:
            new_status = "active" if enabled else "disabled"
        else:
            new_status = "disabled" if current_status == "active" else "active"

        ok = self._rewrite_status(skill_file, new_status)
        if not ok:
            return None

        skill["status"] = new_status
        skill["enabled"] = (new_status == "active")
        logger.info(f"[SkillLibrary] Toggled skill '{slug}' status: {current_status} -> {new_status}")
        return skill

    def get_skill_file(self, skill_name_or_slug: str, relative_file_path: str) -> Optional[Dict[str, Any]]:
        """Retrieves a sub-resource file (e.g. references/*.md, scripts/*.py) inside a skill folder."""
        skill = self.get_skill(skill_name_or_slug)
        if not skill:
            return None
        folder = os.path.dirname(skill["file_path"])
        target_path = os.path.normpath(os.path.join(folder, relative_file_path))
        if not target_path.startswith(folder) or not os.path.isfile(target_path):
            return None
        try:
            with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return {
                "skill_name": skill["name"],
                "file_path": relative_file_path,
                "size_kb": round(len(content) / 1024, 1),
                "content": content,
            }
        except Exception as e:
            logger.warning(f"[SkillLibrary] Error reading {target_path}: {e}")
            return None

    def approve_skill(self, slug: str) -> bool:
        """Promotes a skill from 'pending' to 'active'."""
        folder = os.path.join(self.root_dir, slug)
        skill_file = os.path.join(folder, "SKILL.md")
        parsed = self.parse_skill_file(skill_file)
        if not parsed:
            return False

        parsed["status"] = "active"
        return self._rewrite_status(skill_file, "active")

    def reject_skill(self, slug: str, delete_folder: bool = True) -> bool:
        """Rejects and optionally deletes a skill folder."""
        folder = os.path.join(self.root_dir, slug)
        if not os.path.isdir(folder):
            return False
        if delete_folder:
            shutil.rmtree(folder, ignore_errors=True)
            logger.info(f"[SkillLibrary] Deleted skill folder: {folder}")
            return True
        skill_file = os.path.join(folder, "SKILL.md")
        return self._rewrite_status(skill_file, "rejected")

    def _rewrite_status(self, skill_file: str, new_status: str) -> bool:
        try:
            with open(skill_file, "r", encoding="utf-8") as f:
                content = f.read()
            if re.search(r"(?m)^status:\s*['\"]?\w+['\"]?", content):
                updated = re.sub(r"(?m)^status:\s*['\"]?\w+['\"]?", f"status: {new_status}", content)
            else:
                updated = re.sub(r"^---\s*\n", f"---\nstatus: {new_status}\n", content)
            with open(skill_file, "w", encoding="utf-8") as f:
                f.write(updated)
            return True
        except Exception as e:
            logger.error(f"[SkillLibrary] Error updating status in {skill_file}: {e}")
            return False

    def get_prompt_manifest(self, user_task: Optional[str] = None) -> str:
        """
        Progressive Disclosure Engine (FR-17):
        1. Index level: List names & descriptions of active skills.
        2. Relevant detail: If user task matches keywords of a skill, include its full steps!
        """
        active_skills = self.list_skills(status_filter="active")
        if not active_skills:
            return ""

        # 1. Compact index manifest with dynamic paths (Hermes Parity)
        lines = [
            f"## Skills & Execution Architecture ({len(active_skills)} Active Skills):",
            f"- Active User Runtime Skills: {self.root_dir}",
            f"- Bundled In-Tree Skills: {get_bundled_skills_dir()}",
            "- Tools Implementation: backend/tools/ (dispatched via backend/tools/registry.py)",
            "- Community Skills Hub: 100,000+ indexed skills searchable and installable on-demand via skills_hub engine.",
            "\nActive Catalog Summary:",
        ]
        for s in active_skills[:12]:
            lines.append(f"- **{s['name']}** ({s['category']}): {s['description']}")

        # 2. Progressive disclosure: Include full skill instructions when relevant to current task
        if user_task:
            task_lower = user_task.lower()
            task_tokens = set(re.findall(r"\w+", task_lower))
            matched_skills = []
            for s in active_skills:
                skill_name_lower = s["name"].lower()
                triggers = [t.lower() for t in s.get("trigger_keywords", [])]
                name_words = set(re.findall(r"\w+", skill_name_lower))
                if (name_words & task_tokens) or any(t in task_lower for t in triggers) or skill_name_lower in task_lower:
                    matched_skills.append(s)

            if matched_skills:
                lines.append("\n## Active Skill Instructions:")
                for ms in matched_skills[:2]:
                    lines.append(f"\n### {ms['name']}\n{ms.get('body', '')}")

        return "\n".join(lines).strip()

    def sync_from_database(self):
        """Seeds file-based skills from SQLite database on first startup if empty."""
        existing_files = self.list_skills()
        if existing_files:
            return  # already populated

        try:
            from memory import memory_engine
            db_skills = memory_engine.get_all_agent_skills(active_only=False)
            for d in db_skills:
                steps = d.get("procedure_steps", [])
                triggers = d.get("trigger_keywords", [])
                self.save_skill(
                    name=d["name"],
                    category=d.get("category", "coding"),
                    description=d.get("description", ""),
                    procedure_steps=steps if isinstance(steps, list) else [str(steps)],
                    trigger_keywords=triggers if isinstance(triggers, list) else [],
                    status="active" if d.get("is_active") else "pending",
                    learned=bool(d.get("learned_from_experience", False)),
                )
            logger.info(f"[SkillLibrary] Initialized {len(db_skills)} skills from SQLite to disk.")
        except Exception as e:
            logger.warning(f"[SkillLibrary] Sync from DB error: {e}")


skill_library = SkillLibraryManager()
