"""
Fog Studio, phase 1: the mirror and its UI.

    python run.py            (add --camera 1 for an external webcam, --windowed for no full screen)

What works in this phase:
    the start screen, the webcam as a mirror, fog over the glass, drag the mouse to wipe it,
    the navbar with a button, the help panel (h), the brush slider, toasts.

Read GUIDE.md next to this file for a line-by-line walk through.
"""
from studio.app import App, parse_args


def main():
    App(parse_args()).run()


if __name__ == "__main__":
    main()
