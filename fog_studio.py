"""
Fog Studio: a fogged-up bathroom mirror you can breathe on, draw on and wipe.

    python fog_studio.py            (add --camera 1 for an external webcam, --windowed for no full screen)

Everything runs on this laptop. No frame, sound or data ever leaves it.

Modes (tabs, or keys 1 to 4):
    1 Fog      breathe to fog, pinch to draw, fist to wipe; old drawings come back as ghosts
    2 Neon     pinch to draw glowing neon in the air; peace sign changes colour, fist erases
    3 Reveal   a word hides under thick fog: wipe it clear before the 30 seconds run out
    4 Motion   OpenCV optical flow: anything that moves wipes the fog

The code lives in studio/, one file per job:
    config.py   sizes, tuning values, colours
    gfx.py      small maths and drawing helpers
    camera.py   the webcam as a mirrored 960 x 540 frame
    hands.py    MediaPipe on a thread, gestures, the pen and the fist wiper
    audio.py    breath detector (mic) and synthesised sound effects
    fog.py      the fog grid (erase, wipe, breathe, re-fog) and the frosted look
    modes.py    the four tabs
    effects.py  vignette, light sweep, breath puffs, pinch star, bevel
    ui.py       navbar, brush slider, toasts, help, start screen
    debug.py    the debug overlay and the live OpenCV panel
    app.py      ties it together: input, and one frame at a time in App.step()
"""
from studio.app import App, parse_args


def main():
    App(parse_args()).run()


if __name__ == "__main__":
    main()
