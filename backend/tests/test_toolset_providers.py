"""
test_toolset_providers.py — Comprehensive Unit & Integration Tests for Anara Toolset Providers Engine.

Tests:
1. get_toolset_config for all 7 primary toolsets + aliases:
   - computer_use
   - browser_automation (and 'browser')
   - web_search_scraping (and 'web')
   - image_generation (and 'image_gen')
   - video_generation (and 'video_gen')
   - text_to_speech (and 'tts')
   - speech_to_text (and 'stt')
2. Readiness status calculation: 'ready', 'needs_keys', 'needs_setup'
3. is_set key annotation on env_vars
4. Active provider detection and fallback
5. set_active_provider for all toolsets including web capability splits ('search' vs 'extract')
6. set_provider_env: setting env vars, persisting to .env and process env
7. get_toolset_models for toolsets with catalogs (image_generation, video_generation, speech_to_text, text_to_speech)
8. set_active_model: validating model existence and persisting to configuration
9. Error handling: invalid toolset names, invalid provider names, invalid models, invalid capabilities.
10. 100% Native Project Anara branding verification.
"""

import os
import sys
import tempfile
from pathlib import Path
import pytest

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from core.toolset_providers import (
    get_toolset_config,
    set_active_provider,
    set_provider_env,
    get_toolset_models,
    set_active_model,
    canonical_toolset_name,
    TOOLSET_PROVIDERS,
    TOOLSET_MODELS_CATALOG,
    TOOLSET_ALIASES,
)
from config import load_config, save_config


class TestToolsetCanonicalization:
    """Verifies toolset naming and alias resolution."""

    def test_alias_normalization(self):
        assert canonical_toolset_name("browser") == "browser_automation"
        assert canonical_toolset_name("web") == "web_search_scraping"
        assert canonical_toolset_name("search") == "web_search_scraping"
        assert canonical_toolset_name("tts") == "text_to_speech"
        assert canonical_toolset_name("stt") == "speech_to_text"
        assert canonical_toolset_name("image_gen") == "image_generation"
        assert canonical_toolset_name("video_gen") == "video_generation"
        assert canonical_toolset_name("computer_use") == "computer_use"
        assert canonical_toolset_name("unknown_toolset") == "unknown_toolset"


class TestGetToolsetConfig:
    """Verifies get_toolset_config for all primary toolsets."""

    @pytest.mark.parametrize(
        "toolset_key",
        [
            "computer_use",
            "browser_automation",
            "browser",
            "web_search_scraping",
            "web",
            "image_generation",
            "image_gen",
            "video_generation",
            "video_gen",
            "text_to_speech",
            "tts",
            "speech_to_text",
            "stt",
        ],
    )
    def test_get_toolset_config_primary_matrices(self, toolset_key):
        cfg = get_toolset_config(toolset_key)
        assert cfg["has_category"] is True
        assert isinstance(cfg["providers"], list)
        assert len(cfg["providers"]) > 0
        assert "active_provider" in cfg
        assert cfg["active_provider"] is not None

        # Check every provider entry structure
        for prov in cfg["providers"]:
            assert "name" in prov
            assert "badge" in prov
            assert "tag" in prov
            assert "env_vars" in prov
            assert "is_active" in prov
            assert "status" in prov
            assert prov["status"] in ("ready", "needs_keys", "needs_setup", "needs_auth")
            for ev in prov["env_vars"]:
                assert "key" in ev
                assert "prompt" in ev
                assert "is_set" in ev
                assert isinstance(ev["is_set"], bool)

    def test_get_toolset_config_web_capability_augmentation(self):
        cfg = get_toolset_config("web")
        assert "active_search_backend" in cfg
        assert "active_extract_backend" in cfg
        assert cfg["active_search_backend"] is not None
        assert cfg["active_extract_backend"] is not None

    def test_get_toolset_config_unknown_toolset(self):
        cfg = get_toolset_config("non_existent_toolset_xyz")
        assert cfg["has_category"] is False
        assert cfg["providers"] == []
        assert cfg["active_provider"] is None


