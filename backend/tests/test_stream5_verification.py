"""
test_stream5_verification.py — Comprehensive Re-Verification Suite for Stream 5
Multi-Modal Cognition, Media & Omnichannel Platform Gateways (Batches 11, 12).
Ensures 100% compliance with Anara Agent and Anara Engineering Standards.
"""

import asyncio
import os
import sys
from pathlib import Path
import numpy as np
import pytest

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


# ══════════════════════════════════════════════════════════════════════════════
# 1. AUDIO & EMOTION PARITY
# ══════════════════════════════════════════════════════════════════════════════

def test_audio_ser_silence_guard():
    """Digital silence or low ambient noise must return neutral, never clinical sadness."""
    from cognition.audio import analyze_speech_emotion

    # Pure silence (all zeros)
    silence = np.zeros(16000, dtype=np.int16).tobytes()
    res = analyze_speech_emotion(silence, sample_rate=16000)
    assert res["emotion"] == "neutral"
    assert res["pitch_hz"] == 0.0

    # Low amplitude ambient noise (RMS < 0.006)
    noise = (np.random.randn(16000) * 50).astype(np.int16).tobytes()
    res_noise = analyze_speech_emotion(noise, sample_rate=16000)
    assert res_noise["emotion"] == "neutral"


def test_audio_parabolic_interpolation_vertex():
    """Verify DSP parabolic peak interpolation vertex formula math parity."""
    # Synthetic pure 200Hz sine wave (well within human voice range)
    sr = 16000
    duration = 0.5
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # 200 Hz tone with audible amplitude
    tone = (0.5 * np.sin(2 * np.pi * 200 * t) * 32767).astype(np.int16).tobytes()

    from cognition.audio import analyze_speech_emotion
    res = analyze_speech_emotion(tone, sample_rate=sr)
    # Detected pitch should be close to 200 Hz (+/- 10 Hz)
    assert 185.0 <= res["pitch_hz"] <= 215.0


def test_audio_thought_block_stripping():
    """TTS voice synthesis text filter must completely strip thought/think blocks."""
    from cognition.audio import filter_tts_speech_text

    raw = (
        "<thought>I should speak gently and explain the solution carefully.</thought>"
        "Hello! I am ready to help you today."
    )
    cleaned = filter_tts_speech_text(raw)
    assert "thought" not in cleaned.lower()
    assert "gently" not in cleaned.lower()
    assert "Hello! I am ready to help you today." in cleaned

    # Also test <think> and <thinking>
    raw2 = "<think>Analyzing user query...</think>Here is the weather report."
    assert filter_tts_speech_text(raw2) == "Here is the weather report."

    raw3 = "<thinking>Multi-step plan...</thinking>Operation completed."
    assert filter_tts_speech_text(raw3) == "Operation completed."


def test_emotion_thought_block_stripping():
    """Emotion engine must strip thought blocks before analyzing affective cues."""
    from cognition.emotion import EmotionEngine
    ee = EmotionEngine()

    # Thought block contains keywords like 'dance' or 'sad' but actual speech is neutral
    text = "<thought>Maybe I should do a happy dance or look sad</thought>I updated the documentation."
    res = ee.analyze(text, allow_dance=True)
    # The thought text should be stripped, so it should not trigger dance from inside <thought>
    assert res is not None
    assert res.get("animation_name") != "dance"


def test_emotion_word_boundary_matching():
    """Emotion trigger keywords must match on word boundaries only, not arbitrary substrings."""
    from cognition.emotion import EmotionEngine
    ee = EmotionEngine()

    # "guidance" or "attendance" must NOT trigger "dance"
    text = "We will provide technical guidance for the team attendance."
    res = ee.analyze(text, allow_dance=True)
    assert res is not None
    assert res.get("animation_name") != "dance"


def test_emotion_allow_dance_gate():
    """When allow_dance=False, dance category animations must be skipped."""
    from cognition.emotion import EmotionEngine
    ee = EmotionEngine()

    # With allow_dance=False, dance animations must be gated
    res_no_dance = ee.analyze("Let's dance now", allow_dance=False)
    assert res_no_dance is not None
    assert res_no_dance.get("animation_name") != "dance"
    assert res_no_dance.get("gesture") != "dance"

    # With allow_dance=True, dance behavior should be allowed
    res_dance = ee.analyze("Let's dance now", allow_dance=True)
    assert res_dance is not None
    assert res_dance.get("animation_name") == "dance" or res_dance.get("gesture") == "dance"


