"""
test_connections_unified_endpoints.py — Verifies the Unified Connections Endpoints
in Project Anara (GET & POST /api/integrations/connections).
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app
from memory import memory_engine


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_get_unified_connections(client):
    """Verifies GET /api/integrations/connections returns aggregate platforms."""
    resp = client.get("/api/integrations/connections")
    assert resp.status_code == 200
    data = resp.json()
    assert "connections" in data
    assert isinstance(data["connections"], list)

    platform_ids = [c["id"] for c in data["connections"]]
    assert "telegram" in platform_ids
    assert "whatsapp" in platform_ids
    assert "google" in platform_ids
    assert "spotify" in platform_ids

    for c in data["connections"]:
        assert "id" in c
        assert "name" in c
        assert "category" in c
        assert "status" in c
        assert "enabled" in c
        assert "config" in c
        assert "meta" in c


def test_save_connection_whatsapp(client):
    """Verifies POST /api/integrations/connections/whatsapp whitelist updating."""
    test_number = "628999999999"
    resp = client.post(
        "/api/integrations/connections/whatsapp",
        json={"config": {"allowed_numbers": test_number}, "enabled": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["platform"] == "whatsapp"

    # Verify persisted in memory_engine
    val = memory_engine.get_app_setting("whatsapp_allowed_numbers")
    assert test_number in (val or "")


def test_save_connection_google_email_validation(client):
    """Verifies email regex validation on Google Workspace connection."""
    # Invalid email
    bad_resp = client.post(
        "/api/integrations/connections/google",
        json={"config": {"email": "not-an-email"}, "enabled": True},
    )
    assert bad_resp.status_code == 400
    assert "Invalid email" in bad_resp.json()["detail"]

    # Valid email
    good_resp = client.post(
        "/api/integrations/connections/google",
        json={"config": {"email": "tester@anara.local"}, "enabled": True},
    )
    assert good_resp.status_code == 200
    assert good_resp.json()["status"] == "success"


def test_save_connection_custom_platform(client):
    """Verifies dynamic persistence for other connection platforms (Discord, Slack, etc.)."""
    resp = client.post(
        "/api/integrations/connections/discord",
        json={"config": {"bot_token": "mock_discord_token_123"}, "enabled": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["platform"] == "discord"
    assert data["enabled"] is True
    assert data["config"]["bot_token"] == "mock_discord_token_123"
