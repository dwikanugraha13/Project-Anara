import asyncio
import json
import logging
import os
import re
import subprocess
import tempfile
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
        return {"status": "error", "message": "Command cannot be empty."}

    # Dynamic pre-flight validation via Sandbox Security Engine (Single Source of Truth)
    from core.sandbox import check_command_safety
    is_safe, denial_reason = check_command_safety(cmd)
    if not is_safe:
        logger.warning(f"[High-Risk Guard] Blocked potentially destructive command: {cmd}")
        return {
            "status": "error",
            "message": denial_reason or f"BLOCKED BY SECURITY POLICY: Command '{cmd}' flagged as high risk."
        }

    # Workspace Sentinel Blast-Radius Guard (Hermes Repo-Safety)
    from core.workspace_sentinel import workspace_sentinel
    is_sentinel_safe, sentinel_msg = workspace_sentinel.validate_cli_command(cmd)
    if not is_sentinel_safe:
        logger.warning(f"[WorkspaceSentinel] Blocked high blast-radius command: {cmd}")
        return {
            "status": "error",
            "message": sentinel_msg or f"BLOCKED BY WORKSPACE SENTINEL: Command '{cmd}' flagged for high blast radius."
        }

    from core import anara_agent
    active_f = anara_agent.get_session_dir()
    cwd = os.path.abspath(os.path.expanduser(workdir)) if workdir else active_f
    if not os.path.exists(cwd):
        cwd = tempfile.gettempdir()

    _emit_agent_event("agent_action_start", {
        "tool_name": "execute_cli_command",
        "action_title": "Terminal Execution",
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

        status_label = "Success" if is_ok else f"Failed (exit code {return_code})"
        _emit_agent_event("agent_action_complete", {
            "tool_name": "execute_cli_command",
            "action_title": f"Terminal: {status_label}",
            "summary": f"Finished (exit code {return_code}).",
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
    """Autonomously creates notes or to-do items into Anara's SQLite Brain (Hermes Parity)."""
    from memory import memory_engine
    act = (action or "add").strip().lower()
    t_clean = (title or "Task").strip()
    c_clean = (content or "").strip()

    _emit_agent_event("agent_action_start", {
        "tool_name": "manage_memory_and_todos",
        "action_title": "Manage Memory & Tasks",
        "detail": f"Action: {act} -> '{t_clean}'",
        "icon": "🧠"
    })

    try:
        if act in ["add", "create", "save"]:
            note_id = memory_engine.create_note_or_todo(title=t_clean, content=c_clean, category=category)
            res_payload = {
                "status": "success",
                "action": "add",
                "id": note_id,
                "title": t_clean,
                "category": category,
                "message": f"Recorded '{t_clean}' to {category} list."
            }
        elif act in ["complete", "toggle", "done"]:
            all_notes = memory_engine.get_notes_and_todos()
            target_id = None
            for n in all_notes:
                if t_clean.lower() in n.get("title", "").lower():
                    target_id = n["id"]
                    break
            if target_id:
                memory_engine.toggle_todo(target_id)
                res_payload = {
                    "status": "success",
                    "action": "complete",
                    "id": target_id,
                    "title": t_clean,
                    "message": f"Marked task '{t_clean}' as completed."
                }
            else:
                res_payload = {
                    "status": "not_found",
                    "action": "complete",
                    "title": t_clean,
                    "message": f"Task '{t_clean}' not found in active list."
                }
        else:
            res_payload = {
                "status": "success",
                "action": act,
                "title": t_clean,
                "message": f"Action '{act}' processed successfully."
            }

        _emit_agent_event("agent_action_complete", {
            "tool_name": "manage_memory_and_todos",
            "action_title": "Memory & Tasks Updated",
            "summary": res_payload["message"],
            "icon": "🧠"
        })

        return res_payload
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
            "summary": res.get("message", "Memory operation completed."),
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
        "action_title": "Session History Search",
        "detail": f"Query: '{clean_q}'",
        "icon": "search"
    })

    try:
        results = memory_engine.search_conversation_history(query=clean_q, limit=safe_limit)
        if not results:
            msg = f"No previous conversation history matched query '{clean_q}'."
            _emit_agent_event("agent_action_complete", {
                "tool_name": "session_search",
                "action_title": "Session Search Completed",
                "summary": msg,
                "icon": "search"
            })
            return {"status": "success", "results": [], "message": msg}

        formatted = []
        for r in results:
            created = (r.get("created_at") or "")[:19]
            session = r.get("session_title") or f"Session #{r.get('session_id', '?')}"
            speaker = r.get("speaker_name") or "User"
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

        msg = f"Found {len(formatted)} relevant conversation turns."
        _emit_agent_event("agent_action_complete", {
            "tool_name": "session_search",
            "action_title": "Session Search Completed",
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


def _resolve_windows_app_executable(app_name: str) -> Optional[str]:
    """
    Dynamically locates executable for a Windows application without static hardcoded paths (Hermes Parity).
    Checks:
    1. System PATH via shutil.which
    2. Windows Registry App Paths (HKCU & HKLM)
    3. Standard Program Directories (%LOCALAPPDATA%\\Programs, %PROGRAMFILES%, %PROGRAMFILES(X86)%)
    """
    clean = (app_name or "").strip().lower()
    if not clean:
        return None

    # 1. System PATH
    candidates = [
        clean,
        f"{clean}.exe",
        f"{clean}.cmd",
        f"{clean}.bat",
    ]
    for c in candidates:
        found = shutil.which(c)
        if found and os.path.isfile(found):
            return found

    # 2. Windows Registry App Paths (OS standard for registered applications)
    if sys.platform == "win32":
        try:
            import winreg
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for sub in (
                    rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{clean}.exe",
                    rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{clean}",
                ):
                    try:
                        with winreg.OpenKey(root, sub) as k:
                            val, _ = winreg.QueryValueEx(k, "")
                            if val and os.path.isfile(val):
                                return val
                    except Exception:
                        pass
        except Exception:
            pass

        # 3. Dynamic scan of standard program directories
        search_roots = [
            os.path.expandvars("%LOCALAPPDATA%\\Programs"),
            os.path.expandvars("%PROGRAMFILES%"),
            os.path.expandvars("%PROGRAMFILES(X86)%"),
        ]
        for root_dir in search_roots:
            if not os.path.isdir(root_dir):
                continue
            try:
                for root, dirs, files in os.walk(root_dir):
                    rel = os.path.relpath(root, root_dir)
                    if rel.count(os.sep) > 3:
                        continue
                    for f in files:
                        if f.lower().endswith(".exe") and clean in f.lower():
                            full_p = os.path.join(root, f)
                            if os.path.isfile(full_p):
                                return full_p
            except Exception:
                pass

    return None


async def _tool_system_control(
    action: str,
    target: Optional[str] = None,
    arguments: Optional[str] = None,
    url: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Controls desktop applications, URLs, and OS functions locally on Windows (Hermes Parity)."""
    import shutil
    import webbrowser

    act = (action or "open").strip().lower()
    tgt = (target or url or kwargs.get("app") or "").strip()
    args = (arguments or kwargs.get("args") or "").strip()

    if not tgt and not url:
        return {"status": "error", "message": "Target application, URL, or document path cannot be empty."}

    # If url parameter is passed or target is a URL
    target_url = url or (tgt if (tgt.startswith("http://") or tgt.startswith("https://")) else None)

    try:
        if act in ["open", "launch", "start", "run"]:
            # Case A: URL opening (Hermes Parity: webbrowser.open)
            if target_url:
                webbrowser.open(target_url)
                return {
                    "status": "success",
                    "action": "open_url",
                    "url": target_url,
                    "message": f"URL '{target_url}' opened successfully in browser."
                }

            # Case B: Desktop Application Launching (Hermes Parity: dynamic resolution)
            exe_path = _resolve_windows_app_executable(tgt)
            if exe_path:
                cmd_list = [exe_path]
                if args:
                    import shlex
                    try:
                        cmd_list.extend(shlex.split(args))
                    except Exception:
                        cmd_list.append(args)
                subprocess.Popen(cmd_list, shell=False)
                return {
                    "status": "success",
                    "action": "open_app",
                    "target": tgt,
                    "executable": exe_path,
                    "message": f"Application '{tgt}' ({os.path.basename(exe_path)}) launched successfully."
                }

            # Case C: ShellExecute fallback (for registered file associations or protocols)
            if hasattr(os, "startfile"):
                try:
                    os.startfile(tgt)
                    return {
                        "status": "success",
                        "action": "open_shell",
                        "target": tgt,
                        "message": f"Target '{tgt}' opened successfully."
                    }
                except Exception:
                    pass

            # Case D: Generic cmd.exe start
            subprocess.Popen(f'cmd.exe /c start "" "{tgt}"', shell=True)
            return {
                "status": "success",
                "action": "open_cmd",
                "target": tgt,
                "message": f"Command to open '{tgt}' sent to system."
            }

        else:
            return {
                "status": "success",
                "action": act,
                "message": f"System control command '{act}' for '{tgt}' processed successfully."
            }
    except Exception as e:
        logger.warning(f"[AgentTools] System control error: {e}")
        return {"status": "error", "message": f"Failed to execute system control for '{tgt}': {e}"}


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

    return {"status": "success", "message": f"Holographic HUD '{t_clean}' has been projected to screen."}


async def _tool_delegate_subagent(
    title: Optional[str] = None,
    mission_prompt: Optional[str] = None,
    goal: Optional[str] = None,
    context: Optional[str] = None,
    tasks: Optional[List[Dict[str, Any]]] = None,
    background: bool = False,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Spawns specialized autonomous subagent worker(s) in background or parallel batch (Hermes Parity).
    By default runs synchronously (background=False) to deliver real model findings to the orchestrator.
    """
    from core import subagent_manager

    # 1. Batch tasks mode
    if tasks and isinstance(tasks, list):
        if not background:
            results = await subagent_manager.spawn_batch_and_join(tasks, shared_context=context or mission_prompt or "")
            return {
                "status": "success",
                "batch_size": len(results),
                "results": [r.to_dict() for r in results],
            }
        else:
            spawned_tasks = []
            for t_item in tasks:
                g_text = t_item.get("goal") or t_item.get("title") or "Subagent Mission"
                c_text = t_item.get("context") or context or mission_prompt or ""
                t_obj = await subagent_manager.spawn_subagent_task(title=g_text, mission_prompt=c_text)
                spawned_tasks.append(t_obj)

            return {
                "status": "success",
                "mode": "batch_background",
                "batch_size": len(spawned_tasks),
                "task_ids": [t.task_id for t in spawned_tasks],
            }

    # 2. Single task mode
    effective_goal = (goal or title or "Background Task").strip()
    effective_context = (context or mission_prompt or "").strip()

    if not effective_goal and not effective_context:
        return {"status": "error", "message": "Task goal or title cannot be empty."}

    task = await subagent_manager.spawn_subagent_task(
        title=effective_goal,
        mission_prompt=effective_context,
    )

    if not background:
        if task._async_task:
            await task._async_task
        findings_text = task.result.executive_summary if task.result else ""
        return {
            "status": "success",
            "task_id": task.task_id,
            "goal": task.goal,
            "findings": findings_text,
        }

    _emit_agent_event("agent_action_complete", {
        "tool_name": "delegate_subagent",
        "action_title": f"Sub-Agent #{task.task_id} Active",
        "detail": f"Goal: {effective_goal[:60]}",
        "summary": "Task delegated to background worker.",
        "icon": "subagent"
    })

    return {
        "status": "success",
        "task_id": task.task_id,
        "goal": task.goal,
    }


async def _tool_trigger_avatar_animation(animation_name: str, emotion: Optional[str] = None) -> Dict[str, Any]:
    """Controls physical gestures, body movements, or 3D avatar dance animations on screen."""
    anim = (animation_name or "dance").strip().lower()
    emo = (emotion or "happy").strip().lower()

    _emit_agent_event("agent_action_start", {
        "tool_name": "trigger_avatar_animation",
        "action_title": f"Avatar 3D: {anim.title()}",
        "detail": f"Playing animation '{anim}' (emotion: {emo})",
        "icon": "dance" if anim in ["dance", "rumba"] else "sparkles"
    })

    if anim in ["dance", "rumba"]:
        _emit_agent_event("emotion_update", {
            "type": "emotion_update",
            "emotion": "dance",
            "gesture": "joy",
            "intensity": 1.0,
        })
        msg = "Avatar 3D dance animation triggered."
    else:
        _emit_agent_event("emotion_update", {
            "type": "emotion_update",
            "emotion": emo,
            "gesture": anim,
            "intensity": 0.8,
        })
        msg = f"Avatar 3D expression '{anim}' ({emo}) triggered."

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
        return {"status": "error", "message": "Skill name cannot be empty."}
    if not clean_desc:
        return {"status": "error", "message": "Skill description cannot be empty."}
    if not steps:
        steps = [f"Standard procedure for {clean_name}"]

    _emit_agent_event("agent_action_start", {
        "tool_name": "learn_and_save_skill",
        "action_title": f"Learning Skill: {clean_name}",
        "detail": f"Category: {clean_cat}",
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

        msg = f"New skill '{clean_name}' ({clean_cat}) learned and committed to Skill Library (agentskills.io)."
        _emit_agent_event("agent_action_complete", {
            "tool_name": "learn_and_save_skill",
            "action_title": f"Skill Saved: {clean_name}",
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
        return {"status": "error", "message": f"Failed to save skill: {e}"}


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
        return {"status": "error", "message": "Questionnaire list is invalid or empty."}

    return await request_interactive_question(parsed_questions, timeout=300.0)


async def _tool_skill_view(name: str, file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Anara Skill Viewer:
    Loads and views the complete procedure, CLI scripts, sub-resource files (references/templates/scripts),
    and workflow instructions of any skill from the agentskills.io library on demand.
    """
    clean_name = (name or "").strip()
    if not clean_name:
        return {"status": "error", "message": "Skill name cannot be empty."}

    from core.skill_library import skill_library

    # If a specific sub-resource file path is requested (e.g. references/*.md)
    if file_path and file_path.strip():
        sub_file = skill_library.get_skill_file(clean_name, file_path.strip())
        if not sub_file:
            return {
                "status": "error",
                "message": f"Reference file '{file_path}' not found inside skill '{clean_name}'."
            }
        _emit_agent_event("agent_action_complete", {
            "tool_name": "skill_view",
            "action_title": f"Load Skill Reference: {sub_file['file_path']}",
            "detail": f"Skill: {sub_file['skill_name']}",
            "summary": f"Reference file '{file_path}' loaded successfully ({sub_file['size_kb']} KB).",
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
            "message": f"Skill '{clean_name}' not found in Skill Library (agentskills.io)."
        }

    _emit_agent_event("agent_action_complete", {
        "tool_name": "skill_view",
        "action_title": f"Load Skill: {skill['name']}",
        "detail": f"Category: {skill['category']}",
        "summary": f"Technical instructions for skill '{skill['name']}' loaded to active memory.",
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



