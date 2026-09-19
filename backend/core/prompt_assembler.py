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

    @classmethod
    def probe_git_worktree_snapshot(cls, root_path: str) -> str:
        """
        Extracts live, real-time Git status and worktree facts bounded by strict timeouts (Hermes Agent Parity).
        Provides the ground truth of changed and untracked files so the agent is never blind to local edits.
        """
        if not root_path or not os.path.isdir(root_path):
            return ""

        git_dir = os.path.join(root_path, ".git")
        if not os.path.isdir(git_dir):
            return ""

        import subprocess
        lines = []
        try:
            # 1. Branch name
            b_res = subprocess.run(
                ["git", "-C", root_path, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=0.5
            )
            branch = b_res.stdout.strip() if b_res.returncode == 0 else "main"
            lines.append(f"- Git Branch: {branch}")

            # 2. Live Git Status
            st_res = subprocess.run(
                ["git", "-C", root_path, "status", "--short"],
                capture_output=True,
                text=True,
                timeout=0.8
            )
            if st_res.returncode == 0:
                raw_st = st_res.stdout.strip()
                if raw_st:
                    st_lines = raw_st.splitlines()
                    preview_st = "\n    ".join(st_lines[:15])
                    more_cnt = len(st_lines) - 15
                    more_msg = f"\n    [... {more_cnt} berkas lainnya berubah ...]" if more_cnt > 0 else ""
                    lines.append(f"- Status Berkas Berubah (Live Ground Truth):\n    {preview_st}{more_msg}")
                else:
                    lines.append("- Status Berkas: Bersih (Clean working tree)")

            # 3. Recent commits
            log_res = subprocess.run(
                ["git", "-C", root_path, "log", "-3", "--oneline"],
                capture_output=True,
                text=True,
                timeout=0.5
            )
            if log_res.returncode == 0 and log_res.stdout.strip():
                log_lines = "\n    ".join(log_res.stdout.strip().splitlines())
                lines.append(f"- Commit Terakhir:\n    {log_lines}")

            # 4. Project verify commands
            verify_cmds = []
            if os.path.isfile(os.path.join(root_path, "run_tests.py")):
                verify_cmds.append("python run_tests.py")
            if os.path.isfile(os.path.join(root_path, "test_general_agent.py")):
                verify_cmds.append("python test_general_agent.py")
            if os.path.isfile(os.path.join(root_path, "pytest.ini")) or os.path.isdir(os.path.join(root_path, "backend", "tests")):
                verify_cmds.append("pytest")
            if os.path.isfile(os.path.join(root_path, "package.json")):
                verify_cmds.append("npm test")
            if verify_cmds:
                lines.append(f"- Perintah Verifikasi Uji Proyek: {', '.join(verify_cmds)}")
        except Exception:
            pass

        return "\n".join(lines)

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
            "- PENALARAN INTENSI PENGGUNA (CONVERSATION VS ACTION — HERMES PARITY): Jika konteks obrolan adalah diskusi konseptual, tanya-jawab arsitektur, atau respons kelanjutan topik (misal 'oke lanjut', 'siap', 'lanjutkan'), jawablah secara MURNI dalam percakapan naratif yang cerdas dan tuntas. Dilarang memanggil alat terminal (seperti pytest, test runner, git) jika pengguna tidak secara eksplisit meminta eksekusi atau pengujian fisik.\n"
            "- PEMBUKTIAN FAKTA BERBASIS GROUND-TRUTH (HERMES PARITY): Ketika pengguna bertanya apakah suatu implementasi, kode, atau subsistem sudah beres/selesai, DILARANG KERAS berasumsi atau menyimpulkan berdasarkan ingatan percakapan lama. Kamu wajib memverifikasi realitas nyata di repositori saat ini: periksa status berkas Git (terutama berkas baru '??' atau modifikasi 'M' yang tertera di info workspace di bawah), baca berkas implementasi terkini dengan 'read_local_file', dan jalankan perintah verifikasi pengujian proyek ('run_tests.py' / 'pytest') untuk membuktikan kebenaran dengan hasil pengujian nyata.\n"
            "- INTEGRITAS REPOSITORI & PENGHAPUSAN TERTARGET (HERMES REPO-SAFETY): Workspace aktif adalah repositori kode sumber proyek nyata, BUKAN folder kosong sekali-pakai (disposable scratchpad). DILARANG KERAS menjalankan pembersihan massal sapu-jagat (seperti 'rm -rf *', 'Remove-Item * -Recurse', 'git clean -fdx') atau menimpa arsitektur proyek secara liar. Jika pengguna secara eksplisit meminta menghapus berkas tertentu, gunakan alat 'delete_local_file' secara spesifik dan tertarget pada berkas sasaran tersebut.\n"
            "- Gunakan tools yang tersedia secara mandiri, akurat, dan tepat guna saat tindakan nyata memang dibutuhkan.\n"
            "- KOMUNIKASI NATURAL & ZERO-CANNED (ANARA STANDARD): Berbicaralah dengan gaya Anara yang cerdas, hangat, luwes, dan lugas sesuai soul.md. DILARANG KERAS mengeluarkan kalimat kalengan pembuka robotik.\n"
            "- PRINSIP KECUKUPAN EKSEKUSI (SUFFICIENT FULFILLMENT PRINCIPLE — ANARA STANDARD): Ketika suatu alat visual atau aksi telah berhasil memenuhi maksud esensial pengguna, segera selesaikan giliran tugas dengan respon akhir yang cerdas dan tuntas. Dilarang memicu eksekusi investigasi sekunder berlebihan kecuali diminta secara eksplisit.\n"
            "- EKSPLORASI BERKAS & FOLDER MANDIRI (AUTONOMI READ-ONLY): Ketika pengguna meminta memeriksa folder, memeriksa berkas yang dipulihkan, atau melihat isi direktori, SELALU UTAMAKAN tools read-only langsung ('list_directory', 'scan_workspace_folder', 'glob_find_files', 'read_local_file') daripada terminal. Tindakan inspeksi atau pembacaan ini sepenuhnya aman dan dapat kamu jalankan langsung secara otonom tanpa meminta persetujuan pengguna.\n"
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

        # Slot 7: Project Context & Live Worktree Snapshot (Hermes Ground-Truth Parity)
        from core.agent import anara_agent
        root_path = (workspace_tree or {}).get("root_path") or anara_agent.get_session_dir(session_id)
        if not root_path or not os.path.isdir(root_path):
            root_path = anara_agent.get_project_repo_root()

        project_name = (workspace_tree or {}).get("workspace_name") or os.path.basename(root_path.rstrip("\\/")) or "Project Anara"
        total_files = (workspace_tree or {}).get("total_files") or 0

        git_snapshot = cls.probe_git_worktree_snapshot(root_path)

        slot7_project = (
            f"[LIVE WORKSPACE & REPOSITORY SNAPSHOT (HERMES GROUND-TRUTH)]:\n"
            f"- Nama Project: {project_name}\n"
            f"- Root Path Fisik: {root_path}\n"
        )
        if git_snapshot:
            slot7_project += f"{git_snapshot}\n"
        if total_files > 0:
            files_preview = ', '.join([f['path'] for f in (workspace_tree or {}).get('files', [])[:25]]) or '(Folder siap dibangun)'
            slot7_project += f"- Berkas Terindeks ({total_files} total): {files_preview}\n"

        slot7_project += (
            "- PANDUAN KERJA WORKSPACE: Seluruh operasi membaca dan memodifikasi berkas "
            "berada di dalam root proyek ini. Manfaatkan status berkas Git di atas sebagai bukti nyata "
            "pekerjaan pengguna saat memverifikasi atau melanjutkan tugas."
        )

        # Scan for local AGENTS.md / CLAUDE.md / RULES.md in project root
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

        slots = [slot1_identity, slot2_mode, slot3_tools, slot4_memory]
        if slot5_scratchpad:
            slots.append(slot5_scratchpad)
        if slot6_skills:
            slots.append(slot6_skills)
        if slot7_project:
            slots.append(slot7_project)

        return "\n\n".join(slots)
