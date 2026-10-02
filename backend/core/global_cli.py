"""
global_cli.py — Global CLI Command Installer for Project Anara.
Anara Engineering Standards:
1. Installs 'anara' command shim for Windows CMD / PowerShell (anara.cmd, anara.ps1, anara.exe) and Git Bash / MSYS / POSIX (anara).
2. Deploys native Windows PE executable (anara.exe) and launcher scripts to %LOCALAPPDATA%\\anara\\bin and ~/bin.
3. Adds %LOCALAPPDATA%\\anara\\bin permanently to Windows User PATH.
4. Synchronizes to existing in-PATH user directories for zero-restart instant terminal activation across all shells.
5. 100% parity with global standalone agent launchers.
"""

from __future__ import annotations

import io
import logging
import os
import re
import shutil
import subprocess
import sys
import zipfile
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
        return Path(sys.executable)

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
    def get_user_profile_bin_dir(cls) -> Path:
        """Returns ~/bin (canonical first directory in Git Bash $PATH on Windows)."""
        b_dir = Path.home() / "bin"
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
            "$old = if ($old) { $old } else { '' }; "
            "$new = ($old.TrimEnd(';') + ';' + $target).TrimStart(';'); "
            "[Environment]::SetEnvironmentVariable('Path', $new, 'User'); "
            "Write-Output 'ADDED' "
            "} else { Write-Output 'ALREADY' } }"
        )
        try:
            import base64
            encoded_bytes = ps_cmd.encode("utf-16le")
            encoded_cmd = base64.b64encode(encoded_bytes).decode("ascii")
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded_cmd],
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
    def build_exe_launcher(cls, target_exe: Path, py_exe: Path, cli_py: Path) -> bool:
        """
        Builds a native Windows PE executable (anara.exe) using distlib launcher stub
        with embedded shebang and zip archive containing isolated bootstrap __main__.py.
        """
        try:
            import pip._vendor.distlib.scripts as distlib_scripts
            stub_dir = os.path.dirname(distlib_scripts.__file__)
            stub_name = "t64.exe" if sys.maxsize > 2**32 else "t32.exe"
            stub_path = os.path.join(stub_dir, stub_name)
            if not os.path.isfile(stub_path):
                return False

            with open(stub_path, "rb") as f:
                stub_bytes = f.read()

            project_root = str(cli_py.parent).replace("\\", "\\\\")
            backend_dir = str(cli_py.parent / "backend").replace("\\", "\\\\")

            main_py = (
                "import os, re, sys\n"
                "os.environ.pop('PYTHONHOME', None)\n"
                "os.environ.pop('PYTHONPATH', None)\n"
                f"sys.path.insert(0, r'{project_root}')\n"
                f"sys.path.insert(0, r'{backend_dir}')\n"
                "from cli import main\n"
                "if __name__ == '__main__':\n"
                "    sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])\n"
                "    sys.exit(main())\n"
            )

            shebang = b"#!" + str(py_exe).encode("utf-8") + b"\n"

            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("__main__.py", main_py.encode("utf-8"))

            full_exe_bytes = stub_bytes + shebang + zip_buf.getvalue()
            target_exe.parent.mkdir(parents=True, exist_ok=True)
            with open(target_exe, "wb") as f:
                f.write(full_exe_bytes)
            return True
        except Exception as e:
            logger.debug(f"[GlobalCLI] Notice building native exe launcher: {e}")
            return False

    @classmethod
    def install(cls) -> Dict[str, Any]:
        """
        Installs global 'anara' command shim for all shells (CMD, PowerShell, Git Bash, WSL, POSIX).
        """
        py_exe = str(cls.get_python_exe())
        cli_py = str(cls.get_cli_script())
        anara_bin = cls.get_anara_bin_dir()
        user_bin = cls.get_user_profile_bin_dir()

        # 1. Windows Batch Command: anara.cmd
        cmd_content = (
            "@echo off\n"
            "setlocal\n"
            'set "PYTHONHOME="\n'
            'set "PYTHONPATH="\n'
            f'"{py_exe}" "{cli_py}" %*\n'
            "endlocal\n"
        )
        cmd_path = anara_bin / "anara.cmd"
        with open(cmd_path, "w", encoding="utf-8") as f:
            f.write(cmd_content)

        # 2. PowerShell Script: anara.ps1
        ps_content = (
            "#!/usr/bin/env pwsh\n"
            '[Environment]::SetEnvironmentVariable("PYTHONHOME", $null, "Process")\n'
            '[Environment]::SetEnvironmentVariable("PYTHONPATH", $null, "Process")\n'
            f'& "{py_exe}" "{cli_py}" @args\n'
        )
        ps_path = anara_bin / "anara.ps1"
        with open(ps_path, "w", encoding="utf-8") as f:
            f.write(ps_content)

        # 3. Bash/POSIX Script: anara (for Git Bash / MSYS / Cygwin / Linux / macOS)
        # Forward slashes work cleanly in POSIX shells on Windows without drive-relative mangling
        py_fwd = py_exe.replace("\\", "/")
        cli_fwd = cli_py.replace("\\", "/")

        bash_content = (
            "#!/usr/bin/env sh\n"
            "# Project Anara Universal POSIX Shell Launcher\n"
            "unset PYTHONHOME\n"
            "unset PYTHONPATH\n"
            f'PY_EXE="{py_fwd}"\n'
            f'CLI_PY="{cli_fwd}"\n'
            'exec "$PY_EXE" "$CLI_PY" "$@"\n'
        )
        sh_path = anara_bin / "anara"
        with open(sh_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(bash_content)
        try:
            os.chmod(sh_path, 0o755)
        except Exception:
            pass

        # 4. Native Windows PE Executable: anara.exe
        exe_path = anara_bin / "anara.exe"
        exe_built = cls.build_exe_launcher(exe_path, Path(py_exe), Path(cli_py))

        # 5. Add anara_bin to Windows User PATH
        cls.add_to_windows_user_path(anara_bin)

        # 6. Deploy to ~/bin (highest priority in Git Bash $PATH: /c/Users/<user>/bin)
        try:
            shutil.copy2(cmd_path, user_bin / "anara.cmd")
            shutil.copy2(ps_path, user_bin / "anara.ps1")
            shutil.copy2(sh_path, user_bin / "anara")
            if exe_built and exe_path.is_file():
                shutil.copy2(exe_path, user_bin / "anara.exe")
        except Exception as e:
            logger.debug(f"[GlobalCLI] Notice copying to user bin {user_bin}: {e}")

        # 7. Instant Zero-Restart Sync: synchronize/overwrite across all user-writable directories in PATH
        active_in_path_targets: List[str] = [str(anara_bin), str(user_bin)]
        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        user_home_lower = str(Path.home()).lower().replace("/", "\\")

        for p in path_dirs:
            p_strip = p.strip()
            if not p_strip:
                continue
            p_obj = Path(p_strip)
            if p_obj.is_dir() and os.access(p_obj, os.W_OK):
                p_lower = str(p_obj).lower().replace("/", "\\")
                if user_home_lower in p_lower and any(kw in p_lower for kw in ("python\\bin", "npm", "local\\bin", "scripts", "anara\\bin", "anara\\bin")):
                    try:
                        shutil.copy2(cmd_path, p_obj / "anara.cmd")
                        shutil.copy2(ps_path, p_obj / "anara.ps1")
                        shutil.copy2(sh_path, p_obj / "anara")
                        if exe_built and exe_path.is_file():
                            shutil.copy2(exe_path, p_obj / "anara.exe")
                        if str(p_obj) not in active_in_path_targets:
                            active_in_path_targets.append(str(p_obj))
                    except Exception:
                        pass

        # Update current process PATH
        os.environ["PATH"] = f"{user_bin};{anara_bin};{os.environ.get('PATH', '')}"

        return {
            "status": "success",
            "installed_dir": str(anara_bin),
            "user_bin_dir": str(user_bin),
            "command": "anara",
            "cmd_file": str(cmd_path),
            "ps_file": str(ps_path),
            "sh_file": str(sh_path),
            "exe_file": str(exe_path) if exe_built else None,
            "instant_sync_targets": active_in_path_targets,
            "message": "Global command 'anara' is now available across all shells and directories.",
        }

    @classmethod
    def uninstall(cls) -> Dict[str, Any]:
        """Removes anara shims and binaries."""
        targets = [cls.get_anara_bin_dir(), cls.get_user_profile_bin_dir()]
        for b_dir in targets:
            for fname in ("anara.cmd", "anara.ps1", "anara", "anara.exe"):
                f = b_dir / fname
                if f.is_file():
                    try:
                        f.unlink()
                    except Exception:
                        pass
        return {"status": "success", "message": "Global 'anara' command uninstalled."}

    @classmethod
    def is_installed(cls) -> bool:
        anara_bin = cls.get_anara_bin_dir()
        return (
            (anara_bin / "anara.cmd").is_file()
            or (anara_bin / "anara.exe").is_file()
            or (anara_bin / "anara").is_file()
        )


global_cli_installer = GlobalCLIInstaller()
