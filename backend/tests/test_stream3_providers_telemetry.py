"""
test_stream3_providers_telemetry.py — Comprehensive Verification Suite for Stream 3
(Batches 7, 8: Providers, Model Routing & Telemetry).
Anara Enterprise Architecture Standards.
"""

import asyncio
import json
import os
import re
import tempfile
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from providers.caller import (
    StreamingThinkScrubber,
    _strip_think_blocks,
    _clean_model_chat_text,
    _execute_native_agent_loop,
    call_universal_chat_model,
    stream_universal_chat_model,
)
from providers.native_turn import NativeToolCall, NativeTurnResult, TurnUsage
from providers.profile_implementations import (
    GeminiProviderProfile,
    CodexOpenAIProviderProfile,
    AnthropicProviderProfile,
    OpenAICompatibleProviderProfile,
    _parse_openai_compatible_native_payload,
)
from providers.profile_registry import (
    resolve_provider_profile,
    get_registered_profiles,
    register_provider_profile,
)
from providers.discovery import (
    _is_vision_supported,
    _is_reasoning_model,
    refresh_codex_oauth_token_if_needed,
    _OAUTH_REFRESH_LOCK,
)
from providers.constants import _infer_model_badge_and_category
from providers.accounts import (
    _sanitize_account_for_client,
    get_fallback_model_id,
    get_providers_status_list_async,
)
from telemetry.event_bus import TelemetryEventBus, AgentEvent, EventType, ActivityProvenance
from cognition.soul import _atomic_write_soul, save_soul_raw, get_soul_prompt


# ─────────────────────────────────────────────────────────────────────────────
# 1. STREAMING THINK SCRUBBER (Anara Standard)
# ─────────────────────────────────────────────────────────────────────────────

def test_streaming_think_scrubber_closed_pairs():
    """Validates that closed <tag>...</tag> pairs are stripped regardless of boundary."""
    scrubber = StreamingThinkScrubber()
    assert scrubber.feed("<think>internal reasoning</think>Hello world") == "Hello world"
    assert scrubber.flush() == ""

    scrubber.reset()
    assert scrubber.feed("Start <thought>deliberation</thought> End") == "Start  End"
    assert scrubber.flush() == ""


def test_streaming_think_scrubber_split_across_deltas():
    """Validates that tags split across delta boundaries are safely buffered and stripped."""
    scrubber = StreamingThinkScrubber()
    d1 = scrubber.feed("<thi")
    d2 = scrubber.feed("nk>hidden reasoning</thi")
    d3 = scrubber.feed("nk>Visible text")
    tail = scrubber.flush()
    assert (d1 + d2 + d3 + tail) == "Visible text"


def test_streaming_think_scrubber_prose_mention_preserved():
    """Validates that mid-line mentions of '<think>' in prose are preserved, not stripped."""
    scrubber = StreamingThinkScrubber()
    prose = "The <think> tag is used by deep thinking models."
    result = scrubber.feed(prose) + scrubber.flush()
    assert result == prose


def test_streaming_think_scrubber_orphan_close():
    """Validates that orphan close tags are cleanly removed with whitespace (Anara Standard)."""
    scrubber = StreamingThinkScrubber()
    res = scrubber.feed("Response text</think> continues") + scrubber.flush()
    assert res == "Response textcontinues"


def test_streaming_think_scrubber_unterminated_at_boundary():
    """Validates that an unclosed think block at stream boundary discards trailing reasoning."""
    scrubber = StreamingThinkScrubber()
    res = scrubber.feed("<think>reasoning without close tag") + scrubber.flush()
    assert res == ""


# ─────────────────────────────────────────────────────────────────────────────
# 2. CONTEXT COMPACTION & CUT_IDX SAFETY (Anara Enterprise Architecture)
# ─────────────────────────────────────────────────────────────────────────────

def test_native_agent_loop_cut_idx_preserves_initial_prompt():
    """
    Validates that in-loop context compaction preserves the initial user prompt
    and does NOT produce consecutive same-role turns (Anthropic & Gemini strict alternation).
    """
    turn_counter = 0
    received_histories = []

    async def mock_caller(history):
        nonlocal turn_counter
        turn_counter += 1
        received_histories.append(list(history))
        if turn_counter == 1:
            return NativeTurnResult(
                text="",
                tool_calls=[NativeToolCall(call_id="c1", name="read_file", arguments={"path": "a.txt"})]
            )
        elif turn_counter == 2:
            return NativeTurnResult(
                text="",
                tool_calls=[NativeToolCall(call_id="c2", name="read_file", arguments={"path": "b.txt"})]
            )
        return NativeTurnResult(text="Done inspecting.")

    def record_anthropic(history, turn, results):
        raw_blocks = [{"type": "tool_use", "id": c.call_id, "name": c.name, "input": c.arguments} for c in turn.tool_calls]
        history.append({"role": "assistant", "content": raw_blocks})
        user_blocks = [{"type": "tool_result", "tool_use_id": c.call_id, "content": res} for c, res, _ in results]
        history.append({"role": "user", "content": user_blocks})

    initial_hist = [{"role": "user", "content": "Analyze system codebase"}]
    res = asyncio.run(_execute_native_agent_loop(
        native_turn_caller=mock_caller,
        record_results_fn=record_anthropic,
        initial_history=initial_hist,
        user_prompt="Analyze system codebase",
        read_only=True,
    ))
    assert "Done inspecting." in res


