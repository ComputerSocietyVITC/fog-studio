#!/bin/sh
# Fog Studio setup for macOS and Linux:  sh setup.sh
# It makes a .venv folder here and installs everything Fog Studio needs into it.
cd "$(dirname "$0")" || exit 1

PY=""
for v in python3.12 python3.11 python3.13 python3.10 python3.9 python3 python; do
    if command -v "$v" >/dev/null 2>&1 && "$v" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 9) else 1)' 2>/dev/null; then
        PY="$v"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "Python 3.9 or newer was not found. Install Python 3.12 from https://www.python.org/downloads/ and run setup again."
    exit 1
fi
echo "Using $("$PY" --version 2>&1)"

fail() {
    echo
    echo "Setup failed. The error is above. Check your internet connection and run setup.sh again."
    exit 1
}

if [ ! -d .venv ]; then
    echo "Creating the environment in .venv ..."
    "$PY" -m venv .venv || fail
fi
VPY=.venv/bin/python
[ -x "$VPY" ] || VPY=.venv/Scripts/python.exe
echo "Installing OpenCV, NumPy, MediaPipe and sounddevice. This can take a few minutes ..."
"$VPY" -m pip install --upgrade pip --quiet || fail
"$VPY" -m pip install --default-timeout=120 --retries 5 -r requirements.txt || fail

echo
"$VPY" -c "import cv2, numpy, mediapipe; print('Installed: OpenCV', cv2.__version__, '| NumPy', numpy.__version__, '| MediaPipe', mediapipe.__version__)" || fail
if ! "$VPY" -c "import sounddevice" 2>/dev/null; then
    echo "Note: the microphone library needs PortAudio. On Linux: sudo apt install libportaudio2"
    echo "Without it the app still runs; hold space to fog the mirror."
fi
[ -f models/hand_landmarker.task ] || echo "Warning: models/hand_landmarker.task is missing. Hand tracking will be off."

echo
echo "Setup done."
echo "In every new terminal, turn the environment on first:"
echo "    source $(dirname "$VPY")/activate"
echo "Then start the app:"
echo "    python fog_studio.py --windowed"
