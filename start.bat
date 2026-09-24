@echo off
title DroidRouter 9 - Android VM & Proxy Gateway Engine
chcp 65001 > nul
cd /d "%~dp0"

echo ======================================================================
echo           DROIDROUTER 9 - LOCAL ANDROID & PROXY ENGINE
echo ======================================================================
echo.
echo [1/2] Checking Python environment...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ to continue.
    pause
    exit /b 1
)

echo [2/2] Starting DroidRouter 9 local server on http://127.0.0.1:9090...
python main.py

pause
