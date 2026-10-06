---
category: autonomous-ai-agents
name: agent-cli-and-launcher-engineering
description: Use when building agent CLI runners and cross-shell shims.
---

# Agent CLI & Launcher Engineering

Use this skill when auditing, designing, building, or troubleshooting agent CLI entry points, cross-shell launchers (CMD, PowerShell, Git Bash, MSYS2, POSIX), zero-restart PATH deployment, and terminal workspace initialization.

## Core Architectural Invariants

### 1. Forward-Slash Windows Paths in POSIX Shell Shims (Git Bash Mangling Defense)
- When authoring POSIX wrapper scripts (e.g. `anara`) for Git Bash, MSYS, or Cygwin on Windows, **NEVER** convert Windows drive paths (`C:\...`) to MSYS mount paths (`/c/...`) as arguments to native Windows PE binaries (such as `python.exe`).
- Native Windows applications do not recognize `/c/` as a root drive letter; Windows interprets the leading `/` as the root of the current drive (`C:`), expanding `/c/Users/...` into `C:\c\Users\...` and throwing `[Errno 2] No such file or directory`.
- Use forward-slash Windows paths (e.g. `C:/Users/Bravo/.../python.exe` and `C:/Users/Bravo/.../cli.py`): POSIX shells on Windows natively execute `C:/...` binary paths without error, AND native Windows binaries receive arguments they parse correctly.

### 2. Multi-Shell 4-Tier Launcher Matrix
A robust CLI installation on Windows requires four complementary artifacts deployed side-by-side:
1. **Windows Command Script (`<name>.cmd`)**: Batch launcher for `cmd.exe` using `setlocal` and clearing `PYTHONHOME` and `PYTHONPATH` (`set "PYTHONHOME="`, `set "PYTHONPATH="`) to prevent user global Python environments from corrupting the agent virtualenv.
2. **PowerShell Script (`<name>.ps1`)**: Native PowerShell launcher using `[Environment]::SetEnvironmentVariable` to clear process-level Python variables and forwarding `@args`.
3. **POSIX Shell Script (`<name>`)**: Extensionless shell script with forward-slash Windows paths and `unset PYTHONHOME PYTHONPATH`.
4. **Native Windows PE Executable (`<name>.exe`)**: Compiled/assembled binary launcher using `pip._vendor.distlib.scripts` launcher stubs (`t64.exe` or `t32.exe`) + embedded shebang `#!{py_exe}\n` + embedded zip containing an isolated `__main__.py` that injects `{project_root}` and `{backend_dir}` into `sys.path`. Native `.exe` files have the highest execution priority across CMD, PowerShell, and the Windows Run dialog.

### 3. Dual-Path Installation & Zero-Restart PATH Synchronization
- Deploy the 4-tier launcher matrix to both:
  1. The canonical agent binary folder: `%LOCALAPPDATA%/<agent>/bin`, permanently registered in `HKCU\Environment\Path` via PowerShell.
  2. The user profile binary folder: `~/bin` (`C:\Users\<user>\bin`), which holds the highest priority in Git Bash's default `$PATH` (`/c/Users/<user>/bin`).
- On installation or update, scan all directories in the live process `os.environ["PATH"]`. For every writable user directory (`npm`, `Python\bin`, virtualenv scripts, tool directories), copy and overwrite existing shims. This guarantees instant zero-restart activation and eliminates stale or broken shims from shadowing the working launcher.

### 4. Silent Git Branch Detection in Non-Git Workspaces
- When probing git branch status during CLI banner and toolbar initialization (`git branch --show-current`), always redirect standard error (`stderr=subprocess.DEVNULL`).
- When a user launches the CLI in a non-git directory (e.g. user home `C:\Users\<user>` or system temp), Git writes `fatal: not a git repository (or any of the parent directories): .git` to stderr. Redirecting stderr prevents this harmless diagnostic from polluting the CLI interface.

### 5. Windows NTFS Junction & Reparse Point Traversal Defense
- When recursively scanning workspace directory trees starting from an arbitrary `cwd` (such as `C:\Users\<user>`), Windows user profile directories contain hidden NTFS junction points (`Application Data`, `Cookies`, `Recent`, `SendTo`, `Start Menu`).
- Attempting to descend into these junctions raises `PermissionError: [WinError 5] Access is denied` or `FileNotFoundError: [WinError 3] The system cannot find the path specified`.
- Check `getattr(entry.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400` (`FILE_ATTRIBUTE_REPARSE_POINT`). If set, skip the entry immediately.
- Catch all remaining filesystem permission and path errors quietly and log at `logger.debug` rather than `logger.warning` to prevent terminal console flooding on startup.

### 6. Windows `.bat`/`.vbs` Service Launchers for FastAPI/Uvicorn
- **Launch via uvicorn from project root**, not `cd backend && python main.py`. The correct command is `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000` with `PYTHONPATH` set to the `backend/` directory. Running `main.py` directly from within `backend/` causes import path issues and misaligned `os.getcwd()` for workspace resolution.
- **CWD for backend launch:** Set working directory to project root, not `backend/`. VBS: `sh.CurrentDirectory = rootDir`, BAT: `cd /d "%~dp0"`.
- **Python version fallback chain must be current:** Always include the latest installed Python in the fallback chain (e.g. Python314 before Python312/311). Stale chains that stop at Python312 silently fall back to a global `python` which may lack project dependencies.
- **`.vbs` silent launcher:** Uses `sh.Run cmd, 0, False` (window style 0 = hidden, False = async). Set `PYTHONIOENCODING=utf-8`, `PYTHONPATH=backendDir`, and `ANARA_SILENT_DAEMON=1` as process-level environment variables before launching.
- **`.bat` visible launcher:** Uses `start "title" cmd /k "..."` to open separate windows for backend, frontend, and tunnel. Include port-conflict pre-check (`netstat -ano | findstr ":8000"`) before launching.
- **STOP script:** Layer three shutdown strategies: (1) CLI daemon manager `cli.py daemon stop`, (2) PID file ledger at `%LOCALAPPDATA%\<agent>\run\*.pid`, (3) port-scan fallback killing LISTENING processes on 8000/3000.

### 7. Fast-Path Standalone CLI Subcommands
- The CLI entry point should intercept standalone inspection flags (`--version`, `-v`, `version`, `status`, `models`, `install-cli`) before loading heavy prompt sessions or conversational history.
- Provide clean, immediate machine-readable and human-readable output with exit code 0.
