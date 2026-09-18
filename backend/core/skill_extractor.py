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
        # Only trigger if constructive mutating tools were used
        constructive_tools = {"write_local_file", "edit_file", "generate_file_artifact", "create_zip_archive"}
        if not any(t in constructive_tools for t in tools_used):
            return None

        # Check existing skills in SQLite database
        from memory import memory_engine
        existing_skills = memory_engine.get_all_agent_skills()
        existing_names = [s["name"].lower() for s in existing_skills]

        prompt = f"""Kamu adalah Anara Autonomous Skill Extractor untuk Project Anara.
Agen baru saja berhasil menyelesaikan tugas konstruksi koding berikut:
Permintaan User: "{user_prompt}"
Alat yang Digunakan: {', '.join(tools_used)}
Laporan Hasil Eksekusi: "{final_summary[:600]}"

TUGAS:
1. Evaluasi apakah pekerjaan ini menghasilkan prosedur/resep teknis yang REUSABLE (dapat digunakan kembali di masa depan).
   Contoh alur yang bernilai: Scaffold proyek framework, setup styling/linter, integrasi database, pembuatan API endpoint, packaging zip, dsb.
2. Jika BUKAN prosedur reusable (misal cuma perbaikan typo satu kata atau obrolan santai), kembalikan is_reusable: false.
3. Jika YA (is_reusable: true):
   - name: Nama keahlian singkat & profesional (contoh: 'Scaffold Proyek React Vite Tailwind', 'Setup Docker Swarm').
   - category: 'coding' | 'architecture' | 'devops' | 'system'
   - description: 1-2 kalimat ringkasan tentang apa yang diselesaikan dan kapan keahlian ini dipanggil.
   - trigger_keywords: Array 3-5 kata kunci pemicu spesifik (contoh: ['react', 'vite', 'tailwind', 'scaffold']).
   - procedure_steps: Array 3-6 langkah konkret yang telah dilakukan.

KEMBALIKAN HANYA JSON VALID:
{{
  "is_reusable": true,
  "name": "Scaffold Proyek React Vite Tailwind",
  "category": "coding",
  "description": "Menyiapkan starter proyek React modern berbasis Vite dengan Tailwind CSS.",
  "trigger_keywords": ["react", "vite", "tailwind"],
  "procedure_steps": [
    "1. Inisialisasi struktur berkas proyek React",
    "2. Konfigurasi Tailwind CSS dan utilitas styling",
    "3. Implementasi komponen layout dan state awal"
  ]
}}"""

        try:
            from core.key_manager import key_manager
            from core.capabilities import get_fast_auxiliary_model
            from google.genai import types
            client = key_manager.get_client()

            cfg = types.GenerateContentConfig(
                max_output_tokens=350,
                temperature=0.2
            )
            aux_model = get_fast_auxiliary_model()
            res = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=aux_model,
                    contents=[prompt],
                    config=cfg
                ),
                timeout=8.0
            )

            if not res or not res.text:
                return None

            raw = res.text.strip()
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not json_match:
                return None

            data = json.loads(json_match.group(0))
            if not data.get("is_reusable") or not data.get("name"):
                return None

            skill_name = data["name"].strip()
            if skill_name.lower() in existing_names:
                logger.info(f"[SkillExtractor] Skill '{skill_name}' already exists in database. Skipping duplicate.")
                return None

            from core.skill_library import skill_library
            saved = skill_library.save_skill(
                name=skill_name,
                category=data.get("category", "coding"),
                description=data.get("description", ""),
                trigger_keywords=data.get("trigger_keywords", []),
                procedure_steps=data.get("procedure_steps", []),
                status="pending",  # FR-16: Stored as pending, requires user review/approval
                learned=True,
            )

            logger.info(f"[Anara Skill Extractor] Extracted new skill (pending approval): '{skill_name}' at {saved.get('file_path')}")
            return saved

        except Exception as e:
            logger.debug(f"[SkillExtractor] Extraction skipped or failed: {e}")
            return None
