"""
anara_agent.py

Anara Autonomous Agent Engine (Hermes-Style ReAct Loop & Workspace Management).
Provides:
1. ReAct Autonomous Execution Loop (Thought -> Plan -> Action -> Observation -> Final Answer)
2. Workspace File & Folder Explorer (Parsing, PDF text extraction, Code preview)
3. Multi-Step Tool Chaining across OpenRouter Hermes 3, Claude 3.7, Groq, and Gemini
"""

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional
import httpx
from tools import dispatch_tool_call, _emit_agent_event

logger = logging.getLogger(__name__)

# Use system temp directory for uploaded files so project directory stays 100% clean
WORKSPACE_DIR = os.path.join(tempfile.gettempdir(), "anara_agent_workspace")
os.makedirs(WORKSPACE_DIR, exist_ok=True)


class AnaraAgent:
    """
    Autonomous ReAct Agent Engine for Anara.
    Manages session-isolated project workspaces and directory exploration.
    """

    def __init__(self):
        self.base_workspace_path = WORKSPACE_DIR
        self._session_custom_names: Dict[int, str] = {}
        self._session_active_paths: Dict[int, str] = {}
        self._active_session_id: Optional[int] = None

    def set_active_session_id(self, session_id: Optional[int]):
        """Sets the globally active session ID for the agent."""
        self._active_session_id = session_id

    def get_active_session_id(self) -> Optional[int]:
        """Returns the currently active session ID."""
        return self._active_session_id

    def has_active_custom_workspace(self, session_id: Optional[int] = None) -> bool:
        """Returns True if the session has an explicitly attached user project folder (Anara Code mode)."""
        effective_sid = session_id if session_id is not None else self._active_session_id
        if effective_sid is not None:
            if effective_sid in self._session_active_paths and os.path.isdir(self._session_active_paths[effective_sid]):
                return True
            try:
                from memory import memory_engine
                sess = memory_engine.get_session(effective_sid)
                if sess and sess.get("workspace_info"):
                    stored_path = sess["workspace_info"].get("root_path")
                    if stored_path and sess["workspace_info"].get("is_external") and os.path.isdir(stored_path):
                        return True
            except Exception:
                pass
        return False

    def get_session_dir(self, session_id: Optional[int] = None) -> str:
        """Returns the active external folder, or isolated temporary directory, strictly for a session."""
        effective_sid = session_id if session_id is not None else self._active_session_id

        if effective_sid is not None:
            # 1. Check in-memory active path
            active_path = self._session_active_paths.get(effective_sid)
            if active_path and os.path.isdir(active_path):
                return active_path

            # 2. Check SQLite workspace_info if not loaded in memory yet
            try:
                from memory import memory_engine
                sess = memory_engine.get_session(effective_sid)
                if sess and sess.get("workspace_info"):
                    stored_path = sess["workspace_info"].get("root_path")
                    if stored_path and sess["workspace_info"].get("is_external") and os.path.isdir(stored_path):
                        self._session_active_paths[effective_sid] = stored_path
                        name = sess["workspace_info"].get("name")
                        if name:
                            self._session_custom_names[effective_sid] = name
                        return stored_path
            except Exception:
                pass

            # 3. Dedicated clean session workspace folder
            s_dir = os.path.join(self.base_workspace_path, f"session_{effective_sid}")
            os.makedirs(s_dir, exist_ok=True)
            return s_dir

        active_path = self._session_active_paths.get(0)
        if active_path and os.path.isdir(active_path):
            return active_path

        s_dir = os.path.join(self.base_workspace_path, "default")
        os.makedirs(s_dir, exist_ok=True)
        return s_dir

    def attach_local_folder(self, folder_path: str, session_id: Optional[int] = None) -> Dict[str, Any]:
        """Binds an existing user-selected local folder to a session without copying it."""
        clean_path = os.path.abspath(os.path.expanduser(folder_path.strip().strip('"\'')))
        if not os.path.isdir(clean_path):
            raise ValueError(f"Folder '{clean_path}' tidak ditemukan.")

        effective_sid = session_id if session_id is not None else self._active_session_id
        folder_name = os.path.basename(clean_path.rstrip("\\/")) or "Project Workspace"

        if effective_sid is not None:
            self._session_active_paths[effective_sid] = clean_path
            self.set_custom_folder_name(folder_name, session_id=effective_sid)
            from memory import memory_engine
            memory_engine.set_session_workspace_info(effective_sid, {
                "name": folder_name,
                "root_path": clean_path,
                "is_external": True,
            })
        else:
            self._session_active_paths[0] = clean_path
            self.set_custom_folder_name(folder_name, session_id=0)

        tree = self.get_workspace_tree(session_id=effective_sid)
        _emit_agent_event("workspace_folder_imported", {
            "session_id": effective_sid,
            "folder_name": folder_name,
            "folder_path": clean_path,
            "total_files": tree["total_files"],
            "tree": tree,
        })
        logger.info(f"[AnaraAgent] Attached local workspace '{clean_path}' to session #{effective_sid}")
        return tree

    def set_custom_folder_name(self, name: Optional[str], session_id: Optional[int] = None):
        """Sets the friendly display name for the imported project folder in a session."""
        effective_sid = session_id if session_id is not None else (self._active_session_id or 0)
        if name:
            self._session_custom_names[effective_sid] = name.strip()
        else:
            self._session_custom_names.pop(effective_sid, None)

    def init_empty_workspace(self, folder_name: str, session_id: Optional[int] = None) -> Dict[str, Any]:
        """Initializes a new empty project folder workspace for building projects from scratch."""
        clean_name = folder_name.strip() or "New Project"
        self.set_custom_folder_name(clean_name, session_id=session_id)
        target_dir = self.get_session_dir(session_id)
        os.makedirs(target_dir, exist_ok=True)
        
        # Persist to database if session_id is provided
        if session_id is not None:
            try:
                from memory import memory_engine
                memory_engine.set_session_workspace_info(session_id, {
                    "name": clean_name,
                    "total_files": 0,
                    "root_path": target_dir
                })
            except Exception as e:
                logger.warning(f"[Workspace] Failed to persist empty workspace for session #{session_id}: {e}")

        tree = self.get_workspace_tree(session_id=session_id)
        _emit_agent_event("workspace_folder_imported", {
            "session_id": session_id,
            "folder_name": clean_name,
            "total_files": 0,
            "tree": tree
        })
        self.ensure_git_repo(session_id=session_id)
        logger.info(f"[AnaraAgent] Initialized empty project workspace '{clean_name}' for session #{session_id}")
        return tree

    def ensure_git_repo(self, session_id: Optional[int] = None) -> bool:
        """Initializes a clean git repository in the workspace folder if not already present."""
        effective_sid = session_id if session_id is not None else self._active_session_id
        target_dir = self.get_session_dir(effective_sid)
        if not os.path.exists(target_dir):
            return False
        git_dir = os.path.join(target_dir, ".git")
        if os.path.exists(git_dir) and os.path.isdir(git_dir):
            return True

        try:
            subprocess.run(["git", "init"], cwd=target_dir, capture_output=True, timeout=10)
            gi_path = os.path.join(target_dir, ".gitignore")
            if not os.path.exists(gi_path):
                with open(gi_path, "w", encoding="utf-8") as f:
                    f.write("# Anara Workspace Ignore\nnode_modules/\nvenv/\n__pycache__/\n.DS_Store\n*.log\n.next/\ndist/\nbuild/\n")
            subprocess.run(["git", "add", "."], cwd=target_dir, capture_output=True, timeout=10)
            subprocess.run(["git", "commit", "-m", "Initial baseline commit by Anara Agent"], cwd=target_dir, capture_output=True, timeout=10)
            logger.info(f"[AnaraAgent] Initialized git repository in '{target_dir}'")
            return True
        except Exception as e:
            logger.warning(f"[AnaraAgent] Could not auto-init git in '{target_dir}': {e}")
            return False

    def create_checkpoint(self, session_id: Optional[int] = None) -> Optional[str]:
        """Creates a snapshot backup of workspace files before agent modifications."""
        effective_sid = session_id if session_id is not None else self._active_session_id
        target_dir = self.get_session_dir(effective_sid)
        if not os.path.exists(target_dir):
            return None
        cp_id = f"cp_{int(time.time())}"
        cp_dir = os.path.join(tempfile.gettempdir(), "anara_checkpoints", f"sess_{effective_sid or 0}", cp_id)
        os.makedirs(cp_dir, exist_ok=True)

        ignored = {".git", "node_modules", "venv", "__pycache__", ".next", "dist", "build"}
        copied = 0
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in ignored and "anara_checkpoints" not in d]
            rel = os.path.relpath(root, target_dir)
            dest_folder = os.path.join(cp_dir, rel) if rel != "." else cp_dir
            os.makedirs(dest_folder, exist_ok=True)
            for f in files:
                src_f = os.path.join(root, f)
                dst_f = os.path.join(dest_folder, f)
                try:
                    shutil.copy2(src_f, dst_f)
                    copied += 1
                except Exception:
                    pass
        logger.info(f"[Checkpoint] Created snapshot {cp_id} with {copied} files.")
        return cp_id

    def rollback_checkpoint(self, checkpoint_id: str, session_id: Optional[int] = None) -> bool:
        """Restores workspace files from a previously saved checkpoint snapshot."""
        effective_sid = session_id if session_id is not None else self._active_session_id
        safe_cp = os.path.basename(checkpoint_id.strip())
        cp_dir = os.path.join(tempfile.gettempdir(), "anara_checkpoints", f"sess_{effective_sid or 0}", safe_cp)
        target_dir = self.get_session_dir(effective_sid)
        if not os.path.exists(cp_dir) or not os.path.exists(target_dir):
            return False

        for root, dirs, files in os.walk(cp_dir):
            rel = os.path.relpath(root, cp_dir)
            dest_folder = os.path.join(target_dir, rel) if rel != "." else target_dir
            os.makedirs(dest_folder, exist_ok=True)
            for f in files:
                src_f = os.path.join(root, f)
                dst_f = os.path.join(dest_folder, f)
                try:
                    shutil.copy2(src_f, dst_f)
                except Exception:
                    pass
        logger.info(f"[Checkpoint] Successfully rolled back to snapshot {safe_cp}.")
        return True

    def record_git_commit(self, file_path: str, message: str, session_id: Optional[int] = None) -> Optional[str]:
        """
        FR-18: Automatically stages and commits workspace file changes per build step.
        Returns the short git commit SHA or None.
        """
        effective_sid = session_id if session_id is not None else self._active_session_id
        target_dir = self.get_session_dir(effective_sid)
        if not os.path.exists(target_dir):
            return None

        self.ensure_git_repo(effective_sid)
        try:
            rel_file = os.path.relpath(file_path, target_dir) if os.path.isabs(file_path) else file_path
            # Stage specific file
            subprocess.run(["git", "add", rel_file], cwd=target_dir, capture_output=True, timeout=10)
            # Commit with clean message
            clean_msg = f"anara(build): {message}"
            subprocess.run(
                ["git", "commit", "-m", clean_msg],
                cwd=target_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            # Get short commit hash
            rev_res = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=target_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            sha = rev_res.stdout.strip()
            if sha:
                logger.info(f"[GitCheckpoint] Stored commit {sha} for '{rel_file}': {message}")
                return sha
        except Exception as e:
            logger.warning(f"[GitCheckpoint] Could not record git commit: {e}")
        return None

    def rollback_git_commit(self, commit_sha: str, session_id: Optional[int] = None) -> bool:
        """
        FR-18: Rolls back or reverts a specific git commit in the workspace.
        """
        effective_sid = session_id if session_id is not None else self._active_session_id
        target_dir = self.get_session_dir(effective_sid)
        if not os.path.exists(target_dir):
            return False

        try:
            res = subprocess.run(
                ["git", "revert", "--no-edit", commit_sha],
                cwd=target_dir,
                capture_output=True,
                text=True,
                timeout=15
            )
            if res.returncode == 0:
                logger.info(f"[GitRollback] Reverted commit {commit_sha} successfully.")
                return True

            # Fallback to reset HEAD~1
            res2 = subprocess.run(
                ["git", "reset", "--hard", "HEAD~1"],
                cwd=target_dir,
                capture_output=True,
                text=True,
                timeout=15
            )
            return res2.returncode == 0
        except Exception as e:
            logger.warning(f"[GitRollback] Rollback error for {commit_sha}: {e}")
            return False

    def get_workspace_tree(self, session_id: Optional[int] = None) -> Dict[str, Any]:
        """Returns both flat file items and recursive nested folder tree of active workspace for a session."""
        effective_sid = session_id if session_id is not None else self._active_session_id

        if effective_sid is None and (0 not in self._session_active_paths and 0 not in self._session_custom_names):
            return {
                "workspace_name": "Project Workspace",
                "root_path": "",
                "total_files": 0,
                "files": [],
                "nested_tree": [],
                "is_custom_folder": False
            }

        items = []
        target_dir = self.get_session_dir(effective_sid)
        custom_name = self._session_custom_names.get(effective_sid if effective_sid is not None else 0)
        
        # If no custom name yet, try looking up from database
        if not custom_name and effective_sid is not None:
            try:
                from memory import memory_engine
                sess = memory_engine.get_session(effective_sid)
                if sess and sess.get("workspace_info"):
                    custom_name = sess["workspace_info"].get("name")
                    stored_path = sess["workspace_info"].get("root_path")
                    if stored_path and sess["workspace_info"].get("is_external") and os.path.isdir(stored_path):
                        self._session_active_paths[effective_sid] = stored_path
                        target_dir = stored_path
                    if custom_name:
                        self._session_custom_names[effective_sid] = custom_name
            except Exception:
                pass

        IGNORED = {".git", "node_modules", "venv", "__pycache__", ".next", "dist", "build", ".vscode", ".idea"}

        def build_nested_node(current_path: str, rel_path: str = "") -> List[Dict[str, Any]]:
            nodes = []
            try:
                entries = sorted(os.scandir(current_path), key=lambda e: (not e.is_dir(), e.name.lower()))
                for entry in entries:
                    if entry.name in IGNORED:
                        continue
                    entry_rel = os.path.join(rel_path, entry.name).replace("\\", "/")
                    if custom_name and entry_rel.startswith(f"{custom_name}/"):
                        display_rel = entry_rel[len(custom_name) + 1:]
                    else:
                        display_rel = entry_rel

                    if entry.is_dir(follow_symlinks=False):
                        children = build_nested_node(entry.path, entry_rel)
                        nodes.append({
                            "name": entry.name,
                            "path": display_rel or entry.name,
                            "type": "directory",
                            "children": children
                        })
                    elif entry.is_file(follow_symlinks=False):
                        ext = os.path.splitext(entry.name)[1].lower()
                        size_kb = round(entry.stat().st_size / 1024, 1)
                        file_obj = {
                            "name": entry.name,
                            "path": display_rel or entry.name,
                            "full_path": entry.path,
                            "type": "file",
                            "ext": ext,
                            "size_kb": size_kb,
                            "is_pdf": ext == ".pdf",
                            "is_image": ext in [".png", ".jpg", ".jpeg", ".webp", ".svg"],
                            "is_code": ext in [".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".txt", ".html", ".css", ".yaml", ".yml", ".sql", ".sh", ".rs", ".go", ".java", ".c", ".cpp"],
                        }
                        nodes.append(file_obj)
                        items.append(file_obj)
            except Exception as err:
                logger.warning(f"[WorkspaceTree] Error reading {current_path}: {err}")
            return nodes

        nested_tree = []
        if os.path.exists(target_dir):
            nested_tree = build_nested_node(target_dir)

        friendly_name = custom_name or "Project Workspace"
        return {
            "workspace_name": friendly_name,
            "session_id": session_id,
            "is_custom_folder": bool(custom_name),
            "root_path": target_dir,
            "total_files": len(items),
            "files": items,
            "nested_tree": nested_tree
        }

    def save_uploaded_file(self, filename: str, content_bytes: bytes, relative_path: Optional[str] = None, session_id: Optional[int] = None) -> Dict[str, Any]:
        """Saves an uploaded file into the session-isolated workspace directory, preserving relative subdirectory structure."""
        target_dir = self.get_session_dir(session_id)
        raw_rel = (relative_path or filename or "file.txt").replace("\\", "/")
        clean_rel = re.sub(r"^[a-zA-Z]:[/\\]?", "", raw_rel).lstrip("/")
        
        dest_path = os.path.join(target_dir, clean_rel)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        
        with open(dest_path, "wb") as f:
            f.write(content_bytes)

        ext = os.path.splitext(dest_path)[1].lower()
        size_kb = round(len(content_bytes) / 1024, 1)

        logger.info(f"[AnaraAgent] Saved workspace file (session {session_id}): {clean_rel} ({size_kb} KB)")
        
        _emit_agent_event("workspace_file_uploaded", {
            "session_id": session_id,
            "filename": os.path.basename(dest_path),
            "relative_path": clean_rel,
            "size_kb": size_kb,
            "ext": ext
        })

        return {
            "status": "success",
            "session_id": session_id,
            "filename": os.path.basename(dest_path),
            "relative_path": clean_rel,
            "path": dest_path,
            "size_kb": size_kb,
            "ext": ext
        }

    def clear_workspace(self, session_id: Optional[int] = None):
        """Detaches a session workspace. Never deletes a user-selected external folder."""
        key = session_id if session_id is not None else 0
        external_path = self._session_active_paths.get(key)
        target_dir = self.get_session_dir(session_id)
        if session_id is not None:
            self._session_custom_names.pop(session_id, None)
            self._session_active_paths.pop(session_id, None)
            try:
                from memory import memory_engine
                memory_engine.set_session_workspace_info(session_id, None)
            except Exception:
                pass
        else:
            self._session_custom_names.clear()
            self._session_active_paths.clear()

        # HARD SAFETY GUARD: NEVER clear project repository root or user directories!
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        clean_target = os.path.abspath(target_dir)

        is_safe_sandbox = (
            "anara_agent_workspace" in clean_target
            or "anara\\workspace\\session_" in clean_target.lower()
            or "anara/workspace/session_" in clean_target.lower()
        )

        if clean_target == repo_root or not is_safe_sandbox:
            logger.warning(f"[SafetyGuard] Refusing to wipe non-sandbox directory: {target_dir}")
            return

        # Only clear Anara's temporary workspace. An external user folder is detached safely.
        if not external_path and os.path.exists(target_dir):
            for item in os.listdir(target_dir):
                p = os.path.join(target_dir, item)
                try:
                    if os.path.isfile(p):
                        os.unlink(p)
                    elif os.path.isdir(p):
                        shutil.rmtree(p)
                except Exception:
                    pass
        logger.info(f"[AnaraAgent] Cleared workspace for session: {session_id}")

    async def reflect_and_learn_skill(self, user_mission: str, executed_steps: List[str], final_result: str):
        """
        Hermes-Style Post-Mission Reflection Loop.
        Automatically evaluates if the executed mission can be distilled into a reusable procedural skill.
        """
        from memory import memory_engine
        if not executed_steps or len(executed_steps) < 2:
            return

        try:
            # Check if this mission contains unique procedural knowledge
            m_lower = user_mission.lower()
            if any(w in m_lower for w in ["analisis", "ekstrak", "hitung", "scrape", "buatkan", "otomasi", "format"]):
                # Create a concise skill name and description
                words = [w for w in re.sub(r"[^\w\s]", "", user_mission).split() if len(w) > 3][:4]
                skill_name = "Prosedur: " + " ".join(words).title()
                
                skill = memory_engine.add_agent_skill(
                    name=skill_name,
                    category="learned",
                    description=f"Keahlian prosedural yang dipelajari otomatis dari misi: '{user_mission[:80]}'",
                    trigger_keywords=words,
                    procedure_steps=executed_steps[:5],
                    learned_from_experience=True
                )
                if skill:
                    logger.info(f"[AnaraAgent] 🧠 Auto-Learned Skill: '{skill_name}' from mission")
                    _emit_agent_event("agent_skill_learned", {
                        "skill_name": skill_name,
                        "description": skill["description"],
                        "steps": executed_steps[:5]
                    })
        except Exception as e:
            logger.debug(f"[AnaraAgent] Reflection error: {e}")


# Global singleton instance
anara_agent = AnaraAgent()
