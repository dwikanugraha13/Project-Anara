@echo off
title Anara AI Agent - CLI Runner
cd /d "%~dp0"
if exist backend\venv\Scripts\python.exe (
    backend\venv\Scripts\python.exe cli.py %*
) else (
    python cli.py %*
)
