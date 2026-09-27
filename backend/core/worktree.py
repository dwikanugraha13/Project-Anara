"""
worktree.py — Git Worktree Isolation Manager for Sub-Agents & Mutating Missions.
Anara Enterprise Architecture:
1. Isolated worktree creation for sub-agents (hermes -w parity) preventing dirty working tree states.
2. Atomic merge/apply on test verification pass.
3. Automatic cleanup and pruning on failure, interrupt, or timeout.
4. Safe fallback if workspace is not a Git repository.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("anara.core.worktree")


class GitWorktreeManager:
    """Manages ephemeral Git worktrees for safe, isolated sub-agent execution."""

    @staticmethod
    def is_git_repo(target_dir: str) -> bool:
        """Verifies if target directory is inside a valid Git repository."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=target_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
            )
            return res.returncode == 0 and "true" in res.stdout.strip().lower()
        except Exception:
            return False

    @classmethod
    def create_worktree(
        cls,
        repo_dir: str,
        task_id: str,
        base_ref: str = "HEAD",
    ) -> Optional[Tuple[str, str]]:
        """
        Creates an isolated Git worktree under .anara/worktrees/anara-wt-<task_id>.
        Returns (worktree_absolute_path, branch_name) or None if not a Git repo.
        """
        if not cls.is_git_repo(repo_dir):
            logger.debug(f"[Worktree] '{repo_dir}' is not a Git repo. Skipping worktree isolation.")
            return None

        clean_task = task_id.replace(":", "_").replace("/", "_")
        branch_name = f"anara/wt-{clean_task}"
        worktrees_root = Path(repo_dir) / ".anara" / "worktrees"
        worktrees_root.mkdir(parents=True, exist_ok=True)
        worktree_dir = worktrees_root / f"wt-{clean_task}"

        # Clean existing directory if stale
        if worktree_dir.exists():
            cls.remove_worktree(repo_dir, str(worktree_dir), branch_name, force=True)

        try:
            # git worktree add -b <branch> <path> <base_ref>
            cmd = [
                "git",
                "worktree",
                "add",
                "-b",
                branch_name,
                str(worktree_dir),
                base_ref,
            ]
            res = subprocess.run(
                cmd,
                cwd=repo_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=30,
            )
            if res.returncode != 0:
                logger.warning(f"[Worktree] Failed to add worktree: {res.stderr.strip()}")
                return None

            logger.info(f"[Worktree] Created isolated worktree at '{worktree_dir}' on branch '{branch_name}'")
            return (str(worktree_dir), branch_name)
        except Exception as e:
            logger.warning(f"[Worktree] Exception creating worktree: {e}")
            return None

    @classmethod
    def apply_and_merge_worktree(
        cls,
        repo_dir: str,
        worktree_dir: str,
        branch_name: str,
        commit_msg: Optional[str] = None,
    ) -> bool:
        """
        Transfers verified code changes from isolated worktree back to the main working tree.
        """
        if not os.path.isdir(worktree_dir):
            return False

        try:
            # 1. Check if worktree has modifications
            status_res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=worktree_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=10,
            )
            has_uncommitted = bool(status_res.stdout.strip())

            if has_uncommitted:
                # Commit all worktree changes
                subprocess.run(["git", "add", "-A"], cwd=worktree_dir, check=False, timeout=15)
                subprocess.run(
                    ["git", "commit", "-m", commit_msg or f"feat(anara): subagent verified task {branch_name}"],
                    cwd=worktree_dir,
                    check=False,
                    timeout=15,
                )

            # 2. Check if worktree branch is ahead of base
            diff_res = subprocess.run(
                ["git", "diff", f"HEAD...{branch_name}"],
                cwd=repo_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=15,
            )
            if not diff_res.stdout.strip():
                logger.debug(f"[Worktree] No code diff to apply from '{branch_name}'.")
                cls.remove_worktree(repo_dir, worktree_dir, branch_name)
                return True

            # 3. Apply changes via git cherry-pick or diff apply
            apply_res = subprocess.run(
                ["git", "merge", "--squash", branch_name],
                cwd=repo_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=25,
            )
            success = apply_res.returncode == 0
            if success:
                logger.info(f"[Worktree] Successfully merged changes from '{branch_name}' into main workspace.")
                cls.remove_worktree(repo_dir, worktree_dir, branch_name)
            else:
                logger.warning(f"[Worktree] Squash merge conflict: {apply_res.stderr.strip()}")
                # Abort conflicting index in main repo to prevent leaving repo dirty
                subprocess.run(["git", "merge", "--abort"], cwd=repo_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                # Preserve worktree directory and branch for inspection rather than permanent data loss
                logger.info(f"[Worktree] Preserved worktree at '{worktree_dir}' and branch '{branch_name}' for manual inspection.")
            return success
        except Exception as e:
            logger.error(f"[Worktree] Error merging worktree changes: {e}")
            subprocess.run(["git", "merge", "--abort"], cwd=repo_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            return False

    @classmethod
    def remove_worktree(
        cls,
        repo_dir: str,
        worktree_dir: str,
        branch_name: Optional[str] = None,
        force: bool = True,
    ) -> bool:
        """Prunes and removes an ephemeral worktree directory and its branch."""
        try:
            if cls.is_git_repo(repo_dir):
                # git worktree remove [--force] <path>
                cmd = ["git", "worktree", "remove"]
                if force:
                    cmd.append("--force")
                cmd.append(worktree_dir)
                subprocess.run(cmd, cwd=repo_dir, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)

                if branch_name:
                    subprocess.run(
                        ["git", "branch", "-D", branch_name],
                        cwd=repo_dir,
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=10,
                    )

            if os.path.exists(worktree_dir):
                shutil.rmtree(worktree_dir, ignore_errors=True)

            logger.debug(f"[Worktree] Cleaned up worktree at '{worktree_dir}'")
            return True
        except Exception as e:
            logger.debug(f"[Worktree] Cleanup notice for '{worktree_dir}': {e}")
            if os.path.exists(worktree_dir):
                shutil.rmtree(worktree_dir, ignore_errors=True)
            return False

    @classmethod
    def cleanup_stale_worktrees(cls, repo_dir: str, max_age_hours: float = 24.0) -> int:
        """Removes orphan or stale worktree folders older than max_age_hours."""
        worktrees_root = Path(repo_dir) / ".anara" / "worktrees"
        if not worktrees_root.is_dir():
            return 0

        reaped = 0
        now = time.time()
        max_age_sec = max_age_hours * 3600.0

        for item in worktrees_root.iterdir():
            if item.is_dir() and item.name.startswith("wt-"):
                try:
                    mtime = item.stat().st_mtime
                    if now - mtime > max_age_sec:
                        branch_name = f"anara/{item.name.replace('wt-', 'wt-')}"
                        cls.remove_worktree(repo_dir, str(item), branch_name=branch_name, force=True)
                        reaped += 1
                except Exception:
                    pass

        return reaped


# Global singleton
worktree_manager = GitWorktreeManager()
