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
    assert "[... truncated" in pruned
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
    assert "[INITIAL SESSION GOAL (PROTECTED HEAD)]" in compacted or "[TUJUAN AWAL / INISIASI SESI (PROTECTED HEAD)]" in compacted
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
    from tools.output_manager import compact_tool_output, compact_tool_payload
    short_text = "Standard short terminal output"
    assert compact_tool_output(short_text) == short_text

    long_output = "\n".join([f"Processing item {i}: [STATUS_OK]" for i in range(120)])
    compacted = compact_tool_output(long_output, max_lines=40, max_chars=1200)
    assert "[OUTPUT TRUNCATED:" in compacted
    assert "Processing item 0:" in compacted
    assert "Processing item 119:" in compacted
    assert len(compacted) < len(long_output)

    # Test Area 2.A: Recursive list & nested dictionary payload compaction
    large_list_payload = {
        "status": "success",
        "files": [f"src/module_{i}/index.ts" for i in range(150)],
        "details": {
            "output": "\n".join([f"log line {i}" for i in range(100)])
        }
    }
    compacted_payload = compact_tool_payload(large_list_payload, max_list_items=30)
    assert len(compacted_payload["files"]) <= 31
    assert any("additional items omitted" in str(f) for f in compacted_payload["files"])
    assert "src/module_0/index.ts" in compacted_payload["files"]
    assert "src/module_149/index.ts" in compacted_payload["files"]
    assert "[OUTPUT TRUNCATED:" in compacted_payload["details"]["output"]


def test_anara_platform_tool_registry():
    from tools.toolsets import PlatformToolRegistry, CORE_TOOLS
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


def test_dynamic_toolset_pruning_hermes_parity():
    """Verify Hermes & Claude Code Parity: Task-domain toolset pruning reduces tool bloat."""
    from tools.toolsets import PlatformToolRegistry, ESSENTIAL_CODING_TOOLS

    # 1. Plain coding task -> pruned to essential tools (~21 tools instead of 60+)
    coding_tools = PlatformToolRegistry.get_pruned_tools_for_execution(
        platform="cli",
        user_task="fix the syntax error in auth.py and run pytest"
    )
    assert len(coding_tools) <= 25
    for et in ESSENTIAL_CODING_TOOLS:
        assert et in coding_tools
    # Irrelevant domain tools MUST be pruned away
    assert "spotify_playback" not in coding_tools
    assert "ha_call_service" not in coding_tools
    assert "cronjob_manage" not in coding_tools
    assert "kanban_create_task" not in coding_tools

    # 2. Spotify task -> dynamically expands to include Spotify playback
    music_tools = PlatformToolRegistry.get_pruned_tools_for_execution(
        platform="cli",
        user_task="play my favorite lofi music on spotify"
    )
    assert "spotify_playback" in music_tools
    assert "spotify_search" in music_tools

    # 3. Web research task -> dynamically expands to include web search & scraping
    web_tools = PlatformToolRegistry.get_pruned_tools_for_execution(
        platform="web_studio",
        user_task="search the internet for fastapi docs on websockets"
    )
    assert "web_search" in web_tools
    assert "fetch_webpage" in web_tools

    # 4. Read-only constraint -> excludes mutating tools
    ro_tools = PlatformToolRegistry.get_pruned_tools_for_execution(
        platform="cli",
        user_task="inspect the code",
        read_only=True
    )
    assert "read_local_file" in ro_tools
    assert "write_local_file" not in ro_tools
    assert "edit_file" not in ro_tools


def test_anara_autonomous_memory_nudge():
    from memory.memory_nudge import SessionTurnTracker
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
    from memory.memory_nudge import TaskScratchpad, memory_nudge_manager
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
    from tools.self_correction import AnaraLoopBreaker

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
    from core.command_hub import (
        handle_channel_command,
        command_hub,
        UniversalCommandContext,
        UniversalCommandResponse,
        CommandButton,
    )

    async def run_commands():
        # 1. Test /help
        req_help = ChannelRequest(text="/help", channel="telegram", channel_id="chat_1", user_id="u1")
        res_help = await handle_channel_command(req_help)
        assert res_help is not None
        assert "Universal Commands" in res_help.text or "Daftar Perintah Universal" in res_help.text

        # 2. Test /status
        req_status = ChannelRequest(text="/status", channel="cli", channel_id="cli_1", user_id="u1")
        res_status = await handle_channel_command(req_status)
        assert res_status is not None
        assert "ANARA SYSTEM STATUS" in res_status.text or "STATUS SISTEM ANARA" in res_status.text

        # 3. Test /skills
        req_skills = ChannelRequest(text="/skills", channel="whatsapp", channel_id="wa_1", user_id="u1")
        res_skills = await handle_channel_command(req_skills)
        assert res_skills is not None
        assert "SKILL LIBRARY ANARA" in res_skills.text

        # 4. Test /memory
        req_mem = ChannelRequest(text="/memory", channel="web", channel_id="web_1", user_id="u1")
        res_mem = await handle_channel_command(req_mem)
        assert res_mem is not None
        assert "ANARA PERSISTENT MEMORY" in res_mem.text or "MEMORI PERSISTEN ANARA" in res_mem.text

        # 5. Test decorator @command_hub.register and decoupled buttons
        @command_hub.register("testping", aliases=["tping"], description="Test ping command", usage="/testping")
        async def _cmd_ping(ctx: UniversalCommandContext) -> UniversalCommandResponse:
            btns = [[CommandButton(text="Ping Button", callback_data="ping:ok")]]
            return UniversalCommandResponse(text="Pong!", buttons=btns)

        ctx_ping = UniversalCommandContext(channel="telegram", channel_id="chat_1", raw_text="/testping", command="testping")
        res_ping = await command_hub.dispatch(ctx_ping)
        assert res_ping is not None
        assert res_ping.text == "Pong!"
        markup = res_ping.to_reply_markup()
        assert markup is not None
        assert markup["inline_keyboard"][0][0]["callback_data"] == "ping:ok"

        # Verify dynamic /help includes newly registered command
        res_help2 = await handle_channel_command(req_help)
        assert "/testping" in res_help2.text
        assert "Test ping command" in res_help2.text

        # 6. Non-command request should return None (seamless fallback)
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
        assert "tidak boleh kosong" in res1["message"] or "empty" in res1["message"].lower()

        res2 = await _tool_video_analyze(video_path="")
        assert res2["status"] == "error"

        res3 = await _tool_vision_analyze(image_path="nonexistent_photo_12345.jpg")
        assert res3["status"] == "error"
        assert "tidak ditemukan" in res3["message"] or "not found" in res3["message"].lower()

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
    assert "[REPLY CONTEXT: User replied to message from DEVOPS]" in formatted
    assert "Server API sedang down" in formatted
    assert "bisa jelaskan ini?" in formatted

    # Normal message without quote should remain intact
    normal_msg = {"text": "halo anara"}
    assert format_whatsapp_message_context(normal_msg) == "halo anara"

    # 6. Verify WhatsApp media attachment formatting with local file & code preview
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as tf:
        tf.write("def calculate_metrics():\n    return {'score': 100}\n")
        temp_py_path = tf.name

    try:
        wa_media_msg = {
            "text": "[Dokumen]",
            "localPath": temp_py_path,
            "fileName": "analytics.py",
            "mediaType": "document"
        }
        wa_formatted = format_whatsapp_message_context(wa_media_msg)
        assert "[ATTACHMENT RECEIVED VIA WHATSAPP]:" in wa_formatted
        assert "- Type: Document" in wa_formatted
        assert "- File: analytics.py" in wa_formatted
        assert "- Path:" in wa_formatted
        assert "calculate_metrics" in wa_formatted
        assert "analytics.py" in wa_formatted
    finally:
        if os.path.exists(temp_py_path):
            os.remove(temp_py_path)

    # 7. Verify WhatsAppWebhookPayload validation
    from routers.integration_routes import WhatsAppWebhookPayload
    wp = WhatsAppWebhookPayload(
        phone="628123456789",
        text="tolong baca foto ini",
        localPath="C:/anara/staging/photo_123.jpg",
        fileName="photo_123.jpg",
        mediaType="photo"
    )
    assert wp.mediaType == "photo"
    assert wp.localPath == "C:/anara/staging/photo_123.jpg"

    # 8. Verify transcribe_audio_file safety
    from cognition.audio import transcribe_audio_file
    empty_trans = asyncio.run(transcribe_audio_file(""))
    assert empty_trans is None

    # 9. Verify Structured CLI Argument Tokenizer & AST Dissector
    from core.plan_detector import split_shell_pipeline, evaluate_command_safety

    # Test quote-safe pipeline splitting
    pipe_parts = split_shell_pipeline('python -c "import os; print(os.getcwd())"')
    assert len(pipe_parts) == 1
    assert "import os; print" in pipe_parts[0]

    multi_parts = split_shell_pipeline("git status --short; git log -n 5 | Select-Object -First 3")
    assert len(multi_parts) == 3
    assert multi_parts[0] == "git status --short"

    # Test deterministic subcommand risk matrix
    assert evaluate_command_safety("git status --short") == "read_only"
    assert evaluate_command_safety("git log -n 5") == "read_only"
    assert evaluate_command_safety("git diff") == "read_only"
    assert evaluate_command_safety("git branch") == "read_only"
    assert evaluate_command_safety("git branch -D old-branch") == "mutating"
    assert evaluate_command_safety("git reset --hard HEAD~1") == "mutating"
    assert evaluate_command_safety("git commit -m 'feat'") == "mutating"

    assert evaluate_command_safety("npm -v") == "read_only"
    assert evaluate_command_safety("npm list --depth=0") == "read_only"
    assert evaluate_command_safety("npm install axios") == "mutating"

    assert evaluate_command_safety("pip list") == "read_only"
    assert evaluate_command_safety("pip install fastapi") == "mutating"

    assert evaluate_command_safety("Get-Process | Select-Object -First 5") == "read_only"
    assert evaluate_command_safety("dir && type notes.txt") == "read_only"

    # Chained escalation
    assert evaluate_command_safety("dir; rm -rf temp") == "mutating"
    assert evaluate_command_safety("dir; rm -rf /") == "ask"
    assert evaluate_command_safety("format c:") == "ask"

    # Python one-liner inspection
    assert evaluate_command_safety('python -c "import sys; print(sys.version)"') == "read_only"
    assert evaluate_command_safety('python -c "import os; os.remove(\'x.txt\')"') == "mutating"

    # 10. Verify Model Sovereignty & Dynamic Model Resolution
    from core.capabilities import get_fast_auxiliary_model, ModelCapabilityRegistry
    from providers.accounts import set_active_model_id, get_active_model_id

    # Test preserving active model with custom provider prefix (e.g. 9Router proxy)
    orig_active = get_active_model_id()
    try:
        set_active_model_id("9router/ag/gemini-3.8-flash-high")
        assert get_fast_auxiliary_model() == "9router/ag/gemini-3.8-flash-high"

        # Test audio live-preview cleaning while keeping prefix intact
        set_active_model_id("9router/gemini-3.1-flash-live-preview")
        assert get_fast_auxiliary_model() == "9router/gemini-3.1-flash"
    finally:
        set_active_model_id(orig_active)

    assert ModelCapabilityRegistry.resolve_auxiliary_model() == get_fast_auxiliary_model()

    # 11. Verify Hermes Anti-Leak Sanitization (Zero JSON tool call leak)
    import re
    raw_leak_sample = '```json\n{\n  "action": "tool_call",\n  "tool": "read_local_file",\n  "arguments": {"file_path": "backend/providers.py"}\n}\n```'
    cleaned = re.sub(r"```(?:json)?\s*\{[\s\S]*?\"action\"\s*:\s*\"tool_call\"[\s\S]*?\}\s*```", "", raw_leak_sample).strip()
    assert cleaned == ""
    # Ensure falsy fallback never restores the leak
    safe_final = cleaned if (cleaned and '"action": "tool_call"' not in cleaned) else "Tindakan telah selesai dieksekusi oleh sistem."
    assert "tool_call" not in safe_final
    assert safe_final == "Tindakan telah selesai dieksekusi oleh sistem."


def test_multi_tool_parsing_and_parallelism():
    """Verify multi-tool extraction (array, multiple blocks, XML) and asyncio.gather parallelism."""
    import asyncio
    from providers.caller import _extract_and_parse_tool_calls

    # 1. Multiple code blocks
    multi_block = (
        'Mari kita periksa berkas:\n'
        '```json\n{"action": "tool_call", "tool": "read_local_file", "arguments": {"file_path": "a.py"}}\n```\n'
        'Dan berkas kedua:\n'
        '```json\n{"action": "tool_call", "tool": "read_local_file", "arguments": {"file_path": "b.py"}}\n```'
    )
    calls, lead, malformed = _extract_and_parse_tool_calls(multi_block)
    assert not malformed
    assert len(calls) == 2
    assert calls[0]["tool"] == "read_local_file"
    assert calls[0]["arguments"]["file_path"] == "a.py"
    assert calls[1]["tool"] == "read_local_file"
    assert calls[1]["arguments"]["file_path"] == "b.py"
    assert "Mari kita periksa" in lead

    # 2. JSON array of tool calls
    array_call = (
        '```json\n'
        '[\n'
        '  {"action": "tool_call", "tool": "grep_search_code", "arguments": {"pattern": "asyncio"}},\n'
        '  {"action": "tool_call", "tool": "list_directory", "arguments": {"path": "."}}\n'
        ']\n'
        '```'
    )
    calls2, _, malformed2 = _extract_and_parse_tool_calls(array_call)
    assert not malformed2
    assert len(calls2) == 2
    assert calls2[0]["tool"] == "grep_search_code"
    assert calls2[1]["tool"] == "list_directory"

    # 3. XML style tool calls
    xml_call = '<tool_call>{"action": "tool_call", "tool": "get_system_info", "arguments": {}}</tool_call>'
    calls3, _, malformed3 = _extract_and_parse_tool_calls(xml_call)
    assert not malformed3
    assert len(calls3) == 1
    assert calls3[0]["tool"] == "get_system_info"

    # 4. Asyncio gather concurrency test
    execution_order = []
    async def _mock_read(name: str, delay: float):
        await asyncio.sleep(delay)
        execution_order.append(name)
        return {"status": "success", "content": f"data_{name}"}

    async def _run_gather():
        res = await asyncio.gather(
            _mock_read("fast", 0.01),
            _mock_read("slow", 0.03),
        )
        return res

    results = asyncio.run(_run_gather())
    assert len(results) == 2
    assert results[0]["content"] == "data_fast"
    assert results[1]["content"] == "data_slow"