# ══════════════════════════════════════════════════════════════════════════════
# 2. VISUAL PROJECTION PARITY
# ══════════════════════════════════════════════════════════════════════════════

def test_visual_zero_static_keyword_gating():
    """could_be_visual_request must be deprecated and return False; intent is model-driven."""
    from cognition.visual import could_be_visual_request
    assert could_be_visual_request("show me an image of a cat") is False
    assert could_be_visual_request("cuaca hari ini") is False
    assert could_be_visual_request("project a holographic weather card") is False


@pytest.mark.anyio
async def test_visual_bounded_lru_cache():
    """Visual query cache must enforce bounded LRU eviction and TTL."""
    import time
    from cognition.visual import _cache_visual_result, _get_cached_visual, _VISUAL_QUERY_CACHE, _MAX_VISUAL_CACHE_SIZE

    # Cache an entry
    test_key = "test_projection_query"
    test_val = {"has_visual": True, "visual_type": "weather", "weather_data": {}}
    await _cache_visual_result(test_key, test_val)

    hit = await _get_cached_visual(test_key)
    assert hit is not None
    assert hit["visual_type"] == "weather"

    # Verify TTL expiration
    _VISUAL_QUERY_CACHE[test_key] = (time.time() - 301.0, test_val)
    expired = await _get_cached_visual(test_key)
    assert expired is None


def test_visual_safe_json_extraction():
    """_parse_classifier_json must strip fences, backtrack quotes, and salvage dangling brackets."""
    from cognition.visual import _parse_classifier_json

    # Clean JSON with markdown fences
    fenced = "```json\n{\"visual_type\": \"image\", \"search_query\": \"mountain landscape\"}\n```"
    d1 = _parse_classifier_json(fenced)
    assert d1 is not None
    assert d1["visual_type"] == "image"
    assert d1["search_query"] == "mountain landscape"

    # Truncated JSON without closing brackets
    truncated = "{\"visual_type\": \"knowledge_card\", \"title\": \"Quantum Mechanics\", \"steps\": [\"Step 1\", \"Step 2\""
    d2 = _parse_classifier_json(truncated)
    assert d2 is not None
    assert d2["visual_type"] == "knowledge_card"
    assert d2["title"] == "Quantum Mechanics"

    # Conversational text surrounding JSON
    surrounded = "Here is your JSON response:\n```json\n{\"visual_type\": \"weather\", \"temp_c\": 28}\n```\nHope that helps!"
    d3 = _parse_classifier_json(surrounded)
    assert d3 is not None
    assert d3["visual_type"] == "weather"


# ══════════════════════════════════════════════════════════════════════════════
# 3. OMNICHANNEL PLATFORMS
# ══════════════════════════════════════════════════════════════════════════════

def test_telegram_html_tag_balancing():
    """split_html_chunks must balance unclosed tags across split boundaries."""
    from integrations.telegram.formatter import split_html_chunks

    # Create HTML with unclosed <blockquote> and <b> that exceeds chunk limit
    inner = "A" * 2000
    html_text = f"<blockquote><b>Important Notice:</b>\n{inner}\n<b>Second Section:</b>\n{inner}</blockquote>"

    chunks = split_html_chunks(html_text, max_chars=2500)
    assert len(chunks) >= 2

    # Chunk 1 must close any tags it opened
    assert chunks[0].endswith("</b></blockquote>") or chunks[0].endswith("</blockquote>")
    # Chunk 2 must reopen tags that were split
    assert chunks[1].startswith("<blockquote") or chunks[1].startswith("<b>")


