@echo off
setlocal
rem Fog Studio setup for Windows: double-click this file.
rem It makes a .venv folder here and installs everything Fog Studio needs into it.
cd /d "%~dp0"

set "PY="
for %%V in (3.12 3.11 3.13 3.10 3.9) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
    )
)
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 9) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo Python 3.9 or newer was not found.
    echo Install Python 3.12 from https://www.python.org/downloads/
    echo During the install, tick "Add python.exe to PATH". Then run setup.bat again.
    goto :end
)
for /f "delims=" %%P in ('%PY% --version 2^>^&1') do echo Using %%P

if not exist ".venv\Scripts\python.exe" (
    echo Creating the environment in .venv ...
    %PY% -m venv .venv || goto :fail
)
echo Installing OpenCV, NumPy, MediaPipe and sounddevice. This can take a few minutes ...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet || goto :fail
".venv\Scripts\python.exe" -m pip install --default-timeout=120 --retries 5 -r requirements.txt || goto :fail

echo.
".venv\Scripts\python.exe" -c "import cv2, numpy, mediapipe, sounddevice; print('Installed: OpenCV', cv2.__version__, '| NumPy', numpy.__version__, '| MediaPipe', mediapipe.__version__, '| sounddevice', sounddevice.__version__)" || goto :fail
if not exist "models\hand_landmarker.task" echo Warning: models\hand_landmarker.task is missing. Hand tracking will be off.

echo.
echo Setup done.
echo In every new terminal, turn the environment on first:
echo     .venv\Scripts\activate
echo Then start the app:
echo     python fog_studio.py --windowed
echo Or just double-click run_fog_studio.bat
goto :end

:fail
echo.
echo Setup failed. The error is above. Check your internet connection and run setup.bat again.

:end
if /i not "%~1"=="--no-pause" pause
endlocal
