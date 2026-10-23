"""
Fog Studio, phase 2: breathe on the mirror.

    python run.py            (add --camera 1 for an external webcam, --windowed for no full screen)

New in this phase:
    the microphone hears your breath ("haaa") and the mirror fogs up; space does it too.
    Wiped glass slowly fogs back (o), and old drawings come back as ghosts (x cleans them).

Read GUIDE.md next to this file for a line-by-line walk through.
"""
from studio.app import App, parse_args


def main():
    App(parse_args()).run()


if __name__ == "__main__":
    main()
