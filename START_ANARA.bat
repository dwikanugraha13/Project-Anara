@echo off
title Anara 3D AI Assistant - Launcher
color 0B

:: ════════════════════════════════════════════════════════════════════
::  ANARA LAUNCHER — jalankan Backend FastAPI + Frontend Next.js
::  Double-click saja: otomatis minta izin Administrator via UAC.
:: ════════════════════════════════════════════════════════════════════

:: ── Auto-elevate ke Administrator ────────────────────────────────────
net session >nul 2>&1
if %errorLevel% equ 0 goto :admin_ok

echo Meminta hak akses Administrator...
powershell -NoProfile -Command "try { Start-Process -FilePath '%~f0' -Verb RunAs } catch { exit 1 }"
if errorlevel 1 (
    color 0C
    echo.
    echo  [BATAL] Izin Administrator ditolak. Server tetap bisa dijalankan
    echo  tanpa admin: jalankan ulang lalu pilih "Yes", atau jalankan
    echo  backend dan frontend secara manual dari CMD biasa.
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

:: ── [0/4] Validasi struktur proyek ───────────────────────────────────
if not exist "%~dp0backend\main.py" (
    color 0C
    echo.
    echo  [ERROR] backend\main.py tidak ditemukan! Pastikan launcher ada di root 'Project Anara'.
    echo.
    pause
    exit /b 1
)
if not exist "%~dp0frontend\package.json" (
    color 0C
    echo.
    echo  [ERROR] frontend\package.json tidak ditemukan!
    echo.
    pause
    exit /b 1
)

echo  [0/4] Struktur proyek valid.
echo.

:: ── [1/4] Resolve path npm.cmd (tahan banting di konteks Administrator) ──
set "NPM_CMD="
for /f "delims=" %%i in ('where npm.cmd 2^>nul') do (
    if not defined NPM_CMD set "NPM_CMD=%%i"
)
if not defined NPM_CMD if exist "%ProgramFiles%\nodejs\npm.cmd" set "NPM_CMD=%ProgramFiles%\nodejs\npm.cmd"
if not defined NPM_CMD if exist "%APPDATA%\npm\npm.cmd" set "NPM_CMD=%APPDATA%\npm\npm.cmd"
if defined NPM_CMD (
    echo  [1/4] npm ditemukan: %NPM_CMD%
) else (
    color 0E
    echo  [PERINGATAN] npm tidak ditemukan di PATH maupun lokasi standar Node.js.
    echo               Jendela frontend mungkin gagal start. Pastikan Node.js v18+
    echo               terinstall untuk SEMUA USER atau tambahkan ke System PATH.
)
echo.

:: ── [2/4] Install dependencies frontend bila belum ada ──────────────
if not exist "%~dp0frontend\node_modules\" (
    echo  [2/4] node_modules belum ada — menjalankan "npm install" sekali...
    pushd "%~dp0frontend"
    call "%NPM_CMD%" install
    popd
) else (
    echo  [2/4] Dependencies frontend siap ^(node_modules ada^).
)
echo.

:: ── [3/4] Cek port 8000 / 3000 yang mungkin masih terpakai ───────────
set "PORT_WARN=0"
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul 2>&1 && (
    echo  [PERINGATAN] Port 8000 sudah dipakai proses lain — backend mungkin duplikat.
    set "PORT_WARN=1"
)
netstat -ano | findstr /R /C:":3000 .*LISTENING" >nul 2>&1 && (
    echo  [PERINGATAN] Port 3000 sudah dipakai proses lain — frontend mungkin duplikat.
    set "PORT_WARN=1"
)
if "%PORT_WARN%"=="1" echo.
echo  [3/4] Pengecekan port selesai.
echo.

:: ── [4/4] Luncurkan kedua server di jendela terpisah ────────────────
echo  [4/4] Menjalankan server...
echo.

echo   ^> Backend FastAPI  ^(http://localhost:8000^)
start "Anara - Backend Server" cmd /k "cd /d ""%~dp0backend"" && if exist venv\Scripts\python.exe (venv\Scripts\python.exe main.py) else (if exist venv\Scripts\activate.bat (call venv\Scripts\activate.bat) && python main.py)"

echo   ^> Frontend Next.js ^(http://localhost:3000^)
start "Anara - Frontend Web" cmd /k "cd /d ""%~dp0frontend"" && ""%NPM_CMD%"" run dev"

echo.
echo ======================================================================
echo   KEDUA SERVER DILUNCURKAN DI JENDELA CMD TERPISAH!
echo.
echo   - Backend     : http://localhost:8000   (docs: /docs)
echo   - 3D Companion: http://localhost:3000   (Voice, Avatar, HUD)
echo   - Code Studio : http://localhost:3000/code (Autonomous AI IDE)
echo.
echo   Tunggu sampai kedua jendela selesai loading, lalu buka browser
echo   ke http://localhost:3000 atau http://localhost:3000/code
echo.
echo   Jika salah satu jendela menampilkan error, jendela itu TIDAK akan
echo   tertutup otomatis agar pesan errornya bisa dibaca.
echo ======================================================================
timeout /t 8 >nul
exit /b 0
