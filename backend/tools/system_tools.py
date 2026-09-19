import asyncio
import json
import logging
import os
import re
import subprocess
from typing import Any, Dict, Optional

from .events import _emit_agent_event

logger = logging.getLogger(__name__)


async def _tool_execute_cli_command(command: str, workdir: Optional[str] = None) -> Dict[str, Any]:
    """
    Safely executes terminal commands in workspace with extended 120s timeout
    for building, testing, linting, and running scripts.
    """
    cmd = (command or "").strip()
    if not cmd:
        return {"status": "error", "message": "Perintah terminal kosong"}

    # Dynamic pre-flight validation via Sandbox Security Engine (Single Source of Truth)
    from core.sandbox import check_command_safety
    is_safe, denial_reason = check_command_safety(cmd)
    if not is_safe:
        logger.warning(f"[High-Risk Guard] Blocked potentially destructive command: {cmd}")
        return {
            "status": "error",
            "message": denial_reason or f"DITOLAK SISTEM KEAMANAN ANARA: Perintah '{cmd}' terdeteksi berisiko tinggi."
        }

    # Windows 11 Compatibility: auto-translate deprecated WMIC syntax to modern PowerShell CIM cmdlets
    if os.name == "nt":
        if re.search(r"wmic\s+path\s+win32_battery", cmd, re.IGNORECASE):
            cmd = "Get-CimInstance Win32_Battery | Select-Object EstimatedChargeRemaining, BatteryStatus"
        elif re.search(r"wmic\s+(?:os|path\s+win32_operatingsystem)", cmd, re.IGNORECASE):
            cmd = "Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, OSArchitecture"
        elif re.search(r"wmic\s+(?:cpu|path\s+win32_processor)", cmd, re.IGNORECASE):
            cmd = "Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, MaxClockSpeed"

    from core import anara_agent
    active_f = anara_agent.get_session_dir()
    cwd = os.path.abspath(os.path.expanduser(workdir)) if workdir else active_f
    if not os.path.exists(cwd):
        cwd = tempfile.gettempdir()

    _emit_agent_event("agent_action_start", {
        "tool_name": "execute_cli_command",
        "action_title": "Eksekusi Terminal",
        "detail": f"CMD: {cmd[:50]}",
        "icon": "terminal"
    })

    try:
        from core.sandbox import command_sandbox
        sandbox_res = await command_sandbox.execute(
            command=cmd,
            cwd=cwd,
            timeout_seconds=120.0
        )

        combined = sandbox_res.get("output", "").strip()
        return_code = sandbox_res.get("exit_code", 0)
        is_ok = sandbox_res.get("status") == "success"

        status_label = "Berhasil" if is_ok else f"Gagal (Code {return_code})"
        _emit_agent_event("agent_action_complete", {
            "tool_name": "execute_cli_command",
            "action_title": f"Terminal: {status_label}",
            "summary": f"Selesai (exit code {return_code}).",
            "raw_result": combined[:800],
            "icon": "terminal"
        })

        from tools.output_manager import compact_tool_output
        return {
            "status": "success" if is_ok else "error",
            "return_code": return_code,
            "working_directory": cwd,
            "sandboxed": True,
            "output": compact_tool_output(combined, max_lines=60, max_chars=4000, source_label="cli_output")
        }
    except Exception as e:
        logger.warning(f"[AgentTools] CLI exec error: {e}")
        return {"status": "error", "message": str(e)}


