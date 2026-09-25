@echo off
title Stop Project Anara (Background Daemon)
color 0C
echo ======================================================================
echo            STOPPING PROJECT ANARA BACKGROUND DAEMON
echo ======================================================================
echo.

:: 1. Try stopping gracefully via CLI daemon manager
set "PYTHON_EXE=python"
if exist "%~dp0backend\venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0backend\venv\Scripts\python.exe"

"%PYTHON_EXE%" "%~dp0cli.py" daemon stop >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [OK] Anara Daemon successfully stopped via CLI manager.
    timeout /t 2 >nul
    exit /b 0
)

:: 2. Check official PID files (Anara Lifecycle Ledger)
set "RUN_DIR=%LOCALAPPDATA%\anara\run"
if exist "%RUN_DIR%\backend.pid" (
    set /p B_PID=<"%RUN_DIR%\backend.pid"
    if defined B_PID (
        echo Stopping Backend PID %B_PID% from ledger...
        taskkill /F /PID %B_PID% >nul 2>&1
        del /f /q "%RUN_DIR%\backend.pid" >nul 2>&1
    )
)

if exist "%RUN_DIR%\frontend.pid" (
    set /p F_PID=<"%RUN_DIR%\frontend.pid"
    if defined F_PID (
        echo Stopping Frontend PID %F_PID% from ledger...
        taskkill /F /PID %F_PID% >nul 2>&1
        del /f /q "%RUN_DIR%\frontend.pid" >nul 2>&1
    )
)

echo Checking remaining backend processes (port 8000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    tasklist /FI "PID eq %%a" 2>nul | findstr /I "python node cmd" >nul
    if not errorlevel 1 (
        echo Stopping Backend process PID %%a...
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo Checking frontend processes (port 3000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000" ^| findstr "LISTENING"') do (
    tasklist /FI "PID eq %%a" 2>nul | findstr /I "python node cmd" >nul
    if not errorlevel 1 (
        echo Stopping Frontend process PID %%a...
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo.
echo [OK] All Project Anara background processes have been stopped.
echo ======================================================================
timeout /t 3 >nul
exit /b 0
