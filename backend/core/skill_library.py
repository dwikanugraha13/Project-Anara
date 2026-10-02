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
import logging
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional
import yaml

logger = logging.getLogger(__name__)

from constants import get_anara_skills_dir, get_bundled_skills_dir
from core.skills_sync import sync_bundled_skills

WINDOWS_RESERVED_NAMES = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
MAX_SKILL_FILE_BYTES = 1_048_576  # 1 MiB cap (Anara Standard)


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Writes content atomically to destination path using temporary file replace (Anara Standard)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.tmp")
    try:
        with os.fdopen(temp_fd, "w", encoding=encoding) as f:
            f.write(content)
        os.replace(temp_path, str(path))
    except Exception:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        raise


def _safe_rmtree(path: Path | str) -> None:
    """Removes a directory tree, resetting read-only attributes on Windows if needed (Anara Standard)."""
    def _handle_readonly(func, fpath, exc_info):
        try:
            import stat
            os.chmod(fpath, stat.S_IWRITE | stat.S_IWUSR | stat.S_IRWXU)
            func(fpath)
        except Exception:
            pass

    try:
        shutil.rmtree(path, onexc=lambda fn, p, exc: _handle_readonly(fn, p, (type(exc), exc, None)))
    except TypeError:
        shutil.rmtree(path, onerror=_handle_readonly)
    except Exception:
        shutil.rmtree(path, ignore_errors=True)


def _resolve_skills_root() -> str:
    """
    Resolves the active user runtime skills directory with auto-seeding (Anara Standard).
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
    """Creates a filesystem-safe folder slug from skill name, avoiding Windows reserved names."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    clean_s = s.strip("-") or "skill"
    if clean_s in WINDOWS_RESERVED_NAMES:
        clean_s = f"{clean_s}_skill"
    return clean_s


