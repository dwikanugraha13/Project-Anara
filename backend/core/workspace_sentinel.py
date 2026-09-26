"""
workspace_sentinel.py — Ground-Truth Verification & Workspace Integrity Sentinel for Project Anara.
Hermes Agent Parity: Subsystem 5.

Pillars:
1. Workspace Integrity & Blast Radius Guard (Pilar A):
   - Confines file writes/edits to valid project boundaries.
   - Protects sacred infrastructure (.git metadata, anara_brain.db) from raw corruption or deletion.
   - Flags high-blast-radius destructive shell commands (rm -rf *, Remove-Item * -Recurse, git clean -fdx).
2. Ground-Truth Verification Engine (Pilar B):
   - Post-Write Read-Back Verification: Probes the physical disk bytes immediately after modification
     to prevent "phantom edits" where an agent assumes text replacement succeeded without landing.
   - Physical Test Ground-Truth Evaluation: Inspects actual exit_code and test harness logs
     (pytest / run_tests.py) to prevent premature "mission accomplished" hallucinations.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("anara.core.workspace_sentinel")


class WorkspaceSentinel:
    """Protects repository filesystem integrity and validates runtime execution correctness."""

    # 1. High-blast-radius destructive shell command patterns
    DESTRUCTIVE_SHELL_PATTERNS: List[str] = [
        r"\brm\s+-[rf]{1,2}\s+(?:\*|\.\/\*|\.\s*$)",
        r"\bdel\b.*\/[sq].*(?:\*|\.\*)",
        r"\brmdir\b.*\/[sq]\s+(?:\.|\*|[a-zA-Z]:[/\\]?$)",
        r"\bremove-item\b.*-(?:recurse|r)\b.*(?:\*|\.[\/\\]\*|\s\.)",
        r"\bgit\s+clean\s+-[fdx]{1,4}\b",
    ]

    # 2. Sacred infrastructure directories & files
    PROTECTED_DIRECTORIES: Set[str] = {".git", ".ssh"}
    PROTECTED_FILES_DELETE: Set[str] = {".env", ".env.local", "id_rsa", "anara_brain.db"}

    def __init__(self, workspace_root: Optional[str] = None):
        self._workspace_root_str = workspace_root

    @property
    def workspace_root(self) -> Path:
        """Dynamically resolves the active workspace root."""
        if self._workspace_root_str and os.path.isdir(self._workspace_root_str):
            return Path(self._workspace_root_str).resolve()
        try:
            from core.agent import anara_agent
            active_dir = anara_agent.get_session_dir()
            if active_dir and os.path.isdir(active_dir):
                return Path(active_dir).resolve()
        except Exception:
            pass
        return Path.cwd().resolve()

    def _resolve_session_id(self, explicit_sid: Optional[str] = None) -> str:
        """Dynamically resolves the active session identifier from context."""
        if explicit_sid and explicit_sid != "default":
            return str(explicit_sid)
        try:
            from core.agent import anara_agent
            active = anara_agent.get_active_session_id()
            if active:
                return str(active)
        except Exception:
            pass
        try:
            from core.channel_adapter import get_active_channel_context
            ctx = get_active_channel_context()
            if ctx and ctx.get("channel_id"):
                return f"{ctx.get('channel')}_{ctx.get('channel_id')}"
        except Exception:
            pass
        return "default"

    def validate_cli_command(self, command: str) -> Tuple[bool, Optional[str]]:
        """
        Validates whether a shell command possesses a destructive high blast-radius.
        Returns: (is_safe, error_message)
        """
        cmd_clean = (command or "").strip()
        if not cmd_clean:
            return True, None

        cmd_lower = cmd_clean.lower()
        for pattern in self.DESTRUCTIVE_SHELL_PATTERNS:
            if re.search(pattern, cmd_lower):
                logger.warning(f"[WorkspaceSentinel] Blocked mass wipe command: {cmd_clean}")
                try:
                    import asyncio
                    from telemetry.event_bus import telemetry_bus, EventType, ActivityProvenance
                    eff_sid = self._resolve_session_id()
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        telemetry_bus.emit(
                            event_type=EventType.GUARDRAIL_TRIGGERED,
                            provenance=ActivityProvenance.WORKSPACE_SENTINEL,
                            session_id=eff_sid,
                            trace_id="guardrail_blast_radius",
                            payload={"command": cmd_clean, "pattern": pattern, "risk": "ask"}
                        )
                    )
                except (RuntimeError, Exception):
                    pass
                return False, (
                    f"WORKSPACE SENTINEL BLOCKED: Command '{cmd_clean}' blocked due to "
                    "massive destructive blast-radius (Hermes Repo-Safety). "
                    "Use targeted per-file operations (delete_local_file) instead of mass wipe."
                )

        return True, None

    def validate_file_access(
        self,
        target_path: str,
        action: str = "write",
        workspace_root: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Ensures target path stays within safe project boundaries and does not corrupt sacred files.
        Actions: 'read', 'write', 'edit', 'delete'
        Returns: (is_safe, error_message)
        """
        clean_p = (target_path or "").strip().strip('"\'')
        if not clean_p:
            return False, "File path cannot be empty."

        root = Path(workspace_root).resolve() if workspace_root else self.workspace_root
        try:
            resolved = (root / clean_p).resolve() if not os.path.isabs(clean_p) else Path(clean_p).resolve()
        except Exception as e:
            return False, f"Invalid path: {e}"

        # 1. Confinement check: prevent directory traversal outside workspace for mutating operations
        authorized_roots = [root]
        if not workspace_root and not self._workspace_root_str:
            try:
                from core.agent import anara_agent
                sess_dir = anara_agent.get_session_dir()
                if sess_dir and os.path.isdir(sess_dir):
                    authorized_roots.append(Path(sess_dir).resolve())
                repo_root = anara_agent.get_project_repo_root()
                if repo_root and os.path.isdir(repo_root):
                    authorized_roots.append(Path(repo_root).resolve())
            except Exception:
                pass
            try:
                import tempfile
                authorized_roots.append(Path(tempfile.gettempdir()).resolve())
            except Exception:
                pass

        is_confined = False
        for auth_root in authorized_roots:
            try:
                if resolved.is_relative_to(auth_root):
                    is_confined = True
                    break
            except AttributeError:
                try:
                    resolved.relative_to(auth_root)
                    is_confined = True
                    break
                except ValueError:
                    pass

        if not is_confined and action in ("write", "edit", "delete"):
            return False, (
                f"SECURITY RESTRICTION: Path '{clean_p}' resolves outside authorized workspace boundaries "
                f"({root}). Mutating operations outside the project root are forbidden (Hermes Repo-Safety)."
            )

        # 2. Sacred infrastructure protection (.git objects, credentials, database)
        parts = [p.lower() for p in resolved.parts]
        target_base = resolved.name.lower()

        # Prevent raw text edits or deletes inside internal .git directory
        if ".git" in parts and action in ("write", "edit", "delete"):
            return False, "SECURITY ERROR: Direct modification of internal '.git' directory is blocked to preserve repository integrity."

        # Prevent access to sensitive user credentials directories
        if any(d in parts for d in (".ssh", ".aws", ".gnupg", ".docker")):
            return False, "SECURITY ERROR: Access to sensitive credentials directory is blocked."

        # Prevent modification or deletion of sensitive credentials or active SQLite database (Hermes File-Safety Parity)
        PROTECTED_SACRED_FILES = frozenset({"anara_brain.db", "state.db", "auth.json", ".env", ".env.local"})
        if target_base in PROTECTED_SACRED_FILES:
            if action in ("write", "edit", "delete"):
                return False, f"SECURITY ERROR: Direct modification of protected file '{target_base}' is restricted."
            elif action == "read" and target_base in (".env", ".env.local", "auth.json"):
                return False, f"SECURITY ERROR: Direct reading of sensitive credentials file '{target_base}' is blocked to prevent token exfiltration."

        return True, None

    def verify_read_back(
        self,
        file_path: str,
        expected_snippet: str = ""
    ) -> Dict[str, Any]:
        """
        Post-write Ground-Truth Verification (Anti-Phantom Edit).
        Immediately probes physical disk bytes after write/edit to confirm changes truly landed.
        Returns: Dict with verification result and metadata.
        """
        clean_p = (file_path or "").strip().strip('"\'')
        if not clean_p or not os.path.isfile(clean_p):
            # Attempt resolving relative to workspace
            candidate = os.path.join(str(self.workspace_root), clean_p)
            if os.path.isfile(candidate):
                clean_p = candidate
            else:
                return {
                    "verified": False,
                    "file_path": clean_p,
                    "exists": False,
                    "error": f"File '{clean_p}' was not found on physical disk after write operation."
                }

        try:
            with open(clean_p, "r", encoding="utf-8", errors="replace") as f:
                disk_content = f.read()

            file_size = len(disk_content)
            snippet_matched = True
            if expected_snippet and expected_snippet.strip():
                snippet_matched = (expected_snippet.strip() in disk_content)
                is_verified = snippet_matched and file_size > 0
            else:
                is_verified = True  # Existence of physical file confirmed (permits empty files like __init__.py)
            return {
                "verified": is_verified,
                "file_path": clean_p,
                "exists": True,
                "file_size": file_size,
                "snippet_matched": snippet_matched,
                "error": None if is_verified else "Expected content was not found in physical file after modification."
            }
        except Exception as e:
            return {
                "verified": False,
                "file_path": clean_p,
                "exists": True,
                "error": f"Disk read-back verification failed: {e}"
            }

    def verify_ground_truth(
        self,
        test_output: str,
        exit_code: int,
        task_description: str = "",
        modified_files: Optional[List[str]] = None,
        session_id: str = "default",
    ) -> Dict[str, Any]:
        """
        Physical Test Ground-Truth Evaluation (Hermes Parity).
        Evaluates physical test output to prevent premature 'mission accomplished' hallucinations.
        Automatically synthesizes and commits an Architectural Decision Record (ADR) upon test pass.
        """
        out_clean = test_output or ""
        out_upper = out_clean.upper()

        has_failure_signals = any(sig in out_upper for sig in (
            "FAILED (", "FAILURES=", "ERROR:", "ERRORS=", "EXCEPTION:", "TRACEBACK"
        )) and ("0 FAILED" not in out_upper and "FAILED: 0" not in out_upper)

        is_passed = (exit_code == 0) and not has_failure_signals
        eff_sid = self._resolve_session_id(session_id)

        if is_passed:
            guidance = "Physical verification PASS (exit_code=0). Task completion claim proven valid through actual testing."
            if task_description:
                try:
                    from memory.episodic_adr import episodic_adr_manager
                    import asyncio
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        episodic_adr_manager.synthesize_and_record_adr_milestone(
                            task_prompt=task_description,
                            modified_files=modified_files or [],
                            test_output=out_clean,
                            session_id=eff_sid,
                        )
                    )
                except (RuntimeError, Exception):
                    pass
        else:
            from tools.self_correction import ErrorClassifier
            err_type, detail = ErrorClassifier.classify(out_clean)
            cat = err_type or "execution_failure"
            guidance = (
                f"[GROUND-TRUTH VERIFICATION FAILED: exit_code={exit_code}, category={cat}]\n"
                "Physical workspace verification failed. Do not claim the task is complete until tests succeed with exit code 0.\n"
                f"Detail: {detail or 'Inspect the failure traceback above, apply targeted fixes, and re-verify.'}"
            )

        try:
            import asyncio
            from telemetry.event_bus import telemetry_bus, EventType, ActivityProvenance
            loop = asyncio.get_running_loop()
            loop.create_task(
                telemetry_bus.emit(
                    event_type=EventType.GROUND_TRUTH_CHECK,
                    provenance=ActivityProvenance.WORKSPACE_SENTINEL,
                    session_id=eff_sid,
                    trace_id="ground_truth_test",
                    payload={
                        "exit_code": exit_code,
                        "verified": is_passed,
                        "has_failure_signals": has_failure_signals,
                        "output_snippet": out_clean[:300]
                    }
                )
            )
        except (RuntimeError, Exception):
            pass

        return {
            "verified": is_passed,
            "exit_code": exit_code,
            "has_failure_signals": has_failure_signals,
            "requires_correction": not is_passed,
            "guidance": guidance,
        }


# Global singleton instance
workspace_sentinel = WorkspaceSentinel()
