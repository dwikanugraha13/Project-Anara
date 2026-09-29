"""
global_cli.py — Global CLI Command Installer for Project Anara.
Anara Engineering Standards:
1. Installs 'anara' command shim for Windows CMD / PowerShell (anara.cmd) and Git Bash / MSYS (anara).
2. Deploys to %LOCALAPPDATA%\\anara\\bin and adds it permanently to User PATH.
3. Synchronizes to existing in-PATH user directories for zero-restart instant terminal activation.
4. Parity with global CLI tools like 'hermes' and 'claude'.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("anara.core.global_cli")


class GlobalCLIInstaller:
    """Manages the installation and discovery of the global 'anara' terminal command."""

    @classmethod
    def get_project_root(cls) -> Path:
        current_file = Path(__file__).resolve()
        return current_file.parent.parent.parent

    @classmethod
    def get_python_exe(cls) -> Path:
        root = cls.get_project_root()
        venv_py = root / "backend" / "venv" / "Scripts" / "python.exe"
        if venv_py.is_file():
            return venv_py
        dot_venv_py = root / "backend" / ".venv" / "Scripts" / "python.exe"
        if dot_venv_py.is_file():
            return dot_venv_py
        return Path(os.sys.executable)

    @classmethod
    def get_cli_script(cls) -> Path:
        root = cls.get_project_root()
        return root / "cli.py"

    @classmethod
    def get_anara_bin_dir(cls) -> Path:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            b_dir = Path(local_app_data) / "anara" / "bin"
        else:
            b_dir = Path.home() / ".anara" / "bin"
        b_dir.mkdir(parents=True, exist_ok=True)
        return b_dir

    @classmethod
    def is_in_path(cls, directory: Path) -> bool:
        norm_target = str(directory.resolve()).lower().rstrip("\\/")
        current_path = os.environ.get("PATH", "")
        for p in current_path.split(os.pathsep):
            if p.strip() and str(Path(p).resolve()).lower().rstrip("\\/") == norm_target:
                return True
        return False

    @classmethod
    def add_to_windows_user_path(cls, directory: Path) -> bool:
        """Permanently appends directory to Windows HKCU\\Environment\\Path via PowerShell."""
        if os.name != "nt":
            return False
        dir_str = str(directory.resolve()).replace("'", "''")
        ps_cmd = (
            f"$target = '{dir_str}'; "
            "[Environment]::GetEnvironmentVariable('Path', 'User') -split ';' | "
            "Where-Object { $_ -eq $target } | Measure-Object | ForEach-Object { "
            "if ($_.Count -eq 0) { "
            "$old = [Environment]::GetEnvironmentVariable('Path', 'User'); "
            "$new = ($old.TrimEnd(';') + ';' + $target).TrimStart(';'); "
            "[Environment]::SetEnvironmentVariable('Path', $new, 'User'); "
            "Write-Output 'ADDED' "
            "} else { Write-Output 'ALREADY' } }"
        )
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            return "ADDED" in res.stdout or "ALREADY" in res.stdout
        except Exception as e:
            logger.debug(f"[GlobalCLI] Notice updating User PATH: {e}")
            return False

    @classmethod
    def install(cls) -> Dict[str, Any]:
        """
        Installs global 'anara' command shim for all shells.
        """
        py_exe = str(cls.get_python_exe())
        cli_py = str(cls.get_cli_script())
        anara_bin = cls.get_anara_bin_dir()

        # 1. Windows Batch Command: anara.cmd
        cmd_content = (
            f"@echo off\n"
            f'"{py_exe}" "{cli_py}" %*\n'
        )
        cmd_path = anara_bin / "anara.cmd"
        with open(cmd_path, "w", encoding="utf-8") as f:
            f.write(cmd_content)

        # 2. Bash/POSIX Script: anara
        # Convert C:\ to /c/ for MSYS / Git Bash compatibility
        py_bash = py_exe.replace("\\", "/")
        if len(py_bash) >= 2 and py_bash[1] == ":":
            py_bash = f"/{py_bash[0].lower()}{py_bash[2:]}"
        cli_bash = cli_py.replace("\\", "/")

        bash_content = (
            f"#!/usr/bin/env sh\n"
            f'exec "{py_bash}" "{cli_bash}" "$@"\n'
        )
        sh_path = anara_bin / "anara"
        with open(sh_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(bash_content)
        try:
            os.chmod(sh_path, 0o755)
        except Exception:
            pass

        # 3. Add anara_bin to Windows User PATH
        cls.add_to_windows_user_path(anara_bin)

        # 4. Instant Zero-Restart Sync: also deploy to existing user directories in PATH
        # (e.g. %LOCALAPPDATA%\Python\bin or npm global bin)
        active_in_path_targets: List[str] = []
        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        for p in path_dirs:
            p_strip = p.strip()
            if not p_strip:
                continue
            p_obj = Path(p_strip)
            if p_obj.is_dir() and os.access(p_obj, os.W_OK):
                # Identify user-owned bin directories
                p_lower = str(p_obj).lower().replace("/", "\\")
                user_home_lower = str(Path.home()).lower().replace("/", "\\")
                if user_home_lower in p_lower and any(kw in p_lower for kw in ("python\\bin", "npm", "local\\bin", "scripts")):
                    try:
                        shutil.copy2(cmd_path, p_obj / "anara.cmd")
                        shutil.copy2(sh_path, p_obj / "anara")
                        active_in_path_targets.append(str(p_obj))
                    except Exception:
                        pass

        # Also update current process os.environ['PATH']
        os.environ["PATH"] = f"{anara_bin};{os.environ.get('PATH', '')}"

        return {
            "status": "success",
            "installed_dir": str(anara_bin),
            "command": "anara",
            "cmd_file": str(cmd_path),
            "sh_file": str(sh_path),
            "instant_sync_targets": active_in_path_targets,
            "message": "Global command 'anara' is now available in any terminal window.",
        }

    @classmethod
    def uninstall(cls) -> Dict[str, Any]:
        """Removes anara shims."""
        anara_bin = cls.get_anara_bin_dir()
        for f in (anara_bin / "anara.cmd", anara_bin / "anara"):
            if f.is_file():
                try:
                    f.unlink()
                except Exception:
                    pass
        return {"status": "success", "message": "Global 'anara' command uninstalled."}

    @classmethod
    def is_installed(cls) -> bool:
        cmd_path = cls.get_anara_bin_dir() / "anara.cmd"
        return cmd_path.is_file()


global_cli_installer = GlobalCLIInstaller()
