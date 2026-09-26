"""
test_pillar2_git_worktree.py — Verification test suite for Pillar 2: Git Worktree Isolation.
Anara Engineering Standards:
1. Worktree isolation detection and creation.
2. Ephemeral branch and worktree directory management.
3. Safe cleanup and pruning on task abort.
4. SubAgentManager integration with use_worktree=True.
"""

import asyncio
import os
import shutil
import subprocess
import tempfile
import pytest

from core.worktree import GitWorktreeManager
from core.subagent import SubAgentManager, SubagentState


def _init_dummy_git_repo(tmp_path: str) -> None:
    """Helper to initialize an isolated git repo for testing."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "AnaraTest"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "anara@test.local"], cwd=tmp_path, check=True)
    # Create initial commit
    init_file = os.path.join(tmp_path, "README.md")
    with open(init_file, "w") as f:
        f.write("# Anara Test Repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=tmp_path, check=True, stdout=subprocess.DEVNULL)


def test_worktree_detection_and_creation():
    """Verifies that GitWorktreeManager detects git repo, creates worktree, and cleans up."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        _init_dummy_git_repo(tmp_dir)

        assert GitWorktreeManager.is_git_repo(tmp_dir) is True

        # Create worktree
        wt_result = GitWorktreeManager.create_worktree(tmp_dir, "test_task_123")
        assert wt_result is not None
        wt_dir, branch_name = wt_result

        assert os.path.isdir(wt_dir)
        assert os.path.isfile(os.path.join(wt_dir, "README.md"))
        assert "anara/wt-test_task_123" in branch_name

        # Clean up
        cleaned = GitWorktreeManager.remove_worktree(tmp_dir, wt_dir, branch_name)
        assert cleaned is True
        assert not os.path.exists(wt_dir)


def test_worktree_apply_and_merge():
    """Verifies that modifications inside worktree are squash merged back to parent workspace."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        _init_dummy_git_repo(tmp_dir)

        wt_result = GitWorktreeManager.create_worktree(tmp_dir, "mutate_task_456")
        assert wt_result is not None
        wt_dir, branch_name = wt_result

        # Modify a file inside the isolated worktree
        new_file = os.path.join(wt_dir, "test_feature.py")
        with open(new_file, "w") as f:
            f.write("# Verified subagent feature code\n")

        # Apply and merge back
        success = GitWorktreeManager.apply_and_merge_worktree(
            tmp_dir, wt_dir, branch_name, commit_msg="feat: add feature code"
        )
        assert success is True

        # Check file now exists in main workspace
        assert os.path.isfile(os.path.join(tmp_dir, "test_feature.py"))
        # Check worktree directory was automatically pruned
        assert not os.path.exists(wt_dir)


def test_subagent_with_worktree_integration():
    """Verifies SubAgentManager spawns and cleans up worktree on successful completion."""
    async def _run():
        with tempfile.TemporaryDirectory() as tmp_dir:
            _init_dummy_git_repo(tmp_dir)
            orig_cwd = os.getcwd()

            try:
                os.chdir(tmp_dir)
                mgr = SubAgentManager()

                async def mock_worker(task):
                    # Simulate subagent mutating code in task.worktree_dir
                    if task.worktree_dir:
                        feature_path = os.path.join(task.worktree_dir, "subagent_created.txt")
                        with open(feature_path, "w") as f:
                            f.write("Created inside isolated worktree!\n")
                    return "Success from subagent"

                task = await mgr.spawn_subagent_task(
                    title="Worktree isolation subtask",
                    use_worktree=True,
                    worker_coro_factory=mock_worker,
                    timeout_seconds=15.0,
                )

                # Await task execution
                if task._async_task:
                    await task._async_task

                assert task.state == SubagentState.SUCCEEDED
                # Verify change was merged back to main workspace
                assert os.path.isfile(os.path.join(tmp_dir, "subagent_created.txt"))
                # Verify worktree directory is cleaned up
                assert task.worktree_dir is not None
                assert not os.path.exists(task.worktree_dir)
            finally:
                os.chdir(orig_cwd)

    asyncio.run(_run())
