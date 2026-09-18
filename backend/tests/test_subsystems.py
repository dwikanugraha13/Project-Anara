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


def test_anara_loop_breaker():
    from tools.loopbreaker import AnaraLoopBreaker

    lb = AnaraLoopBreaker(max_identical=4)

    # 1. Normal varied calls should not trigger stall
    stalled, msg = lb.record_and_check("read_local_file", {"file_path": "a.py"})
    assert stalled is False
    assert msg is None

    stalled, msg = lb.record_and_check("read_local_file", {"file_path": "b.py"})
    assert stalled is False

    # 2. Four identical calls in a row should trigger stall
    lb.reset()
    for i in range(3):
        stalled, msg = lb.record_and_check("read_local_file", {"file_path": "c.py", "offset": 1})
        assert stalled is False

    stalled, msg = lb.record_and_check("read_local_file", {"file_path": "c.py", "offset": 1})
    assert stalled is True
    assert "[SYSTEM REFLECTION" in msg
    assert "c.py" not in msg or "read_local_file" in msg

    # 3. Ping-pong alternation (A -> B -> A -> B -> A -> B)
    lb.reset()
    calls = [
        ("read_local_file", {"file_path": "x.py"}),
        ("grep_search_code", {"pattern": "foo"}),
        ("read_local_file", {"file_path": "x.py"}),
        ("grep_search_code", {"pattern": "foo"}),
        ("read_local_file", {"file_path": "x.py"}),
    ]
    for name, args in calls:
        stalled, msg = lb.record_and_check(name, args)
        assert stalled is False

    # 6th call completing the ping-pong cycle
    stalled, msg = lb.record_and_check("grep_search_code", {"pattern": "foo"})
    assert stalled is True
    assert "ping-pong loop" in msg


def test_unified_command_hub():
    import asyncio
    from core.channel_adapter import ChannelRequest
    from core.command_hub import handle_channel_command

    async def run_commands():
        # 1. Test /help
        req_help = ChannelRequest(text="/help", channel="telegram", channel_id="chat_1", user_id="u1")
        res_help = await handle_channel_command(req_help)
        assert res_help is not None
        assert "Daftar Perintah Universal" in res_help.text

        # 2. Test /status
        req_status = ChannelRequest(text="/status", channel="cli", channel_id="cli_1", user_id="u1")
        res_status = await handle_channel_command(req_status)
        assert res_status is not None
        assert "STATUS SISTEM ANARA" in res_status.text

        # 3. Test /skills
        req_skills = ChannelRequest(text="/skills", channel="whatsapp", channel_id="wa_1", user_id="u1")
        res_skills = await handle_channel_command(req_skills)
        assert res_skills is not None
        assert "SKILL LIBRARY ANARA" in res_skills.text

        # 4. Test /memory
        req_mem = ChannelRequest(text="/memory", channel="web", channel_id="web_1", user_id="u1")
        res_mem = await handle_channel_command(req_mem)
        assert res_mem is not None
        assert "MEMORI PERSISTEN ANARA" in res_mem.text

        # 5. Non-command request should return None
        req_normal = ChannelRequest(text="halo apa kabar", channel="telegram", channel_id="chat_1", user_id="u1")
        res_normal = await handle_channel_command(req_normal)
        assert res_normal is None

    asyncio.run(run_commands())


def test_anara_tool_decorator_and_schema_extraction():
    from tools.base import anara_tool, extract_schema_from_callable
    from tools.registry import registry
    from typing import Optional, List

    @anara_tool(
        name="unit_test_probe_tool",
        description="Probe tool for automated schema extraction verification.",
        risk="read_only",
        category="testing",
        icon="check-circle"
    )
    def probe_action(file_name: str, max_results: int = 25, filter_tags: Optional[List[str]] = None) -> bool:
        """Runs a probe test.
        :param file_name: Target file name to inspect
        :param max_results: Max items
        :param filter_tags: Optional tag filters
        """
        return True

    # 1. Verify schema extraction
    schema = extract_schema_from_callable(probe_action)
    assert schema["type"] == "OBJECT"
    assert "file_name" in schema["properties"]
    assert schema["properties"]["file_name"]["type"] == "STRING"
    assert schema["properties"]["file_name"]["description"] == "Target file name to inspect"
    assert schema["properties"]["max_results"]["type"] == "INTEGER"
    assert schema["properties"]["filter_tags"]["type"] == "ARRAY"
    assert schema["properties"]["filter_tags"]["items"]["type"] == "STRING"
    assert "file_name" in schema.get("required", [])
    assert "max_results" not in schema.get("required", [])

    # 2. Verify registration in central ToolRegistry
    tool = registry.get_tool("unit_test_probe_tool")
    assert tool is not None
    assert tool.risk == "read_only"
    assert tool.category == "testing"
    assert tool.icon == "check-circle"
    assert tool.declaration is not None
    assert tool.declaration.name == "unit_test_probe_tool"


def test_anara_vision_and_video_tools():
    import asyncio
    from tools.registry import registry
    import tools.tool_specs
    from tools.vision_tools import _tool_vision_analyze, _tool_video_analyze

    # 1. Verify tools are registered in central registry
    v_tool = registry.get_tool("vision_analyze")
    assert v_tool is not None
    assert v_tool.risk == "read_only"
    assert v_tool.category == "multimedia"

    vid_tool = registry.get_tool("video_analyze")
    assert vid_tool is not None
    assert vid_tool.risk == "read_only"

    # 2. Verify aliases resolve
    assert registry.resolve_name("analyze_image") == "vision_analyze"
    assert registry.resolve_name("analyze_video") == "video_analyze"

    # 3. Test empty input handling
    async def run_checks():
        res1 = await _tool_vision_analyze(image_path="")
        assert res1["status"] == "error"
        assert "tidak boleh kosong" in res1["message"]

        res2 = await _tool_video_analyze(video_path="")
        assert res2["status"] == "error"

        res3 = await _tool_vision_analyze(image_path="nonexistent_photo_12345.jpg")
        assert res3["status"] == "error"
        assert "tidak ditemukan" in res3["message"]

    asyncio.run(run_checks())

    # 4. Verify dynamic vision model resolution
    from tools.vision_tools import _resolve_vision_model, _resolve_fallback_vision_model
    v_model = _resolve_vision_model()
    assert isinstance(v_model, str) and len(v_model) > 0
    fb_model = _resolve_fallback_vision_model()
    assert isinstance(fb_model, str) and len(fb_model) > 0

    # 5. Verify WhatsApp quoted context extraction
    from integrations import format_whatsapp_message_context
    msg_with_quote = {
        "text": "bisa jelaskan ini?",
        "quotedText": "Server API sedang down di port 8000",
        "quotedSender": "DevOps"
    }
    formatted = format_whatsapp_message_context(msg_with_quote)
    assert "[KONTEKS: PENGGUNA MEMBALAS/MEREPLY PESAN DARI DEVOPS]" in formatted
    assert "Server API sedang down" in formatted
    assert "bisa jelaskan ini?" in formatted

    # Normal message without quote should remain intact
    normal_msg = {"text": "halo anara"}
    assert format_whatsapp_message_context(normal_msg) == "halo anara"




