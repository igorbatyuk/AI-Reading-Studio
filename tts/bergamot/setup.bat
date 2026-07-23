@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if errorlevel 1 (
  echo Python launcher "py" not found. Install Python 3.10 from python.org
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating Bergamot venv ^(Python 3.10^)...
  py -3.10 -m venv .venv
  if errorlevel 1 (
    echo Failed to create venv. Install Python 3.10 ^(bergamot wheels require 3.10 or older^).
    exit /b 1
  )
)

echo Installing bergamot package...
".venv\Scripts\python.exe" -m pip install -U pip bergamot
if errorlevel 1 exit /b 1

echo.
echo Download example model en -^> uk ^(enuk^)...
".venv\Scripts\python.exe" -m bergamot download -m enuk
if errorlevel 1 (
  echo Download failed. You can retry later:
  echo   .venv\Scripts\python.exe -m bergamot download -m enuk
)

echo.
echo List available / installed models:
".venv\Scripts\python.exe" -m bergamot ls

echo.
echo Done. In the app: Settings -^> Translation -^> Bergamot ^(local^)
endlocal
