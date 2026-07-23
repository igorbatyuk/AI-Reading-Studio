@echo off
chcp 65001 >nul
cd /d "%~dp0"

where py >nul 2>&1
if errorlevel 1 (
    echo Python launcher not found. Install Python 3.11 from https://www.python.org/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python 3.11 venv...
    py -3.11 -m venv .venv
    if errorlevel 1 (
        echo Failed to create venv. Try: py -3.11 -m venv .venv
        pause
        exit /b 1
    )
)

echo Installing Coqui TTS (this may take several minutes)...
.venv\Scripts\python.exe -m pip install -U pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo pip install failed.
    pause
    exit /b 1
)

echo.
echo Done. Add speaker .wav files to tts\xtts\speakers\ — see speakers\README.md
pause
