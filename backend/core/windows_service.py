"""
windows_service.py — Native Windows Background Daemon & Autostart Manager for Project Anara.
Anara Engineering Standards:
1. Automated registration into Windows Task Scheduler (schtasks.exe) on user login.
2. Graceful non-elevated fallback to the Windows user Startup folder (shell:startup).
3. Zero-window silent background execution on machine boot/restart.
4. Idempotent check: runs once on first setup/start and persists across system reboots.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("anara.core.windows_service")

TASK_NAME_DEFAULT = "Anara_Gateway"
TASK_DESCRIPTION = "Project Anara Autonomous AI Assistant — Background Gateway Service"


class WindowsAutostartManager:
    """Manages automatic startup for Project Anara across Windows reboots."""

    @staticmethod
    def is_windows() -> bool:
        return os.name == "nt"

    @classmethod
    def get_project_root(cls) -> Path:
        """Resolves project root directory."""
        # backend/core/windows_service.py -> ../../ -> Project Anara
        current_file = Path(__file__).resolve()
        return current_file.parent.parent.parent

    @classmethod
    def get_silent_launcher_path(cls) -> Path:
        """Returns path to START_ANARA_SILENT.vbs in project root."""
        root = cls.get_project_root()
        vbs = root / "START_ANARA_SILENT.vbs"
        if not vbs.is_file():
            # Fallback search
            cwd_vbs = Path.cwd() / "START_ANARA_SILENT.vbs"
            if cwd_vbs.is_file():
                return cwd_vbs
        return vbs

    @classmethod
    def get_user_startup_folder(cls) -> Optional[Path]:
        """Resolves Windows user's Startup folder path."""
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return None
        folder = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        if folder.is_dir():
            return folder
        return None

    @classmethod
    def check_task_scheduler_exists(cls, task_name: str = TASK_NAME_DEFAULT) -> bool:
        """Checks if task exists in Windows Task Scheduler."""
        if not cls.is_windows():
            return False
        try:
            res = subprocess.run(
                ["schtasks", "/query", "/tn", task_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
            )
            return res.returncode == 0
        except Exception:
            return False

    @classmethod
    def check_startup_folder_exists(cls, task_name: str = TASK_NAME_DEFAULT) -> bool:
        """Checks if launcher exists in Windows Startup folder."""
        folder = cls.get_user_startup_folder()
        if not folder:
            return False
        vbs_target = folder / f"{task_name}.vbs"
        lnk_target = folder / f"{task_name}.lnk"
        return vbs_target.is_file() or lnk_target.is_file()

    @classmethod
    def get_status(cls, task_name: str = TASK_NAME_DEFAULT) -> Dict[str, Any]:
        """Returns autostart configuration status."""
        sch_ok = cls.check_task_scheduler_exists(task_name)
        startup_ok = cls.check_startup_folder_exists(task_name)
        active = sch_ok or startup_ok
        method = "task_scheduler" if sch_ok else ("startup_folder" if startup_ok else "none")

        return {
            "installed": active,
            "method": method,
            "task_scheduler": sch_ok,
            "startup_folder": startup_ok,
            "task_name": task_name,
            "launcher": str(cls.get_silent_launcher_path()),
        }

    @classmethod
    def install(
        cls,
        task_name: str = TASK_NAME_DEFAULT,
        delay_seconds: int = 30,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Installs autostart hook.
        Primary: Windows Task Scheduler (onlogon with delay).
        Fallback: Windows Startup Folder (user-level, zero privileges required).
        """
        if not cls.is_windows():
            return {
                "status": "error",
                "message": "Autostart installation is only supported on Windows.",
            }

        launcher = cls.get_silent_launcher_path()
        if not launcher.is_file():
            return {
                "status": "error",
                "message": f"Silent launcher script not found at '{launcher}'.",
            }

        # 1. Try Windows Task Scheduler
        # Format delay as mmmm:ss (minutes up to 9999, seconds up to 59 per schtasks spec)
        mins = delay_seconds // 60
        secs = delay_seconds % 60
        delay_str = f"{mins:04d}:{secs:02d}"
        cmd_str = f'wscript.exe "{launcher}"'
        sch_cmd = [
            "schtasks",
            "/create",
            "/tn",
            task_name,
            "/tr",
            cmd_str,
            "/sc",
            "onlogon",
            "/delay",
            delay_str,
        ]
        if force:
            sch_cmd.append("/f")

        try:
            res = subprocess.run(
                sch_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=10,
            )
            if res.returncode == 0:
                logger.info(f"[WindowsService] Registered '{task_name}' in Windows Task Scheduler (onlogon).")
                return {
                    "status": "success",
                    "method": "task_scheduler",
                    "message": f"Successfully registered '{task_name}' in Windows Task Scheduler (launches 30s after login).",
                }
            else:
                logger.debug(f"[WindowsService] Task scheduler note ({res.stderr.strip()}). Falling back to Startup folder.")
        except Exception as e:
            logger.debug(f"[WindowsService] Task scheduler attempt exception: {e}")

        # 2. Fallback to Windows Startup folder
        folder = cls.get_user_startup_folder()
        if not folder:
            return {
                "status": "error",
                "message": "Could not locate Windows Startup folder for fallback registration.",
            }

        vbs_target = folder / f"{task_name}.vbs"
        try:
            vbs_content = (
                f"' Project Anara Automated Startup Launcher\n"
                f"Set sh = CreateObject(\"WScript.Shell\")\n"
                f"sh.Run \"wscript.exe \"\"{launcher}\"\"\", 0, False\n"
            )
            with open(vbs_target, "w", encoding="utf-8") as f:
                f.write(vbs_content)

            logger.info(f"[WindowsService] Created startup launcher at '{vbs_target}'.")
            return {
                "status": "success",
                "method": "startup_folder",
                "message": f"Successfully registered '{task_name}' in Windows Startup Folder.",
                "path": str(vbs_target),
            }
        except Exception as err:
            logger.error(f"[WindowsService] Failed to write startup folder launcher: {err}")
            return {
                "status": "error",
                "message": f"Failed to install autostart: {err}",
            }

    @classmethod
    def uninstall(cls, task_name: str = TASK_NAME_DEFAULT) -> Dict[str, Any]:
        """Removes autostart registration from Task Scheduler and Startup Folder."""
        if not cls.is_windows():
            return {"status": "error", "message": "Only supported on Windows."}

        # 1. Remove Task Scheduler
        try:
            subprocess.run(
                ["schtasks", "/delete", "/tn", task_name, "/f"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5,
            )
        except Exception:
            pass

        # 2. Remove Startup folder file
        folder = cls.get_user_startup_folder()
        if folder:
            vbs_target = folder / f"{task_name}.vbs"
            lnk_target = folder / f"{task_name}.lnk"
            if vbs_target.is_file():
                try:
                    vbs_target.unlink()
                except Exception:
                    pass
            if lnk_target.is_file():
                try:
                    lnk_target.unlink()
                except Exception:
                    pass

        return {
            "status": "success",
            "message": f"Autostart service '{task_name}' uninstalled successfully.",
        }

    @classmethod
    def ensure_autostart_registered(cls, task_name: str = TASK_NAME_DEFAULT) -> bool:
        """
        Idempotent startup hook: verifies autostart is configured.
        If not yet registered, automatically installs it seamlessly.
        """
        status = cls.get_status(task_name)
        if not status["installed"]:
            res = cls.install(task_name, force=True)
            return res.get("status") == "success"
        return True


# Global singleton
windows_autostart = WindowsAutostartManager()