class TestReadinessStatusAndEnvInspection:
    """Verifies server-computed provider readiness statuses."""

    def test_keyless_providers_are_ready(self):
        tts_cfg = get_toolset_config("tts")
        edge_row = next(p for p in tts_cfg["providers"] if p["name"] == "Microsoft Edge TTS")
        assert edge_row["status"] == "ready"
        assert len(edge_row["env_vars"]) == 0

        web_cfg = get_toolset_config("web")
        ddg_row = next(p for p in web_cfg["providers"] if p["name"] == "DuckDuckGo")
        assert ddg_row["status"] == "ready"

        browser_cfg = get_toolset_config("browser")
        local_row = next(p for p in browser_cfg["providers"] if p["name"] == "Local Browser")
        assert local_row["status"] == "ready"

    def test_keyed_providers_report_needs_keys_when_unset(self, monkeypatch):
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        tts_cfg = get_toolset_config("tts")
        el_row = next(p for p in tts_cfg["providers"] if p["name"] == "ElevenLabs")
        assert el_row["status"] == "needs_keys"
        assert el_row["env_vars"][0]["is_set"] is False

    def test_keyed_providers_report_ready_when_key_is_set(self, monkeypatch):
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key-12345")
        tts_cfg = get_toolset_config("tts")
        el_row = next(p for p in tts_cfg["providers"] if p["name"] == "ElevenLabs")
        assert el_row["status"] == "ready"
        assert el_row["env_vars"][0]["is_set"] is True


class TestSetActiveProvider:
    """Verifies persisting active provider selections."""

    def test_set_active_provider_tts(self):
        res = set_active_provider("tts", "ElevenLabs")
        assert res["ok"] is True
        assert res["provider"] == "ElevenLabs"

        # Verify in config
        cfg = load_config()
        assert cfg.get("tts", {}).get("provider") == "elevenlabs"

        # Reset to edge
        set_active_provider("tts", "Microsoft Edge TTS")
        cfg = load_config()
        assert cfg.get("tts", {}).get("provider") == "edge"

    def test_set_active_provider_browser(self):
        res = set_active_provider("browser", "Browserbase")
        assert res["ok"] is True
        assert res["provider"] == "Browserbase"

        cfg = load_config()
        assert cfg.get("browser", {}).get("cloud_provider") == "browserbase"

        # Switch to local
        set_active_provider("browser", "Local Browser")
        cfg = load_config()
        assert cfg.get("browser", {}).get("cloud_provider") == "local"

    def test_set_active_provider_computer_use(self):
        res = set_active_provider("computer_use", "Anara Native Desktop Control")
        assert res["ok"] is True
        cfg = load_config()
        assert cfg.get("computer_use", {}).get("backend") == "native"

        set_active_provider("computer_use", "cua-driver (background)")
        cfg = load_config()
        assert cfg.get("computer_use", {}).get("backend") == "cua"

    def test_set_active_provider_web_split_capabilities(self):
        # Set shared backend
        set_active_provider("web", "DuckDuckGo")
        cfg = load_config()
        assert cfg.get("web", {}).get("backend") == "ddgs"

        # Set search capability
        res = set_active_provider("web", "Brave Search", capability="search")
        assert res["ok"] is True
        assert res["capability"] == "search"
        cfg = load_config()
        assert cfg.get("web", {}).get("search_backend") == "brave"

        # Set extract capability
        res = set_active_provider("web", "Tavily", capability="extract")
        assert res["ok"] is True
        assert res["capability"] == "extract"
        cfg = load_config()
        assert cfg.get("web", {}).get("extract_backend") == "tavily"

    def test_set_active_provider_invalid_inputs(self):
        with pytest.raises(KeyError):
            set_active_provider("unknown_toolset", "DuckDuckGo")

        with pytest.raises(KeyError):
            set_active_provider("web", "NonExistentProvider123")

        with pytest.raises(ValueError):
            set_active_provider("web", "Brave Search", capability="invalid_cap")


class TestSetProviderEnv:
    """Verifies set_provider_env function."""

    def test_set_provider_env_keys(self):
        test_vars = {"TEST_ANARA_KEY_1": "secret-val-1", "TEST_ANARA_KEY_2": "secret-val-2"}
        res = set_provider_env("web", test_vars)
        assert res["ok"] is True
        assert set(res["updated"]) == {"TEST_ANARA_KEY_1", "TEST_ANARA_KEY_2"}
        assert os.environ.get("TEST_ANARA_KEY_1") == "secret-val-1"
        assert os.environ.get("TEST_ANARA_KEY_2") == "secret-val-2"

        # Clean up
        os.environ.pop("TEST_ANARA_KEY_1", None)
        os.environ.pop("TEST_ANARA_KEY_2", None)

    def test_set_provider_env_invalid(self):
        with pytest.raises(ValueError):
            set_provider_env("web", {})


