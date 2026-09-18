"""
test_subsystems.py — Enterprise Regression Suite for Project Anara Core Subsystems.
Tests Context Compaction, FTS5 Search, Deduplication, Skill Viewer, and Process Lifecycle.
"""

import os
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from core.context_compactor import ContextCompactor, prune_tool_output
from integrations.dedup import MessageDeduplicator
from core.lifecycle import is_pid_alive, record_process_start, get_process_pid, record_process_exit
from core.reasoning_effort import clamp_effort, EFFORT_LADDER
from core.capabilities import ModelCapabilityRegistry


def test_context_compactor_pruning():
    raw_code = "```python\n" + ("x = 1\n" * 80) + "```"
    pruned = prune_tool_output(raw_code, max_chars=100)
    assert "[... cuplikan kode" in pruned
    assert len(pruned) < len(raw_code)


def test_context_compactor_protected_head_and_tail():
    history = [
        {"id": 1, "user_text": "Goal: Build eCommerce store", "ai_text": "Understood, starting."},
        {"id": 2, "user_text": "Step 1 complete", "ai_text": "Great."},
        {"id": 3, "user_text": "Step 2 complete", "ai_text": "Great."},
        {"id": 4, "user_text": "Step 3 complete", "ai_text": "Great."},
        {"id": 5, "user_text": "Final verification", "ai_text": "All tests passed."},
    ]
    compacted = ContextCompactor.compact_history(history, verbatim_turns=2, protect_head_n=1)
    assert "[TUJUAN AWAL / INISIASI SESI (PROTECTED HEAD)]" in compacted
    assert "Goal: Build eCommerce store" in compacted
    assert "Final verification" in compacted


def test_message_deduplicator_sliding_window():
    dedup = MessageDeduplicator(max_size=3, ttl_seconds=2.0)
    assert not dedup.is_duplicate("msg_1")
    assert dedup.is_duplicate("msg_1")

    assert not dedup.is_duplicate("msg_2")
    assert not dedup.is_duplicate("msg_3")
    assert not dedup.is_duplicate("msg_4")  # Exceeds max_size, prunes oldest

    # msg_4 is live
    assert dedup.contains("msg_4")


def test_reasoning_effort_clamping():
    assert clamp_effort("xhigh", ["low", "medium", "high"]) == "high"
    assert clamp_effort("ultra", ["none", "low"]) == "low"
    assert clamp_effort("none", ["none", "high"]) == "none"
    assert clamp_effort("invalid_string", ["low", "high"]) == "low"


def test_process_lifecycle_ledger(tmp_path=None):
    cur_pid = os.getpid()
    assert is_pid_alive(cur_pid)

    pid_path = record_process_start("test_daemon", pid=cur_pid)
    assert pid_path.is_file()
    assert get_process_pid("test_daemon") == cur_pid

    record_process_exit("test_daemon")
    assert get_process_pid("test_daemon") is None


def test_model_capabilities_universal():
    assert ModelCapabilityRegistry.supports_voice("gpt-4o-realtime-preview")
    assert ModelCapabilityRegistry.supports_vision("qwen-vl-max")
    assert ModelCapabilityRegistry.supports_vision("claude-3-opus")


def test_smart_output_truncation():
    from tools.output_manager import compact_tool_output
    short_text = "Standard short terminal output"
    assert compact_tool_output(short_text) == short_text

    long_output = "\n".join([f"Processing item {i}: [STATUS_OK]" for i in range(120)])
    compacted = compact_tool_output(long_output, max_lines=40, max_chars=1200)
    assert "[OUTPUT TERPOTONG:" in compacted
    assert "Processing item 0:" in compacted
    assert "Processing item 119:" in compacted
    assert len(compacted) < len(long_output)


def test_anara_platform_tool_registry():
    from tools.platform_registry import PlatformToolRegistry, CORE_TOOLS
    tele_tools = PlatformToolRegistry.get_tools_for_platform(platform="telegram")
    for ct in CORE_TOOLS:
        assert ct in tele_tools
    assert "take_screenshot" in tele_tools
    assert "web_search" in tele_tools
    # Desktop web studio specific tools shouldn't be in Telegram
    assert "scan_workspace_folder" not in tele_tools

    # Test dynamic intent expansion
    intent_tools = PlatformToolRegistry.get_tools_for_platform(
        platform="telegram",
        user_task="tolong putar lagu lofi di spotify dong"
    )
    assert "spotify_playback" in intent_tools
    assert "spotify_search" in intent_tools


