"""
Fog Studio, phase 4: polish and sound.

    python run.py            (add --camera 1 for an external webcam, --windowed for no full screen)

New in this phase:
    droplets run down thick fog, dark corners, a slow light sweep, breath you can see,
    and sound made live: a glass squeak when you draw fast and a whoosh when you wipe (m mutes).

Read GUIDE.md next to this file for a line-by-line walk through.
"""
from studio.app import App, parse_args


def main():
    App(parse_args()).run()


if __name__ == "__main__":
    main()