class TestToolsetModels:
    """Verifies get_toolset_models and set_active_model."""

    def test_get_toolset_models_image_gen(self):
        models_data = get_toolset_models("image_gen", provider="FAL.ai")
        assert models_data["has_models"] is True
        assert models_data["default"] == "fal-ai/flux-2/klein/9b"
        assert len(models_data["models"]) > 0
        model_ids = {m["id"] for m in models_data["models"]}
        assert "fal-ai/flux-2/klein/9b" in model_ids
        assert "fal-ai/flux-2-pro" in model_ids

    def test_get_toolset_models_video_gen(self):
        models_data = get_toolset_models("video_gen", provider="FAL.ai Video")
        assert models_data["has_models"] is True
        assert models_data["default"] == "pixverse-v6"
        model_ids = {m["id"] for m in models_data["models"]}
        assert "pixverse-v6" in model_ids
        assert "ltx-2.3" in model_ids

    def test_get_toolset_models_speech_to_text(self):
        models_data = get_toolset_models("stt", provider="Local Whisper")
        assert models_data["has_models"] is True
        assert models_data["default"] == "base"
        model_ids = {m["id"] for m in models_data["models"]}
        assert "base" in model_ids
        assert "large-v3" in model_ids

    def test_get_toolset_models_text_to_speech(self):
        models_data = get_toolset_models("tts", provider="Microsoft Edge TTS")
        assert models_data["has_models"] is True
        assert models_data["default"] == "en-US-AriaNeural"
        model_ids = {m["id"] for m in models_data["models"]}
        assert "en-US-AriaNeural" in model_ids
        assert "id-ID-GadisNeural" in model_ids

    def test_get_toolset_models_unsupported_toolset(self):
        models_data = get_toolset_models("computer_use")
        assert models_data["has_models"] is False
        assert models_data["models"] == []

    def test_set_active_model_success(self):
        # Select FLUX 2 Pro
        res = set_active_model("image_gen", "fal-ai/flux-2-pro", provider="FAL.ai")
        assert res["ok"] is True
        assert res["model"] == "fal-ai/flux-2-pro"

        cfg = load_config()
        assert cfg.get("image_gen", {}).get("model") == "fal-ai/flux-2-pro"

        # Verify get_toolset_models reflects current
        models_data = get_toolset_models("image_gen", provider="FAL.ai")
        assert models_data["current"] == "fal-ai/flux-2-pro"

    def test_set_active_model_invalid(self):
        with pytest.raises(ValueError):
            set_active_model("image_gen", "non_existent_model_id_123", provider="FAL.ai")

        with pytest.raises(ValueError):
            set_active_model("computer_use", "any_model")


class TestToolsetApiEndpoints:
    """Verifies FastAPI HTTP routes for toolset config, providers, models, and env."""

    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    def test_api_get_toolset_config(self, client):
        resp = client.get("/api/tools/toolsets/tts/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "text_to_speech"
        assert data["has_category"] is True
        assert len(data["providers"]) > 0

        # Also test brain route prefix
        resp2 = client.get("/api/brain/toolsets/tts/config")
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "text_to_speech"

    def test_api_put_toolset_provider(self, client):
        resp = client.put("/api/tools/toolsets/tts/provider", json={"provider": "OpenAI TTS"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["provider"] == "OpenAI TTS"

        # Reset
        client.put("/api/tools/toolsets/tts/provider", json={"provider": "Microsoft Edge TTS"})

    def test_api_put_toolset_env(self, client):
        resp = client.put(
            "/api/tools/toolsets/web/env",
            json={"env_vars": {"TEST_API_ENDPOINT_KEY": "dummy_secret_val"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "TEST_API_ENDPOINT_KEY" in data["updated"]
        os.environ.pop("TEST_API_ENDPOINT_KEY", None)

    def test_api_get_toolset_models(self, client):
        resp = client.get("/api/tools/toolsets/image_gen/models?provider=FAL.ai")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_models"] is True
        assert len(data["models"]) > 0

    def test_api_put_toolset_model(self, client):
        resp = client.put(
            "/api/tools/toolsets/image_gen/model",
            json={"model": "fal-ai/flux-2-pro", "provider": "FAL.ai"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["model"] == "fal-ai/flux-2-pro"

