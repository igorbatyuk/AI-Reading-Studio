@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python venv for Whisper alignment...
  py -3.11 -m venv .venv 2>nul || py -3.12 -m venv .venv 2>nul || python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install faster-whisper
echo.
echo Whisper worker ready. Enable in Settings - Highlight - Whisper alignment.
pause
