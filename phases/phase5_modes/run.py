"""
Fog Studio, phase 5: modes.

    python run.py            (add --camera 1 for an external webcam, --windowed for no full screen)

New in this phase:
    tabs in the navbar (or keys 1 to 4): Fog, Neon (draw with light; peace sign changes colour),
    Reveal (a word hides under the fog: find it in 30 s) and Motion (OpenCV optical flow wipes the fog).

Read GUIDE.md next to this file for a line-by-line walk through.
"""
from studio.app import App, parse_args


def main():
    App(parse_args()).run()


if __name__ == "__main__":
    main()
