@echo off
setlocal
cd /d "%~dp0"
py -3.10 -m venv .venv 2>nul || python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -U pip styletts2
echo StyleTTS2 venv ready. Add .pth + config.yml to %%USERPROFILE%%\.ai_reading_studio\styletts2_models\
pause
