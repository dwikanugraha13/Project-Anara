@echo off
title Anara 3D AI Assistant - Launcher
color 0B

:: ════════════════════════════════════════════════════════════════════
::  ANARA LAUNCHER — run Backend FastAPI + Frontend Next.js
::  Double-click: automatically requests Administrator permission via UAC.
:: ════════════════════════════════════════════════════════════════════

:: ── Auto-elevate to Administrator ────────────────────────────────────
net session >nul 2>&1
if %errorLevel% equ 0 goto :admin_ok

echo Requesting Administrator access...
powershell -NoProfile -Command "try { Start-Process -FilePath '%~f0' -Verb RunAs } catch { exit 1 }"
if errorlevel 1 (
    color 0C
    echo.
    echo  [CANCEL] Administrator permission denied. Server can still run
    echo  without admin: re-run and select "Yes", or run
    echo  backend and frontend manually from a regular CMD.
    echo.
    pause
)
exit /b

:admin_ok
:: Ensure working directory is the script folder
cd /d "%~dp0"

echo ======================================================================
echo            ANARA 3D AI ASSISTANT - LAUNCHER (ADMIN MODE)
echo ======================================================================
echo.

:: ── [0/4] Validate project structure ───────────────────────────────────
if not exist "%~dp0backend\main.py" (
    color 0C
    echo.
    echo  [ERROR] backend\main.py not found! Ensure launcher is in root 'Project Anara'.
    echo.
    pause
    exit /b 1
)
if not exist "%~dp0frontend\package.json" (
    color 0C
    echo.
    echo  [ERROR] frontend\package.json not found!
    echo.
    pause
    exit /b 1
)

echo  [0/4] Project structure valid.
echo.

:: ── [1/4] Resolve path python.exe & npm.cmd (resilient in Administrator context) ──
set "PYTHON_CMD="
if exist "%~dp0backend\venv\Scripts\python.exe" set "PYTHON_CMD=%~dp0backend\venv\Scripts\python.exe"
if not defined PYTHON_CMD for /f "delims=" %%i in ('where python.exe 2^>nul') do (
    if not defined PYTHON_CMD set "PYTHON_CMD=%%i"
)
if not defined PYTHON_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not defined PYTHON_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PYTHON_CMD if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PYTHON_CMD set "PYTHON_CMD=python"
echo  [1/4] Python found: %PYTHON_CMD%

set "NPM_CMD="
for /f "delims=" %%i in ('where npm.cmd 2^>nul') do (
    if not defined NPM_CMD set "NPM_CMD=%%i"
)
if not defined NPM_CMD if exist "%ProgramFiles%\nodejs\npm.cmd" set "NPM_CMD=%ProgramFiles%\nodejs\npm.cmd"
if not defined NPM_CMD if exist "%APPDATA%\npm\npm.cmd" set "NPM_CMD=%APPDATA%\npm\npm.cmd"
if defined NPM_CMD (
    echo  [1/4] npm found: %NPM_CMD%
) else (
    color 0E
    echo  [WARNING] npm not found in PATH or standard Node.js location.
    echo               Frontend window may fail to start. Ensure Node.js v18+
    echo               is installed for ALL USERS or add to System PATH.
)
echo.

:: ── [2/4] Install frontend dependencies if not present ──────────────
if not exist "%~dp0frontend\node_modules\" (
    echo  [2/4] node_modules not found — running "npm install" once...
    pushd "%~dp0frontend"
    call "%NPM_CMD%" install
    popd
) else (
    echo  [2/4] Frontend dependencies ready ^(node_modules found^).
)
echo.

:: ── [3/4] Check port 8000 / 3000 that may still be in use ───────────
set "PORT_WARN=0"
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul 2>&1 && (
    echo  [WARNING] Port 8000 already in use by another process — backend may be duplicate.
    set "PORT_WARN=1"
)
netstat -ano | findstr /R /C:":3000 .*LISTENING" >nul 2>&1 && (
    echo  [WARNING] Port 3000 already in use by another process — frontend may be duplicate.
    set "PORT_WARN=1"
)
if "%PORT_WARN%"=="1" echo.
echo  [3/4] Port check complete.
echo.

:: ── [4/4] Launch both servers in separate windows ────────────────
echo  [4/4] Starting servers...
echo.

echo   ^> Backend FastAPI  ^(http://localhost:8000^)
start "Anara - Backend Server" cmd /k "cd /d ""%~dp0backend"" && ""%PYTHON_CMD%"" main.py"

echo   ^> Frontend Next.js ^(http://localhost:3000^)
start "Anara - Frontend Web" cmd /k "cd /d ""%~dp0frontend"" && ""%NPM_CMD%"" run dev"

echo   ^> Cloudflare Tunnel ^(https://anara.my.id^)
start "Anara - Remote Tunnel" cmd /c "cd /d ""%~dp0"" && ""%PYTHON_CMD%"" cli.py gateway tunnel"

echo.
echo ======================================================================
echo   SERVER & CLOUDFLARE TUNNEL LAUNCHED!
echo.
echo   - Backend     : http://localhost:8000   (docs: /docs)
echo   - 3D Companion: http://localhost:3000   (Voice, Avatar, HUD)
echo   - Code Studio : http://localhost:3000/code (Autonomous AI IDE)
echo   - Remote Web  : https://anara.my.id     (Cloudflare Gateway)
echo.
echo   Wait until both windows finish loading, then open browser
echo   at http://localhost:3000 or http://localhost:3000/code
echo.
echo   If any window shows an error, it will NOT close automatically
echo   so the error message can be read.
echo ======================================================================
timeout /t 8 >nul
exit /b 0
