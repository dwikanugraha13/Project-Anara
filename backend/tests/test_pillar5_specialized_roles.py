"""
test_pillar5_specialized_roles.py — Verification test suite for Pillar 5: Specialized Sub-Agent Roles.
Anara Multi-Agent Swarm Architecture:
1. Principle of least privilege role specialization (Explorer, Implementer, Verifier).
2. Read-only gate enforcement per role.
3. Tailored system prompts for exploration, implementation, and adversarial validation.
"""

import pytest
from core.subagent import get_role_configuration, SubAgentTask, SubagentState


def test_specialized_subagent_role_configurations():
    """Verifies that role configuration yields correct least-privilege permissions and prompts."""
    # 1. Explorer (read-only recon)
    exp_prompt, exp_ro = get_role_configuration("explorer")
    assert exp_ro is True
    assert "[ROLE: CODEBASE EXPLORER" in exp_prompt
    assert "extract_code_outline" in exp_prompt

    # Also test synonym "recon"
    recon_prompt, recon_ro = get_role_configuration("recon")
    assert recon_ro is True
    assert "[ROLE: CODEBASE EXPLORER" in recon_prompt

    # 2. Implementer (mutating / coder)
    imp_prompt, imp_ro = get_role_configuration("implementer")
    assert imp_ro is False
    assert "[ROLE: IMPLEMENTER" in imp_prompt

    # Also test synonym "coder"
    coder_prompt, coder_ro = get_role_configuration("coder")
    assert coder_ro is False
    assert "[ROLE: IMPLEMENTER" in coder_prompt

    # 3. Verifier (adversarial QA gatekeeper)
    ver_prompt, ver_ro = get_role_configuration("verifier")
    assert ver_ro is True
    assert "[ROLE: ADVERSARIAL VERIFIER" in ver_prompt

    # Also test synonym "reviewer"
    rev_prompt, rev_ro = get_role_configuration("reviewer")
    assert rev_ro is True
    assert "[ROLE: ADVERSARIAL VERIFIER" in rev_prompt

    # 4. Orchestrator (leadership)
    orch_prompt, orch_ro = get_role_configuration("orchestrator")
    assert orch_ro is False

    # 5. Default leaf
    leaf_prompt, leaf_ro = get_role_configuration("leaf")
    assert leaf_ro is True


def test_subagent_task_role_metadata():
    """Verifies that SubAgentTask properly captures and stores specialized role configuration."""
    task = SubAgentTask(
        task_id="task_test_001",
        goal="Audit security headers",
        context="Check middleware",
        role="verifier",
        depth=1,
        platform="cli",
        use_worktree=True,
    )

    assert task.role == "verifier"
    assert task.use_worktree is True
    assert task.state == SubagentState.PENDING
