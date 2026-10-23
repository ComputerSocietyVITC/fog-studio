# Fog Studio in 6 phases

The finished app is built up in six steps. Every phase is a complete program that runs on its own. Each one adds a few features to the one before it, so you can explore one idea at a time.

| Phase | Folder | What it adds | New files |
| --- | --- | --- | --- |
| 1 | `phase1_mirror_ui` | The webcam as a mirror, fog over the glass, drag the mouse to wipe it. The whole UI: start screen, navbar, a button, help panel, brush slider, toasts | `config` `gfx` `camera` `fog` `modes` `ui` `app` |
| 2 | `phase2_breath` | The microphone hears your breath and the mirror fogs up. Re-fog, ghost writing | `audio` |
| 3 | `phase3_hands` | MediaPipe hand tracking: pinch to draw, fist to wipe, two hands, gestures; breath follows your face | `hands` `effects` |
| 4 | `phase4_polish_sound` | Droplets, vignette, light sweep, visible breath, synthesised squeak and whoosh | (bigger `effects`, `audio`) |
| 5 | `phase5_modes` | Tabs: Fog, Neon, Reveal (a game), Motion (OpenCV optical flow) | (bigger `modes`) |
| 6 | `phase6_complete` | Photo booth, gallery, debug view. This is the finished app in `../studio/` | `debug` |

## Run a phase

With your venv active (see the main README), from the repo folder:

```text
python phases/phase1_mirror_ui/run.py --windowed
```

Phases 1 and 2 only need OpenCV, NumPy and sounddevice. From phase 3 on, the hand models are found in `fog-studio/models/`.

## How to read a phase

1. Run it and play with it first.
2. Open `GUIDE.md` in that folder. It explains every file that is new or changed in that phase, function by function and line by line. Files that did not change are not explained again.
3. Do the "Try this" experiments at the end of each guide. They are small edits that show what each number or line does.

Each phase keeps the same files and the same names as the finished app. Code you learn in phase 1 is still there, unchanged, in phase 6.

## The shape of every phase

```text
run.py          starts the app (App(parse_args()).run())
studio/
  config.py     sizes and tuning numbers
  gfx.py        drawing helpers (rounded boxes, text)
  camera.py     the webcam, mirrored and cropped to 16:9
  fog.py        the fog grid and the frosted-glass look
  modes.py      what the mirror does (one mode, then four tabs in phase 5)
  ui.py         everything drawn on top: navbar, slider, toasts, help, start screen
  app.py        the App: keys, mouse, and one frame at a time in App.step()
  audio.py      (phase 2+) microphone breath detector, (phase 4+) sound effects
  hands.py      (phase 3+) MediaPipe, gestures, the pen and the wiper
  effects.py    (phase 3+) the pinch star and the bevel, (phase 4+) vignette, light sweep, puffs
```

Every frame, `App.step()` does the same things in the same order:

```text
read the camera  ->  sense (breath, hands)  ->  update the mode  ->  render the mirror  ->  effects  ->  UI on top  ->  show
```
