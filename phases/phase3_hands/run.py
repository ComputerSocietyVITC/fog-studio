"""
Fog Studio, phase 3: your hands.

    python run.py            (add --camera 1 for an external webcam, --windowed for no full screen)

New in this phase:
    MediaPipe finds your hands: pinch thumb and index to draw, make a fist and swipe to wipe.
    Two hands draw with two pens. Both palms open (hold) clears. Breath follows your face.

Read GUIDE.md next to this file for a line-by-line walk through.
"""
from studio.app import App, parse_args


def main():
    App(parse_args()).run()


if __name__ == "__main__":
    main()