async def _tool_manage_memory_and_todos(action: str, title: str, content: Optional[str] = None, category: str = "todo") -> Dict[str, Any]:
    """Autonomously creates notes or to-do items into Anara's SQLite Brain."""
    from memory import memory_engine
    act = (action or "add").strip().lower()
    t_clean = (title or "Tugas Baru").strip()
    c_clean = (content or "").strip()

    _emit_agent_event("agent_action_start", {
        "tool_name": "manage_memory_and_todos",
        "action_title": "Memperbarui Memori & Tugas",
        "detail": f"Aksi: {act} -> '{t_clean}'",
        "icon": "🧠"
    })

    try:
        if act in ["add", "create", "catat", "tambah"]:
            note_id = memory_engine.create_note_or_todo(title=t_clean, content=c_clean, category=category)
            res_msg = f"Berhasil mencatat '{t_clean}' ke dalam daftar tugas/catatan Anara."
        elif act in ["complete", "selesai"]:
            all_notes = memory_engine.get_notes_and_todos()
            target_id = None
            for n in all_notes:
                if t_clean.lower() in n.get("title", "").lower():
                    target_id = n["id"]
                    break
            if target_id:
                memory_engine.toggle_todo(target_id)
                res_msg = f"Tugas '{t_clean}' berhasil ditandai selesai."
            else:
                res_msg = f"Tugas '{t_clean}' tidak ditemukan."
        else:
            res_msg = f"Aksi '{act}' selesai diproses."

        _emit_agent_event("agent_action_complete", {
            "tool_name": "manage_memory_and_todos",
            "action_title": "Memori Tersimpan",
            "summary": res_msg,
            "icon": "🧠"
        })

        return {"status": "success", "message": res_msg}
    except Exception as e:
        logger.warning(f"[AgentTools] Memory task error: {e}")
        return {"status": "error", "message": str(e)}


async def _tool_anara_memory(
    action: str,
    target: str = "memory",
    content: Optional[str] = None,
    old_text: Optional[str] = None
) -> Dict[str, Any]:
    """Universal Anara Persistent Memory Tool for MEMORY.md and USER.md."""
    from memory.file_memory import file_memory
    act = (action or "add").strip().lower()
    tgt = (target or "memory").strip().lower()

    _emit_agent_event("agent_action_start", {
        "tool_name": "memory",
        "action_title": f"Anara Memory ({act})",
        "detail": f"Target: {tgt} | {('Substr: ' + old_text) if old_text else ('Content: ' + (content[:50] if content else ''))}",
        "icon": "🧠"
    })

    try:
        res = file_memory.execute_memory_action(
            action=act,
            target=tgt,
            content=content,
            old_text=old_text
        )
        _emit_agent_event("agent_action_complete", {
            "tool_name": "memory",
            "action_title": f"Anara Memory {res.get('status', 'complete').title()}",
            "summary": res.get("message", "Operasi memori selesai."),
            "icon": "🧠"
        })
        return res
    except Exception as e:
        logger.warning(f"[AgentTools] Anara memory tool error: {e}")
        return {"status": "error", "message": str(e)}


async def _tool_session_search(query: str, limit: int = 5) -> Dict[str, Any]:
    """Anara Long-Term Conversation History & Session Recall."""
    from memory import memory_engine
    clean_q = (query or "").strip()
    safe_limit = max(1, min(limit or 5, 20))

    _emit_agent_event("agent_action_start", {
        "tool_name": "session_search",
        "action_title": "Mencari Riwayat Sesi Obrolan",
        "detail": f"Query: '{clean_q}'",
        "icon": "search"
    })

    try:
        results = memory_engine.search_conversation_history(query=clean_q, limit=safe_limit)
        if not results:
            msg = f"Tidak ditemukan percakapan terdahulu yang cocok dengan kata kunci '{clean_q}'."
            _emit_agent_event("agent_action_complete", {
                "tool_name": "session_search",
                "action_title": "Pencarian Riwayat Selesai",
                "summary": msg,
                "icon": "search"
            })
            return {"status": "success", "results": [], "message": msg}

        formatted = []
        for r in results:
            created = (r.get("created_at") or "")[:19]
            session = r.get("session_title") or f"Sesi #{r.get('session_id', '?')}"
            speaker = r.get("speaker_name") or "Pengguna"
            u_text = (r.get("user_text") or "").strip()
            a_text = (r.get("ai_text") or "").strip()
            if len(a_text) > 300:
                a_text = a_text[:300] + "..."
            formatted.append({
                "timestamp": created,
                "session": session,
                "speaker": speaker,
                "user_text": u_text,
                "ai_text": a_text
            })

        msg = f"Ditemukan {len(formatted)} riwayat percakapan yang relevan."
        _emit_agent_event("agent_action_complete", {
            "tool_name": "session_search",
            "action_title": "Pencarian Riwayat Berhasil",
            "summary": msg,
            "icon": "search"
        })
        return {
            "status": "success",
            "results": formatted,
            "message": msg
        }
    except Exception as e:
        logger.warning(f"[AgentTools] session_search error: {e}")
        return {"status": "error", "message": str(e)}