def test_anara_autonomous_memory_nudge():
    from cognition.memory_nudge import SessionTurnTracker
    tracker = SessionTurnTracker(session_id="test_sess", memory_nudge_interval=10, skill_nudge_interval=15)
    
    for i in range(1, 10):
        assert tracker.increment_turn() is None
    
    # Turn 10: memory nudge
    nudge_10 = tracker.increment_turn()
    assert nudge_10 is not None
    assert "[ANARA AUTONOMOUS MEMORY NUDGE (Turn 10)]" in nudge_10

    for i in range(11, 15):
        assert tracker.increment_turn() is None
    
    # Turn 15: skill creation nudge
    nudge_15 = tracker.increment_turn()
    assert nudge_15 is not None
    assert "[ANARA SKILL CREATION NUDGE (Turn 15)]" in nudge_15


def test_anara_task_scratchpad():
    from cognition.memory_nudge import TaskScratchpad, memory_nudge_manager
    pad = TaskScratchpad(session_id="test_pad_durable")
    assert pad.render_to_prompt() == ""

    pad.set_objective("Bangun REST API FastAPI", steps=["Scaffold project", "Definisikan model Pydantic", "Testing"])
    pad.add_finding("SQLite database active in WAL mode")
    pad.mark_step(0, "done")
    pad.mark_step(1, "in_progress")

    rendered = pad.render_to_prompt()
    assert "ANARA ACTIVE SCRATCHPAD" in rendered
    assert "Bangun REST API FastAPI" in rendered
    assert "[x] 1. Scaffold project" in rendered
    assert "[-] 2. Definisikan model Pydantic" in rendered
    assert "[ ] 3. Testing" in rendered
    assert "SQLite database active in WAL mode" in rendered

    # Test SQLite Persistence restoration across memory clearance
    pad2 = TaskScratchpad(session_id="test_pad_durable")
    loaded = pad2.load_from_db()
    assert loaded is True
    assert pad2.objective == "Bangun REST API FastAPI"
    assert pad2.steps[0]["status"] == "done"
    assert pad2.steps[1]["status"] == "in_progress"
    assert "SQLite database active in WAL mode" in pad2.findings

    # Test Manager restore
    manager_pad = memory_nudge_manager.get_scratchpad("test_pad_durable")
    assert manager_pad.objective == "Bangun REST API FastAPI"


def test_anara_telemetry_event_bus():
    import asyncio
    from telemetry.event_bus import TelemetryEventBus, EventType, ActivityProvenance

    bus = TelemetryEventBus()
    q = bus.subscribe("session_123")
    assert q.qsize() == 0

    events_received = []
    bus.register_hook(lambda ev: events_received.append(ev))

    async def run_emit():
        await bus.emit(
            event_type=EventType.SESSION_START,
            provenance=ActivityProvenance.AGENT_ORCHESTRATOR,
            session_id="session_123",
            trace_id="tr_abc",
            payload={"task": "build_test"}
        )

    asyncio.run(run_emit())
    assert q.qsize() == 1
    assert len(events_received) == 1
    ev = q.get_nowait()
    assert ev.event_type == EventType.SESSION_START
    assert ev.trace_id == "tr_abc"

    bus.unsubscribe("session_123", q)
    assert "session_123" not in bus._listeners


def test_anara_tool_tracer():
    import asyncio
    from telemetry.tracer import ToolTracer
    from telemetry.event_bus import telemetry_bus, EventType

    q = telemetry_bus.subscribe("tracer_test_sess")

    async def run_trace():
        tracer = ToolTracer(session_id="tracer_test_sess", trace_id="tr_trace", tool_name="read_file", args={"path": "test.txt"})
        await tracer.__aenter__()
        await asyncio.sleep(0.01)
        await tracer.__aexit__(None, None, None)

    asyncio.run(run_trace())

    ev1 = q.get_nowait()
    ev2 = q.get_nowait()

    assert ev1.event_type == EventType.TOOL_START
    assert ev1.payload["tool"] == "read_file"

    assert ev2.event_type == EventType.TOOL_COMPLETED
    assert ev2.payload["status"] == "success"
    assert ev2.payload["duration_ms"] >= 5.0

    telemetry_bus.unsubscribe("tracer_test_sess", q)
