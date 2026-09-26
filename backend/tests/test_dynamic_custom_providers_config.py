import pytest
import os
from unittest.mock import patch

from memory import memory_engine
from providers.discovery import detect_model_capabilities
from providers.profile_implementations import OpenAICompatibleProviderProfile


def test_custom_provider_merged_from_config():
    """Verifies declarative custom providers from config.yaml are merged into get_custom_providers()."""
    fake_config = {
        "model": {
            "custom_providers": [
                {
                    "name": "Test Docker vLLM",
                    "prefix": "dockervllm",
                    "base_url": "http://10.0.0.5:8000/v1",
                    "api_key": "secret_dockervllm_key",
                    "default_model": "qwen2.5-coder-7b",
                    "is_active": True
                }
            ]
        }
    }

    with patch("config.load_config", return_value=fake_config):
        providers = memory_engine.get_custom_providers(include_secrets=True)
        found = [p for p in providers if p["prefix"] == "dockervllm"]
        assert len(found) == 1, "Expected dockervllm provider to be loaded from config"
        assert found[0]["base_url"] == "http://10.0.0.5:8000/v1"
        assert found[0]["api_key"] == "secret_dockervllm_key"
        assert found[0]["source"] == "config.yaml"

        # Verify endpoint routing
        profile = OpenAICompatibleProviderProfile()
        ep, headers, target_m = profile._resolve_endpoint_and_headers("dockervllm/qwen2.5-coder-7b")
        assert ep == "http://10.0.0.5:8000/v1/chat/completions"
        assert headers["Authorization"] == "Bearer secret_dockervllm_key"
        assert target_m == "qwen2.5-coder-7b"


def test_detect_model_capabilities_dynamic_handshake():
    """Verifies capability handshake from OpenRouter, Ollama, and OpenAI metadata."""
    # 1. OpenRouter multimodal format
    or_item = {
        "id": "qwen/qwen-2.5-vl-72b-instruct",
        "architecture": {"modality": "text+image->text"},
        "modalities": ["text", "image"]
    }
    caps = detect_model_capabilities(or_item, or_item["id"])
    assert caps["supports_vision"] is True
    assert caps["supports_text"] is True

    # 2. Ollama clip family format (e.g. llava or minicpm)
    ollama_item = {
        "name": "minicpm-v",
        "details": {"families": ["clip", "minicpm"]}
    }
    caps_ol = detect_model_capabilities(ollama_item, "minicpm-v")
    assert caps_ol["supports_vision"] is True

    # 3. Reasoning model format (e.g. deepseek-reasoner or o3-mini)
    reasoning_item = {
        "id": "deepseek-reasoner"
    }
    caps_r = detect_model_capabilities(reasoning_item, "deepseek-reasoner")
    assert caps_r["supports_reasoning"] is True

    # 4. Audio realtime format
    audio_item = {
        "id": "gpt-4o-realtime-preview",
        "modalities": ["text", "audio"]
    }
    caps_a = detect_model_capabilities(audio_item, "gpt-4o-realtime-preview")
    assert caps_a["supports_audio"] is True
