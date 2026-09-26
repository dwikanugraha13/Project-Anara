import pytest
import os
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from memory import memory_engine
import tools.vision_tools as vt


def test_resolve_anthropic_vision_model_uses_active():
    orig = memory_engine.get_app_setting("active_ai_model")
    try:
        memory_engine.set_app_setting("active_ai_model", "anthropic/claude-3-7-sonnet")
        model = vt._resolve_anthropic_vision_model()
        assert model == "claude-3-7-sonnet", f"Expected claude-3-7-sonnet, got {model}"

        memory_engine.set_app_setting("active_ai_model", "claude-3-5-haiku-20241022")
        model2 = vt._resolve_anthropic_vision_model()
        assert model2 == "claude-3-5-haiku-20241022", f"Expected claude-3-5-haiku-20241022, got {model2}"
    finally:
        memory_engine.set_app_setting("active_ai_model", orig or "gemini-2.0-flash")


def test_resolve_fallback_vision_model_dynamic():
    orig = memory_engine.get_app_setting("active_ai_model")
    try:
        memory_engine.set_app_setting("active_ai_model", "openai/gpt-4o")
        model = vt._resolve_fallback_vision_model()
        assert model == "gpt-4o", f"Expected gpt-4o, got {model}"

        memory_engine.set_app_setting("active_ai_model", "qwen/qwen-2.5-vl-72b-instruct")
        model2 = vt._resolve_fallback_vision_model()
        assert "qwen" in model2.lower()
    finally:
        memory_engine.set_app_setting("active_ai_model", orig or "gemini-2.0-flash")


def test_tool_vision_analyze_anthropic_payload_dynamic():
    orig = memory_engine.get_app_setting("active_ai_model")
    captured_payloads = []

    class DummyResponse:
        status_code = 200
        text = '{"content": [{"type": "text", "text": "Dynamic Anthropic vision output"}]}'
        def json(self):
            return {"content": [{"type": "text", "text": "Dynamic Anthropic vision output"}]}

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass
        async def post(self, url, headers=None, json=None, **kwargs):
            captured_payloads.append({"url": url, "headers": headers, "json": json})
            return DummyResponse()
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    async def _run():
        memory_engine.set_app_setting("active_ai_model", "anthropic/claude-3-7-sonnet")
        from core.key_manager import key_manager as km_inst
        with patch("httpx.AsyncClient", DummyClient), \
             patch("memory.memory_engine.get_custom_providers", return_value=[]), \
             patch("providers.accounts.get_provider_key", side_effect=lambda p: "test_anthropic_key" if p == "anthropic" else None), \
             patch.object(km_inst, "execute_with_failover", side_effect=RuntimeError("no gemini key")), \
             patch("os.path.isfile", return_value=True), \
             patch("os.path.abspath", return_value="C:/dummy/test.png"), \
             patch("builtins.open", unittest.mock.mock_open(read_data=b"fake_png")):
            
            # Directly verify _resolve_anthropic_vision_model returns dynamic model
            m = vt._resolve_anthropic_vision_model()
            assert m == "claude-3-7-sonnet"

            # Execute vision tool
            res = await vt._tool_vision_analyze("C:/dummy/test.png", "Describe this image")
            assert res["status"] == "success"
            assert len(captured_payloads) == 1
            payload = captured_payloads[0]["json"]
            assert payload["model"] == "claude-3-7-sonnet", f"Expected model 'claude-3-7-sonnet' in payload, got {payload.get('model')}"

    try:
        asyncio.run(_run())
    finally:
        memory_engine.set_app_setting("active_ai_model", orig or "gemini-2.0-flash")
