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
                    more_msg = f"\n    [... {more_cnt} additional files modified ...]" if more_cnt > 0 else ""
                    lines.append(f"- Status Berkas / Changed Files Status (Live Ground Truth):\n    {preview_st}{more_msg}")
                else:
                    lines.append("- Status Berkas: Bersih / Clean working tree")

            # 3. Recent commits
            log_res = subprocess.run(
                ["git", "-C", root_path, "log", "-3", "--oneline"],
                capture_output=True,
                text=True,
                timeout=0.5
            )
            if log_res.returncode == 0 and log_res.stdout.strip():
                log_lines = "\n    ".join(log_res.stdout.strip().splitlines())
                lines.append(f"- Recent Commits:\n    {log_lines}")

            # 4. Project verify commands
            verify_cmds = []
            if os.path.isfile(os.path.join(root_path, "run_tests.py")):
                verify_cmds.append("python run_tests.py")
            if os.path.isfile(os.path.join(root_path, "test_general_agent.py")):
                verify_cmds.append("python test_general_agent.py")
            if os.path.isfile(os.path.join(root_path, "pytest.ini")) or os.path.isdir(os.path.join(root_path, "backend", "tests")):
                verify_cmds.append("python -m pytest")
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

        # Slot 3: Tool Guidance & Permission Gate Rules (Hermes Parity)
        slot3_tools = (
            "[TOOL GUIDANCE & PERMISSION GATE RULES]:\n"
            "- USER INTENT REASONING (CONVERSATION VS ACTION — HERMES PARITY): When the context is conceptual discussion, architectural Q&A, or conversational follow-up (e.g. 'ok proceed', 'yes', 'explain', 'what do you think?'), respond purely in natural conversational prose. Do NOT execute terminal commands or mutating tools unless the user explicitly requests physical execution or testing.\n"
            "- GROUND-TRUTH FACT VERIFICATION (PEMBUKTIAN FAKTA BERBASIS GROUND-TRUTH — HERMES PARITY): When asked if an implementation, code, or subsystem is complete/fixed, NEVER assume or hallucinate from past conversation memory. Actively verify real workspace ground truth: inspect git status, read current code with 'read_local_file', and run project test verification commands ('run_tests.py' / 'pytest') to prove correctness with physical exit codes.\n"
            "- REPOSITORY INTEGRITY & TARGETED DELETION (HERMES REPO-SAFETY): The workspace is an active source code repository, not a disposable scratchpad. NEVER execute destructive mass wipes ('rm -rf *', 'Remove-Item * -Recurse', 'git clean -fdx'). If the user explicitly requests deleting a specific file, use 'delete_local_file' targeted specifically at that file.\n"
            "- AUTONOMOUS MULTI-TOOL EXECUTION: Invoke available tools accurately and proactively when physical actions are required.\n"
            "- NATURAL COMMUNICATION & ZERO-CANNED RESPONSES: Speak in Anara's warm, direct, and empathetic persona. NEVER output robotic, canned opening formulas.\n"
            "- SUFFICIENT FULFILLMENT PRINCIPLE: When a tool or visual action has fulfilled the user's essential intent, conclude your turn with a complete and helpful report. Avoid redundant secondary calls unless requested.\n"
            "- AUTONOMOUS READ-ONLY EXPLORATION: Always prioritize direct read-only tools ('read_local_file', 'glob_find_files', 'grep_search_code', 'list_directory') over raw terminal commands for file inspection. These operations execute autonomously without prompting approval.\n"
            "- PUSH-BUTTON SAFETY GATES: In Plan Mode, only read-only inspection tools are permitted. In Build Mode, full construction, file modifications, and terminal executions are authorized after user confirmation.\n"
            "- MULTILINGUAL ADAPTATION (CRITICAL): Always respond in the user's active language (English if English, Bahasa Indonesia if Indonesian, 日本語 if Japanese, 한국어 if Korean, etc.)."
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
            from memory.memory_nudge import memory_nudge_manager
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
            f"- Project Name: {project_name}\n"
            f"- Physical Root Path: {root_path}\n"
        )
        if git_snapshot:
            slot7_project += f"{git_snapshot}\n"
        if total_files > 0:
            files_preview = ', '.join([f['path'] for f in (workspace_tree or {}).get('files', [])[:25]]) or '(Empty / clean folder)'
            slot7_project += f"- Indexed Files ({total_files} total): {files_preview}\n"

        slot7_project += (
            "- WORKSPACE GUIDELINES: All file operations are confined within this project root. "
            "Use the Git worktree status above as ground truth when verifying or resuming tasks."
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

        # Inject Episodic Architecture Decision Records (Hermes Parity: Pilar 3)
        try:
            from memory.episodic_adr import episodic_adr_manager
            recent_adrs = episodic_adr_manager.get_recent_project_adrs(limit=4)
            if recent_adrs:
                adr_lines = [
                    f"- [{a['created_at'][:10] if a.get('created_at') else 'ADR'}] {a['architecture_decision']} (Alasan: {a['rationale']})"
                    for a in recent_adrs
                ]
                slot7_project += f"\n\n[REKAMAN KEPUTUSAN ARSITEKTUR TERDAHULU (EPISODIC ADR)]:\n" + "\n".join(adr_lines)
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
