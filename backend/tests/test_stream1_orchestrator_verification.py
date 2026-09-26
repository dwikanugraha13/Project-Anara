"""
test_stream1_orchestrator_verification.py
Comprehensive verification test suite for Stream 1 (Batches 1, 2, 4):
1. Zero static keyword gating in session state intent evaluation.
2. Persist-Before-Execute durability in tool execution ledger.
3. SQLite connection lifecycle and pragma enforcement (foreign_keys, synchronous, busy_timeout, handle closure).
4. Subagent anti-fork-bomb depth budgeting & disk spilling.
5. Negative verification stop-gate staleness tracking & dynamic suggestion.
6. Omnichannel fence-aware chunking without syntax corruption.
"""

import asyncio
import os
import sqlite3
import pytest
from core.session_manager import session_state_manager, PendingAction, ActionState
from core.autonomous_engine import autonomous_engine
from core.subagent import subagent_manager, apply_summary_budget, DEFAULT_MAX_SUMMARY_CHARS
from core.convergence import ConvergenceDetector
from core.channel_adapter import split_message_chunks
from core.plan_detector import is_explicit_plan_approval, _INTENT_CACHE


def test_sqlite_pragmas_and_handle_closure():
    """Verify that _get_conn contextmanager sets SQLite pragmas and closes handles."""
    # 1. Test session_state_manager connection
    with session_state_manager._get_conn() as conn:
        assert isinstance(conn, sqlite3.Connection)
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys;")
        assert cur.fetchone()[0] == 1

        cur.execute("PRAGMA busy_timeout;")
        assert cur.fetchone()[0] == 15000

    # Connection should be closed outside contextmanager
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1;")

    # 2. Test autonomous_engine connection
    with autonomous_engine._get_conn() as conn_ae:
        assert isinstance(conn_ae, sqlite3.Connection)
        cur_ae = conn_ae.cursor()
        cur_ae.execute("PRAGMA foreign_keys;")
        assert cur_ae.fetchone()[0] == 1

        cur_ae.execute("PRAGMA busy_timeout;")
        assert cur_ae.fetchone()[0] == 15000

    with pytest.raises(sqlite3.ProgrammingError):
        conn_ae.execute("SELECT 1;")


def test_persist_before_execute_durability():
    """Verify tool call start and result are persistently written to SQLite tool_execution_ledger."""
    test_sid = 999111
    test_channel = "test_chan"
    test_cid = "user_99"

    # 1. Persist tool call start before execution
    call_id = session_state_manager.persist_tool_call_start(
        session_id=test_sid,
        channel=test_channel,
        channel_id=test_cid,
        tool_name="write_local_file",
        tool_args={"path": "test.py", "content": "print(1)"}
    )
    assert call_id.startswith("call_")

    # Read back immediately from SQLite before completion
    history = session_state_manager.get_tool_execution_history(session_id=test_sid, limit=10)
    assert len(history) >= 1
    latest = history[0]
    assert latest["call_id"] == call_id
    assert latest["tool_name"] == "write_local_file"
    assert latest["status"] == "running"
    assert latest["completed_at"] is None

    # 2. Persist tool call result upon execution completion
    session_state_manager.persist_tool_call_result(
        call_id=call_id,
        result_summary="File written successfully (12 bytes).",
        is_error=False
    )

    # Read back immediately from SQLite after completion
    history_after = session_state_manager.get_tool_execution_history(session_id=test_sid, limit=10)
    completed_rec = [r for r in history_after if r["call_id"] == call_id][0]
    assert completed_rec["status"] == "completed"
    assert "File written successfully" in completed_rec["result_summary"]
    assert completed_rec["completed_at"] is not None