class SkillLibraryManager:
    """Manages the agentskills.io folder-based skill repository with progressive disclosure (Anara Standard)."""

    def __init__(self, root_dir: Optional[str] = None):
        self._lock = threading.RLock()
        self._root_dir = root_dir
        self._skills_cache: List[Dict[str, Any]] = []
        self._cache_mtime: float = 0.0

    @property
    def root_dir(self) -> str:
        if self._root_dir:
            return self._root_dir
        return str(get_anara_skills_dir())

    @root_dir.setter
    def root_dir(self, val: str):
        with self._lock:
            self._root_dir = val
            self._invalidate_cache()

    def _invalidate_cache(self):
        with self._lock:
            self._cache_mtime = 0.0
            self._skills_cache.clear()

    def invalidate_cache(self):
        """Public alias for external cache invalidation (skills_hub parity)."""
        self._invalidate_cache()

    def parse_skill_file(self, skill_md_path: str) -> Optional[Dict[str, Any]]:
        """Parses frontmatter and body markdown from a SKILL.md file."""
        if not os.path.isfile(skill_md_path):
            return None
        try:
            with open(skill_md_path, "r", encoding="utf-8") as f:
                content = f.read(MAX_SKILL_FILE_BYTES)

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

        steps_md = "\n".join([f"{idx + 1}. {re.sub(r'^\d+\.\s*', '', str(s).strip())}" for idx, s in enumerate(procedure_steps)])

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

        # Security verification before saving (Hermes skills_guard parity)
        from core.skills_hub import validate_skill_content_safety
        is_safe, threat = validate_skill_content_safety(full_content)
        if not is_safe:
            logger.warning(f"[SkillLibrary] Refused to save unsafe skill '{name}': {threat}")
            return {
                "ok": False,
                "error": f"Security verification failed: {threat}",
                "name": name,
                "slug": slug,
            }

        skill_file = os.path.join(folder, "SKILL.md")
        with self._lock:
            atomic_write_text(Path(skill_file), full_content)
            self._invalidate_cache()

        logger.info(f"[SkillLibrary] Saved skill '{name}' ({status}) to {skill_file}")

        # Mirror to SQLite database if legacy table exists (Anara Standard)
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

    def patch_skill(
        self,
        name_or_slug: str,
        old_string: str,
        new_string: str,
        relative_file_path: Optional[str] = None,
        replace_all: bool = False,
    ) -> Dict[str, Any]:
        """
        Applies a targeted find-and-replace patch to an existing skill (Anara skill_manage patch standard).
        """
        skill = self.get_skill(name_or_slug)
        if not skill:
            return {"ok": False, "error": f"Skill '{name_or_slug}' not found."}

        target_file = skill["file_path"]
        if relative_file_path:
            clean_rel = relative_file_path.strip().replace("\\", "/").lstrip("/")
            folder = os.path.dirname(skill["file_path"])
            custom_path = os.path.normpath(os.path.join(folder, clean_rel))
            if not custom_path.startswith(folder):
                return {"ok": False, "error": "Path traversal prohibited."}
            target_file = custom_path

        if not os.path.isfile(target_file):
            return {"ok": False, "error": f"File '{target_file}' not found."}

        try:
            with open(target_file, "r", encoding="utf-8") as f:
                content = f.read(MAX_SKILL_FILE_BYTES)

            needle = old_string
            if needle not in content:
                if needle.strip() in content:
                    needle = needle.strip()
                else:
                    return {"ok": False, "error": f"old_string not found in '{os.path.basename(target_file)}'."}

            if not replace_all and content.count(needle) > 1:
                return {"ok": False, "error": f"old_string matches {content.count(needle)} occurrences. Please provide more context."}

            if replace_all:
                patched = content.replace(needle, new_string)
            else:
                patched = content.replace(needle, new_string, 1)

            if os.path.basename(target_file) == "SKILL.md":
                from core.skills_hub import validate_skill_content_safety
                is_safe, threat = validate_skill_content_safety(patched)
                if not is_safe:
                    return {"ok": False, "error": f"Security verification failed: {threat}"}

                now_iso = datetime.now().isoformat()
                patched = re.sub(r"(updated_at:\s*).*(\n)", rf"\g<1>'{now_iso}'\2", patched)

            with self._lock:
                atomic_write_text(Path(target_file), patched)
                self._invalidate_cache()

            logger.info(f"[SkillLibrary] Successfully patched skill '{skill['name']}' at {target_file}")
            return {
                "ok": True,
                "name": skill["name"],
                "slug": skill["slug"],
                "file_path": target_file,
                "action": "patched"
            }
        except Exception as e:
            logger.error(f"[SkillLibrary] Error patching skill '{name_or_slug}': {e}")
            return {"ok": False, "error": str(e)}

    def _compute_scan_signature(self) -> float:
        """Computes composite mtime signature across root and all skill directories (Anara Standard)."""
        try:
            total_mtime = os.path.getmtime(self.root_dir)
            for skill_path in Path(self.root_dir).rglob("SKILL.md"):
                if any(part.startswith(".") for part in skill_path.parts):
                    continue
                try:
                    total_mtime = max(total_mtime, skill_path.stat().st_mtime)
                except Exception:
                    pass
            return total_mtime
        except Exception:
            return 0.0

    def list_skills(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scans runtime skills directory with dynamic mtime signature caching (Anara Standard)."""
        if not os.path.isdir(self.root_dir):
            return []

        with self._lock:
            curr_sig = self._compute_scan_signature()
            if self._cache_mtime == curr_sig and self._skills_cache:
                cached_results = list(self._skills_cache)
            else:
                results = []
                for skill_path in Path(self.root_dir).rglob("SKILL.md"):
                    # Exclude hidden directories (like .hub, .git)
                    if any(part.startswith(".") for part in skill_path.parts):
                        continue
                    parsed = self.parse_skill_file(str(skill_path))
                    if parsed:
                        results.append(parsed)

                self._skills_cache = sorted(results, key=lambda s: s.get("name", ""))
                self._cache_mtime = curr_sig
                cached_results = list(self._skills_cache)

        if status_filter and status_filter != "all":
            return [s for s in cached_results if s.get("status") == status_filter]
        return cached_results

    def get_skill(self, name_or_slug: str) -> Optional[Dict[str, Any]]:
        """Retrieves a skill by name or slug."""
        clean = name_or_slug.strip().lower()
        for s in self.list_skills():
            if s["slug"].lower() == clean or s["name"].lower() == clean or slugify(s["name"]) == clean:
                return s
        return None

    def toggle_skill(self, slug: str, enabled: Optional[bool] = None) -> Optional[Dict[str, Any]]:
        """
        Toggles a skill between 'active' and 'disabled' (Anara Standard).
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

        self._invalidate_cache()
        skill["status"] = new_status
        skill["enabled"] = (new_status == "active")
        logger.info(f"[SkillLibrary] Toggled skill '{slug}' status: {current_status} -> {new_status}")
        return skill

    def get_skill_file(self, skill_name_or_slug: str, relative_file_path: str) -> Optional[Dict[str, Any]]:
        """Retrieves a sub-resource file with path traversal and size limits (Anara Enterprise Architecture)."""
        clean_rel = (relative_file_path or "").strip().replace("\\", "/")
        if not clean_rel or clean_rel.startswith("/") or ".." in clean_rel.split("/"):
            logger.warning(f"[SkillLibrary] Blocked path traversal attempt in skill file: {relative_file_path}")
            return None

        skill = self.get_skill(skill_name_or_slug)
        if not skill:
            return None
        folder_path = Path(os.path.dirname(skill["file_path"])).resolve()
        target_path = Path(os.path.join(str(folder_path), clean_rel)).resolve()
        try:
            if not target_path.is_relative_to(folder_path) or not target_path.is_file():
                return None
        except AttributeError:
            if not str(target_path).startswith(str(folder_path) + os.sep) or not target_path.is_file():
                return None

        try:
            if target_path.stat().st_size > MAX_SKILL_FILE_BYTES:
                logger.warning(f"[SkillLibrary] Refused to read file exceeding limit: {target_path}")
                return None
            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(MAX_SKILL_FILE_BYTES)
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
        skill_meta = self.get_skill(slug)
        if skill_meta and skill_meta.get("dir_path"):
            folder = skill_meta["dir_path"]
            skill_file = skill_meta.get("file_path") or os.path.join(folder, "SKILL.md")
        else:
            folder = os.path.join(self.root_dir, slug)
            skill_file = os.path.join(folder, "SKILL.md")

        parsed = self.parse_skill_file(skill_file)
        if not parsed:
            return False

        parsed["status"] = "active"
        ok = self._rewrite_status(skill_file, "active")
        if ok:
            self._invalidate_cache()
        return ok

    def reject_skill(self, slug: str, delete_folder: bool = True) -> bool:
        """Rejects and optionally deletes a skill folder with root protection (Anara Standard)."""
        clean_slug = (slug or "").strip().lower()
        if not clean_slug or clean_slug in {".", "~"}:
            return False

        skill_meta = self.get_skill(clean_slug)
        root_p = Path(self.root_dir).resolve()
        if skill_meta and skill_meta.get("dir_path"):
            target_dir = Path(skill_meta["dir_path"]).resolve()
        else:
            if any(c in clean_slug for c in ("/", "\\", "..")):
                return False
            target_dir = (root_p / clean_slug).resolve()

        if target_dir == root_p or not target_dir.is_relative_to(root_p):
            return False

        folder = str(target_dir)
        if not os.path.isdir(folder):
            return False

        if delete_folder:
            # Refuse to delete category bucket folders that do not own their own SKILL.md
            if not (target_dir / "SKILL.md").is_file():
                return False
            _safe_rmtree(target_dir)
            self._invalidate_cache()
            logger.info(f"[SkillLibrary] Deleted skill folder: {folder}")
            return True

        skill_file = os.path.join(folder, "SKILL.md")
        ok = self._rewrite_status(skill_file, "rejected")
        if ok:
            self._invalidate_cache()
        return ok

    def _rewrite_status(self, skill_file: str, new_status: str) -> bool:
        """Safely updates status in YAML frontmatter block only (Anara Standard)."""
        try:
            with open(skill_file, "r", encoding="utf-8") as f:
                content = f.read()

            fm_match = re.match(r"^(---\s*\n)(.*?)(\n---\s*\n)(.*)$", content, re.DOTALL)
            if fm_match:
                head, fm_body, sep, body = fm_match.groups()
                if re.search(r"(?m)^status:\s*.*$", fm_body):
                    new_fm = re.sub(r"(?m)^status:\s*.*$", f"status: {new_status}", fm_body)
                else:
                    new_fm = f"status: {new_status}\n" + fm_body
                updated = f"{head}{new_fm}{sep}{body}"
            else:
                updated = f"---\nstatus: {new_status}\n---\n\n{content}"

            atomic_write_text(Path(skill_file), updated)
            return True
        except Exception as e:
            logger.error(f"[SkillLibrary] Error updating status in {skill_file}: {e}")
            return False

    def get_prompt_manifest(self, user_task: Optional[str] = None) -> str:
        """
        True Progressive Disclosure Engine (Anara Enterprise Architecture):
        Provides an active skills catalog index without prompt body stuffing.
        Full instructions are loaded strictly on demand via the skill_view tool.
        """
        active_skills = self.list_skills(status_filter="active")
        if not active_skills:
            return ""

        lines = [
            f"## Active Skills & Domain Capabilities ({len(active_skills)} Available Skills):",
            f"- Runtime Skills Directory: {self.root_dir}",
            "- PROGRESSIVE DISCLOSURE DIRECTIVE: Skills below provide specialized workflows, conventions, and scripts.",
            "  If your task matches or relates to a skill, call the `skill_view(skill_name)` tool to retrieve its detailed procedure on-demand.",
            "  Never guess internal skill steps or file paths without loading them first.",
            "\nAvailable Skills Index:",
        ]
        for s in active_skills:
            desc = (s.get("description") or "").strip()
            if len(desc) > 200:
                desc = desc[:197] + "..."
            lines.append(f"- **{s['name']}** ({s.get('category', 'general')}): {desc}")

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