async def _tool_system_control(action: str, target: Optional[str] = None) -> Dict[str, Any]:
    """Controls desktop applications and OS functions locally on Windows."""
    act = (action or "open").strip().lower()
    tgt = (target or "").strip().lower()

    user_appdata = os.environ.get("APPDATA", "")
    spotify_exe = os.path.join(user_appdata, "Spotify", "Spotify.exe")
    spotify_cmd = f'"{spotify_exe}"' if os.path.exists(spotify_exe) else "cmd.exe /c start spotify:"

    known_apps = {
        "spotify": spotify_cmd, "musik": spotify_cmd, "music": spotify_cmd,
        "notepad": "notepad.exe", "catatan": "notepad.exe",
        "calculator": "calc.exe", "kalkulator": "calc.exe",
        "chrome": "cmd.exe /c start chrome",
        "edge": "cmd.exe /c start msedge",
        "browser": "cmd.exe /c start https://google.com",
        "explorer": "explorer.exe", "folder": "explorer.exe",
        "terminal": "cmd.exe /c start powershell",
        "powershell": "cmd.exe /c start powershell",
        "cmd": "cmd.exe /c start cmd",
        "vs code": "cmd.exe /c code", "vscode": "cmd.exe /c code", "code": "cmd.exe /c code",
        "telegram": "cmd.exe /c start tg:",
        "whatsapp": "cmd.exe /c start whatsapp:",
    }

    try:
        if act in ["open", "buka", "launch", "jalankan", "start", "putar", "setel"]:
            app_cmd = None
            for key, cmd in known_apps.items():
                if key in tgt:
                    app_cmd = cmd
                    break
            if not app_cmd and tgt:
                app_cmd = f"cmd.exe /c start {tgt}"

            if app_cmd:
                subprocess.Popen(app_cmd, shell=True)
                result_msg = f"Berhasil membuka aplikasi '{tgt.title() or app_cmd}' di laptop."
            else:
                result_msg = f"Aplikasi '{tgt}' tidak dikenali dalam daftar aman."
        else:
            result_msg = f"Perintah sistem '{act}' dieksekusi."
    except Exception as e:
        logger.warning(f"[AgentTools] System control error: {e}")
        result_msg = f"Gagal mengeksekusi perintah sistem: {e}"

    return {"status": "success", "result": result_msg}


async def _tool_project_hud(visual_type: str, title: str, summary: str, specs_json: Optional[str] = None) -> Dict[str, Any]:
    """Directly projects a holographic HUD card onto the user's screen from Anara's brain."""
    v_type = (visual_type or "knowledge_card").strip().lower()
    t_clean = (title or "Informasi Anara").strip()
    s_clean = (summary or "").strip()

    specs = []
    if specs_json:
        try:
            specs = json.loads(specs_json)
            if isinstance(specs, dict):
                specs = [{"label": k, "value": str(v)} for k, v in specs.items()]
        except Exception:
            pass

    _emit_agent_event("agent_hud_project", {
        "visual_type": v_type,
        "title": t_clean,
        "summary": s_clean,
        "specs": specs,
        "badge": "Anara Agent Proactive"
    })

    return {"status": "success", "message": f"Holographic HUD '{t_clean}' telah diproyeksikan ke layar."}


