"""
skill_extractor.py — Anara Post-Build Autonomous Skill Extractor.
Analyzes successfully completed multi-step tasks in Build Mode, distills the reusable
architectural and procedural workflow, and commits it into SQLite agent_skills for lifelong learning.
"""

import asyncio
import json
import logging
import re
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class SkillExtractor:
    """Automates post-mission skill extraction and self-improvement."""

    @staticmethod
    async def extract_and_save_skill_async(
        user_prompt: str,
        tools_used: List[str],
        final_summary: str,
        workspace_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Extracts and registers a new skill if the turn accomplished a meaningful
        and reusable technical workflow (Anara Lifelong Learning loop).
        """
        # Only trigger if constructive mutating tools were used (Anara Enterprise Architecture)
        constructive_tools = {
            "write_local_file", "edit_file", "execute_cli_command",
            "execute_code", "generate_file_artifact", "create_zip_archive", "rezip_archive",
            "write_file", "patch", "terminal"
        }
        if not any(t in constructive_tools for t in tools_used):
            return None

        # Check existing skills across filesystem library AND SQLite database (Anara Standard)
        from core.skill_library import skill_library, slugify
        existing_slugs = {s["slug"].lower() for s in skill_library.list_skills(status_filter="all")}
        existing_names = {s["name"].lower() for s in skill_library.list_skills(status_filter="all")}
        try:
            from memory import memory_engine
            for s in memory_engine.get_all_agent_skills():
                existing_names.add(s["name"].lower())
                existing_slugs.add(slugify(s["name"]))
        except Exception:
            pass

        from core.prompt_loader import load_prompt
        prompt = load_prompt(
            "skill_extractor",
            user_prompt=user_prompt,
            tools_used=", ".join(tools_used),
            final_summary=final_summary[:2500]
        )

        try:
            from core.capabilities import get_fast_auxiliary_model
            from providers.caller import call_universal_chat_model

            aux_model = get_fast_auxiliary_model()
            raw = await asyncio.wait_for(
                call_universal_chat_model(
                    model_id=aux_model,
                    user_prompt=prompt,
                    max_tokens=None,
                    temperature=0.2,
                    read_only=True
                ),
                timeout=12.0
            )

            if not raw or not isinstance(raw, str):
                return None

            raw_str = raw.strip()
            from providers.caller import _extract_json_balanced, _robust_parse_json

            data = None
            for candidate, _, _ in _extract_json_balanced(raw_str):
                parsed = _robust_parse_json(candidate)
                if isinstance(parsed, dict) and "is_reusable" in parsed:
                    data = parsed
                    break

            if not data:
                parsed = _robust_parse_json(raw_str)
                if isinstance(parsed, dict) and "is_reusable" in parsed:
                    data = parsed

            if not data:
                return None

            raw_reusable = data.get("is_reusable")
            is_reusable = raw_reusable is True or str(raw_reusable).lower() in ("true", "1")
            skill_name = str(data.get("name", "")).strip()

            if not is_reusable or not skill_name:
                return None

            candidate_slug = slugify(skill_name)
            if skill_name.lower() in existing_names or candidate_slug in existing_slugs:
                logger.info(f"[SkillExtractor] Skill '{skill_name}' ({candidate_slug}) already exists. Skipping duplicate.")
                return None

            # Enforce Anara Agent Hardline standard: description <= 60 chars ending with a period
            desc = str(data.get("description", "")).strip()
            if len(desc) > 60:
                desc = desc[:57].rstrip() + "..."
            if desc and not desc.endswith("."):
                desc += "."

            from core.skill_library import skill_library
            saved = skill_library.save_skill(
                name=skill_name,
                category=data.get("category", "coding"),
                description=desc,
                trigger_keywords=data.get("trigger_keywords", []),
                procedure_steps=data.get("procedure_steps", []),
                status="pending",  # FR-16: Stored as pending, requires user review/approval
                learned=True,
            )

            if isinstance(saved, dict) and saved.get("file_path"):
                logger.info(f"[Anara Skill Extractor] Extracted new skill (pending approval): '{skill_name}' at {saved.get('file_path')}")
            return saved

        except Exception as e:
            logger.debug(f"[SkillExtractor] Extraction skipped or failed: {e}")
            return None