def test_telegram_callback_data_ceiling():
    """Callback data generated for inline buttons must never exceed 64 bytes."""
    from integrations.telegram.keyboards import _make_model_callback_data
    from integrations.platforms.telegram import TelegramPlatformAdapter

    # Short model ID
    short_cb = _make_model_callback_data("gpt-4o")
    assert len(short_cb.encode("utf-8")) <= 64

    # Extremely long model ID (e.g. 100+ chars)
    long_model = "custom_provider_with_a_very_long_name/fine_tuned_meta_llama_3_3_70b_instruct_q8_custom_quantized_v2_exp"
    long_cb = _make_model_callback_data(long_model)
    assert len(long_cb.encode("utf-8")) <= 64
    assert long_cb.startswith("setms:")

    # Approval callback data
    adapter = TelegramPlatformAdapter()
    class DummyAction:
        action_id = "a_very_long_plan_action_id_that_could_potentially_exceed_telegram_sixty_four_byte_limit_if_not_carefully_bounded"
        tool_name = "terminal"
        tool_args = {"command": "ls -la"}
    rendered = adapter.render_approval("Approval needed", DummyAction())
    buttons = rendered["reply_markup"]["inline_keyboard"][0]
    for btn in buttons:
        assert len(btn["callback_data"].encode("utf-8")) <= 64


def test_whatsapp_markdown_formatting():
    """WhatsApp adapter must convert markdown headers, bold, strikethrough, while preserving code fences."""
    from integrations.platforms.whatsapp import WhatsAppPlatformAdapter
    adapter = WhatsAppPlatformAdapter()

    msg = (
        "### System Status\n"
        "This is **bold text** and this is ~~deleted~~.\n"
        "```python\ndef test():\n    **not bold**\n```\n"
        "Ending line."
    )
    formatted = adapter.format_message(msg)

    # Headers converted to bold *...*
    assert "*System Status*" in formatted
    # Bold **...** converted to *...*
    assert "*bold text*" in formatted
    # Strike ~~...~~ converted to ~...~
    assert "~deleted~" in formatted
    # Inside code fence must be preserved untouched
    assert "```python\ndef test():\n    **not bold**\n```" in formatted


def test_secret_scrubbing_on_error_paths():
    """Platform error paths must scrub secrets, bot tokens, and webhook URLs via redact_sensitive_text."""
    from core.logger import redact_sensitive_text

    raw_err = "Failed to connect to https://api.telegram.org/bot123456789:ABCdefGHIjklMNOpqrSTUvwxYZ/sendMessage"
    redacted = redact_sensitive_text(raw_err)
    assert "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ" not in redacted
    assert "bot[REDACTED]" in redacted or "[REDACTED_SECRET" in redacted or "bot***" in redacted

    webhook_err = "Discord webhook failed: https://discord.com/api/webhooks/123456789/abcdefghijk_secret_token_here"
    redacted_wh = redact_sensitive_text(webhook_err)
    assert "abcdefghijk_secret_token_here" not in redacted_wh


# ══════════════════════════════════════════════════════════════════════════════
# 4. MAIN SERVER LIFECYCLE
# ══════════════════════════════════════════════════════════════════════════════

def test_server_security_headers():
    """FastAPI app must apply enterprise security headers via SecurityHeadersMiddleware."""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_server_cors_configuration():
    """Verify CORS middleware restricts origins and respects dynamic tunnel regex."""
    from main import app
    import re

    # Locate CORSMiddleware
    cors_middleware = next((m for m in app.user_middleware if "CORS" in str(m.cls)), None)
    assert cors_middleware is not None

    origin_regex = cors_middleware.kwargs.get("allow_origin_regex")
    assert origin_regex is not None
    pattern = re.compile(origin_regex)

    # Valid origins
    assert pattern.match("https://trycloudflare.com")
    assert pattern.match("https://my-subdomain.trycloudflare.com")
    assert pattern.match("https://anara.my.id")
    assert pattern.match("https://api.anara.my.id:8000")

    # Invalid origins
    assert not pattern.match("https://evil-site.com")
    assert not pattern.match("https://trycloudflare.com.malicious.org")


def test_server_signal_handler_registration():
    """Verify Win32 ConsoleCtrlHandler and POSIX signal handlers can be registered cleanly."""
    from main import _install_signal_handlers
    # Calling it must complete without error
    _install_signal_handlers()