async def _tool_delegate_subagent(title: str, mission_prompt: str) -> Dict[str, Any]:
    """
    Spawns a specialized autonomous subagent worker in background to handle heavy tasks
    (multi-file analysis, deep web scraping, batch document auditing) without blocking.
    """
    t_clean = (title or "Tugas Latar Belakang").strip()
    m_clean = (mission_prompt or "").strip()
    if not m_clean:
        return {"status": "error", "message": "mission_prompt tidak boleh kosong"}

    from core import subagent_manager
    task = await subagent_manager.spawn_subagent_task(title=t_clean, mission_prompt=m_clean)

    _emit_agent_event("agent_action_complete", {
        "tool_name": "delegate_subagent",
        "action_title": f"Sub-Agent #{task.task_id} Aktif",
        "detail": f"Misi: {t_clean}",
        "summary": "Tugas berhasil didelegasikan ke pekerja latar belakang.",
        "icon": "subagent"
    })

    return {
        "status": "success",
        "task_id": task.task_id,
        "title": t_clean,
        "message": f"Subagent #{task.task_id} ('{t_clean}') telah berhasil diaktifkan di latar belakang."
    }


async def _tool_trigger_avatar_animation(animation_name: str, emotion: Optional[str] = None) -> Dict[str, Any]:
    """Mengendalikan gerakan fisik, gestur tubuh, atau tarian avatar 3D Anara di layar."""
    anim = (animation_name or "dance").strip().lower()
    emo = (emotion or "happy").strip().lower()

    _emit_agent_event("agent_action_start", {
        "tool_name": "trigger_avatar_animation",
        "action_title": f"Avatar 3D: {anim.title()}",
        "detail": f"Memainkan animasi '{anim}' (emosi: {emo})",
        "icon": "dance" if anim in ["dance", "rumba", "joget", "dansa"] else "sparkles"
    })

    if anim in ["dance", "rumba", "joget", "dansa"]:
        _emit_agent_event("emotion_update", {
            "type": "emotion_update",
            "emotion": "dance",
            "gesture": "joy",
            "intensity": 1.0,
        })
        msg = "Avatar 3D Anara mulai menari dengan irama musik Latin Rumba."
    else:
        _emit_agent_event("emotion_update", {
            "type": "emotion_update",
            "emotion": emo,
            "gesture": anim,
            "intensity": 0.8,
        })
        msg = f"Avatar 3D Anara menampilkan ekspresi '{anim}' ({emo})."

    _emit_agent_event("agent_action_complete", {
        "tool_name": "trigger_avatar_animation",
        "action_title": f"Avatar 3D: {anim.title()}",
        "detail": msg,
        "summary": msg,
        "icon": "sparkles"
    })

    return {
        "status": "success",
        "animation": anim,
        "emotion": emo,
        "message": msg
    }