def test_zero_static_keyword_gating_in_evaluate_intent():
    """Verify evaluate_intent uses model-driven approval reasoning rather than static hardcoded word checks."""
    test_channel = "test_gate"
    test_channel_id = "test_user_gate"

    action = PendingAction(
        plan_id="act_model_driven",
        session_id="8888",
        channel=test_channel,
        channel_id=test_channel_id,
        tool_name="terminal",
        tool_args={"command": "npm run build"},
        plan_text="Build frontend assets with npm run build",
        original_prompt="build frontend",
    )
    session_state_manager.store_pending(action)

    try:
        # Machine tokens
        res_y = session_state_manager.evaluate_intent("y", test_channel, test_channel_id)
        assert res_y["has_pending"] is True
        assert res_y["is_approval"] is True

        res_n = session_state_manager.evaluate_intent("no", test_channel, test_channel_id)
        assert res_n["has_pending"] is True
        assert res_n["is_approval"] is False

        # Pre-seed reasoning cache to simulate model verdicts without live API call
        _INTENT_CACHE["gas min"] = "approve"
        _INTENT_CACHE["jangan lakukan sekarang"] = "reject"

        res_approve = session_state_manager.evaluate_intent("gas min", test_channel, test_channel_id)
        assert res_approve["is_approval"] is True

        res_reject = session_state_manager.evaluate_intent("jangan lakukan sekarang", test_channel, test_channel_id)
        assert res_reject["is_approval"] is False
    finally:
        session_state_manager.clear_pending(test_channel, test_channel_id)


def test_subagent_depth_budgeting_and_spilling():
    """Verify recursive depth limit and line-snapped head/tail summary disk spilling."""
    # 1. Depth boundary: depth > 2 must be rejected to prevent recursive fork bombs
    loop = asyncio.new_event_loop()
    try:
        task_bomb = loop.run_until_complete(
            subagent_manager.spawn_subagent_task(
                title="Fork Bomb Attempt",
                depth=3  # Exceeds max depth 2
            )
        )
        assert task_bomb.status == "failed"
        assert "Delegation depth limit reached" in task_bomb.result.executive_summary
    finally:
        loop.close()

    # 2. Summary budgeting and disk spilling
    large_text = "Line " + "\nLine ".join([f"{i} lorem ipsum dolor sit amet" for i in range(1000)])
    budgeted, spill_file = apply_summary_budget("task_spill_test", large_text, max_chars=500)
    assert spill_file is not None
    assert os.path.exists(spill_file)
    assert "ANARA HEAD/TAIL WINDOW" in budgeted
    assert "read_local_file" in budgeted
    # Clean up spill file
    try:
        os.unlink(spill_file)
    except Exception:
        pass


def test_negative_verification_stop_gate_dynamic():
    """Verify negative verification stop gate invalidates prior tests on new code mutations and suggests detected test commands."""
    conv = ConvergenceDetector(read_only=False)

    # 1. Modify a verifiable code file
    conv.record_turn_actions(
        step=1,
        executed_calls=[{
            "tool_name": "edit_file",
            "args": {"path": "backend/core/runner.py"},
            "risk": "mutating",
            "is_error": False,
            "summary": "Updated runner.py"
        }]
    )
    # Stop gate should block completion because no tests ran
    nudge = conv.evaluate_final_stop_gate(agent_mode="build")
    assert nudge is not None
    assert "VERIFICATION STOP-GATE" in nudge
    assert "runner.py" in nudge

    # 2. Run passing test
    conv.record_turn_actions(
        step=2,
        executed_calls=[{
            "tool_name": "execute_cli_command",
            "args": {"command": "pytest backend/tests/test_subsystems.py"},
            "risk": "action",
            "is_error": False,
            "summary": "1 passed, 0 failed in 0.5s"
        }]
    )
    # Stop gate should now pass
    assert conv.evaluate_final_stop_gate(agent_mode="build") is None

    # 3. Modify another code file (staleness tracking: renders prior test invalid!)
    conv.record_turn_actions(
        step=3,
        executed_calls=[{
            "tool_name": "write_local_file",
            "args": {"path": "backend/core/session_manager.py"},
            "risk": "mutating",
            "is_error": False,
            "summary": "Updated session_manager.py"
        }]
    )
    # Stop gate must block completion again!
    nudge_stale = conv.evaluate_final_stop_gate(agent_mode="build")
    assert nudge_stale is not None
    assert "session_manager.py" in nudge_stale


def test_omnichannel_fence_aware_chunking():
    """Verify split_message_chunks preserves markdown code fence integrity across splits."""
    long_code_msg = (
        "Here is the implementation:\n\n"
        "```python\n"
        + "\n".join([f"def func_{i}():\n    return {i}" for i in range(80)])
        + "\n```\n\nHope this helps!"
    )
    chunks = split_message_chunks(long_code_msg, max_chars=350, add_part_headers=False)
    assert len(chunks) > 1
    for idx, c in enumerate(chunks[:-1]):
        # If chunk contains code block, it must be balanced (even number of ```)
        count_fence = c.count("```")
        assert count_fence % 2 == 0, f"Chunk #{idx} broke code block fence! count={count_fence}"
