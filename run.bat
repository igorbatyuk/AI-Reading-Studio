@echo off
chcp 65001 >nul
title AI Reading Studio
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo Python not found. Install Python 3.12+ from https://www.python.org/
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo Error: requirements.txt not found.
    pause
    exit /b 1
)

python -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install dependencies.
        pause
        exit /b 1
    )
)

python main.py
if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
