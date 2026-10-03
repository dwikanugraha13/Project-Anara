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
        Extracts live, real-time Git status and worktree facts bounded by strict timeouts (Anara Standard).
        Provides the ground truth of changed and untracked files so the agent is never blind to local edits.
        Supports standard repositories, submodules, and linked Git worktrees.

        IMPORTANT: Uses synchronous subprocess.run — callers in async context MUST wrap
        with asyncio.to_thread() or run_in_executor() to prevent event loop blocking.
        """
        if not root_path or not os.path.isdir(root_path):
            return ""

        git_path = os.path.join(root_path, ".git")
        if not os.path.exists(git_path):
            return ""

        import subprocess
        lines = []

        # Suppress CRLF warnings that spam Windows stdout and slow git on large repos
        git_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

        # 1. Branch name
        try:
            b_res = subprocess.run(
                ["git", "-C", root_path, "-c", "core.safecrlf=false", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=0.6,
                env=git_env
            )
            branch = b_res.stdout.strip() if b_res.returncode == 0 else "main"
            lines.append(f"- Git Branch: {branch}")
        except Exception:
            lines.append("- Git Branch: main")

        # 2. Live Git Status
        try:
            st_res = subprocess.run(
                ["git", "-C", root_path, "-c", "core.safecrlf=false", "status", "--short"],
                capture_output=True,
                text=True,
                timeout=0.8,
                env=git_env
            )
            if st_res.returncode == 0:
                raw_st = st_res.stdout.strip()
                if raw_st:
                    st_lines = raw_st.splitlines()
                    preview_st = "\n    ".join(st_lines[:15])
                    more_cnt = len(st_lines) - 15
                    more_msg = f"\n    [... {more_cnt} additional files modified ...]" if more_cnt > 0 else ""
                    lines.append(f"- Changed Files Status (Live Ground Truth):\n    {preview_st}{more_msg}")
                else:
                    lines.append("- Working Tree Status: Clean")
        except Exception:
            pass

        # 3. Recent commits
        try:
            log_res = subprocess.run(
                ["git", "-C", root_path, "-c", "core.safecrlf=false", "log", "-3", "--oneline"],
                capture_output=True,
                text=True,
                timeout=0.6,
                env=git_env
            )
            if log_res.returncode == 0 and log_res.stdout.strip():
                log_lines = "\n    ".join(log_res.stdout.strip().splitlines())
                lines.append(f"- Recent Commits:\n    {log_lines}")
        except Exception:
            pass

        # 4. Dynamic Project Verification Commands Discovery (Anara Enterprise Architecture)
        try:
            verify_cmds = []
            if os.path.isfile(os.path.join(root_path, "pytest.ini")) or os.path.isfile(os.path.join(root_path, "pyproject.toml")) or os.path.isdir(os.path.join(root_path, "tests")) or os.path.isdir(os.path.join(root_path, "backend", "tests")):
                verify_cmds.append("pytest")
            if os.path.isfile(os.path.join(root_path, "package.json")):
                if os.path.isfile(os.path.join(root_path, "pnpm-lock.yaml")):
                    verify_cmds.append("pnpm test")
                elif os.path.isfile(os.path.join(root_path, "bun.lockb")) or os.path.isfile(os.path.join(root_path, "bun.lock")):
                    verify_cmds.append("bun test")
                elif os.path.isfile(os.path.join(root_path, "yarn.lock")):
                    verify_cmds.append("yarn test")
                else:
                    verify_cmds.append("npm test")
            if os.path.isfile(os.path.join(root_path, "Cargo.toml")):
                verify_cmds.append("cargo test")
            if os.path.isfile(os.path.join(root_path, "go.mod")):
                verify_cmds.append("go test ./...")
            if os.path.isfile(os.path.join(root_path, "run_tests.py")):
                verify_cmds.append("python run_tests.py")
            if verify_cmds:
                lines.append(f"- Project Verification Commands: {', '.join(verify_cmds)}")
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
        model_id: str = "",
        reasoning_effort: Optional[str] = None,
    ) -> str:
        # Slot 1: Identity & Core Personality
        from cognition import get_soul_prompt
        slot1_identity = get_soul_prompt(mode="chat" if is_chat_mode else "voice").strip()

        # Slot 2: Operational Mode Boundaries (Loaded dynamically from backend/prompts/modes/)
        from core.prompt_loader import load_prompt
        if mode == "plan":
            slot2_mode = load_prompt("modes/plan_mode").strip()
        elif mode in ("conversational", "chat"):
            slot2_mode = load_prompt("modes/conversational_mode").strip()
        else:
            slot2_mode = load_prompt("modes/build_mode").strip()

        # Slot 3: Tool Guidance & Permission Gate Rules (Loaded from backend/prompts/)
        slot3_tools = load_prompt("operational_guidelines").strip()

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
                skill_lines = "\n".join([f"- **{sk['name']}** ({sk.get('category', 'general')}): {sk.get('description', '')}" for sk in skills_list[:8]])
                slot6_skills = load_prompt("skills_manifest", skill_lines=skill_lines).strip()

        # Slot 7: Project Context & Repository Snapshot (Workspace Context)
        from core.agent import anara_agent
        has_custom = (
            bool((workspace_tree or {}).get("is_custom_folder"))
            or anara_agent.has_attached_workspace(session_id)
            or bool((workspace_tree or {}).get("root_path"))
        )
        is_build_mode = mode in ("build", "code")
        has_attached = has_custom or is_build_mode
        
        slot7_project = ""
        slot_git_status = ""
        root_path = ""

        if has_attached:
            if has_custom:
                root_path = (workspace_tree or {}).get("root_path") or anara_agent.get_session_dir(session_id)
            else:
                root_path = anara_agent.get_project_repo_root()

            if not root_path or not os.path.isdir(root_path):
                root_path = anara_agent.get_project_repo_root()

            project_name = (workspace_tree or {}).get("workspace_name") or (os.path.basename(root_path.rstrip("\\/")) if root_path else "Project Anara")
            total_files = (workspace_tree or {}).get("total_files") or 0
            git_snapshot = cls.probe_git_worktree_snapshot(root_path) if root_path else ""

            files_info = ""
            if total_files > 0:
                files_preview = ', '.join([f['path'] for f in (workspace_tree or {}).get('files', [])[:25]]) or '(Empty / clean folder)'
                files_info = f"- Indexed Files ({total_files} total): {files_preview}\n"

            slot7_project = (
                f"[LIVE WORKSPACE & REPOSITORY SNAPSHOT (ANARA GROUND-TRUTH)]:\n"
                f"- Project Name: {project_name}\n"
                f"- Physical Root Path: {root_path}\n"
                f"{files_info}"
                "- WORKSPACE GUIDELINES: All file operations are confined within this project root."
            )
            if git_snapshot:
                slot_git_status = (
                    f"[LIVE GIT WORKTREE STATUS (GROUND-TRUTH)]:\n"
                    f"{git_snapshot}\n"
                    "Use the live Git worktree status above as ground truth when verifying or resuming tasks."
                )
        else:
            home_dir = os.path.expanduser('~')
            recent_projects = []
            try:
                from memory import memory_engine
                recent_projects = memory_engine.get_recent_workspace_paths(limit=3)
            except Exception:
                pass
            recent_line = f"\n- Recent Project Workspaces: {', '.join(recent_projects)}" if recent_projects else ""
            switch_prompt = f"Ask if they would like to switch to one of their project workspaces ({recent_projects[0]}) or another directory." if recent_projects else "Inform them they can attach or pick a project folder anytime."
            slot7_project = (
                "[ENVIRONMENT & WORKSPACE CONTEXT (ANARA STANDARD)]:\n"
                f"- Host OS: Windows (11)\n"
                f"- User Home Directory: {home_dir}\n"
                f"- Current Working Directory: {home_dir}\n"
                f"- Active Project Workspace: None (no project folder has been attached to this session yet).{recent_line}\n"
                f"- GUIDELINES: You are currently operating at {home_dir}. The user has not selected or attached a project workspace for this session. "
                f"When asked what workspace or folder you are currently in, state that you are currently at {home_dir}. "
                f"{switch_prompt}"
            )

        # Scan for local AGENTS.md / CLAUDE.md / RULES.md in project root
        if root_path and os.path.isdir(root_path):
            for custom_doc in ["AGENTS.md", "CLAUDE.md", "RULES.md"]:
                doc_p = os.path.join(root_path, custom_doc)
                if os.path.isfile(doc_p):
                    try:
                        with open(doc_p, "r", encoding="utf-8-sig", errors="ignore") as f:
                            raw_content = f.read()
                        if raw_content:
                            # 70% head / 20% tail truncation snapped to line boundaries for oversized instruction files (Anara Standard)
                            if len(raw_content) > 12000:
                                head_budget = int(12000 * 0.7)
                                tail_budget = int(12000 * 0.2)
                                head_nl = raw_content.rfind("\n", 0, head_budget)
                                head_text = raw_content[:head_nl].strip() if head_nl > 100 else raw_content[:head_budget].strip()
                                tail_start = len(raw_content) - tail_budget
                                tail_nl = raw_content.find("\n", tail_start)
                                tail_text = raw_content[tail_nl:].strip() if (tail_nl != -1 and tail_nl < len(raw_content) - 50) else raw_content[-tail_budget:].strip()
                                doc_content = f"{head_text}\n\n[... truncated oversized repository rules ...]\n\n{tail_text}"
                            else:
                                doc_content = raw_content.strip()
                            slot7_project += f"\n\n[PROJECT REPOSITORY RULES ({custom_doc})]:\n{doc_content}"
                            break
                    except Exception:
                        pass

        # Inject Episodic Architecture Decision Records into Tier 3 (Anara Standard: Pillar 3)
        # Working memory and recent decision records sit strictly in Tier 3 (Volatile Tail), capped at 1,500 chars
        slot_adr = ""
        try:
            from memory.episodic_adr import episodic_adr_manager
            recent_adrs = episodic_adr_manager.get_recent_project_adrs(limit=4)
            if recent_adrs:
                adr_lines = [
                    f"- [{a['created_at'][:10] if a.get('created_at') else 'ADR'}] {a['architecture_decision']} (Rationale: {a['rationale']})"
                    for a in recent_adrs
                ]
                rendered_adr = "[HISTORICAL ARCHITECTURE DECISIONS (EPISODIC ADR)]:\n" + "\n".join(adr_lines)
                if len(rendered_adr) > 1500:
                    rendered_adr = rendered_adr[:1450] + "\n[... truncated ADR records ...]"
                slot_adr = rendered_adr.strip()
        except Exception:
            pass

        # Tier 2b: Active Channel / Interface Context & Session Metadata (Dual-Identity: Numeric UI ID + Canonical Key)
        ch_clean = (channel or "").strip().lower()
        sess_disp = str(session_id) if session_id is not None else "workspace_session"
        canonical_key = ""
        try:
            if session_id is not None:
                from memory import memory_engine
                s_obj = memory_engine.get_session(session_id)
                if s_obj:
                    canonical_key = s_obj.get("session_key") or ""
                    num_id = s_obj.get("id", session_id)
                    if canonical_key:
                        sess_disp = f"#{num_id} ({canonical_key})"
                    else:
                        sess_disp = f"#{num_id}"
                    if not ch_clean and s_obj.get("channel"):
                        ch_clean = str(s_obj["channel"]).strip().lower()
        except Exception:
            pass

        if not ch_clean:
            ch_clean = "web"

        from providers.accounts import get_active_model_id
        from providers.constants import get_model_grounding_metadata
        current_active_model = model_id or get_active_model_id()
        grounding = get_model_grounding_metadata(current_active_model, reasoning_effort=reasoning_effort)

        model_display_line = (
            f"- Active AI Model ID: {current_active_model}\n"
            f"- Model Display Name: {grounding['clean_name']}\n"
            f"- Serving Infrastructure: {grounding['gateway']}\n"
            f"- Upstream Route / Provider: {grounding['route_name']}\n"
            f"- Reasoning / Thinking Level: {grounding['tier_display']}\n"
        ) if current_active_model else ""

        model_grounding_instruction = (
            f"[ACTIVE MODEL & RUNTIME GROUNDING]:\n"
            f"You are currently powered by {grounding['clean_name']} served via {grounding['serving_origin']}.\n"
            f"Current Thinking / Reasoning Effort is: {grounding['tier_display']}.\n"
            f"When asked about your AI model, active reasoning tier, or whether thinking is ON or OFF in conversation, always answer with 100% precision: state that your model is {grounding['clean_name']} and your reasoning effort is {grounding['tier_display']}.\n"
            f"If Reasoning Level is 'Off', you must accurately state that thinking is disabled / turned off. Never claim to be running on Standard or Medium when thinking is Off.\n"
            f"Never claim to be running directly on Google AI Studio, OpenAI direct, or another vendor default unless specifically configured with direct API keys for that provider.\n\n"
        ) if current_active_model else ""

        slot_channel = (
            f"[ACTIVE RUNTIME & SESSION METADATA]:\n"
            f"- Current Platform / Channel: {ch_clean}\n"
            f"- Current Session: {sess_disp}\n"
            f"- Current User / Speaker: {speaker_name or 'Agnan'}\n"
            f"{model_display_line}"
            f"- Active Workspace Root: {root_path if root_path else os.path.expanduser('~')}\n\n"
            f"{model_grounding_instruction}"
        )
        if ch_clean == "cli":
            slot_channel += (
                "[ACTIVE PLATFORM INTERFACE: TERMINAL / CLI SESSION]\n"
                "You are currently interacting with the user inside an interactive Terminal (CLI) session.\n"
                "Provide direct, concise terminal-friendly responses without raw HTML tags. Persona: gaul santai, kasual, lu-gue."
            )
        elif ch_clean in ("web", "web_studio", "studio", "code", "desktop"):
            slot_channel += (
                "[ACTIVE PLATFORM INTERFACE: WEB & DESKTOP STUDIO]\n"
                "You are currently interacting with the user inside the Web Studio / Desktop GUI interface (Code Studio & 3D Companion).\n"
                "You have access to interactive code editor tabs, diff viewer, and visual timeline cards.\n"
                "Persona: gaul santai, kasual, lu-gue. Be direct and avoid conversational fluff."
            )
        elif ch_clean == "telegram":
            slot_channel += (
                "[ACTIVE PLATFORM INTERFACE: TELEGRAM MESSENGER]\n"
                "You are on Telegram. Standard Markdown auto-converts: **bold**, *italic*, ~~strikethrough~~, ||spoiler||, `code`, ```blocks```, [links](url), ## headers. "
                "Prefer bullets or labeled lines for structured data (avoid wide tables; small tables become Unicode ASCII boxes).\n"
                "You can send files natively: write MEDIA:/absolute/path/to/file in your response. Images (.png, .jpg, .webp) send as photos, videos (.mp4) play inline; image URLs via ![alt](url) send as photos. "
                "Audio: add [[audio_as_voice]] on its own line to send ANY audio file as a native voice bubble note (PTT); without it, .mp3/.m4a arrive as audio files, other formats as documents.\n"
                "CONVERSATION RULES: Be direct — match the length of your reply to the weight of the ask: a one-line question gets a one-line answer, and finished work gets a short report of what changed, what's verified, and what's left, never a replay of the process. "
                "No filler ('Great question', 'I'd be happy to'), no restating the request back, no narrating tool calls the user can see. Plain claims over adjectives. "
                "Persona preference: gaul santai, kasual, lu-gue."
            )
        elif ch_clean == "whatsapp":
            slot_channel += (
                "[ACTIVE PLATFORM INTERFACE: WHATSAPP MESSENGER]\n"
                "You are on WhatsApp. Text format: *bold*, _italic_, ~strikethrough~, monospace ```blocks``` and `code`. "
                "No markdown tables or Markdown headers (# is converted to *bold*). Use bullets (- or •) and *bold labels* for structured information.\n"
                "You can send files natively: write MEDIA:/absolute/path/to/file in your response. "
                "Audio: add [[audio_as_voice]] on its own line to send as a native voice bubble note.\n"
                "CONVERSATION RULES: Be direct and concise — mobile chat screens require compact, high-signal replies. "
                "No filler, no robotic preambles, no restating the user prompt. Persona: gaul santai, kasual, lu-gue."
            )
        elif ch_clean == "discord":
            slot_channel += (
                "[ACTIVE PLATFORM INTERFACE: DISCORD]\n"
                "You are on Discord. Standard Markdown supported: **bold**, *italic*, __underline__, ~~strikethrough~~, ||spoiler||, > quotes, ```code blocks```.\n"
                "You can send files natively: write MEDIA:/absolute/path/to/file in your response.\n"
                "CONVERSATION RULES: Be direct and concise. Avoid robotic filler. Persona: gaul santai, kasual, lu-gue."
            )
        elif ch_clean == "slack":
            slot_channel += (
                "[ACTIVE PLATFORM INTERFACE: SLACK]\n"
                "You are on Slack. Format: *bold*, _italic_, ~strike~, `code`, ```blocks```. Standard mrkdwn rules apply.\n"
                "You can send files natively: write MEDIA:/absolute/path/to/file in your response.\n"
                "CONVERSATION RULES: Be direct, concise, and professional. Persona: gaul santai, kasual, lu-gue."
            )
        elif ch_clean:
            slot_channel += f"[ACTIVE PLATFORM INTERFACE: {ch_clean.upper()}]"

        # Anara 3-Tier Prefix Caching Architecture:
        # Tier 1 — Stable Prefix (Tokens 0..N remain byte-identical across turns): Identity, Mode, Tools
        # Tier 2 — Semi-Static Context: Active Platform Interface, Workspace Snapshot & Rules, Skills Manifest
        # Tier 3 — Volatile Tail: Long-Term Memory, Live Git Worktree Status, Episodic ADR, Working Memory / Scratchpad State
        slots = [slot1_identity, slot2_mode, slot3_tools]
        if slot_channel:
            slots.append(slot_channel)
        if slot7_project:
            slots.append(slot7_project)
        if slot6_skills:
            slots.append(slot6_skills)
        if slot4_memory:
            slots.append(slot4_memory)
        if slot_git_status:
            slots.append(slot_git_status)
        if slot_adr:
            slots.append(slot_adr)
        if slot5_scratchpad:
            slots.append(slot5_scratchpad)

        # Token-aware slot assembly (Anara Standard)
        # Reserves ~6000 tokens for tool catalog + conversation history injected by caller.py
        from core.token_budget import budget_aware_slot_assembly
        return budget_aware_slot_assembly(
            slots=slots,
            model_id=current_active_model,
            reserved_for_conversation=6000,
        )
