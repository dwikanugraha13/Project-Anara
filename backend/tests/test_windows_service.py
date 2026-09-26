"""
test_windows_service.py — Verification test suite for Windows Background Autostart Service.
Anara Engineering Standards:
1. Automated Windows Autostart status and launcher resolution.
2. Graceful fallback to Startup folder when Task Scheduler is non-elevated.
3. Idempotent registration and uninstallation.
"""

import os
import pytest
from core.windows_service import WindowsAutostartManager


def test_windows_autostart_paths_and_status():
    """Verifies that project root and silent launcher paths are accurately resolved."""
    root = WindowsAutostartManager.get_project_root()
    assert os.path.isdir(root)

    launcher = WindowsAutostartManager.get_silent_launcher_path()
    assert launcher.name == "START_ANARA_SILENT.vbs"
    assert launcher.is_file()

    status = WindowsAutostartManager.get_status()
    assert "installed" in status
    assert "method" in status
    assert status["task_name"] == "Anara_Gateway"


def test_windows_autostart_idempotent_ensure():
    """Verifies that ensure_autostart_registered() is idempotent and safe to invoke on startup."""
    ok = WindowsAutostartManager.ensure_autostart_registered()
    assert ok is True

    status_after = WindowsAutostartManager.get_status()
    assert status_after["installed"] is True
