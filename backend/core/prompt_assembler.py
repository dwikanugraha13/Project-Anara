"""
prompt_assembler.py — 6-Slot Enterprise Prompt Assembler for Project Anara.
Implements the Hermes & Claude Code architectural standard:
Slot 1: Identity & Persona (SOUL.md)
Slot 2: Operational Mode Instructions (Plan Mode vs Build Mode)
Slot 3: Tool Guidelines & Catalog
Slot 4: Long-Term Memory Snapshot (Facts, Preferences, Persona)
Slot 5: Active Skills Manifest (Hermes Skills Library)
Slot 6: Workspace & Project Context (File tree, Git status, AGENTS.md)
"""

import os
from typing import Optional, Dict, Any, List


class PromptAssembler:
    """Orchestrates structured 6-slot system prompt assembly with zero hardcoded constraints."""

    @staticmethod
    def assemble(
        mode: str = "plan",
        speaker_name: Optional[str] = None,
        workspace_tree: Optional[Dict[str, Any]] = None,
        active_skills: Optional[List[Dict[str, Any]]] = None,
        is_chat_mode: bool = True,
        session_type: str = "chat",
    ) -> str:
        # Slot 1: Identity & Core Personality
        from cognition import get_soul_prompt
        slot1_identity = get_soul_prompt(mode="chat" if is_chat_mode else "voice").strip()

        # Slot 2: Operational Mode Boundaries (Clean, adaptif, no hardcoded steps)
        is_code_session = str(session_type).lower() == "code"
        if mode == "plan":
            if is_code_session:
                slot2_mode = (
                    "[STATUS OPERASIONAL: PLAN MODE (ANARA CODE — READ-ONLY ARSITEKTUR REPOSITORI)]\n"
                    "- Kamu berada dalam PLAN MODE di Anara Code Studio (Aman & Read-Only). DILARANG memodifikasi berkas sebelum disetujui pengguna.\n"
                    "- PROTOKOL KLARIFIKASI: Jika instruksi pengguna masih umum atau luas, panggil tool 'interactive_question' untuk menyajikan Wizard Card opsi bertahap.\n"
                    "- PROTOKOL GROUNDING: Lakukan inspeksi lingkungan proyek nyata menggunakan tools read-only untuk mengusulkan path folder konkret di workspace.\n"
                    "- STANDAR CETAK BIRU 5 PILAR: Sajikan rencana dalam 5 bagian: 1. Ringkasan & Konsep, 2. Tech Stack & Dependencies, 3. Arsitektur Struktur Folder (pohon ASCII dengan komentar #), 4. Fitur Utama, 5. Rencana Langkah Eksekusi. Tutup dengan persetujuan sebelum mulai eksekusi."
                )
            else:
                slot2_mode = (
                    "[STATUS OPERASIONAL: PLAN MODE (CONVERSATIONAL PLAN GATE — KEAMANAN BERJENJANG)]\n"
                    "- Terdeteksi permintaan tindakan berisiko atau mutasi sistem di sesi percakapan umum.\n"
                    "- Kamu beroperasi dalam status Read-Only untuk keamanan. DILARANG mengeksekusi modifikasi sebelum disetujui.\n"
                    "- Tugasmu: Sajikan rencana tindakan yang ringkas, jelas, dan terstruktur. Jelaskan konsekuensi dan langkah-langkah yang akan diambil, lalu minta persetujuan pengguna (misal: 'Apakah rencana ini disetujui untuk dieksekusi?')."
                )
        else:
            if is_code_session:
                slot2_mode = (
                    "[STATUS OPERASIONAL: BUILD MODE (ANARA CODE — KONSTRUKSI NYATA & EKSEKUSI OTONOM)]\n"
                    "- Kamu berada dalam BUILD MODE di Anara Code Studio (Eksekusi Otonom Penuh).\n"
                    "- Tugasmu: Eksekusi rencana kerja secara mandiri menggunakan tools modifikasi berkas (edit_file, write_local_file) dan terminal shell (execute_cli_command) TERISOLASI di dalam folder proyek.\n"
                    "- Terapkan self-verification loop: verifikasi hasil pekerjaanmu via terminal test/build sebelum melapor ke pengguna."
                )
            else:
                slot2_mode = (
                    "[STATUS OPERASIONAL: MODE ANARA CHAT — ASISTEN OTONOM & GENERATIF]\n"
                    "- Kamu beroperasi sebagai Asisten Percakapan & Rekayasa Otonom multi-channel.\n"
                    "- Untuk kueri status sistem atau perangkat keras (seperti status baterai laptop via Win32_Battery/WMIC, spesifikasi via systeminfo, CPU, jam/tanggal, git), gunakan 'execute_cli_command' untuk inspeksi nyata dan berikan hasilnya secara ramah, presisi, dan to-the-point.\n"
                    "- Untuk pembuatan berkas proyek multi-file, gunakan 'create_zip_archive' atau 'generate_file_artifact' agar pengguna bisa mengunduh arsip ZIP."
                )

        # Slot 3: Tool Guidance & Permission Gate Rules
        slot3_tools = (
            "[PANDUAN PEMANGGILAN ALAT & PERMISSION GATE]:\n"
            "- Gunakan tools yang tersedia secara mandiri, akurat, dan tepat guna.\n"
            "- Di Plan Mode: Tools read-only yang diizinkan meliputi: 'interactive_question', 'read_local_file', 'grep_search_code', 'glob_find_files', 'list_directory', 'scan_workspace_folder', 'learn_and_save_skill', serta 'execute_cli_command' untuk perintah inspeksi aman (cek baterai laptop via Win32_Battery, spesifikasi sistem via systeminfo, tanggal/jam, node -v, git status). Jawab pertanyaan status sistem secara nyata menggunakan hasil inspeksi ini!\n"
            "- Di Build Mode: Seluruh tools konstruksi, modifikasi berkas, dan terminal diizinkan penuh.\n"
            "- Gunakan 'learn_and_save_skill' secara otonom ketika kamu merancang atau menemukan pola arsitektur baru yang bernilai untuk disimpan permanen ke database SQLite."
        )

        # Slot 4: Memory Snapshot (4-File Persistent Memory Standard: USER.md + MEMORY.md + SQLite Facts)
        from memory import memory_engine, file_memory
        db_memory = memory_engine.get_system_prompt_context(speaker_name, is_chat_mode=is_chat_mode).strip()
        file_snapshot = file_memory.get_prompt_context(speaker_name=speaker_name)
        slot4_memory = f"{file_snapshot}\n\n{db_memory}".strip()

        # Slot 5: Skills Manifest (Skill Library v2 — Progressive Disclosure)
        from core.skill_library import skill_library
        skill_manifest = skill_library.get_prompt_manifest()
        if skill_manifest:
            slot5_skills = skill_manifest
        else:
            skills_list = active_skills if active_skills is not None else memory_engine.get_all_agent_skills(active_only=True)
            if skills_list:
                skill_lines = [f"- **{sk['name']}** ({sk.get('category', 'general')}): {sk.get('description', '')}" for sk in skills_list[:8]]
                slot5_skills = "[KEAHLIAN & SKILLS AGEN AKTIF (HERMES BRAIN)]:\n" + "\n".join(skill_lines)

        # Slot 6: Project Context & AGENTS.md / Repo Rules
        slot6_project = ""
        is_custom = bool(workspace_tree and (workspace_tree.get("is_custom_folder") or workspace_tree.get("is_external")))
        if workspace_tree and (workspace_tree.get("total_files", 0) > 0 or is_custom):
            files_preview = ', '.join([f['path'] for f in workspace_tree.get('files', [])[:25]]) or '(Folder kosong siap dibangun)'
            slot6_project = (
                "[INFO WORKSPACE: ANARA CODE AKTIF (PROYEK LOKAL TERHUBUNG)]:\n"
                f"- Nama Project: {workspace_tree.get('workspace_name')}\n"
                f"- Root Path Fisik: {workspace_tree.get('root_path')}\n"
                f"- Total Berkas: {workspace_tree.get('total_files')} berkas\n"
                f"- Berkas Terindeks: {files_preview}\n"
                "- Seluruh modifikasi berkas ('write_local_file', 'edit_file') dan terminal ('execute_cli_command') TERKUNCI 100% AMAN hanya di dalam folder proyek ini."
            )
            # Scan for local AGENTS.md / CLAUDE.md / RULES.md in project root
            root_path = workspace_tree.get("root_path")
            if root_path and os.path.isdir(root_path):
                for custom_doc in ["AGENTS.md", "CLAUDE.md", "RULES.md"]:
                    doc_p = os.path.join(root_path, custom_doc)
                    if os.path.isfile(doc_p):
                        try:
                            with open(doc_p, "r", encoding="utf-8", errors="ignore") as f:
                                doc_content = f.read(2000).strip()
                                if doc_content:
                                    slot6_project += f"\n\n[ATURAN REPOSITORI PROYEK ({custom_doc})]:\n{doc_content}"
                                    break
                        except Exception:
                            pass
        else:
            slot6_project = (
                "[STATUS WORKSPACE: MODE PERCAKAPAN MULTIVERSAL (MULTI-CHANNEL)]:\n"
                "- Sesi aktif dari antarmuka multi-channel (Telegram, WhatsApp, CLI, atau Web Chat).\n"
                "- Kamu beroperasi dengan fleksibilitas penuh sebagai General AI Agent:\n"
                "  1. Kueri Sistem & Hardware: Jalankan 'execute_cli_command' untuk inspeksi nyata (misal cek status baterai laptop via Win32_Battery, spesifikasi hardware via systeminfo, CPU, jam/tanggal, jaringan) dan laporkan hasilnya secara akurat ke pengguna.\n"
                "  2. Pembuatan Berkas & Kode: Sajikan kode lengkap di obrolan chat dalam format Markdown, serta buat berkas unduhan via 'create_zip_archive' atau 'generate_file_artifact' bila relevan.\n"
                "  3. Eksekusi Mandiri: Bila tindakan telah disetujui melalui protokol Plan/Build Gate, kamu berwenang penuh menjalankan perintah di lingkungan sandbox yang aman."
            )

        slots = [slot1_identity, slot2_mode, slot3_tools, slot4_memory]
        if slot5_skills:
            slots.append(slot5_skills)
        if slot6_project:
            slots.append(slot6_project)

        return "\n\n".join(slots)
