"""
Fog Studio, phase 6: the finished app.

    python run.py            (add --camera 1 for an external webcam, --windowed for no full screen)

New in this phase:
    the photo booth (shutter button, p, or hold a thumbs up: 3-2-1 polaroid), s saves a PNG,
    the gallery strip (g), the help panel lists everything, and the debug view (d, v):
    hand skeletons, timings, the breath graph and a live panel of what OpenCV sees.

The code for this phase is the real app in ../../studio/ (the same one ../../fog_studio.py starts).
This file only starts it from here, so every phase starts the same way. Read GUIDE.md next to it.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))  # the fog-studio folder

from studio.app import App, parse_args  # noqa: E402  (must come after the path line above)


def main():
    App(parse_args()).run()


if __name__ == "__main__":
    main()
