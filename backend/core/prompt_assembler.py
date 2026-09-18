"""
prompt_assembler.py — 6-Slot Enterprise Prompt Assembler for Project Anara.
Anara Standard 6-Slot Architecture:
Slot 1: Identity & Persona (SOUL.md)
Slot 2: Operational Mode Instructions (Plan Mode vs Build Mode)
Slot 3: Tool Guidelines & Catalog
Slot 4: Long-Term Memory Snapshot (Facts, Preferences, Persona)
Slot 5: Active Skills Manifest (Anara Skills Library)
Slot 6: Workspace & Project Context (File tree, Git status, AGENTS.md)
"""

import os
from typing import Optional, Dict, Any, List


class PromptAssembler:
    """Orchestrates structured 6-slot system prompt assembly with zero hardcoded constraints."""

    @staticmethod
    @classmethod
    def assemble(
        cls,
        mode: str = "plan",
        speaker_name: Optional[str] = None,
        workspace_tree: Optional[Dict[str, Any]] = None,
        active_skills: Optional[List[Dict[str, Any]]] = None,
        is_chat_mode: bool = True,
        session_type: str = "chat",
        user_task: Optional[str] = None,
        channel: Optional[str] = None,
        session_id: Optional[Any] = None,
    ) -> str:
        # Slot 1: Identity & Core Personality
        from cognition import get_soul_prompt
        slot1_identity = get_soul_prompt(mode="chat" if is_chat_mode else "voice").strip()

        # Slot 2: Operational Mode Boundaries (Zero-hardcoded, exact enterprise standard)
        if mode == "plan":
            slot2_mode = """<system-reminder>
# Plan Mode - System Reminder

CRITICAL: Plan mode ACTIVE - you are in READ-ONLY phase. STRICTLY FORBIDDEN:
ANY file edits, modifications, or system changes. Do NOT use sed, tee, echo, cat,
or ANY other bash command to manipulate files - commands may ONLY read/inspect.
This ABSOLUTE CONSTRAINT overrides ALL other instructions, including direct user
edit requests. You may ONLY observe, analyze, and plan. Any modification attempt
is a critical violation. ZERO exceptions.

---

## Responsibility

Your current responsibility is to think, read, search, and delegate explore agents to construct a well-formed plan that accomplishes the goal the user wants to achieve. Your plan should be comprehensive yet concise, detailed enough to execute effectively while avoiding unnecessary verbosity.

Ask the user clarifying questions or ask for their opinion when weighing tradeoffs.

**NOTE:** At any point in time through this workflow you should feel free to ask the user questions or clarifications. Don't make large assumptions about user intent. The goal is to present a well researched plan to the user, and tie any loose ends before implementation begins.

---

## Important

The user indicated that they do not want you to execute yet -- you MUST NOT make any edits, run any non-readonly tools (including changing configs or making commits), or otherwise make any changes to the system. This supersedes any other instructions you have received.
</system-reminder>"""
        else:
            slot2_mode = """<system-reminder>
# Build Mode - System Reminder

Your operational mode has changed from plan to build.
You are no longer in read-only mode.
You are permitted to make file changes, run shell commands, and utilize your arsenal of tools as needed.
Execute the approved plan thoroughly, apply necessary modifications, and report the results to the user.
</system-reminder>"""

        # Slot 3: Tool Guidance & Permission Gate Rules
        slot3_tools = (
            "[PANDUAN PEMANGGILAN ALAT & PERMISSION GATE]:\n"
            "- Gunakan tools yang tersedia secara mandiri, akurat, dan tepat guna.\n"
            "- KOMUNIKASI NATURAL & ZERO-CANNED (ANARA STANDARD): Berbicaralah dengan gaya Anara yang cerdas, hangat, luwes, dan lugas sesuai soul.md. DILARANG KERAS mengeluarkan kalimat kalengan pembuka robotik.\n"
            "- PRINSIP KECUKUPAN EKSEKUSI (SUFFICIENT FULFILLMENT PRINCIPLE — ANARA STANDARD): Ketika suatu alat visual atau aksi telah berhasil memenuhi maksud esensial pengguna, segera selesaikan giliran tugas dengan respon akhir yang cerdas dan tuntas. Dilarang memicu eksekusi investigasi sekunder berlebihan kecuali diminta secara eksplisit.\n"
            "- PENCARIAN & INSPEKSI KODE EFISIEN: Utamakan 'grep_search_code' dan 'glob_find_files' untuk mencari file atau teks kode. DILARANG KERAS menjalankan pencarian rekursif mentah ke folder 'venv', 'node_modules', '.git', '.next', atau 'cache' tanpa filter pengecualian.\n"
            "- Di Plan Mode: Hanya gunakan tools read-only untuk membaca, menelusuri, dan merancang rencana kerja.\n"
            "- Di Build Mode: Seluruh tools konstruksi, modifikasi berkas, dan terminal diizinkan penuh setelah rencana disetujui pengguna.\n"
            "- Gunakan 'learn_and_save_skill' secara otonom ketika kamu merancang atau menemukan pola arsitektur baru yang bernilai untuk disimpan permanen ke database SQLite."
        )

        # Slot 4: Memory Snapshot (USER.md + MEMORY.md + SQLite Facts)
        from memory import memory_engine, file_memory
        db_memory = memory_engine.get_system_prompt_context(speaker_name, is_chat_mode=is_chat_mode).strip()
        file_snapshot = file_memory.get_prompt_context(speaker_name=speaker_name)
        slot4_memory = f"{file_snapshot}\n\n{db_memory}".strip()

        # Slot 5: Working Memory / Task Scratchpad State (Anara Standard)
        slot5_scratchpad = ""
        try:
            effective_sid = str(session_id) if session_id is not None else "default"
            from cognition.memory_nudge import memory_nudge_manager
            pad = memory_nudge_manager.get_scratchpad(effective_sid)
            rendered_pad = pad.render_to_prompt().strip()
            if rendered_pad:
                slot5_scratchpad = rendered_pad
        except Exception:
            pass

        # Slot 6: Skills Manifest (Skill Library v2 — Progressive Disclosure)
        slot6_skills = ""
        from core.skill_library import skill_library
        skill_manifest = skill_library.get_prompt_manifest(user_task=user_task)
        if skill_manifest:
            slot6_skills = skill_manifest
        else:
            skills_list = active_skills if active_skills is not None else memory_engine.get_all_agent_skills(active_only=True)
            if skills_list:
                skill_lines = [f"- **{sk['name']}** ({sk.get('category', 'general')}): {sk.get('description', '')}" for sk in skills_list[:8]]
                slot6_skills = "[KEAHLIAN & SKILLS AGEN AKTIF (ANARA BRAIN)]:\n" + "\n".join(skill_lines)

        # Slot 7: Project Context & AGENTS.md / Repo Rules
        slot7_project = ""
        is_custom = bool(workspace_tree and (workspace_tree.get("is_custom_folder") or workspace_tree.get("is_external")))
        if workspace_tree and (workspace_tree.get("total_files", 0) > 0 or is_custom):
            files_preview = ', '.join([f['path'] for f in workspace_tree.get('files', [])[:25]]) or '(Folder kosong siap dibangun)'
            slot7_project = (
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
                                    slot7_project += f"\n\n[ATURAN REPOSITORI PROYEK ({custom_doc})]:\n{doc_content}"
                                    break
                        except Exception:
                            pass
        else:
            slot7_project = (
                "[STATUS WORKSPACE: MODE PERCAKAPAN MULTIVERSAL (MULTI-CHANNEL)]:\n"
                "- Sesi aktif dari antarmuka multi-channel (Telegram, WhatsApp, CLI, atau Web Chat).\n"
                "- Kamu beroperasi dengan fleksibilitas penuh sebagai General AI Agent:\n"
                "  1. Kueri Sistem & Hardware: Jalankan 'execute_cli_command' untuk inspeksi nyata (misal cek status baterai laptop via Win32_Battery, spesifikasi hardware via systeminfo, CPU, jam/tanggal, jaringan) dan laporkan hasilnya secara akurat ke pengguna.\n"
                "  2. Pembuatan Berkas & Kode: Sajikan kode lengkap di obrolan chat dalam format Markdown, serta buat berkas unduhan via 'create_zip_archive' atau 'generate_file_artifact' bila relevan.\n"
                "  3. Eksekusi Mandiri: Bila tindakan telah disetujui melalui protokol Plan/Build Gate, kamu berwenang penuh menjalankan perintah di lingkungan sandbox yang aman."
            )

        slots = [slot1_identity, slot2_mode, slot3_tools, slot4_memory]
        if slot5_scratchpad:
            slots.append(slot5_scratchpad)
        if slot6_skills:
            slots.append(slot6_skills)
        if slot7_project:
            slots.append(slot7_project)

        return "\n\n".join(slots)