def test_anthropic_thinking_blocks_preservation():
    """Validates that Anthropic thinking blocks and signatures are captured in NativeTurnResult."""
    raw_payload = {
        "id": "msg_01",
        "type": "message",
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": "Plan carefully.", "signature": "sig_alpha_123"},
            {"type": "text", "text": "Here is the plan."},
            {"type": "tool_use", "id": "tu_01", "name": "read_file", "input": {"path": "main.py"}}
        ],
        "stop_reason": "tool_use",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": 10,
            "cache_read_input_tokens": 20,
        }
    }

    thinking_blocks = []
    text_parts = []
    tool_calls = []
    reasoning_txt = None
    thinking_sig = None

    for b in raw_payload["content"]:
        if b["type"] == "text":
            text_parts.append(b["text"])
        elif b["type"] == "thinking":
            reasoning_txt = b.get("thinking", "")
            thinking_sig = b.get("signature", "")
            thinking_blocks.append(b)
        elif b["type"] == "tool_use":
            tool_calls.append(NativeToolCall(call_id=b["id"], name=b["name"], arguments=b["input"]))

    turn = NativeTurnResult(
        text="".join(text_parts),
        tool_calls=tool_calls,
        reasoning=reasoning_txt,
        thinking_signature=thinking_sig,
        thinking_blocks=thinking_blocks,
        raw_response=raw_payload,
        finish_reason=raw_payload["stop_reason"],
    )

    assert turn.clean_text == "Here is the plan."
    assert len(turn.tool_calls) == 1
    assert turn.thinking_signature == "sig_alpha_123"
    assert len(turn.thinking_blocks) == 1
    assert turn.thinking_blocks[0]["signature"] == "sig_alpha_123"


# ─────────────────────────────────────────────────────────────────────────────
# 3. OPENAI SSE CHUNKS ACCUMULATOR & DELTA TOOL CALLS
# ─────────────────────────────────────────────────────────────────────────────