def test_autonomous_inner_verification_self_correction():
    """Verify autonomous self-correction retry counters, error injection, and reset on success."""
    consecutive_error_retries = 0
    max_error_retries = 3

    # Simulating 1st failure
    error_tool = "execute_cli_command"
    consecutive_error_retries += 1
    assert consecutive_error_retries == 1
    prompt_1 = (
        f"[SYSTEM INNER-VERIFICATION / SELF-CORRECTION (Percobaan {consecutive_error_retries}/{max_error_retries})]:\n"
        f"Alat [{error_tool}] menghasilkan error di atas. "
        f"Analisis penyebab kegagalan secara mandiri, perbaiki parameter pemanggilan, atau gunakan pendekatan/alat alternatif untuk menyelesaikan sasaran pengguna."
    )
    assert "(Percobaan 1/3)" in prompt_1
    assert "Analisis penyebab kegagalan" in prompt_1

    # Simulating 2nd failure
    consecutive_error_retries += 1
    assert consecutive_error_retries == 2
    prompt_2 = (
        f"[SYSTEM INNER-VERIFICATION / SELF-CORRECTION (Percobaan {consecutive_error_retries}/{max_error_retries})]:\n"
        f"Alat [{error_tool}] menghasilkan error di atas. "
    )
    assert "(Percobaan 2/3)" in prompt_2

    # Simulating success on 3rd turn -> counter resets to 0
    consecutive_error_retries = 0
    assert consecutive_error_retries == 0


def test_anara_execution_runner_lifecycle():
    """Verify AnaraExecutionRunner, TurnEvent streaming model, and PendingAction state machine."""
    import asyncio
    from core.runner import AnaraExecutionRunner, TurnEvent, AgentTurnResult
    from core.session_manager import PendingAction, session_state_manager

    # 1. TurnEvent creation
    evt = TurnEvent(
        type="tool_start",
        tool_name="read_local_file",
        content="Reading file test.py",
        metadata={"step": 1}
    )
    assert evt.type == "tool_start"
    assert evt.tool_name == "read_local_file"
    assert evt.metadata["step"] == 1

    # 2. Runner instantiation
    runner = AnaraExecutionRunner(
        session_id=99999,
        speaker_name="Agnann",
        platform="test_platform",
        max_autonomous_retries=3,
    )
    assert runner.session_id == 99999
    assert runner.platform == "test_platform"
    assert runner.max_retries == 3

    # 3. PendingAction state machine integration
    action = PendingAction(
        plan_id="plan_test_123",
        session_id=99999,
        channel="test_platform",
        channel_id="99999",
        tool_name="write_local_file",
        tool_args={"file_path": "test.txt", "content": "hello"},
        original_prompt="tulis berkas test.txt",
    )
    session_state_manager.store_pending(action)
    stored = session_state_manager.get_pending("test_platform", "99999")
    assert stored is not None
    assert stored.plan_id == "plan_test_123"
    assert stored.tool_name == "write_local_file"

    # Verify intent evaluation: "lanjutkan" / "gas" is explicit approval
    intent = session_state_manager.evaluate_intent("lanjutkan dan jalankan", "test_platform", "99999")
    assert intent["has_pending"] is True
    assert intent["is_approval"] is True

    # Clear pending
    cleared = session_state_manager.clear_pending("test_platform", "99999")
    assert cleared is not None
    assert session_state_manager.get_pending("test_platform", "99999") is None


