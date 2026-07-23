@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PIPER_DIR=%~dp0piper"
set "PIPER_EXE=%PIPER_DIR%\piper.exe"

if exist "%PIPER_EXE%" if exist "%PIPER_DIR%\onnxruntime.dll" (
    echo Piper already installed: %PIPER_EXE%
    goto :models
)

echo Downloading Piper for Windows...
set "ZIP=%TEMP%\piper_windows_amd64.zip"
set "URL=https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"

powershell -NoProfile -Command ^
  "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%URL%' -OutFile '%ZIP%'"

if errorlevel 1 (
    echo Download failed. Manual: https://github.com/rhasspy/piper/releases
    pause
    exit /b 1
)

echo Extracting...
if exist "%PIPER_DIR%" rmdir /s /q "%PIPER_DIR%"
powershell -NoProfile -Command ^
  "Expand-Archive -Path '%ZIP%' -DestinationPath '%~dp0_extract' -Force"

if exist "%~dp0_extract\piper\piper.exe" (
    move "%~dp0_extract\piper" "%PIPER_DIR%" >nul
) else (
    echo Unexpected zip layout.
    pause
    exit /b 1
)

rmdir /s /q "%~dp0_extract" 2>nul
del "%ZIP%" 2>nul

if not exist "%PIPER_EXE%" (
    echo piper.exe not found after extract.
    pause
    exit /b 1
)

echo Piper installed: %PIPER_EXE%

:models
echo.
echo Add .onnx models to this folder, e.g. en_US-lessac-medium.onnx
pause
