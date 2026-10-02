"""
test_global_cli.py — Verification test suite for Global 'anara' Terminal Command Installer.
Anara Engineering Standards:
1. Generation of anara.cmd and anara POSIX shell shims.
2. Resolution of python.exe and cli.py paths.
3. Zero-crash execution and idempotent registration.
"""

import os
import pytest
from core.global_cli import GlobalCLIInstaller


def test_global_cli_installer_paths_and_generation():
    """Verifies that project root, python.exe, and shims are generated correctly."""
    root = GlobalCLIInstaller.get_project_root()
    assert os.path.isdir(root)

    py_exe = GlobalCLIInstaller.get_python_exe()
    assert py_exe.is_file()

    cli_py = GlobalCLIInstaller.get_cli_script()
    assert cli_py.is_file()
    assert cli_py.name == "cli.py"

    res = GlobalCLIInstaller.install()
    assert res["status"] == "success"
    assert res["command"] == "anara"

    cmd_file = res["cmd_file"]
    assert os.path.isfile(cmd_file)
    with open(cmd_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "cli.py" in content

    sh_file = res["sh_file"]
    assert os.path.isfile(sh_file)
    with open(sh_file, "r", encoding="utf-8") as f:
        content_sh = f.read()
    assert "cli.py" in content_sh

    ps_file = res["ps_file"]
    assert os.path.isfile(ps_file)
    with open(ps_file, "r", encoding="utf-8") as f:
        content_ps = f.read()
    assert "cli.py" in content_ps

    if res.get("exe_file"):
        assert os.path.isfile(res["exe_file"])

    assert GlobalCLIInstaller.is_installed() is True
