@echo off
rem Starts Fog Studio with a Python that has MediaPipe: .venv in this folder, or ..\.venv-studio next to it.
rem Extra options pass through, e.g. --camera 1
set "STUDIO_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%STUDIO_PY%" set "STUDIO_PY=%~dp0..\.venv-studio\Scripts\python.exe"
if not exist "%STUDIO_PY%" (
    echo No Python environment found. Create one in this folder with:
    echo     python -m venv .venv
    echo     .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
"%STUDIO_PY%" "%~dp0fog_studio.py" %*
if errorlevel 1 pause