def test_openai_sse_accumulator_delta_assembly():
    """Validates that SSE chunks with incremental function names and arguments assemble cleanly."""
    c1 = json.dumps({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_99", "function": {"name": "run_", "arguments": '{"com'}}]}}], "finish_reason": None})
    c2 = json.dumps({"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"name": "command", "arguments": 'mand": "ls"}'}}]}}], "finish_reason": None})
    c3 = json.dumps({"choices": [{"finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 40, "completion_tokens": 20, "total_tokens": 60}})
    sse_text = f"data: {c1}\ndata: {c2}\ndata: {c3}\ndata: [DONE]\n"

    result = _parse_openai_compatible_native_payload(sse_text)
    assert len(result.tool_calls) == 1
    tc = result.tool_calls[0]
    assert tc.call_id == "call_99"
    assert tc.name == "run_command"
    assert tc.arguments == {"command": "ls"}
    assert result.finish_reason == "tool_calls"
    assert result.usage is not None
    assert result.usage["total_tokens"] == 60


# ─────────────────────────────────────────────────────────────────────────────
# 4. DISCOVERY CAPABILITY DETECTION (ZERO STATIC SUBSTRING COLLISION)
# ─────────────────────────────────────────────────────────────────────────────

def test_dynamic_vision_detection_no_vllm_collision():
    """Validates that '-vl' word boundary regex does NOT collide with '-vllm' models."""
    assert _is_vision_supported("qwen2.5-vl-72b") is True
    assert _is_vision_supported("gpt-4o-2024-11-20") is True
    assert _is_vision_supported("claude-3-7-sonnet") is True
    assert _is_vision_supported("gemini-2.5-flash") is True

    # Critical anti-collision checks:
    assert _is_vision_supported("llama-3-8b-instruct-vllm") is False
    assert _is_vision_supported("mistral-7b-vllm-backend") is False


def test_dynamic_reasoning_detection_no_substring_collision():
    """Validates that reasoning model detection uses word boundaries and regex."""
    assert _is_reasoning_model("o1-mini") is True
    assert _is_reasoning_model("o3-mini") is True
    assert _is_reasoning_model("deepseek-r1") is True
    assert _is_reasoning_model("claude-3-7-sonnet") is True

    # No collisions on arbitrary 5.3 versions or model prefixes
    assert _is_reasoning_model("custom-tokenizer-v5.3-standard") is False


def test_model_badge_and_category_word_boundaries():
    """Validates that 'live' audio detection does not collide with words like 'deliver' or 'alive'."""
    b1, cat1, _ = _infer_model_badge_and_category("gemini-3.1-flash-live-preview", "Gemini Live", "gemini")
    assert b1 == "Live Audio"
    assert cat1 == "voice_native"

    # Collision test:
    b2, cat2, _ = _infer_model_badge_and_category("project-deliver-model", "Deliver AI", "custom")
    assert b2 != "Live Audio"
    assert cat2 != "voice_native"


# ─────────────────────────────────────────────────────────────────────────────
# 5. SECRET KEY MASKING & CLIENT PAYLOAD SAFETY
# ─────────────────────────────────────────────────────────────────────────────

def test_sanitize_account_masks_secret_key():
    """Validates that raw API keys are never forwarded unmasked."""
    account = {
        "id": 1,
        "provider": "anthropic",
        "api_key": "sk-ant-api03-1234567890abcdef1234567890",
        "account_label": "Production Anthropic",
    }
    safe = _sanitize_account_for_client(account)
    assert "api_key" not in safe
    assert safe["masked_key"] == "sk-a...7890"
    assert "1234567890abcdef" not in safe["masked_key"]


def test_get_providers_status_list_masks_custom_provider_key():
    """Validates that custom provider raw API keys are masked in custom_data."""
    with patch("memory.memory_engine.get_custom_providers") as mock_custom, \
         patch("providers.discovery.get_all_dynamic_models", new_callable=AsyncMock) as mock_models:
        mock_custom.return_value = [{
            "id": 99,
            "name": "Local 9Router",
            "prefix": "9router",
            "base_url": "https://router.local/v1",
            "api_key": "sk-secret-token-abcdef123456",
            "masked_key": "sk-s...3456",
            "is_active": 1,
        }]
        mock_models.return_value = []

        providers = asyncio.run(get_providers_status_list_async(force_refresh=True))
        custom_p = next((p for p in providers if p.get("id") == "9router"), None)
        assert custom_p is not None
        # Must be masked, never raw
        assert custom_p["custom_data"]["api_key"] == "sk-s...3456"
        assert "sk-secret-token" not in json.dumps(custom_p)


# ─────────────────────────────────────────────────────────────────────────────
# 6. TELEMETRY EVENT BUS & DROP COUNTER
# ─────────────────────────────────────────────────────────────────────────────

def test_telemetry_event_bus_thread_safety_and_drop_counter():
    """Validates bounded queue eviction and thread-safe drop counter accounting."""
    bus = TelemetryEventBus()
    queue = bus.subscribe(session_id="test_session", max_queue_size=2)

    async def _emit_events():
        for i in range(4):
            await bus.emit(
                event_type=EventType.TEXT_CHUNK,
                provenance=ActivityProvenance.AGENT_ORCHESTRATOR,
                session_id="test_session",
                trace_id="tr_01",
                payload={"chunk": f"token_{i}"}
            )

    asyncio.run(_emit_events())

    dropped = bus.get_dropped_count("test_session")
    assert dropped == 2
    assert bus.get_total_dropped() == 2

    stats = bus.get_stats()
    assert stats["active_sessions"] == 1
    assert stats["total_dropped_events"] == 2

    # Verify queue contains the 2 latest items (drop-oldest)
    e1 = queue.get_nowait()
    e2 = queue.get_nowait()
    assert e1.payload["chunk"] == "token_2"
    assert e2.payload["chunk"] == "token_3"

    bus.unsubscribe("test_session", queue)


# ─────────────────────────────────────────────────────────────────────────────
# 7. SOUL ATOMIC WRITER
# ─────────────────────────────────────────────────────────────────────────────

def test_soul_atomic_write_fsync(tmp_path):
    """Validates atomic write through temporary file and fsync."""
    target_file = str(tmp_path / "soul.md")
    content = "# Soul Identity\nAnara Autonomous Coding Agent."

    ok = _atomic_write_soul(target_file, content)
    assert ok is True
    assert os.path.exists(target_file)
    with open(target_file, "r", encoding="utf-8") as f:
        readback = f.read()
    assert readback == content

    # Verify no dangling .tmp files remained
    tmp_files = [f for f in os.listdir(tmp_path) if f.endswith(".tmp")]
    assert len(tmp_files) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 8. CALLER FALLBACK LADDER EXECUTION
# ─────────────────────────────────────────────────────────────────────────────

def test_call_universal_chat_model_fallback_ladder():
    """Validates that call_universal_chat_model triggers the fallback model on primary failure."""
    primary_called = False
    fallback_called = False

    class FailingProfile:
        async def generate_chat(self, **kwargs):
            nonlocal primary_called
            primary_called = True
            raise RuntimeError("503 Service Unavailable: upstream primary quota exceeded")

    class WorkingFallbackProfile:
        async def generate_chat(self, **kwargs):
            nonlocal fallback_called
            fallback_called = True
            return "Fallback model response succeeded."

    def fake_resolver(mid):
        if mid == "failing-model":
            return FailingProfile()
        return WorkingFallbackProfile()

    with patch("providers.profile_registry.resolve_provider_profile", side_effect=fake_resolver), \
         patch("providers.accounts.get_fallback_model_id", return_value="working-fallback-model"):
        res = asyncio.run(call_universal_chat_model(
            model_id="failing-model",
            user_prompt="Hello agent",
        ))
        assert primary_called is True
        assert fallback_called is True
        assert res == "Fallback model response succeeded."
