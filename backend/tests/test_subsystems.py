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
    from tools.output_manager import compact_tool_output, compact_tool_payload
    short_text = "Standard short terminal output"
    assert compact_tool_output(short_text) == short_text

    long_output = "\n".join([f"Processing item {i}: [STATUS_OK]" for i in range(120)])
    compacted = compact_tool_output(long_output, max_lines=40, max_chars=1200)
    assert "[OUTPUT TERPOTONG:" in compacted
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
    assert any("entri lainnya disembunyikan" in str(f) for f in compacted_payload["files"])
    assert "src/module_0/index.ts" in compacted_payload["files"]
    assert "src/module_149/index.ts" in compacted_payload["files"]
    assert "[OUTPUT TERPOTONG:" in compacted_payload["details"]["output"]


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
        assert "[BERKAS DILAMPIRKAN DARI WHATSAPP]:" in wa_formatted
        assert "- Tipe: Document" in wa_formatted
        assert "- Nama Berkas: analytics.py" in wa_formatted
        assert "- Lokasi Tersimpan di PC:" in wa_formatted
        assert "calculate_metrics" in wa_formatted
        assert "Tolong periksa dan proses berkas dokumen analytics.py" in wa_formatted
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
    assert "Balas *setujui*" in wa_payload["text"]

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
    assert "Katakan 'gas' atau 'lanjutkan'" in v_payload["speech_text"]
    assert "Aku akan memperbarui berkas" in v_payload["speech_text"]
    assert "```" not in v_payload["speech_text"]


def test_voice_approval_pass_through_and_intents():
    """Verify semantic model-driven spoken affirmation and cancellation without hardcoded tuples."""
    import asyncio
    from core.plan_detector import classify_approval_intent

    async def _test_intents():
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
    assert "Mode Suara Berhasil Diperbarui" in res_set.text
    assert get_chat_voice_mode("telegram", "chat_101") == "only"

    req_status = ChannelRequest(
        text="/voice status",
        channel="telegram",
        channel_id="chat_101",
        user_id="u1"
    )
    res_status = asyncio.run(handle_channel_command(req_status))
    assert res_status is not None
    assert "PENGATURAN MODE SUARA" in res_status.text
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
        assert "dibatalkan" in res_reject.text.lower()
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
        assert "kedaluwarsa" in res_exp.text.lower()
        assert "5 menit" in res_exp.text.lower()

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
    assert "dipangkas oleh compactor" in compacted or "disembunyikan" in compacted
    assert len(compacted.splitlines()) <= 35


def test_subsystem_4_error_classifier_and_recovery_guidance():
    """Verify Subsystem 4: ErrorClassifier pattern taxonomy and tailored recovery guidance."""
    from tools.self_correction import ErrorClassifier, format_recovery_guidance

    # 1. Missing Python Package
    t1, d1 = ErrorClassifier.classify("ModuleNotFoundError: No module named 'fastapi_limiter'")
    assert t1 == "missing_python_pkg"
    assert d1 == "fastapi_limiter"
    g1 = format_recovery_guidance(t1, d1, 1, 3)
    assert "fastapi_limiter" in g1
    assert "Dependensi Python" in g1

    # 2. Missing Node Package
    t2, d2 = ErrorClassifier.classify("Error: Cannot find module 'tailwind-merge'")
    assert t2 == "missing_node_pkg"
    assert d2 == "tailwind-merge"
    g2 = format_recovery_guidance(t2, d2, 1, 3)
    assert "npm install tailwind-merge" in g2

    # 3. Port Conflict
    t3, d3 = ErrorClassifier.classify("Error: listen EADDRINUSE: address already in use :::8000")
    assert t3 == "port_conflict"
    g3 = format_recovery_guidance(t3, d3, 2, 3)
    assert "digunakan oleh proses lain" in g3

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
    assert "DIAGNOSTIK EKSEKUSI ANARA" in card
    assert "Akar Masalah" in card
    assert "Upaya Mandiri yang Telah Dijalankan" in card
    assert "Rekomendasi Solusi" in card
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
    assert "- Status Berkas" in snapshot
    assert "Perintah Verifikasi Uji Proyek:" in snapshot

    # Test Prompt Assembly with Ground Truth Injected
    prompt = PromptAssembler.assemble(
        mode="build",
        speaker_name="Tester",
        user_task="sudah ku implementasikan subsistem 4 ini , apakah sudah beres semua?",
        channel="telegram",
        session_id=9999
    )
    assert "PEMBUKTIAN FAKTA BERBASIS GROUND-TRUTH" in prompt
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
        assert "dilindungi" in r2["message"].lower()

        # Safely deletes a targeted test file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp:
            tmp_path = tmp.name
            tmp.write(b"content to be safely deleted")

        assert os.path.isfile(tmp_path)
        r3 = await _tool_delete_local_file(tmp_path)
        assert r3["status"] == "success"
        assert not os.path.exists(tmp_path)

    asyncio.run(run_tool_tests())










