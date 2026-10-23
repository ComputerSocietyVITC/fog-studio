# Fog Studio

A fogged-up bathroom mirror on your laptop. Breathe on it and it fogs. Pinch your thumb and index finger to draw in the fog, make a fist and swipe to wipe it like your sleeve. Four modes, a navbar, a photo booth, and a live view of what the computer vision sees.

Everything runs on this laptop. No frames, audio or data ever leave it.

## Run it

```text
git clone https://github.com/ComputerSocietyVITC/fog-studio.git
cd fog-studio
```

Run the setup file. It makes a `.venv` folder, installs everything into it and checks that it all imports:

- **Windows:** double-click `setup.bat`, then double-click `run_fog_studio.bat` to start.
- **macOS / Linux:** `sh setup.sh`, then `source .venv/bin/activate` and `python fog_studio.py`.

By hand instead: `python -m venv .venv`, activate it, `pip install -r requirements.txt`, `python fog_studio.py`.

**Coming from phase 1?** Read [`NUTSHELL.md`](NUTSHELL.md): everything the finished app adds, file by file.

If you start it with a Python that has no MediaPipe, hand tracking is off and a red bar says so.

- **Opening:** it starts full screen. `--windowed` starts in a window, `--camera 1` uses an external webcam, and `--word "YOUR TEXT"` sets the Reveal game's word.
- **Hand-tracking models:** they are in `models/` (MediaPipe Tasks API, about 8 MB). If they are missing, hand tracking turns off. The mouse and the motion mode still work.
- **OpenCV comes with MediaPipe** (`opencv-contrib-python`). Do not also install `opencv-python` in the same venv, because two OpenCV packages clash.
- **Windows breath tip:** if breath does not register, turn off microphone noise suppression (Settings, Sound, your microphone, Audio enhancements / Voice clarity). It deletes breath sounds on purpose.

## Modes (click a tab or press 1 to 4)

| Mode | What happens | Computer vision |
| --- | --- | --- |
| 1 Fog | Breathe to fog, pinch to draw, fist to wipe. Droplets run down thick fog. Wiped glass slowly fogs back (`o` toggles). **Ghost writing:** old drawings reappear when you breathe again, like finger grease on real glass. `x` cleans the glass. | MediaPipe hands and face, OpenCV frosted glass |
| 2 Neon | Pinch to draw glowing neon in the air. Peace sign (or the swatches) changes colour, including rainbow. A fist erases. | MediaPipe hands, OpenCV glow |
| 3 Reveal | A word hides under thick fog. Press Enter, then wipe it clear within 30 s. Your best time is kept. `w` changes the word. | Revealed % measured from the fog mask |
| 4 Motion | Anything that moves wipes the fog (a book, a pen, an elbow). `,` and `.` change the threshold. | **OpenCV Farneback optical flow** (workshop Boss level) |

## Gestures

| Gesture | Action |
| --- | --- |
| Pinch thumb and index (index finger out to start) | Draw |
| Pinch with both hands | Two pens at once |
| Fist and swipe | Wipe a wide area, like your sleeve |
| Thumbs up (hold) | 3-2-1 polaroid photo |
| Peace sign (hold) | Next neon colour |
| Both palms open (hold) | Clear everything |
| Breathe "haaa", or hold space | Fog the mirror |

## Keys

| Key | Action |
| --- | --- |
| `1` to `4` | Switch mode |
| space (hold) | Fog without breathing |
| `c` / `x` | Clear (the ghost writing stays) / clean the glass (ghosts gone) |
| `s` | Save a PNG to `gallery/` |
| `p` / thumbs up / the shutter button | 3-2-1 polaroid photo |
| `g` | Gallery strip |
| `d` | Debug: hand skeletons, pinch ratio, breath graph, FPS, plus a live OpenCV panel |
| `v` | Next OpenCV panel: mask, convex hull and defects, optical flow |
| `h` | Help overlay |
| `m` | Sound on or off (synthesised glass squeak and wipe whoosh) |
| `f` | Full screen on or off |
| `[` `]` | Brush size (also the "brush" slider, bottom left) |
| `-` `=` | Breath needs more / less |
| `esc` / `q` | Start screen / quit |

The mouse draws too: left drag anywhere on the mirror.

## How it works (one frame)

1. Read the webcam, mirror it, and crop it to 16:9 at 960 x 540. The window stretches it to full screen.
2. A background thread runs MediaPipe hand landmarks on the newest frame, and face detection every 5th frame to aim the breath at your mouth.
3. **Gestures** are measured relative to hand size: pinch = thumb-tip-to-index-tip distance / wrist-to-middle-knuckle distance. The pen goes down below 0.22 and up above 0.38. The point is smoothed twice, and strokes are curved through midpoints.
4. **Breath** = microphone loudness above a floating noise floor AND a hissy, flat spectrum (spectral flatness, workshop Lesson 11). Typing is ignored for 300 ms.
5. **The fog** is a 480 x 270 grid of "how much fog". Drawing subtracts from it. Breath adds soft blobs that overlap into density. The frost is the camera blurred, brightened and tinted, blended in with `cv2.blendLinear` wherever there is fog.
6. Effects: vignette, light sweep, breath puffs, the pinch star. Then the UI, then show.

## Code layout

`fog_studio.py` only starts the app. The code is in `studio/`, one file per job:

| File | What it does |
| --- | --- |
| `config.py` | Sizes, tuning values, colours |
| `gfx.py` | Small maths and drawing helpers |
| `camera.py` | The webcam as a mirrored 960 x 540 frame |
| `hands.py` | MediaPipe on a thread, gestures, the pen and the fist wiper |
| `audio.py` | Breath detector (mic) and synthesised sound effects |
| `fog.py` | The fog grid (erase, wipe, breathe, re-fog) and the frosted look |
| `modes.py` | The four tabs; add a mode by writing a class and adding it to `MODES` |
| `effects.py` | Vignette, light sweep, breath puffs, pinch star, bevel |
| `ui.py` | Navbar, brush slider, toasts, help, start screen |
| `debug.py` | The debug overlay and the live OpenCV panel |
| `app.py` | Ties it together: keys, mouse, and one frame at a time in `App.step()` |

## Learn it in 6 phases

`phases/` builds the same app up in six runnable steps. Each phase has a `GUIDE.md` that explains its new code line by line, with "Try this" experiments. Start with `phases/README.md`.

| Phase | Adds |
| --- | --- |
| 1 Mirror + UI | Camera, fog, mouse wiping, navbar, slider, toasts, help, start screen |
| 2 Breath | Microphone breath detector, re-fog, ghost writing |
| 3 Hands | MediaPipe: pinch to draw, fist to wipe, two hands, gestures |
| 4 Polish + sound | Droplets, vignette, light sweep, breath puffs, synthesised squeak and whoosh |
| 5 Modes | Tabs: Neon, Reveal, Motion |
| 6 Complete | Photo booth, gallery, debug view (this is `studio/` itself) |

## Checks

```text
python check_studio.py
```

34 headless checks:
- **Gestures:** gesture classification on synthetic hands, pen hysteresis and lift timing.
- **Wipes and breath:** fist-wipe stamping caps, and the breath floor (it settles, it ignores humming and keystrokes).
- **All modes and controls:** all four modes run with fake keys, mouse and microphone; a drag wipes fog and paints neon; `s` saves; the slider and tabs respond.
- **Failure cases:** no microphone, and a refused camera.
- **Phases:** each of the six phases runs, and a mouse drag wipes its fog.

They use the fake camera and microphone from `tools/fake_io.py`.