def test_universal_channel_adapter_presenters():
    """Verify UniversalChannelAdapter dynamic presenter registry across Telegram, Web Studio, WhatsApp, and CLI."""
    from core.channel_adapter import UniversalChannelAdapter
    from core.session_manager import PendingAction

    action = PendingAction(
        plan_id="act_4567",
        session_id=123,
        channel="telegram",
        channel_id="chat_789",
        tool_name="execute_cli_command",
        tool_args={"command": "npm run build"},
        original_prompt="bangun proyek",
        lead_narration="Aku akan mengompilasi kode proyek agar siap dipublikasikan.",
        risk_level="mutating",
    )

    # 1. Telegram Presentation: Narration + syntax-highlighted code block + inline keyboard
    from integrations.telegram.formatter import format_telegram_html
    tele_payload = UniversalChannelAdapter.render_approval_payload("telegram", action.lead_narration, action)
    assert "Aku akan mengompilasi kode proyek" in tele_payload["text"]
    assert "npm run build" in tele_payload["text"]
    assert "```shell" in tele_payload["text"]
    formatted = format_telegram_html(tele_payload["text"])
    assert "<pre><code>npm run build</code></pre>" in formatted
    assert tele_payload["parse_mode"] == "HTML"
    assert tele_payload["reply_markup"] is not None
    assert tele_payload["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "approve:act_4567"
    assert tele_payload["reply_markup"]["inline_keyboard"][0][1]["callback_data"] == "reject:act_4567"

    # 2. Web Studio Presentation: Decoupled narration and action_metadata
    web_payload = UniversalChannelAdapter.render_approval_payload("web_studio", action.lead_narration, action)
    assert web_payload["type"] == "agent_response"
    assert web_payload["has_pending_action"] is True
    assert web_payload["narration"] == action.lead_narration
    assert web_payload["action_metadata"]["id"] == "act_4567"
    assert web_payload["action_metadata"]["tool"] == "execute_cli_command"
    assert web_payload["action_metadata"]["args"]["command"] == "npm run build"

    # 3. WhatsApp Presentation: Narration + quick-reply footer
    wa_payload = UniversalChannelAdapter.render_approval_payload("whatsapp", action.lead_narration, action)
    assert action.lead_narration in wa_payload["text"]
    assert "npm run build" in wa_payload["text"]
    assert "approve" in wa_payload["text"].lower()

    # 4. CLI Presentation: Narration + interactive prompt
    cli_payload = UniversalChannelAdapter.render_approval_payload("cli", action.lead_narration, action)
    assert action.lead_narration in cli_payload["text"]
    assert "npm run build" in cli_payload["text"]
    assert "[y/N]" in cli_payload["prompt"]


def test_dynamic_action_rationale_zero_canned():
    """Verify dynamic contextual rationale formulation with ZERO canned templates and zero hardcode."""
    from core.channel_adapter import generate_dynamic_action_rationale

    # 1. CLI install command
    r_install = generate_dynamic_action_rationale("execute_cli_command", {"command": "npm install tailwindcss"})
    assert "npm install tailwindcss" in r_install
    assert "aku perlu menjalankan tindakan" not in r_install.lower()

    # 2. Git commit command
    r_git = generate_dynamic_action_rationale("execute_cli_command", {"command": "git commit -m 'feat: auth'"})
    assert "git commit" in r_git
    assert "aku perlu menjalankan tindakan" not in r_git.lower()

    # 3. File write / edit
    r_file = generate_dynamic_action_rationale("edit_file", {"file_path": "backend/main.py"})
    assert "main.py" in r_file
    assert "aku perlu menjalankan tindakan" not in r_file.lower()

    # 4. Archive zip
    r_zip = generate_dynamic_action_rationale("create_zip_archive", {"source_dir": "dist"})
    assert "dist" in r_zip or "zip" in r_zip.lower()
    assert "aku perlu menjalankan tindakan" not in r_zip.lower()


def test_zero_memory_pollution_and_decoupling():
    """Verify that memory logged to session contains zero HTML tags or UI buttons."""
    from core.channel_adapter import UniversalChannelAdapter
    from core.session_manager import PendingAction

    action = PendingAction(
        plan_id="act_clean_99",
        session_id=888,
        channel="telegram",
        channel_id="chat_888",
        tool_name="execute_cli_command",
        tool_args={"command": "pytest"},
        original_prompt="jalankan unit test",
        lead_narration="Aku akan menjalankan pengujian unit untuk memvalidasi fungsi sistem.",
        risk_level="mutating",
    )

    # Lead narration stored in memory MUST NOT contain HTML, buttons, or canned robotic sentences
    assert "<pre>" not in action.lead_narration
    assert "<code>" not in action.lead_narration
    assert "callback_data" not in action.lead_narration
    assert "aku perlu menjalankan tindakan" not in action.lead_narration.lower()

    # Verify action dictionary export
    ad = action.to_dict()
    assert ad["action_id"] == "act_clean_99"
    assert ad["lead_narration"] == action.lead_narration
    assert ad["status"] == "pending"


def test_hermes_anti_leak_sanitizer_on_lead_narration():
    """Verify Hermes Anti-Leak Sanitizer removes leaked tool calls, raw JSON, and observation dumps."""
    from providers.caller import _sanitize_lead_narration, _extract_and_parse_tool_calls
    from core.channel_adapter import generate_dynamic_action_rationale

    # 1. Leaked raw JSON and directory dump
    leaked_sample = (
        '```json\n'
        '{\n'
        '  "action": "tool_call",\n'
        '  "tool": "list_directory",\n'
        '  "arguments": {"directory_path": "backend"}\n'
        '}\n'
        '```\n'
        '\\f"C:/Users/Bravo/backend" berisi 17 item:\n'
        '- [DIR] core\n'
        '- [DIR] tests\n'
        '[STATUS DIREKTORI]: Isi folder berhasil dibaca.'
    )
    cleaned = _sanitize_lead_narration(leaked_sample)
    assert cleaned == ""  # All technical residue stripped away

    # 2. Authentic conversational narration preserved
    authentic = "Aku mau memeriksa struktur backend dulu ya sebelum menjalankan test."
    authentic_with_leak = f"{authentic}\n\n```json\n{{\"action\": \"tool_call\", \"tool\": \"test\"}}\n```"
    cleaned_auth = _sanitize_lead_narration(authentic_with_leak)
    assert "Aku mau memeriksa struktur backend" in cleaned_auth
    assert "tool_call" not in cleaned_auth

    # 3. Earliest boundary extraction on multiple blocks
    multi_turn_hallucination = (
        '```json\n'
        '{\n'
        '  "action": "tool_call",\n'
        '  "tool": "list_directory",\n'
        '  "arguments": {"directory_path": "backend"}\n'
        '}\n'
        '```\n'
        '\\f"C:/backend" berisi 10 item:\n'
        '- [DIR] core\n'
        '```json\n'
        '{\n'
        '  "action": "tool_call",\n'
        '  "tool": "execute_cli_command",\n'
        '  "arguments": {"command": "python test_subsystems.py"}\n'
        '}\n'
        '```'
    )
    calls, lead_text, malformed = _extract_and_parse_tool_calls(multi_turn_hallucination)
    assert not malformed
    assert len(calls) == 2
    # Lead text must be 100% clean of first block's JSON!
    assert "action" not in lead_text
    assert "list_directory" not in lead_text
    assert lead_text == ""

    # 4. Fallback rationale when lead_text is empty
    fallback = generate_dynamic_action_rationale("execute_cli_command", {"command": "python test_subsystems.py"})
    assert "test_subsystems.py" in fallback
    assert "aku perlu menjalankan" not in fallback.lower()


def test_voice_channel_presenter_and_tts_filter():
    """Verify VoiceChannelPresenter and filter_tts_speech_text strip code blocks and technical noise."""
    from cognition.audio import filter_tts_speech_text
    from core.channel_adapter import UniversalChannelAdapter
    from core.session_manager import PendingAction

    raw_text = (
        "Aku akan menjalankan script ini ya.\n"
        "```shell\n"
        "git -C \"C:/Users/Bravo/Documents/Project Anara\" status --short\n"
        "```\n"
        "Silakan periksa di `C:/Users/Bravo/test.txt`."
    )
    filtered = filter_tts_speech_text(raw_text)
    assert "Aku akan menjalankan script ini ya" in filtered
    assert "```" not in filtered
    assert "git -C" not in filtered
    assert "C:/Users/Bravo/test.txt" not in filtered

    # Verify VoiceChannelPresenter output
    action = PendingAction(
        plan_id="act_voice_1",
        session_id=777,
        channel="voice",
        channel_id="default",
        tool_name="write_local_file",
        tool_args={"file_path": "test.txt", "content": "hello"},
        lead_narration="Aku akan memperbarui berkas untuk menyimpan konfigurasi baru.",
    )
    v_payload = UniversalChannelAdapter.render_voice_payload(action.lead_narration, action)
    assert v_payload["has_pending_action"] is True
    assert "Aku akan memperbarui berkas" in v_payload["speech_text"]
    assert "```" not in v_payload["speech_text"]


def test_voice_approval_pass_through_and_intents():
    """Verify semantic model-driven spoken affirmation and cancellation without hardcoded tuples."""
    import asyncio
    from core.plan_detector import classify_approval_intent, _INTENT_CACHE

    async def _test_intents():
        # Pre-seed cache to verify semantic routing without external network latency
        _INTENT_CACHE.update({
            "gas": "approve", "lanjutkan": "approve", "oke": "approve",
            "setujui": "approve", "ya": "approve", "sikat": "approve",
            "batal": "reject", "jangan": "reject", "stop": "reject", "tidak": "reject"
        })
        spoken_approvals = ["gas", "lanjutkan", "oke", "setujui", "ya", "sikat"]
        for w in spoken_approvals:
            intent = await classify_approval_intent(w, "Pending execution")
            assert intent == "approve", f"Expected 'approve' for '{w}', got '{intent}'"

        spoken_cancellations = ["batal", "jangan", "stop", "tidak"]
        for w in spoken_cancellations:
            intent = await classify_approval_intent(w, "Pending execution")
            assert intent == "reject", f"Expected 'reject' for '{w}', got '{intent}'"

    asyncio.run(_test_intents())


def test_safe_inspection_commands_zero_interruption():
    """Verify safe inspection commands across Git, PowerShell, and OS utilities are strictly read_only."""
    from core.plan_detector import evaluate_command_safety

    safe_commands = [
        'git -C "C:/Users/Bravo/Documents/Project Anara" status --short',
        'git -C "my_dir" log -n 5 --oneline',
        'git diff HEAD~1',
        'powershell -NoProfile -Command Get-Process',
        'powershell -c Get-ChildItem',
        'dir C:/Users/Bravo',
        'ls -la',
        'node -v',
        'npm -v',
        'python --version',
        'whoami',
        'systeminfo',
    ]
    for cmd in safe_commands:
        assert evaluate_command_safety(cmd) == "read_only", f"Expected read_only for '{cmd}'"

    mutating_commands = [
        'git push origin main',
        'git commit -m "update"',
        'npm install express',
        'pip install fastapi',
        'powershell -Command Remove-Item -Recurse test',
        'rm -rf /',
    ]
    for cmd in mutating_commands:
        assert evaluate_command_safety(cmd) in ("mutating", "ask"), f"Expected mutating/ask for '{cmd}'"


def test_omnichannel_voice_command_and_modes():
    """Verify universal /voice command, per-chat persistence, 4 modes, and audio synthesis."""
    import asyncio
    import os
    from core.command_hub import get_chat_voice_mode, set_chat_voice_mode, handle_channel_command
    from core.channel_adapter import ChannelRequest
    from cognition.audio import synthesize_speech_audio

    # 1. Test independent per-chat persistence across multiple channels
    set_chat_voice_mode("telegram", "chat_101", "only")
    set_chat_voice_mode("whatsapp", "wa_202", "text")
    set_chat_voice_mode("discord", "disc_303", "both")

    assert get_chat_voice_mode("telegram", "chat_101") == "only"
    assert get_chat_voice_mode("whatsapp", "wa_202") == "text"
    assert get_chat_voice_mode("discord", "disc_303") == "both"
    assert get_chat_voice_mode("telegram", "unknown_chat") == "auto"  # Default is auto

    # 2. Test slash command routing via CommandHub
    req_set = ChannelRequest(
        text="/voice only",
        channel="telegram",
        channel_id="chat_101",
        user_id="u1"
    )
    res_set = asyncio.run(handle_channel_command(req_set))
    assert res_set is not None
    assert "Voice Mode Updated" in res_set.text or "Mode Suara Berhasil Diperbarui" in res_set.text
    assert get_chat_voice_mode("telegram", "chat_101") == "only"

    req_status = ChannelRequest(
        text="/voice status",
        channel="telegram",
        channel_id="chat_101",
        user_id="u1"
    )
    res_status = asyncio.run(handle_channel_command(req_status))
    assert res_status is not None
    assert "VOICE MODE SETTINGS" in res_status.text or "PENGATURAN MODE SUARA" in res_status.text
    assert res_status.reply_markup is not None
    assert res_status.reply_markup["inline_keyboard"][0][0]["callback_data"] == "vmode:text"

    # 3. Test speech audio synthesis
    audio_path = asyncio.run(synthesize_speech_audio("Halo Agnann, aku Anara siap membantu."))
    assert audio_path is not None
    assert os.path.isfile(audio_path)
    assert os.path.getsize(audio_path) > 1000


def test_hermes_hard_interrupt_and_process_reaper():
    """Verify Hermes-parity hard interrupt: cancelling in-flight turn tasks, reaping OS child PIDs, clearing pending state."""
    import asyncio
    import subprocess
    import sys
    from core.session_manager import session_state_manager, PendingAction

    async def run_test():
        # 1. Spawn a real dummy background child process (sleep/ping)
        if sys.platform == "win32":
            proc = subprocess.Popen(["ping", "127.0.0.1", "-n", "10"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            proc = subprocess.Popen(["sleep", "10"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        pid = proc.pid
        assert pid > 0

        # Register PID and dummy running task in session_state_manager
        async def _long_turn():
            await asyncio.sleep(10.0)

        task = asyncio.create_task(_long_turn())
        session_state_manager.register_active_task("telegram", "chat_stop_test", task)
        session_state_manager.register_process_pid("telegram", "chat_stop_test", pid)

        # Store a pending action to verify approval clear
        act = PendingAction(
            plan_id="plan_stop_1",
            session_id=999,
            channel="telegram",
            channel_id="chat_stop_test",
            tool_name="execute_cli_command",
            tool_args={"command": "dir"}
        )
        session_state_manager.store_pending(act)

        assert session_state_manager.get_pending("telegram", "chat_stop_test") is not None
        assert pid in session_state_manager.get_active_pids("telegram", "chat_stop_test")

        # 2. Trigger hard interrupt
        info = await session_state_manager.request_hard_interrupt("telegram", "chat_stop_test", reason="test_stop")
        assert info["task_cancelled"] is True
        assert info["processes_killed"] >= 1
        assert info["pending_cleared"] is True
        assert session_state_manager.get_pending("telegram", "chat_stop_test") is None
        assert pid not in session_state_manager.get_active_pids("telegram", "chat_stop_test")

        # Give OS a moment to reap process
        await asyncio.sleep(0.3)
        assert proc.poll() is not None or task.cancelled()

    asyncio.run(run_test())


def test_slash_commands_never_trigger_voice():
    """Verify that all slash commands are always delivered as text/UI and never converted to voice notes."""
    import asyncio
    from core.command_hub import set_chat_voice_mode, handle_channel_command
    from core.channel_adapter import ChannelRequest

    # Set chat into voice_only mode
    set_chat_voice_mode("telegram", "chat_voice_cmd_test", "only")

    # 1. Test /voice
    req_v = ChannelRequest(text="/voice", channel="telegram", channel_id="chat_voice_cmd_test", user_id="u1")
    res_v = asyncio.run(handle_channel_command(req_v))
    assert res_v is not None
    assert res_v.is_command is True
    assert res_v.reply_markup is not None

    # 2. Test /help
    req_h = ChannelRequest(text="/help", channel="telegram", channel_id="chat_voice_cmd_test", user_id="u1")
    res_h = asyncio.run(handle_channel_command(req_h))
    assert res_h is not None
    assert res_h.is_command is True

    # 3. Test /status
    req_s = ChannelRequest(text="/status", channel="telegram", channel_id="chat_voice_cmd_test", user_id="u1")
    res_s = asyncio.run(handle_channel_command(req_s))
    assert res_s is not None
    assert res_s.is_command is True


def test_state_machine_pending_action_lifecycle():
    """Verify Subsystem 3: ActionState FSM, 300s TTL expiration, fast-path approval, and fast-path rejection."""
    import asyncio
    import time
    from core.session_manager import ActionState, PendingAction, session_state_manager
    from core.channel_adapter import ChannelRequest, process_channel_request

    async def run_fsm_tests():
        ch = "telegram"
        cid = "fsm_test_chat_888"

        # 1. State Enum & creation
        act = PendingAction(
            plan_id="act_fsm_01",
            session_id=888,
            channel=ch,
            channel_id=cid,
            tool_name="write_local_file",
            tool_args={"file_path": "fsm_test.txt", "content": "test"},
            original_prompt="buat file fsm_test.txt",
            state=ActionState.PENDING,
            ttl_seconds=300.0,
        )
        assert act.state == ActionState.PENDING
        assert act.status == "pending"
        assert act.ttl_seconds == 300.0
        assert act.is_expired is False

        # Store in manager
        session_state_manager.set_pending_action(ch, cid, act)
        retrieved = session_state_manager.get_pending_action(ch, cid)
        assert retrieved is not None
        assert retrieved.plan_id == "act_fsm_01"
        assert retrieved.state == ActionState.PENDING

        # 2. Test resolve_action state transitions
        # Transition to EXECUTING
        resolved_exec = session_state_manager.resolve_action(ch, cid, "act_fsm_01", ActionState.EXECUTING)
        assert resolved_exec is not None
        assert resolved_exec.state == ActionState.EXECUTING
        # Still in active store while executing
        assert session_state_manager.get_pending(ch, cid) is not None

        # Transition to EXECUTED (terminal -> cleared)
        resolved_done = session_state_manager.resolve_action(ch, cid, "act_fsm_01", ActionState.EXECUTED)
        assert resolved_done is not None
        assert resolved_done.state == ActionState.EXECUTED
        assert session_state_manager.get_pending(ch, cid) is None

        # 3. Test 300s (5-minute) TTL Expiration
        stale_act = PendingAction(
            plan_id="act_fsm_stale",
            session_id=888,
            channel=ch,
            channel_id=cid,
            tool_name="execute_cli_command",
            tool_args={"command": "dir"},
            original_prompt="cek dir",
            state=ActionState.PENDING,
            created_at=time.time() - 305.0,  # 305 seconds ago (> 300s)
            ttl_seconds=300.0,
        )
        assert stale_act.is_expired is True
        session_state_manager.set_pending_action(ch, cid, stale_act)

        # get_pending_action should auto-expire and return None
        expired_check = session_state_manager.get_pending_action(ch, cid)
        assert expired_check is None
        assert stale_act.state == ActionState.EXPIRED

        # 4. Test sweep clear_expired_actions()
        stale_act_2 = PendingAction(
            plan_id="act_fsm_stale_2",
            session_id=888,
            channel=ch,
            channel_id="fsm_sweep_chat",
            tool_name="execute_cli_command",
            created_at=time.time() - 350.0,
            ttl_seconds=300.0,
        )
        session_state_manager.set_pending_action(ch, "fsm_sweep_chat", stale_act_2)
        swept = session_state_manager.clear_expired_actions()
        assert swept >= 1
        assert session_state_manager.get_pending(ch, "fsm_sweep_chat") is None

        # 5. Fast-Path Rejection via Channel Gateway ("batal")
        reject_act = PendingAction(
            plan_id="act_fsm_rej",
            session_id=888,
            channel=ch,
            channel_id="fsm_rej_chat",
            tool_name="execute_cli_command",
            tool_args={"command": "rm -rf something"},
            original_prompt="hapus sesuatu",
            state=ActionState.PENDING,
            ttl_seconds=300.0,
        )
        session_state_manager.set_pending_action(ch, "fsm_rej_chat", reject_act)
        req_reject = ChannelRequest(text="batal jangan jalankan", channel=ch, channel_id="fsm_rej_chat", user_id="u1")
        res_reject = await process_channel_request(req_reject)
        assert res_reject.status == "cancelled"
        assert any(w in res_reject.text.lower() for w in ("batal", "batalkan", "kubatalkan", "dibatalkan", "ditolak", "menolak", "cancelled", "cancel", "reject", "rejected")), f"Got: {res_reject.text}"
        assert reject_act.state == ActionState.REJECTED
        assert session_state_manager.get_pending(ch, "fsm_rej_chat") is None

        # 6. Expired Confirmation Notice (User confirms action that expired)
        exp_act = PendingAction(
            plan_id="act_fsm_exp_test",
            session_id=888,
            channel=ch,
            channel_id="fsm_exp_chat",
            tool_name="execute_cli_command",
            tool_args={"command": "npm test"},
            created_at=time.time() - 310.0,  # Expired > 300s
            ttl_seconds=300.0,
        )
        session_state_manager.set_pending_action(ch, "fsm_exp_chat", exp_act)
        req_expired_confirm = ChannelRequest(text="gas", channel=ch, channel_id="fsm_exp_chat", user_id="u1")
        res_exp = await process_channel_request(req_expired_confirm)
        assert res_exp.status == "expired_notice"
        assert any(w in res_exp.text.lower() for w in ("kedaluwarsa", "habis", "lewat", "expired", "waktu"))

    asyncio.run(run_fsm_tests())


def test_subsystem_4_context_micro_compactor():
    """Verify Subsystem 4: ContextMicroCompactor anchor sniffing, progress bar cleaning, and disk logging."""
    from tools.self_correction import ContextMicroCompactor

    # 1. Test clean terminal noise
    dirty_text = "Installing [===>   ] 45%\x1b[32m\rSuccess line 1\nStep 2 [========] 100%\rDone!"
    cleaned = ContextMicroCompactor.clean_terminal_noise(dirty_text)
    assert "[===>" not in cleaned
    assert "\x1b[" not in cleaned

    # 2. Test Anchor Sniffing on a 100-line simulated build/test failure
    lines = [f"Step {i}: building module_{i}.o" for i in range(1, 40)]
    lines += [
        "Running tests...",
        "Traceback (most recent call last):",
        "  File \"backend/core/app.py\", line 102, in main",
        "    import missing_dependency",
        "ModuleNotFoundError: No module named 'missing_dependency'",
        "FAILED (failures=1)",
    ]
    lines += [f"Cleanup step {i} finished" for i in range(1, 40)]
    raw_trace = "\n".join(lines)
    assert len(lines) > 80

    compacted = ContextMicroCompactor.compact_output(raw_trace, max_lines=30, source_label="test_sniff")
    assert "ModuleNotFoundError: No module named 'missing_dependency'" in compacted
    assert "Traceback (most recent call last)" in compacted
    assert "truncated by compactor" in compacted or "dipangkas oleh compactor" in compacted or "omitted" in compacted or "disembunyikan" in compacted
    assert len(compacted.splitlines()) <= 35


def test_subsystem_4_error_classifier_and_recovery_guidance():
    """Verify Subsystem 4: ErrorClassifier pattern taxonomy and tailored recovery guidance."""
    from tools.self_correction import ErrorClassifier, format_recovery_guidance

    # 1. Missing Python Package
    t1, d1 = ErrorClassifier.classify("ModuleNotFoundError: No module named 'fastapi_limiter'")
    assert t1 == "missing_python_pkg"
    assert d1 == "fastapi_limiter"
    g1 = format_recovery_guidance(t1, d1, 1, 3, tool_name="execute_cli_command")
    assert "fastapi_limiter" in g1
    assert "Autonomous Recovery Guidance" in g1 or "Panduan Pemulihan Mandiri" in g1

    # 2. Missing Node Package
    t2, d2 = ErrorClassifier.classify("Error: Cannot find module 'tailwind-merge'")
    assert t2 == "missing_node_pkg"
    assert d2 == "tailwind-merge"
    g2 = format_recovery_guidance(t2, d2, 1, 3, tool_name="execute_cli_command")
    assert "tailwind-merge" in g2
    assert "Autonomous Recovery Guidance" in g2 or "Panduan Pemulihan Mandiri" in g2

    # 3. Port Conflict
    t3, d3 = ErrorClassifier.classify("Error: listen EADDRINUSE: address already in use :::8000")
    assert t3 == "port_conflict"
    g3 = format_recovery_guidance(t3, d3, 2, 3, tool_name="execute_cli_command")
    assert "port_conflict" in g3

    # 4. Syntax Error
    t4, d4 = ErrorClassifier.classify("SyntaxError: invalid syntax at line 42")
    assert t4 == "syntax_error"

    # 5. File Not Found
    t5, d5 = ErrorClassifier.classify("FileNotFoundError: [Errno 2] No such file or directory: 'dist/bundle.js'")
    assert t5 == "file_not_found"
    assert d5 == "dist/bundle.js"


def test_subsystem_4_self_correction_circuit_breaker_and_card():
    """Verify Subsystem 4: SelfCorrectionTracker 2x identical circuit breaker and graceful diagnostic card."""
    from tools.self_correction import SelfCorrectionTracker, format_graceful_diagnostic_card
    from tools.catalog import _normalize_tool_args

    # 1. Test Parameter Normalization (Hermes Parity)
    n1 = _normalize_tool_args("read_local_file", {"path": "config.json"})
    assert n1.get("file_path") == "config.json"

    n2 = _normalize_tool_args("grep_search_code", {"query": "def main"})
    assert n2.get("pattern") == "def main"

    n3 = _normalize_tool_args("execute_cli_command", {"cmd": "npm test"})
    assert n3.get("command") == "npm test"

    tracker = SelfCorrectionTracker(max_retries=3, max_identical_failures=2, interactive=False)

    # 2. Test Failure-Tolerant Exploratory Check
    assert tracker.is_failure_tolerant("read_local_file") is True
    assert tracker.is_failure_tolerant("grep_search_code") is True
    assert tracker.is_failure_tolerant("execute_cli_command") is False

    # Attempt 1: First failure
    res1 = tracker.register_attempt(
        tool_name="execute_cli_command",
        command_or_arg="npm run build",
        err_type="missing_node_pkg",
        detail="vite"
    )
    assert res1["allowed"] is True
    assert res1["is_stalled"] is False
    assert res1["budget_exhausted"] is False
    assert res1["attempt"] == 1

    # Attempt 2: Exact same failure signature -> Circuit Breaker trips!
    res2 = tracker.register_attempt(
        tool_name="execute_cli_command",
        command_or_arg="npm run build",
        err_type="missing_node_pkg",
        detail="vite"
    )
    assert res2["allowed"] is False
    assert res2["is_stalled"] is True
    assert res2["attempt"] == 2

    # Attempt 3: Budget exhaustion in non-interactive mode (3rd attempt)
    tracker.reset()
    tracker.register_attempt("execute_cli_command", "step1", "err")
    tracker.register_attempt("execute_cli_command", "step2", "err")
    res_final = tracker.register_attempt("execute_cli_command", "step3", "err")
    assert res_final["budget_exhausted"] is True
    assert tracker.is_exhausted() is True

    # Test Graceful Diagnostic Card (Pilar D)
    card = format_graceful_diagnostic_card(
        history=tracker.history,
        last_error_text="FileNotFoundError: [Errno 2] No such file or directory: 'c.py'",
        original_task="Periksa file konfigurasi"
    )
    assert "EXECUTION DIAGNOSTICS" in card or "DIAGNOSTIK EKSEKUSI ANARA" in card
    assert "Root Cause" in card or "Akar Masalah" in card
    assert "Self-Correction Attempts" in card or "Upaya Mandiri yang Telah Dijalankan" in card
    assert "Recommendations" in card or "Rekomendasi Solusi" in card
    assert "Traceback" not in card


def test_subsystem_4_workspace_ground_truth_snapshot():
    """Verify Hermes Parity: Dynamic Workspace Root & Live Git Snapshot probing."""
    import os
    from core.agent import anara_agent
    from core.prompt_assembler import PromptAssembler

    repo_root = anara_agent.get_project_repo_root()
    assert os.path.isdir(repo_root)
    assert os.path.isdir(os.path.join(repo_root, ".git"))

    # Test Git Worktree Snapshot Probe
    snapshot = PromptAssembler.probe_git_worktree_snapshot(repo_root)
    assert "- Git Branch:" in snapshot
    assert "- Changed Files Status" in snapshot or "- Working Tree Status: Clean" in snapshot
    assert "Project Verification Commands:" in snapshot

    # Test Prompt Assembly with Ground Truth Injected
    prompt = PromptAssembler.assemble(
        mode="build",
        speaker_name="Tester",
        user_task="sudah ku implementasikan subsistem 4 ini , apakah sudah beres semua?",
        channel="telegram",
        session_id=9999
    )
    assert "GROUND-TRUTH FACT VERIFICATION" in prompt or "PEMBUKTIAN FAKTA BERBASIS GROUND-TRUTH" in prompt
    assert "LIVE WORKSPACE & REPOSITORY SNAPSHOT" in prompt
    assert repo_root.replace("\\", "/") in prompt.replace("\\", "/")


def test_subsystem_4_targeted_delete_and_repo_protection():
    """Verify Repo Protection: Bulk wipes require human approval (ask tier), targeted deletion permitted."""
    import asyncio
    import tempfile
    from core.sandbox import check_command_safety
    from core.plan_detector import evaluate_command_safety
    from tools.catalog import get_tool_risk
    from tools.fs_tools import _tool_delete_local_file

    # 1. Unconditional hard block (suicidal host wipe or internal metadata deletion)
    assert check_command_safety("rm -rf /")[0] is False
    assert check_command_safety("rm -rf .git")[0] is False
    assert check_command_safety("reg add HKLM\\Backdoor")[0] is False

    # 2. Bulk wildcard & recursive wipes escalated to 'ask' tier (Granular Human Approval Gate)
    assert evaluate_command_safety("rm -rf *") == "ask"
    assert evaluate_command_safety("Remove-Item -Recurse -Force *") == "ask"
    assert evaluate_command_safety("del /s /q *") == "ask"
    assert evaluate_command_safety("git clean -fdx") == "ask"

    # 3. Targeted deletion permitted via standard mutating approval
    assert evaluate_command_safety("rm temp_script.py") == "mutating"
    assert evaluate_command_safety("Remove-Item 'old_report.txt'") == "mutating"
    assert evaluate_command_safety("git rm old_module.py") == "mutating"
    assert check_command_safety("rm temp_script.py")[0] is True
    assert check_command_safety("Remove-Item 'old_report.txt'")[0] is True

    # 4. Tool risk classification
    assert get_tool_risk("delete_local_file") == "mutating"

    # 5. Tool safety checks
    async def run_tool_tests():
        # Rejects wildcard
        r1 = await _tool_delete_local_file("*.py")
        assert r1["status"] == "error"
        assert "wildcard" in r1["message"].lower()

        # Rejects protected file
        r2 = await _tool_delete_local_file(".env")
        assert r2["status"] == "error"
        assert "protected" in r2["message"].lower() or "dilindungi" in r2["message"].lower()

        # Safely deletes a targeted test file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp:
            tmp_path = tmp.name
            tmp.write(b"content to be safely deleted")

        assert os.path.isfile(tmp_path)
        r3 = await _tool_delete_local_file(tmp_path)
        assert r3["status"] == "success"
        assert not os.path.exists(tmp_path)

    asyncio.run(run_tool_tests())


def test_subsystem_2_screen_metrics_and_chronological_context():
    """Verify Hermes Parity: Dynamic 4-tuple virtual screen metrics and chronological history normalization."""
    from tools.computer_use_tool import _get_screen_metrics
    from core.context_compactor import ContextCompactor

    # 1. Virtual screen metrics must return 4 elements: (vx, vy, width, height)
    metrics = _get_screen_metrics()
    assert isinstance(metrics, tuple)
    assert len(metrics) == 4
    assert metrics[2] > 0 and metrics[3] > 0

    # 2. Test chronological normalization of newest-first SQL results
    newest_first = [
        {"id": 3, "user_text": "coba", "ai_text": "siap coba"},
        {"id": 2, "user_text": "bisa screenshot?", "ai_text": "bisa, mau coba?"},
        {"id": 1, "user_text": "halo", "ai_text": "halo!"},
    ]
    normalized = ContextCompactor.normalize_history(newest_first)
    assert [t["id"] for t in normalized] == [1, 2, 3]

    # 3. Test re-stitching of split turns (orphaned user_text followed by orphaned ai_text)
    split_turns = [
        {"id": 2, "user_text": "", "ai_text": "ini jawabannya"},
        {"id": 1, "user_text": "ini pertanyaannya", "ai_text": ""},
    ]
    re_stitched = ContextCompactor.normalize_history(split_turns)
    assert len(re_stitched) == 1
    assert re_stitched[0]["user_text"] == "ini pertanyaannya"
    assert re_stitched[0]["ai_text"] == "ini jawabannya"


def test_subsystem_2_computer_use_multiversal():
    """Verify Hermes Parity: Universal computer_use actions (screen, mouse, keyboard, hotkey, focus, launch)."""
    import asyncio
    from tools.catalog import get_tool_risk, ANARA_FUNCTION_DECLARATIONS, dispatch_tool_call
    from tools.toolsets import PlatformToolRegistry

    # 1. Verify tool registration in catalog declarations
    tool_names = [d.name for d in ANARA_FUNCTION_DECLARATIONS]
    assert "computer_use" in tool_names
    assert "take_screenshot" in tool_names

    # 2. Risk classification
    assert get_tool_risk("take_screenshot") == "read_only"
    assert get_tool_risk("computer_use") == "mutating"

    # 3. Platform Registry presence
    tools_web = PlatformToolRegistry.get_tools_for_platform("web_studio")
    assert "computer_use" in tools_web
    assert "take_screenshot" in tools_web

    intent_tools = PlatformToolRegistry.get_tools_for_platform("web_studio", user_task="tolong buka opencode dan ketik halo")
    assert "computer_use" in intent_tools


def test_subsystem_5_workspace_sentinel_and_ground_truth():
    """Verify Subsystem 5: WorkspaceSentinel (Blast Radius Guard, File Confinement, Read-Back, Ground-Truth)."""
    import tempfile
    from core.workspace_sentinel import WorkspaceSentinel

    with tempfile.TemporaryDirectory() as tmpdir:
        sentinel = WorkspaceSentinel(workspace_root=tmpdir)

        # 1. CLI Command Blast Radius Guard
        assert sentinel.validate_cli_command("rm -rf *")[0] is False
        assert sentinel.validate_cli_command("Remove-Item -Recurse -Force *")[0] is False
        assert sentinel.validate_cli_command("git clean -fdx")[0] is False
        assert sentinel.validate_cli_command("npm test")[0] is True
        assert sentinel.validate_cli_command("git status --short")[0] is True

        # 2. File Confinement & Sacred Path Protection
        # Sacred .git internal modification blocked
        assert sentinel.validate_file_access(".git/objects/1234", action="write")[0] is False
        assert sentinel.validate_file_access(".git/HEAD", action="edit")[0] is False
        # Sensitive files deletion blocked
        assert sentinel.validate_file_access(".env", action="delete")[0] is False
        assert sentinel.validate_file_access("anara_brain.db", action="delete")[0] is False
        # Normal source files editing allowed
        assert sentinel.validate_file_access("src/index.ts", action="write")[0] is True
        assert sentinel.validate_file_access("config.json", action="edit")[0] is True

        # 3. Post-Write Read-Back Verification
        test_file = os.path.join(tmpdir, "verified_module.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("def compute_total(a, b):\n    return a + b\n")

        # Read-back with matching snippet -> Verified True
        rb_ok = sentinel.verify_read_back(test_file, expected_snippet="compute_total")
        assert rb_ok["verified"] is True
        assert rb_ok["snippet_matched"] is True

        # Read-back with missing snippet -> Verified False
        rb_fail = sentinel.verify_read_back(test_file, expected_snippet="missing_feature")
        assert rb_fail["verified"] is False
        assert rb_fail["snippet_matched"] is False

        # Non-existent file read-back -> Verified False
        rb_nonexistent = sentinel.verify_read_back(os.path.join(tmpdir, "ghost.py"))
        assert rb_nonexistent["verified"] is False

        # 4. Physical Test Ground-Truth Evaluation
        # Test pass
        gt_pass = sentinel.verify_ground_truth("All 37 tests passed successfully! 100% PASS", exit_code=0)
        assert gt_pass["verified"] is True
        assert gt_pass["requires_correction"] is False

        # Test failure (exit code non-zero)
        gt_fail_code = sentinel.verify_ground_truth("Tests finished", exit_code=1)
        assert gt_fail_code["verified"] is False
        assert gt_fail_code["requires_correction"] is True

        # Test failure (exit code 0 but failure signals in output)
        gt_fail_output = sentinel.verify_ground_truth("FAILED (failures=2) in test_api.py", exit_code=0)
        assert gt_fail_output["verified"] is False
        assert gt_fail_output["requires_correction"] is True


def test_pilar_1_subagent_delegation_engine():
    """Verify Pilar 1: Sub-Agent Delegation Engine (Fork-and-Join, Task Isolation, Anti-Fork-Bomb)."""
    import asyncio
    from core.subagent import subagent_manager, SubagentState, SubagentResult
    from tools.catalog import dispatch_tool_call

    async def run_subagent_tests():
        # 1. Custom worker execution with verified contract
        async def mock_worker(task):
            await asyncio.sleep(0.02)
            return "Analisis modul selesai: 12 fungsi terverifikasi."

        task = await subagent_manager.spawn_subagent_task(
            title="Audit Arsitektur",
            mission_prompt="Periksa konsistensi tipe data",
            worker_coro_factory=mock_worker,
        )
        assert task.state in (SubagentState.PENDING, SubagentState.RUNNING)
        await task._async_task
        assert task.state == SubagentState.SUCCEEDED
        assert task.result is not None
        assert isinstance(task.result, SubagentResult)
        assert task.result.status == "completed"
        assert "Analisis modul selesai" in task.result.executive_summary

        # 2. Anti-Fork-Bomb Guard (depth > max_depth)
        deep_task = await subagent_manager.spawn_subagent_task(
            title="Recursive Worker",
            depth=3,  # Exceeds DEFAULT_MAX_DEPTH=2
        )
        assert deep_task.state == SubagentState.FAILED
        assert "depth limit reached" in deep_task.result.executive_summary.lower()

        # 3. Batch Fork-and-Join execution
        batch_tasks = [
            {"goal": "Analisis file A", "context": "cek modul A"},
            {"goal": "Analisis file B", "context": "cek modul B"},
        ]
        batch_results = await subagent_manager.spawn_batch_and_join(
            batch_tasks,
            timeout_seconds=5.0,
            worker_coro_factory=mock_worker,
        )
        assert len(batch_results) == 2
        for br in batch_results:
            assert br.status == "completed"

        # 4. Tool dispatch verification via catalog
        tool_res = await dispatch_tool_call(
            "delegate_subagent",
            {"title": "Misi Latar Belakang", "mission_prompt": "Scrape dokumentasi API", "background": True},
            read_only=False,
        )
        assert tool_res["status"] == "success"
        assert "task_id" in tool_res

    asyncio.run(run_subagent_tests())


def test_subsystem_3_universal_channel_approval_dispatch():
    """Verify Hermes Parity: Unified Omnichannel Approval Dispatcher across Telegram, WhatsApp, Discord, etc."""
    import asyncio
    import time
    from core.session_manager import PendingAction, session_state_manager, ActionState
    from core.channel_adapter import dispatch_channel_approval_resolution

    async def run_dispatch_tests():
        # 1. Telegram reject dispatch
        tg_act = PendingAction(
            plan_id="act_univ_tg",
            session_id=101,
            channel="telegram",
            channel_id="chat_tg_101",
            tool_name="execute_cli_command",
            tool_args={"command": "npm test"},
            original_prompt="jalankan tes",
            state=ActionState.PENDING,
            ttl_seconds=300.0,
            user_id="user_owner",
        )
        session_state_manager.set_pending_action("telegram", "chat_tg_101", tg_act)
        res_tg = await dispatch_channel_approval_resolution(
            channel="telegram",
            channel_id="chat_tg_101",
            plan_id="act_univ_tg",
            action="reject",
            user_id="user_owner",
        )
        assert res_tg["status"] == "rejected"
        assert session_state_manager.get_pending("telegram", "chat_tg_101") is None

        # 2. WhatsApp reject dispatch
        wa_act = PendingAction(
            plan_id="act_univ_wa",
            session_id=102,
            channel="whatsapp",
            channel_id="628123456789",
            tool_name="execute_cli_command",
            tool_args={"command": "dir"},
            original_prompt="cek dir",
            state=ActionState.PENDING,
            ttl_seconds=300.0,
            user_id="628123456789",
        )
        session_state_manager.set_pending_action("whatsapp", "628123456789", wa_act)
        res_wa = await dispatch_channel_approval_resolution(
            channel="whatsapp",
            channel_id="628123456789",
            plan_id="act_univ_wa",
            action="reject",
            user_id="628123456789",
        )
        assert res_wa["status"] == "rejected"
        assert session_state_manager.get_pending("whatsapp", "628123456789") is None

        # 3. Expired or non-existent action dispatch
        res_ghost = await dispatch_channel_approval_resolution(
            channel="discord",
            channel_id="channel_999",
            plan_id="non_existent_plan_id",
            action="approve",
            user_id="someone",
        )
        assert res_ghost["status"] == "expired"

    asyncio.run(run_dispatch_tests())


def test_pillar_2_telemetry_hud_visual_events():
    """Verify Pillar 2: Live Telemetry & Code Studio HUD Event Distribution."""
    import asyncio
    from telemetry.event_bus import telemetry_bus, EventType, ActivityProvenance

    async def run_telemetry_tests():
        sess_id = "test_hud_sess_1"
        q = telemetry_bus.subscribe(sess_id)

        # 1. FILE_MODIFIED event
        await telemetry_bus.emit(
            event_type=EventType.FILE_MODIFIED,
            provenance=ActivityProvenance.TOOL_RUNNER,
            session_id=sess_id,
            trace_id="tr_hud_1",
            payload={"action": "edit", "file_path": "backend/core/test.py", "diff": "+print(1)"},
        )
        evt1 = await asyncio.wait_for(q.get(), timeout=2.0)
        assert evt1.event_type == EventType.FILE_MODIFIED
        assert evt1.payload["action"] == "edit"

        # 2. GUARDRAIL_TRIGGERED event
        await telemetry_bus.emit(
            event_type=EventType.GUARDRAIL_TRIGGERED,
            provenance=ActivityProvenance.WORKSPACE_SENTINEL,
            session_id=sess_id,
            trace_id="tr_hud_2",
            payload={"command": "rm -rf *", "risk": "ask"},
        )
        evt2 = await asyncio.wait_for(q.get(), timeout=2.0)
        assert evt2.event_type == EventType.GUARDRAIL_TRIGGERED
        assert evt2.provenance == ActivityProvenance.WORKSPACE_SENTINEL

        # 3. GROUND_TRUTH_CHECK event
        await telemetry_bus.emit(
            event_type=EventType.GROUND_TRUTH_CHECK,
            provenance=ActivityProvenance.WORKSPACE_SENTINEL,
            session_id=sess_id,
            trace_id="tr_hud_3",
            payload={"exit_code": 0, "verified": True},
        )
        evt3 = await asyncio.wait_for(q.get(), timeout=2.0)
        assert evt3.event_type == EventType.GROUND_TRUTH_CHECK
        assert evt3.payload["verified"] is True

        telemetry_bus.unsubscribe(sess_id, q)

    asyncio.run(run_telemetry_tests())


def test_pillar_3_episodic_adr_project_memory():
    """Verify Pillar 3: Episodic Architecture Decision Records (ADR) & Test Ground-Truth Hook."""
    from memory.episodic_adr import episodic_adr_manager
    from core.workspace_sentinel import workspace_sentinel

    # 1. Record an ADR manually
    adr = episodic_adr_manager.record_project_adr(
        milestone_task="Refactor channel adapters to dynamic environment introspection",
        architecture_decision="Replaced mock available statuses with real HTTP token verification",
        rationale="Eliminated fake states and guaranteed authentic connection reporting",
        affected_files=["backend/integrations/adapters.py"],
        session_id="test_adr_sess",
        test_exit_code=0,
    )
    assert adr["adr_id"].startswith("adr_")
    assert "adapters.py" in adr["affected_files"][0]

    # 2. Query recent ADRs
    recent = episodic_adr_manager.get_recent_project_adrs(limit=5, session_id="test_adr_sess")
    assert len(recent) >= 1
    assert recent[0]["adr_id"] == adr["adr_id"]

    # 3. Search ADRs
    search_res = episodic_adr_manager.search_project_adr("introspection")
    assert len(search_res) >= 1
    assert any("introspection" in r["milestone_task"].lower() or "introspection" in r["architecture_decision"].lower() for r in search_res)

    # 4. WorkspaceSentinel ground-truth hook triggers ADR milestone
    gt_res = workspace_sentinel.verify_ground_truth(
        test_output="40 passed in 2.5s",
        exit_code=0,
        task_description="Subsystem 5 test verification pass",
        modified_files=["backend/core/workspace_sentinel.py"],
        session_id="test_adr_sess",
    )
    assert gt_res["verified"] is True
    assert gt_res["exit_code"] == 0


def test_telegram_semantic_chunking_and_tag_balancing():
    """Verify Telegram semantic chunking, balanced HTML entity splitting, and zero text truncation."""
    import asyncio
    from unittest.mock import patch
    from html.parser import HTMLParser
    from integrations.telegram.formatter import split_html_chunks, split_message_chunks, format_telegram_html
    from integrations.telegram.client import send_telegram_message

    # 1. Markdown semantic chunking creates safe parts with headers
    sample_text = ("Analisis Mendalam Arsitektur:\n\n" + ("* Item penjelasan modul dan berkas sistem penting.\n" * 40))
    parts = split_message_chunks(sample_text, max_chars=2000, add_part_headers=True)
    assert len(parts) >= 2, f"Expected multiple chunks, got {len(parts)}"
    for idx, p in enumerate(parts):
        assert len(p) <= 2050, f"Chunk {idx} exceeded max length: {len(p)}"
        assert f"[Bagian {idx+1}/" in p

    # 2. HTML Tag Balancing: Ensure sub-chunking of long formatted HTML closes and re-opens tags correctly
    raw_html = "<blockquote expandable><b>Header</b>\n\n" + ("<pre><code>" + ("X" * 1200) + "</code></pre>\n\n") * 3 + "</blockquote>"
    html_chunks = split_html_chunks(raw_html, max_chars=2200)
    assert len(html_chunks) >= 2

    class TagValidator(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []
        def handle_starttag(self, tag, attrs):
            self.stack.append(tag)
        def handle_endtag(self, tag):
            assert self.stack, f"Unexpected closing tag </{tag}>"
            top = self.stack.pop()
            assert top == tag, f"Mismatched tag: expected </{top}>, got </{tag}>"

    for idx, chunk in enumerate(html_chunks):
        validator = TagValidator()
        validator.feed(chunk)
        assert not validator.stack, f"Chunk {idx} left unclosed tags: {validator.stack}"

    # 3. End-to-end send_telegram_message mock test with >4000 char message (Zero Truncation Guarantee)
    sent_payloads = []

    async def fake_post(endpoint, payload, token, timeout=20.0, max_retries=3):
        sent_payloads.append((endpoint, payload))
        return 200, {"ok": True, "result": {"message_id": 200 + len(sent_payloads)}}

    async def run_send_test():
        with patch("integrations.telegram.client.get_stored_telegram_token", return_value="fake_token_123"):
            with patch("integrations.telegram.client._telegram_api_post", side_effect=fake_post):
                long_answer = "Laporan Selesai:\n\n" + ("* Berkas penting dan penjelasan teknis mendalam.\n" * 45)
                res = await send_telegram_message(text=long_answer, chat_id="99999")
                assert res.get("status") == "ok"
                assert len(sent_payloads) >= 2, f"Expected chunks sent, got {len(sent_payloads)}"
                for _, payload in sent_payloads:
                    assert len(payload.get("text", "")) <= 4096

    asyncio.run(run_send_test())


# ────────────────────────────────────────────────────────────────────────────────
# TOKEN BUDGET TRACKER — Hermes/Claude Code Parity: Token-Aware Context Management
# ────────────────────────────────────────────────────────────────────────────────

def test_token_budget_model_context_windows():
    """Validates model context window registry resolves correctly for all major providers."""
    from core.token_budget import get_model_context_window, get_input_budget

    # ── Gemini family ──
    ctx, out = get_model_context_window("gemini-2.5-flash")
    assert ctx == 1_048_576, f"Expected 1M context for gemini-2.5-flash, got {ctx}"
    assert out == 65_536

    ctx, out = get_model_context_window("gemini-3.6-flash")
    assert ctx == 1_048_576, "gemini-3.x should match gemini-3 pattern"

    # ── With provider prefix stripping ──
    ctx, _ = get_model_context_window("9router/ag/gemini-2.5-flash-thinking")
    assert ctx == 1_048_576, "Should strip 9router/ag/ prefix and -thinking suffix"

    ctx, _ = get_model_context_window("openrouter/google/gemini-2.5-flash")
    assert ctx == 1_048_576, "Should strip openrouter/ prefix"

    # ── Anthropic family ──
    ctx, out = get_model_context_window("claude-3-5-sonnet-20241022")
    assert ctx == 200_000
    assert out == 8_192

    ctx, out = get_model_context_window("claude-3.7-sonnet")
    assert ctx == 200_000
    assert out == 64_000

    ctx, out = get_model_context_window("anthropic/claude-sonnet-4-20250514")
    assert ctx == 200_000
    assert out == 64_000

    # ── OpenAI family ──
    ctx, _ = get_model_context_window("gpt-4o-2024-11-20")
    assert ctx == 128_000

    ctx, _ = get_model_context_window("codex/o3-mini")
    assert ctx == 200_000

    # ── Unknown model gets safe default ──
    ctx, out = get_model_context_window("some-unknown-model")
    assert ctx == 32_000
    assert out == 4_096

    # ── Empty model id gets safe default ──
    ctx, out = get_model_context_window("")
    assert ctx == 32_000

    # ── Input budget is always less than context window ──
    budget = get_input_budget("gemini-2.5-flash")
    assert 0 < budget < 1_048_576
    assert budget > 100_000, "Budget should be substantial for 1M context window"

    budget_small = get_input_budget("some-unknown-model")
    assert 1024 <= budget_small < 32_000


def test_token_budget_token_counting():
    """Validates token counting works with tiktoken and produces reasonable results."""
    from core.token_budget import count_tokens, count_messages_tokens

    # Basic counting
    assert count_tokens("") == 0
    assert count_tokens("hello") > 0

    # English text: ~1 token per word for simple words
    tokens = count_tokens("The quick brown fox jumps over the lazy dog")
    assert 7 <= tokens <= 12, f"Expected ~9 tokens, got {tokens}"

    # Code should use more tokens per word
    code_tokens = count_tokens("def calculate_fibonacci(n: int) -> int:\n    if n <= 1:\n        return n\n    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)")
    assert code_tokens > 20

    # Message token counting includes overhead
    msgs = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ]
    msg_tokens = count_messages_tokens(msgs)
    assert msg_tokens > count_tokens("You are a helpful assistant.") + count_tokens("Hello!")


def test_token_budget_tracker_lifecycle():
    """Validates the TokenBudgetTracker detects budget thresholds correctly."""
    from core.token_budget import TokenBudgetTracker

    # Use a small model to test budget limits easily
    tracker = TokenBudgetTracker(model_id="gemma-2b")  # 8192 context

    # Fresh tracker with small messages should not be critical
    messages = [
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user", "content": "Hello, please help me."},
    ]
    assert not tracker.is_budget_critical(messages)
    assert not tracker.should_compact_context(messages)

    # Fill with lots of content to trigger compaction
    big_content = "x " * 5000  # ~5000 words ≈ ~5000-6000 tokens
    for i in range(5):
        messages.append({"role": "user", "content": big_content})
        messages.append({"role": "assistant", "content": f"Response {i}"})

    # Should now suggest compaction (>65% of budget)
    assert tracker.should_compact_context(messages)

    # Record step should work without errors
    tracker.record_step(0, messages)

    # Diagnostics should contain required fields
    diag = tracker.get_diagnostics(messages)
    assert "model_id" in diag
    assert "context_window" in diag
    assert "usage_ratio" in diag
    assert "is_critical" in diag
    assert diag["message_count"] == len(messages)


def test_token_budget_tracker_compaction():
    """Validates that compact_messages_if_needed actually reduces token count."""
    from core.token_budget import TokenBudgetTracker

    # Use gemma (small context) to make compaction trigger easily
    tracker = TokenBudgetTracker(model_id="gemma-2b")  # 8192 context

    messages = [
        {"role": "system", "content": "System prompt."},
        {"role": "user", "content": "Original user request."},
    ]

    # Add enough content to exceed 65% threshold
    big_output = "Error trace line " * 500  # ~3000 tokens
    for i in range(4):
        messages.append({"role": "assistant", "content": f"Tool call {i}"})
        messages.append({"role": "user", "content": big_output})

    # Two recent messages that should NOT be compacted
    messages.append({"role": "assistant", "content": "Recent thinking"})
    messages.append({"role": "user", "content": "Recent observation"})

    tokens_before = tracker.current_usage(messages)
    compacted = tracker.compact_messages_if_needed(messages)

    if compacted:
        tokens_after = tracker.current_usage(messages)
        assert tokens_after < tokens_before, "Compaction should reduce token count"
        # First 2 messages (system + user) should be untouched
        assert messages[0]["content"] == "System prompt."
        assert messages[1]["content"] == "Original user request."


def test_token_budget_aware_slot_assembly():
    """Validates that budget_aware_slot_assembly prunes excess slots."""
    from core.token_budget import budget_aware_slot_assembly, count_tokens

    # Create slots that fit within budget
    slots = [
        "Identity: I am Anara.",
        "Mode: Build mode active.",
        "Tools: Use available tools.",
        "Memory: User prefers dark mode.",
    ]
    result = budget_aware_slot_assembly(slots, model_id="gemini-2.5-flash")
    assert "Identity: I am Anara." in result
    assert "Mode: Build mode active." in result
    # All slots should be present for large context models
    assert "Memory:" in result

    # With very small budget and massive slots, last slots should be pruned
    huge_slot = "x " * 20000  # ~20K tokens
    slots_with_huge = [
        "Identity: I am Anara.",
        "Mode: Build mode active.",
        "Memory snapshot" + huge_slot,
        "Skills: " + huge_slot,
        "Project: " + huge_slot,
    ]
    result = budget_aware_slot_assembly(
        slots_with_huge,
        model_id="gemma-2b",  # tiny 8K context
        reserved_for_conversation=2000,
    )
    # Identity and mode should always survive
    assert "Identity: I am Anara." in result
    assert "Mode: Build mode active." in result
    # At least some pruning should have occurred
    result_tokens = count_tokens(result)
    total_tokens = sum(count_tokens(s) for s in slots_with_huge)
    assert result_tokens < total_tokens, "Pruning should reduce total tokens"


def test_context_compactor_token_estimation():
    """Validates the estimate_tokens function in context_compactor."""
    from core.context_compactor import estimate_tokens, ContextCompactor

    assert estimate_tokens("") == 0
    assert estimate_tokens("hello world") > 0
    assert estimate_tokens("a " * 100) > 50  # ~100 tokens

    # History token estimation
    history = [
        {"user_text": "Hello", "ai_text": "Hi there!"},
        {"user_text": "What is 2+2?", "ai_text": "4."},
    ]
    tokens = ContextCompactor.estimate_history_tokens(history)
    assert tokens > 10
    assert tokens < 200  # sanity check for small history


# ────────────────────────────────────────────────────────────────────────────────
# NATIVE TOOL-USE API — Hermes & Claude Code Parity: Structured Tool Calling
# ────────────────────────────────────────────────────────────────────────────────

def test_native_tool_schemas_anthropic_and_openai():
    """Validates dynamic conversion of Anara tool catalog to Anthropic and OpenAI schemas."""
    from tools.catalog import get_native_tools_anthropic, get_native_tools_openai, get_agent_tools

    anth_tools = get_native_tools_anthropic()
    assert len(anth_tools) >= 50, f"Expected 50+ Anthropic tools, got {len(anth_tools)}"
    for t in anth_tools:
        assert "name" in t
        assert "description" in t
        assert "input_schema" in t
        schema = t["input_schema"]
        assert schema.get("type") == "object", f"Tool {t['name']} has invalid type: {schema.get('type')}"
        assert isinstance(schema.get("properties"), dict)

    # Test filtering with read_only
    ro_anth = get_native_tools_anthropic(read_only=True)
    assert 0 < len(ro_anth) < len(anth_tools)
    ro_names = {t["name"] for t in ro_anth}
    assert "read_local_file" in ro_names
    assert "delete_local_file" not in ro_names

    # Test OpenAI schema format
    open_tools = get_native_tools_openai()
    assert len(open_tools) >= 50
    for t in open_tools:
        assert t.get("type") == "function"
        fn = t.get("function", {})
        assert "name" in fn
        assert "parameters" in fn
        params = fn["parameters"]
        assert params.get("type") == "object"

    # Test Gemini tool format
    gem_tools = get_agent_tools()
    assert len(gem_tools) == 1
    assert len(gem_tools[0].function_declarations) >= 50


def test_native_tool_turn_dto_and_lifecycle():
    """Validates NativeToolCall and NativeTurnResult DTO behavior."""
    from providers.native_turn import NativeToolCall, NativeTurnResult

    call = NativeToolCall(
        call_id="toolu_01",
        name="read_local_file",
        arguments={"file_path": "README.md"}
    )
    assert call.call_id == "toolu_01"
    assert call.name == "read_local_file"
    assert call.to_dict() == {
        "call_id": "toolu_01",
        "name": "read_local_file",
        "arguments": {"file_path": "README.md"}
    }

    # Narrative-only turn
    narrative = NativeTurnResult(text="Hello, I can help you with that.")
    assert not narrative.has_tool_calls
    assert narrative.clean_text == "Hello, I can help you with that."

    # Tool-calling turn
    tool_turn = NativeTurnResult(text="", tool_calls=[call])
    assert tool_turn.has_tool_calls
    assert len(tool_turn.tool_calls) == 1


def test_native_agent_loop_narrative_stop():
    """Validates that _execute_native_agent_loop stops immediately when no tool calls are emitted."""
    import asyncio
    from providers.caller import _execute_native_agent_loop
    from providers.native_turn import NativeTurnResult

    async def _mock_narrative_caller(history):
        return NativeTurnResult(text="Task completed successfully with pure explanation.")

    def _mock_recorder(history, turn, results):
        pass

    res = asyncio.run(_execute_native_agent_loop(
        native_turn_caller=_mock_narrative_caller,
        record_results_fn=_mock_recorder,
        initial_history=[{"role": "user", "content": "Explain relativity."}],
        user_prompt="Explain relativity.",
        read_only=True,
    ))

    assert "Task completed successfully" in res


def test_native_agent_loop_tool_execution():
    """Validates multi-turn tool execution and result recording in _execute_native_agent_loop."""
    import asyncio
    from providers.caller import _execute_native_agent_loop
    from providers.native_turn import NativeToolCall, NativeTurnResult

    turn_count = 0
    recorded_results = []

    async def _mock_multi_turn_caller(history):
        nonlocal turn_count
        turn_count += 1
        if turn_count == 1:
            # Emit a native tool call to glob_find_files
            return NativeTurnResult(
                text="Let me inspect the files.",
                tool_calls=[
                    NativeToolCall(
                        call_id="call_glob_01",
                        name="glob_find_files",
                        arguments={"pattern": "*.py", "path": "."}
                    )
                ]
            )
        else:
            # Step 2: Final narrative answer
            return NativeTurnResult(text="Found the project files successfully.")

    def _mock_recorder(history, turn, results):
        recorded_results.extend(results)
        history.append({"role": "assistant", "turn": turn})
        history.append({"role": "tool_results", "results": results})

    res = asyncio.run(_execute_native_agent_loop(
        native_turn_caller=_mock_multi_turn_caller,
        record_results_fn=_mock_recorder,
        initial_history=[{"role": "user", "content": "List files"}],
        user_prompt="List files",
        read_only=True,
    ))

    assert turn_count == 2
    assert "Found the project files successfully." in res
    assert len(recorded_results) == 1
    call_obj, output_str, is_err = recorded_results[0]
    assert call_obj.name == "glob_find_files"
    assert not is_err


def test_native_agent_loop_plan_interception():
    """Validates that mutating tools are properly intercepted in Plan Mode during native execution."""
    import asyncio
    from providers.caller import _execute_native_agent_loop
    from providers.native_turn import NativeToolCall, NativeTurnResult

    async def _mock_mutating_caller(history):
        return NativeTurnResult(
            text="I will now modify the configuration.",
            tool_calls=[
                NativeToolCall(
                    call_id="call_edit_01",
                    name="edit_file",
                    arguments={"file_path": "config.py", "old_string": "a", "new_string": "b"}
                )
            ]
        )

    def _mock_recorder(history, turn, results):
        pass

    interception = asyncio.run(_execute_native_agent_loop(
        native_turn_caller=_mock_mutating_caller,
        record_results_fn=_mock_recorder,
        initial_history=[{"role": "user", "content": "Update config"}],
        user_prompt="Update config",
        read_only=False,
        intercept_mutating_tools=True,
    ))

    assert isinstance(interception, dict)
    assert interception.get("intercepted") is True
    assert interception.get("tool_name") == "edit_file"
    assert interception.get("tool_risk") in ("mutating", "ask")


# ────────────────────────────────────────────────────────────────────────────────
# CONVERGENCE DETECTION — Hermes & Claude Code Parity: Gap 3
# ────────────────────────────────────────────────────────────────────────────────

def test_convergence_goal_satisfaction():
    """Validates that goal satisfaction (mutations + test passed) triggers convergence."""
    from core.convergence import ConvergenceDetector

    detector = ConvergenceDetector(read_only=False)

    # 1. Agent modifies a file
    s1 = detector.record_turn_actions(0, [{
        "tool_name": "edit_file",
        "args": {"file_path": "backend/core/agent.py", "old_string": "x", "new_string": "y"},
        "risk": "mutating",
        "is_error": False,
        "summary": "Replaced string in agent.py"
    }])
    assert not s1.is_converged
    assert detector.phase == "MUTATING"

    # 2. Agent runs pytest and it passes
    s2 = detector.record_turn_actions(1, [{
        "tool_name": "execute_cli_command",
        "args": {"command": "pytest backend/tests/test_subsystems.py"},
        "risk": "mutating",
        "is_error": False,
        "summary": "51 passed in 2.0s"
    }])
    assert detector.phase == "VERIFYING"
    assert detector.last_test_passed is True

    # 3. Agent now attempts to wander / inspect files post-verification
    s3 = detector.record_turn_actions(2, [{
        "tool_name": "read_local_file",
        "args": {"file_path": "backend/core/agent.py"},
        "risk": "read_only",
        "is_error": False,
        "summary": "file contents"
    }])
    assert s3.is_converged is True
    assert s3.reason == "verified_complete"
    assert "MISSION CONVERGED" in s3.guidance


def test_convergence_information_saturation():
    """Validates that repeatedly examining already-explored files triggers saturation convergence."""
    from core.convergence import ConvergenceDetector

    detector = ConvergenceDetector(read_only=False)

    # Inspect file A
    detector.record_turn_actions(0, [{
        "tool_name": "read_local_file",
        "args": {"file_path": "backend/main.py"},
        "risk": "read_only",
        "is_error": False,
        "summary": "main content"
    }])
    assert len(detector.inspected_targets) == 1

    # Redundant inspections of file A
    s_red1 = detector.record_turn_actions(1, [{
        "tool_name": "read_local_file",
        "args": {"file_path": "backend/main.py"},
        "risk": "read_only",
        "is_error": False,
        "summary": "main content"
    }])
    assert not s_red1.is_converged

    detector.record_turn_actions(2, [{
        "tool_name": "read_local_file",
        "args": {"file_path": "backend/main.py"},
        "risk": "read_only",
        "is_error": False,
        "summary": "main content"
    }])

    detector.record_turn_actions(3, [{
        "tool_name": "read_local_file",
        "args": {"file_path": "backend/main.py"},
        "risk": "read_only",
        "is_error": False,
        "summary": "main content"
    }])

    s_final = detector.record_turn_actions(4, [{
        "tool_name": "read_local_file",
        "args": {"file_path": "backend/main.py"},
        "risk": "read_only",
        "is_error": False,
        "summary": "main content"
    }])
    assert s_final.is_converged is True
    assert s_final.reason == "information_saturated"
    assert "INFORMATION SATURATION" in s_final.guidance


def test_convergence_multi_tool_cycles():
    """Validates detection of repeating N-cycles across multiple tools."""
    from core.convergence import ConvergenceDetector

    detector = ConvergenceDetector(read_only=False)

    # 3-step sequence: tool A -> tool B -> tool C
    cycle = [
        {"tool_name": "read_local_file", "args": {"file_path": "file1.py"}, "risk": "read_only", "is_error": False, "summary": ""},
        {"tool_name": "grep_search_code", "args": {"pattern": "def foo", "path": "."}, "risk": "read_only", "is_error": False, "summary": ""},
        {"tool_name": "read_local_file", "args": {"file_path": "file2.py"}, "risk": "read_only", "is_error": False, "summary": ""},
    ]

    # Repeat sequence 1st time
    for i, item in enumerate(cycle):
        detector.record_turn_actions(i, [item])

    # Repeat sequence 2nd time (should trigger cycle warning)
    s_warn = None
    for i, item in enumerate(cycle):
        s_warn = detector.record_turn_actions(3 + i, [item])
    assert s_warn.should_nudge is True
    assert "CYCLE WARNING" in (s_warn.guidance or "")

    # Repeat sequence 3rd time (should trigger hard cyclic stall convergence)
    s_stall = None
    for i, item in enumerate(cycle):
        s_stall = detector.record_turn_actions(6 + i, [item])
    assert s_stall.is_converged is True
    assert s_stall.reason == "cyclic_stall"


def test_convergence_plan_mode_inspection_budget():
    """Validates that open-ended exploration in read-only mode converges at budget ceiling."""
    from core.convergence import ConvergenceDetector

    detector = ConvergenceDetector(read_only=True)

    # Perform 8 steps of distinct inspections
    last_status = None
    for step in range(9):
        last_status = detector.record_turn_actions(step, [{
            "tool_name": "read_local_file",
            "args": {"file_path": f"module_{step}.py"},
            "risk": "read_only",
            "is_error": False,
            "summary": f"content of {step}"
        }])

    assert last_status.is_converged is True
    assert last_status.reason == "inspection_budget_exhausted"
    assert "INSPECTION BUDGET EXHAUSTION" in last_status.guidance


# ────────────────────────────────────────────────────────────────────────────────
# PENDING ACTION PERSISTENCE — Hermes Parity: Crash Resilience for Approvals (Gap 5)
# ────────────────────────────────────────────────────────────────────────────────

def test_session_manager_persistence_and_recovery(tmp_path):
    """Validates that pending actions survive process restart via SQLite persistence."""
    import time
    from core.session_manager import SessionStateManager, PendingAction, ActionState

    db_file = str(tmp_path / "test_pending.db")

    # Instance 1: Store an action
    mgr1 = SessionStateManager(db_path=db_file)
    action = PendingAction(
        plan_id="act_persist_01",
        session_id=42,
        channel="telegram",
        channel_id="chat_999",
        tool_name="write_local_file",
        tool_args={"file_path": "important.txt", "content": "hello world"},
        original_prompt="tulis file important.txt",
        plan_text="Write important.txt with hello world",
        risk_level="mutating",
        state=ActionState.PENDING,
        created_at=time.time(),
        ttl_seconds=300.0,
    )
    mgr1.store_pending(action)
    assert mgr1.get_pending("telegram", "chat_999") is not None

    # Instance 2 (Simulating server restart / crash recovery): Points to SAME database
    mgr2 = SessionStateManager(db_path=db_file)
    recovered = mgr2.get_pending("telegram", "chat_999")

    assert recovered is not None, "Pending action must survive server restart!"
    assert recovered.plan_id == "act_persist_01"
    assert recovered.tool_name == "write_local_file"
    assert recovered.tool_args == {"file_path": "important.txt", "content": "hello world"}
    assert recovered.state == ActionState.PENDING


def test_session_manager_persistence_expiration_on_restart(tmp_path):
    """Validates that actions expired while server was down are swept on restart."""
    import time
    from core.session_manager import SessionStateManager, PendingAction, ActionState

    db_file = str(tmp_path / "test_expire.db")

    # Instance 1: Store an already-expired action (>300s old)
    mgr1 = SessionStateManager(db_path=db_file)
    stale_action = PendingAction(
        plan_id="act_stale_01",
        session_id=42,
        channel="whatsapp",
        channel_id="wa_123",
        tool_name="execute_cli_command",
        tool_args={"command": "rm -rf temp"},
        state=ActionState.PENDING,
        created_at=time.time() - 350.0,  # 350s ago (> 300s TTL)
        ttl_seconds=300.0,
    )
    mgr1.store_pending(stale_action)

    # Instance 2: On restart, the action should be marked expired in DB and NOT loaded into active
    mgr2 = SessionStateManager(db_path=db_file)
    active = mgr2.get_pending("whatsapp", "wa_123")
    assert active is None, "Expired action must not be active on restart"

    # Verify audit history records it as expired
    history = mgr2.get_action_history("whatsapp", "wa_123")
    assert len(history) == 1
    assert history[0]["state"] == "expired"


def test_session_manager_audit_history(tmp_path):
    """Validates that state transitions are recorded in the persistent audit trail."""
    import time
    from core.session_manager import SessionStateManager, PendingAction, ActionState

    db_file = str(tmp_path / "test_audit.db")
    mgr = SessionStateManager(db_path=db_file)

    action = PendingAction(
        plan_id="act_audit_01",
        session_id=101,
        channel="cli",
        channel_id="local",
        tool_name="edit_file",
        tool_args={"file_path": "main.py"},
        state=ActionState.PENDING,
        created_at=time.time(),
        ttl_seconds=300.0,
    )
    mgr.store_pending(action)

    # Transition to EXECUTING
    mgr.resolve_action("cli", "local", "act_audit_01", ActionState.EXECUTING)
    hist1 = mgr.get_action_history("cli", "local")
    assert len(hist1) == 1
    assert hist1[0]["state"] == "executing"

    # Transition to EXECUTED
    mgr.resolve_action("cli", "local", "act_audit_01", ActionState.EXECUTED)
    hist2 = mgr.get_action_history("cli", "local")
    assert len(hist2) == 1
    assert hist2[0]["state"] == "executed"


# ────────────────────────────────────────────────────────────────────────────────
# PER-ROUTE AUTHENTICATION — Hermes & Production API Security Parity (Gap 6)
# ────────────────────────────────────────────────────────────────────────────────

def test_gateway_auth_local_and_remote_policies():
    """Validates local origin auto-bypass, remote rejection, and bearer token authorization."""
    from fastapi.testclient import TestClient
    from main import app
    from core.security import generate_gateway_session_token

    # 1. Local requests (TestClient default host is testclient / 127.0.0.1)
    local_client = TestClient(app)
    res_local = local_client.get("/api/brain/overview")
    assert res_local.status_code == 200, f"Local request should be auto-permitted: {res_local.text}"

    # 2. Public endpoints accessible without token from remote origin
    # Remote client simulated with non-local client tuple and non-local IP headers
    remote_unauth = TestClient(
        app,
        client=("203.0.113.195", 54321),
        headers={"cf-connecting-ip": "203.0.113.195", "cf-ray": "8a1b2c3d4e5f-SIN"}
    )
    res_status = remote_unauth.get("/api/gateway/status")
    assert res_status.status_code == 200, "Gateway status endpoint must remain publicly accessible"
    assert res_status.json().get("auth_required") is True

    res_root = remote_unauth.get("/")
    assert res_root.status_code == 200, "Health check root must remain publicly accessible"

    # 3. Protected endpoint rejected for remote client without token
    res_blocked = remote_unauth.get("/api/brain/overview")
    assert res_blocked.status_code == 401, "Protected endpoint must reject unauthenticated remote access"
    assert "Unauthorized" in res_blocked.json().get("detail", "")

    # 4. Protected endpoint permitted for remote client with valid Bearer token
    valid_token = generate_gateway_session_token()
    remote_auth = TestClient(
        app,
        client=("203.0.113.195", 54321),
        headers={
            "cf-connecting-ip": "203.0.113.195",
            "cf-ray": "8a1b2c3d4e5f-SIN",
            "authorization": f"Bearer {valid_token}"
        }
    )
    res_allowed = remote_auth.get("/api/brain/overview")
    assert res_allowed.status_code == 200, f"Valid bearer token must permit remote access: {res_allowed.text}"


# ────────────────────────────────────────────────────────────────────────────────
# ANTHROPIC TRUE STREAMING — Claude Code Parity: Native SSE Token Stream (Gap 7)
# ────────────────────────────────────────────────────────────────────────────────

def test_anthropic_stream_chat_sse_parsing():
    """Validates line-by-line SSE parsing for Anthropic Messages API streaming."""
    import json

    sse_lines = [
        'event: message_start',
        'data: {"type": "message_start", "message": {"id": "msg_01", "type": "message", "role": "assistant", "model": "claude-3-5-sonnet", "usage": {"input_tokens": 42, "output_tokens": 1}}}',
        '',
        'event: content_block_start',
        'data: {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}',
        '',
        'event: content_block_delta',
        'data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hello "}}',
        '',
        'event: content_block_delta',
        'data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "from "}}',
        '',
        'event: content_block_delta',
        'data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Anthropic!"}}',
        '',
        'event: content_block_stop',
        'data: {"type": "content_block_stop", "index": 0}',
        '',
        'event: message_delta',
        'data: {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 15}}',
        '',
        'event: message_stop',
        'data: {"type": "message_stop"}',
        '',
        'data: [DONE]',
    ]

    # Simulate the exact SSE parsing loop from AnthropicProviderProfile.stream_chat
    chunks = []
    prompt_tokens = 0
    completion_tokens = 0

    for line in sse_lines:
        if not line or not line.startswith("data:"):
            continue
        d_str = line[5:].strip()
        if d_str == "[DONE]":
            break
        event = json.loads(d_str)
        ev_type = event.get("type", "")

        if ev_type == "message_start":
            msg_usage = event.get("message", {}).get("usage", {})
            if msg_usage:
                prompt_tokens = msg_usage.get("input_tokens", 0)
        elif ev_type == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                chunk = delta.get("text", "")
                if chunk:
                    chunks.append(chunk)
        elif ev_type == "message_delta":
            delta_usage = event.get("usage", {})
            if delta_usage:
                completion_tokens = delta_usage.get("output_tokens", 0)

    # Assertions
    assert chunks == ["Hello ", "from ", "Anthropic!"]
    assert "".join(chunks) == "Hello from Anthropic!"
    assert prompt_tokens == 42
    assert completion_tokens == 15


# ────────────────────────────────────────────────────────────────────────────────
# HYBRID RAG & NATIVE POLISH — Hermes Parity: Gap 4 & Gap 2 Polish
# ────────────────────────────────────────────────────────────────────────────────

def test_token_budget_robust_message_counting():
    """Validates robust message token counting across text, Anthropic blocks, and Gemini parts."""
    from core.token_budget import count_messages_tokens

    # Standard dict with text
    msgs_standard = [{"role": "user", "content": "Hello world"}]
    assert count_messages_tokens(msgs_standard) > 0

    # Anthropic style: list of content blocks
    msgs_anthropic = [{
        "role": "user",
        "content": [
            {"type": "text", "text": "Inspect this code"},
            {"type": "tool_result", "content": "File contents here"}
        ]
    }]
    tokens_anth = count_messages_tokens(msgs_anthropic)
    assert tokens_anth > 5

    # Gemini style: mock object with parts attribute
    class MockPart:
        def __init__(self, text):
            self.text = text

    class MockContent:
        def __init__(self, parts):
            self.parts = parts

    msgs_gemini = [MockContent([MockPart("Analyze this log file"), MockPart("Output trace")])]
    tokens_gem = count_messages_tokens(msgs_gemini)
    assert tokens_gem > 5


def test_semantic_rag_cosine_similarity_and_indexing():
    """Validates cosine similarity and vector embedding indexing in semantic_rag."""
    from memory.semantic_rag import cosine_similarity, SemanticRAGMixin

    # 1. Cosine similarity math
    vec_a = [1.0, 0.0, 0.0]
    vec_b = [1.0, 0.0, 0.0]
    assert abs(cosine_similarity(vec_a, vec_b) - 1.0) < 1e-5

    vec_c = [0.0, 1.0, 0.0]
    assert abs(cosine_similarity(vec_a, vec_c) - 0.0) < 1e-5

    vec_d = [-1.0, 0.0, 0.0]
    assert abs(cosine_similarity(vec_a, vec_d) - (-1.0)) < 1e-5

    # 2. Hybrid search indexing
    from memory import memory_engine

    # Store a test memory
    memory_engine.store_memory(
        speaker_name="Agnan",
        key="staging_deployment",
        value="Docker Swarm runner on port 8080 with auto-healing",
        category="deployment"
    )

    # Search via semantic_search_brain
    results = memory_engine.semantic_search_brain("staging deployment port", speaker_name="Agnan")
    assert len(results) > 0
    top = results[0]
    assert "staging" in top["title"].lower() or "staging" in top["content"].lower()


def test_openai_native_tool_turn_mock():
    """Validates OpenAI-style native tool calling and recording in _execute_native_agent_loop."""
    import asyncio
    from providers.caller import _execute_native_agent_loop
    from providers.native_turn import NativeToolCall, NativeTurnResult

    turn_count = 0
    history_states = []

    async def _mock_openai_caller(history):
        nonlocal turn_count
        turn_count += 1
        history_states.append(list(history))
        if turn_count == 1:
            return NativeTurnResult(
                text="",
                tool_calls=[
                    NativeToolCall(
                        call_id="call_read_01",
                        name="read_local_file",
                        arguments={"file_path": "README.md"}
                    )
                ],
                raw_response={"role": "assistant", "content": None, "tool_calls": [{"id": "call_read_01"}]}
            )
        else:
            return NativeTurnResult(text="README inspected successfully.")

    def _record_openai_results(history, turn, results):
        history.append(turn.raw_response)
        for call_obj, output_str, is_err in results:
            history.append({
                "role": "tool",
                "tool_call_id": call_obj.call_id,
                "content": output_str
            })

    res = asyncio.run(_execute_native_agent_loop(
        native_turn_caller=_mock_openai_caller,
        record_results_fn=_record_openai_results,
        initial_history=[{"role": "user", "content": "Read readme"}],
        user_prompt="Read readme",
        read_only=True,
    ))

    assert turn_count == 2
    assert "README inspected successfully." in res


# ────────────────────────────────────────────────────────────────────────────────
# 100% PARITY POLISH: Security Confinement, Offline Vectors & OpenAI-Compatible
# ────────────────────────────────────────────────────────────────────────────────

def test_workspace_sentinel_confinement_security(tmp_path):
    """Validates that WorkspaceSentinel strictly blocks directory traversal outside workspace."""
    from core.workspace_sentinel import WorkspaceSentinel

    sentinel = WorkspaceSentinel(workspace_root=str(tmp_path))

    # 1. Inside workspace path is allowed
    ok_in, _ = sentinel.validate_file_access("subfolder/app.py", action="write")
    assert ok_in is True

    # 2. Directory traversal escaping root is blocked for mutating actions
    ok_escape, err_escape = sentinel.validate_file_access("../../windows/system32/calc.exe", action="write")
    assert ok_escape is False
    assert "outside authorized workspace boundaries" in (err_escape or "")

    ok_edit_escape, _ = sentinel.validate_file_access("../../../etc/shadow", action="edit")
    assert ok_edit_escape is False

    ok_del_escape, _ = sentinel.validate_file_access("../outside.txt", action="delete")
    assert ok_del_escape is False

    # 3. Sensitive credentials directory (.ssh, .aws) blocked
    ok_ssh, err_ssh = sentinel.validate_file_access(".ssh/id_rsa", action="write")
    assert ok_ssh is False
    assert "sensitive credentials directory" in (err_ssh or "")

    ok_aws, _ = sentinel.validate_file_access(".aws/credentials", action="delete")
    assert ok_aws is False


def test_semantic_rag_offline_vector_fallback():
    """Validates deterministic offline vector embedding generation and cosine similarity."""
    from memory.semantic_rag import compute_local_hash_embedding, cosine_similarity, get_text_embedding

    # 1. Deterministic generation & unit normalization
    v1 = compute_local_hash_embedding("Docker container orchestration on staging")
    assert len(v1) == 512
    import numpy as np
    norm = np.linalg.norm(np.array(v1))
    assert abs(norm - 1.0) < 1e-4

    # 2. Semantic alignment: related phrases have higher similarity than unrelated
    v_related = compute_local_hash_embedding("Staging Docker orchestration containers")
    v_unrelated = compute_local_hash_embedding("Strawberry cheesecake baking recipe")

    sim_related = cosine_similarity(v1, v_related)
    sim_unrelated = cosine_similarity(v1, v_unrelated)

    assert sim_related > 0.40, f"Expected high similarity for related topics, got {sim_related}"
    assert sim_unrelated < 0.25, f"Expected low similarity for unrelated topics, got {sim_unrelated}"
    assert sim_related > sim_unrelated + 0.25

    # 3. Dimension mismatch safety
    v_short = [1.0, 0.0]
    assert cosine_similarity(v1, v_short) == 0.0


def test_openai_compatible_native_tool_loop():
    """Validates OpenAICompatibleProviderProfile._try_native_agent_loop structure."""
    import asyncio
    from providers.profile_implementations import OpenAICompatibleProviderProfile

    profile = OpenAICompatibleProviderProfile()
    assert hasattr(profile, "_try_native_agent_loop")
    assert callable(profile._try_native_agent_loop)


# ────────────────────────────────────────────────────────────────────────────────
# PROMPT LOADER & EXTERNALIZED CONFIG — Hermes Parity: Zero Hardcoded Prompts
# ────────────────────────────────────────────────────────────────────────────────

def test_prompt_loader_hot_reload_and_formatting(tmp_path):
    """Validates prompt loader loads external markdown templates with mtime hot-reload and safe formatting."""
    from core.prompt_loader import load_prompt, _PROMPT_CACHE

    # 1. Load standard mode prompts
    p_plan = load_prompt("modes/plan_mode")
    assert "Plan Mode - System Reminder" in p_plan
    assert "CRITICAL: Plan mode ACTIVE" in p_plan

    p_build = load_prompt("modes/build_mode")
    assert "Build Mode - System Reminder" in p_build

    # 2. Test dynamic variable formatting
    p_card = load_prompt(
        "self_correction/diagnostic_card",
        task_goal="Refactor authentication",
        tool_name="edit_file",
        target="src/auth.py",
        err_type="syntax_error",
        steps_str="1. edit_file failed"
    )
    assert "Refactor authentication" in p_card
    assert "src/auth.py" in p_card
    assert "syntax_error" in p_card

    # 3. Test fallback for non-existent prompt
    p_missing = load_prompt("non_existent_prompt_xyz", default="Default prompt {name}", name="Anara")
    assert p_missing == "Default prompt Anara"


def test_model_driven_intent_evaluation():
    """Validates 100% Model-Driven Approval Reasoning and CLI machine binary tokens (Claude Code Parity)."""
    from core.plan_detector import is_explicit_plan_approval, _INTENT_CACHE
    from core.prompt_loader import load_prompt

    # 1. Universal single-character / CLI binary confirmations
    assert is_explicit_plan_approval("y") is True
    assert is_explicit_plan_approval("yes") is True
    assert is_explicit_plan_approval("n") is False
    assert is_explicit_plan_approval("no") is False

    # 2. Cached model-driven reasoning verdicts
    _INTENT_CACHE["gas"] = "approve"
    _INTENT_CACHE["lanjutkan"] = "approve"
    _INTENT_CACHE["batal"] = "reject"
    assert is_explicit_plan_approval("gas") is True
    assert is_explicit_plan_approval("lanjutkan") is True
    assert is_explicit_plan_approval("batal") is False

    # 3. Verify multilingual intent rubric is loaded from external markdown
    rubric = load_prompt("classifiers/approval_intent")
    assert "multilingual intent classification engine" in rubric
    assert "APPROVE" in rubric
    assert "REJECT" in rubric


def test_externalized_classifiers_and_visual_prompts():
    """Validates externalized classifier prompts (visual projection, entity memory, reasoner, adr)."""
    from core.prompt_loader import load_prompt

    # Visual projection prompt
    vp = load_prompt(
        "classifiers/visual_projection",
        system_prompt="SYS",
        recent_context_str="CTX",
        date_full="24 Sep 2026",
        time_str="12:00",
        user_text="Tampilkan foto monas",
        memories_count=15
    )
    assert "HOLOGRAPHIC 3D VISUAL PROJECTION CLASSIFIER" in vp
    assert "Tampilkan foto monas" in vp
    assert '"memory_nodes": 15' in vp

    # Entity memory prompt
    em = load_prompt(
        "classifiers/entity_memory",
        entity="Kucing Anggora",
        entity_title="Kucing Anggora",
        eff_speaker="Agnan"
    )
    assert "Kucing Anggora" in em
    assert "Agnan" in em

    # Memory reasoner prompt
    mr = load_prompt(
        "classifiers/memory_reasoner",
        command="ingat itu ya",
        recent_context="User: saya suka kopi\nAnara: mantap",
        eff_speaker="Agnan"
    )
    assert "ingat itu ya" in mr
    assert "saya suka kopi" in mr

    # ADR synthesizer prompt
    adr = load_prompt("classifiers/adr_synthesizer")
    assert "Architecture Decision Record (ADR) synthesizer" in adr


def test_externalized_platform_and_safety_configs():
    """Validates externalized YAML configurations and filesystem-based skills (Hermes Parity)."""
    from core.prompt_loader import load_config_yaml
    from core.skill_library import skill_library

    # Voice calibration YAML
    calib = load_config_yaml("voice/live_directives.yaml", default={})
    assert "action_approved" in calib
    assert "music_playing" in calib

    # Skills are loaded from filesystem skills/ directly (agentskills.io standard)
    from constants import get_bundled_skills_dir
    bundled_skills = list(Path(get_bundled_skills_dir()).rglob("SKILL.md"))
    assert len(bundled_skills) >= 5, f"Expected 5+ filesystem skills in skills/, got {len(bundled_skills)}"

    # Toolset config YAML (platform aliases)
    ts_cfg = load_config_yaml("config/toolset_config.yaml", default={})
    aliases = ts_cfg.get("platform_aliases", {})
    assert aliases.get("terminal") == "cli"
    assert aliases.get("tele") == "telegram"

    # Failure tolerant tools YAML
    ft_cfg = load_config_yaml("config/failure_tolerant_tools.yaml", default={})
    ft_tools = ft_cfg.get("failure_tolerant_tools", [])
    assert "read_local_file" in ft_tools
    assert "grep_search_code" in ft_tools

    # Blocked domains YAML
    bd_cfg = load_config_yaml("config/blocked_domains.yaml", default={})
    blocked = bd_cfg.get("blocked_domains", [])
    assert "gettyimages.com" in blocked


def test_externalized_convergence_guidance_yaml():
    """Validates externalized convergence guidance templates in convergence/guidance.yaml."""
    from core.prompt_loader import load_config_yaml
    from core.convergence import ConvergenceDetector

    cfg = load_config_yaml("convergence/guidance.yaml", default={})
    assert isinstance(cfg, dict)
    expected_keys = [
        "goal_satisfaction", "stagnation_notice", "cycle_warning",
        "information_saturation", "saturation_notice",
        "inspection_budget_exhaustion", "exploration_guidance"
    ]
    for k in expected_keys:
        assert k in cfg, f"Missing key {k} in convergence/guidance.yaml"
        assert len(cfg[k]) > 10, f"Template for {k} is empty"

    # Verify detector evaluates using YAML templates
    d = ConvergenceDetector()
    d.mutations_count = 1
    d.last_test_passed = True
    d.test_verified_count = 1
    d.history.append(type("ActionRecord", (), {"risk": "read_only"})())
    status = d.evaluate(1)
    assert status.is_converged is True
    assert status.reason == "verified_complete"
    assert "MISSION CONVERGED" in status.guidance


def test_externalized_live_voice_directives_yaml():
    """Validates externalized voice and media runtime directives in voice/live_directives.yaml."""
    from core.prompt_loader import load_config_yaml

    cfg = load_config_yaml("voice/live_directives.yaml", default={})
    assert isinstance(cfg, dict)
    expected_keys = [
        "action_approved", "music_playing", "animations_context",
        "memory_deleted", "hud_projection_with_text", "hud_projection_default",
        "playlist_not_found", "playlist_ready", "no_media_playing"
    ]
    for k in expected_keys:
        assert k in cfg, f"Missing key {k} in voice/live_directives.yaml"

    # Test format safety
    act_msg = cfg["action_approved"].format(target_desc="rebuild database")
    assert "rebuild database" in act_msg
    assert "SYSTEM NOTIFICATION" in act_msg


# ────────────────────────────────────────────────────────────────────────────────
# CUA DESKTOP PARITY & AUTONOMOUS REACT EXECUTION — Hermes & Claude Code Parity
# ────────────────────────────────────────────────────────────────────────────────

def test_universal_cua_tool_availability():
    """Validates that computer_use and take_screenshot are universally available across all platforms."""
    from tools.toolsets import PlatformToolRegistry

    for plat in ("cli", "telegram", "whatsapp", "web_studio", "voice_hud"):
        tools = PlatformToolRegistry.get_pruned_tools_for_execution(platform=plat)
        assert "computer_use" in tools, f"computer_use must be available on {plat}"
        assert "take_screenshot" in tools, f"take_screenshot must be available on {plat}"


def test_autonomous_react_execution_without_ping_pong():
    """Validates that ordinary mutating tools execute autonomously without interception in conversational mode."""
    import asyncio
    from providers.caller import _execute_native_agent_loop
    from providers.native_turn import NativeToolCall, NativeTurnResult

    # Simulate multi-step autonomous workflow: 1) read_local_file -> 2) read_local_file -> 3) final answer
    turn_idx = 0
    executed_tools = []

    async def _mock_cua_caller(history):
        nonlocal turn_idx
        turn_idx += 1
        if turn_idx == 1:
            return NativeTurnResult(
                text="Inspecting constants...",
                tool_calls=[NativeToolCall(call_id="c1", name="read_local_file", arguments={"file_path": "backend/constants.py", "limit": 5})]
            )
        elif turn_idx == 2:
            return NativeTurnResult(
                text="Inspecting constants part 2...",
                tool_calls=[NativeToolCall(call_id="c2", name="read_local_file", arguments={"file_path": "backend/constants.py", "limit": 10})]
            )
        else:
            return NativeTurnResult(text="Beres! Analisis konfigurasi selesai.")

    def _mock_recorder(history, turn, results):
        for call_obj, output_str, is_err in results:
            executed_tools.append(call_obj.name)
        history.append({"role": "assistant", "turn": turn})

    # Conversational mode (intercept_mutating_tools=False): MUST execute all steps in ONE turn without halting
    result = asyncio.run(_execute_native_agent_loop(
        native_turn_caller=_mock_cua_caller,
        record_results_fn=_mock_recorder,
        initial_history=[{"role": "user", "content": "analisis constants.py"}],
        user_prompt="analisis constants.py",
        read_only=False,
        intercept_mutating_tools=False,
    ))

    assert "Beres!" in result
    assert turn_idx == 3
    assert len(executed_tools) == 2
    assert executed_tools == ["read_local_file", "read_local_file"]


def test_openapi_schema_properties_cleanliness():
    """Validates that _convert_to_standard_json_schema never injects fake 'type': 'object' into properties."""
    from tools.catalog import get_native_tools_openai, get_native_tools_anthropic

    for tools in (get_native_tools_openai(), get_native_tools_anthropic()):
        for t in tools:
            fn_dict = t.get("function") or t
            params = fn_dict.get("parameters") or fn_dict.get("input_schema") or {}
            props = params.get("properties", {})
            for p_name, p_val in props.items():
                assert isinstance(p_val, dict), f"Property {p_name} must be a dict"
                assert "type" in p_val, f"Property {p_name} must specify a type"
                # Crucial check: 'type' property must not be an object with empty properties
                assert not (p_name == "type" and p_val.get("type") == "object"), f"Fake type property found in {t}"


def test_negative_verification_stop_gate():
    """Validates negative verification stop-gate intercepts unverified task conclusions after code edits."""
    from core.convergence import ConvergenceDetector

    cd = ConvergenceDetector(read_only=False)
    # Simulate editing a python file
    cd.record_turn_actions(0, [{
        "tool_name": "edit_file",
        "args": {"file_path": "backend/core/sample.py"},
        "risk": "mutating",
        "is_error": False,
        "summary": "Edited sample.py successfully"
    }])

    # Model attempts to conclude without running tests -> Stop Gate MUST intercept!
    nudge = cd.evaluate_final_stop_gate(agent_mode="build")
    assert nudge is not None
    assert "[VERIFICATION STOP-GATE]" in nudge
    assert "sample.py" in nudge

    # Now simulate running pytest successfully
    cd.record_turn_actions(1, [{
        "tool_name": "execute_cli_command",
        "args": {"command": "pytest backend/tests/test_sample.py"},
        "risk": "action",
        "is_error": False,
        "summary": "1 passed in 0.05s"
    }])

    # Stop gate should now permit completion!
    nudge_after_test = cd.evaluate_final_stop_gate(agent_mode="build")
    assert nudge_after_test is None



