async def _tool_learn_and_save_skill(
    name: str,
    category: str,
    description: str,
    trigger_keywords: Optional[List[str]] = None,
    procedure_steps: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Autonomous Anara Skill Engine:
    Learns and permanently saves a new capability, architectural workflow, framework recipe,
    or operational procedure into Anara's SQLite database (agent_skills table) for perpetual future reuse.
    """
    from memory import memory_engine

    clean_name = (name or "").strip()
    clean_cat = (category or "general").strip().lower()
    clean_desc = (description or "").strip()
    triggers = [str(k).strip().lower() for k in (trigger_keywords or []) if str(k).strip()]
    steps = [str(s).strip() for s in (procedure_steps or []) if str(s).strip()]

    if not clean_name:
        return {"status": "error", "message": "Nama skill tidak boleh kosong."}
    if not clean_desc:
        return {"status": "error", "message": "Deskripsi skill tidak boleh kosong."}
    if not steps:
        steps = [f"Prosedur standar untuk {clean_name}"]

    _emit_agent_event("agent_action_start", {
        "tool_name": "learn_and_save_skill",
        "action_title": f"Mempelajari Skill: {clean_name}",
        "detail": f"Kategori: {clean_cat}",
        "icon": "brain"
    })

    try:
        from core.skill_library import skill_library
        res = skill_library.save_skill(
            name=clean_name,
            category=clean_cat,
            description=clean_desc,
            trigger_keywords=triggers,
            procedure_steps=steps,
            status="active",
            learned=True,
        )

        msg = f"Keahlian baru '{clean_name}' ({clean_cat}) berhasil dipelajari dan disimpan ke Skill Library (agentskills.io) Anara."
        _emit_agent_event("agent_action_complete", {
            "tool_name": "learn_and_save_skill",
            "action_title": f"Skill Tersimpan: {clean_name}",
            "detail": clean_desc,
            "summary": msg,
            "icon": "brain"
        })

        return {
            "status": "success",
            "skill": res,
            "message": msg
        }
    except Exception as e:
        logger.warning(f"[AgentTools] learn_and_save_skill error: {e}")
        return {"status": "error", "message": f"Gagal menyimpan skill: {e}"}


async def _tool_interactive_question(questions: Any) -> Dict[str, Any]:
    """
    Prompts the user with an interactive multi-step questionnaire card (Wizard)
    to gather clarification on ambiguous project concepts or architectural choices.
    """
    from .events import request_interactive_question

    parsed_questions = []
    if isinstance(questions, list):
        parsed_questions = questions
    elif isinstance(questions, dict):
        parsed_questions = questions.get("questions") or [questions]

    if not parsed_questions:
        return {"status": "error", "message": "Daftar pertanyaan kuesioner tidak valid atau kosong."}

    return await request_interactive_question(parsed_questions, timeout=300.0)


async def _tool_skill_view(name: str, file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Anara Skill Viewer:
    Loads and views the complete procedure, CLI scripts, sub-resource files (references/templates/scripts),
    and workflow instructions of any skill from the agentskills.io library on demand.
    """
    clean_name = (name or "").strip()
    if not clean_name:
        return {"status": "error", "message": "Nama skill tidak boleh kosong."}

    from core.skill_library import skill_library

    # If a specific sub-resource file path is requested (e.g. references/*.md)
    if file_path and file_path.strip():
        sub_file = skill_library.get_skill_file(clean_name, file_path.strip())
        if not sub_file:
            return {
                "status": "error",
                "message": f"Berkas referensi '{file_path}' tidak ditemukan di dalam skill '{clean_name}'."
            }
        _emit_agent_event("agent_action_complete", {
            "tool_name": "skill_view",
            "action_title": f"Memuat Referensi Skill: {sub_file['file_path']}",
            "detail": f"Skill: {sub_file['skill_name']}",
            "summary": f"Berkas referensi '{file_path}' berhasil dimuat ({sub_file['size_kb']} KB).",
            "icon": "book-open"
        })
        return {
            "status": "success",
            "skill_name": sub_file["skill_name"],
            "file_path": sub_file["file_path"],
            "size_kb": sub_file["size_kb"],
            "content": sub_file["content"],
        }

    skill = skill_library.get_skill(clean_name)
    if not skill:
        return {
            "status": "error",
            "message": f"Skill '{clean_name}' tidak ditemukan di perpustakaan skill (agentskills.io)."
        }

    _emit_agent_event("agent_action_complete", {
        "tool_name": "skill_view",
        "action_title": f"Memuat Keahlian: {skill['name']}",
        "detail": f"Kategori: {skill['category']}",
        "summary": f"Petunjuk teknis dan prosedur skill '{skill['name']}' berhasil dimuat ke memori aktif.",
        "icon": "book-open"
    })

    return {
        "status": "success",
        "name": skill["name"],
        "category": skill["category"],
        "description": skill["description"],
        "instructions": skill["body"],
        "file_path": skill["file_path"],
    }



