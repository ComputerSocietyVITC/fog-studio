# From phase 1 to the finished app, in a nutshell

You built phase 1: the webcam mirror, the fog grid, wiping with the mouse, and the UI. This page lists only **what changes** on the way to the finished app in `studio/`. Open each file next to this page.

Run it: `python fog_studio.py --windowed` (Windows: double-click `run_fog_studio.bat`).

## The map

| File | Since phase 1 |
| --- | --- |
| `audio.py` | **new**: the breath detector and the sound effects |
| `hands.py` | **new**: MediaPipe hand tracking, gestures, the pen and the wiper |
| `effects.py` | **new**: vignette, light sweep, breath puffs, pinch star, bevel |
| `debug.py` | **new**: the debug overlay and the live OpenCV panel |
| `fog.py` | grows: breath blobs, re-fog, fist stamps, grease (ghost writing) |
| `modes.py` | grows: one `FogMode` becomes a `Mode` base class with four tabs |
| `ui.py` | grows: tabs, a sub-bar per mode, icon buttons, gallery, countdown, flash |
| `app.py` | grows: starts the new parts and calls them in `step()` |
| `config.py` | grows: tuning numbers for breath, pinch, wipes, neon colours, Reveal words |
| `camera.py`, `gfx.py` | the same (`gfx` gets `dist`, `lerp` and `card`, a centred message box) |

## The whole change in one function

Phase 1's `App.step()` was: read the camera, wipe with the mouse, render the fog, draw the UI. The finished one:

```python
frame = self.camera.read()
self.tracker.submit(frame)                       # 1. hands: MediaPipe runs on its own thread
self.breath_strength = self.breath.update(now)   # 2. breath: 0 to 1 from the microphone
self.update_hands(now)                           # 3. pens draw (the mouse is a pen too), fists wipe, held gestures fire
self.mode.update(dt, now)                        # 4. the current tab updates its layer
self.effects.update(dt, self.breath_strength, self.mouth, self.mode.uses_fog)
out = self.effects.apply(self.mode.render(frame), now, self.hands)   # 5. the mirror look
self.clean = out.copy()                          # 6. kept for photos (no navbar on it)
self.update_booth(now)
self.ui.draw(out)
self.ui.draw_overlays(out, now)
```

Every feature below plugs into one of these lines.

## 1. Breath fogs the mirror (`audio.py` `Breath`, `fog.py`)

- **Hearing a breath:** the mic is read 512 samples at a time (`_cb`). Two numbers per block:
  - `level`: loudness (RMS, the square root of the mean of the squares).
  - `flat`: spectral flatness. Close to 1 for a hiss like "haaa", close to 0 for a hum or a voice.
- **A floating noise floor** (`update`): the floor follows the room noise, fast down and very slowly up, so one long breath cannot drag it up. A breath is `level` above `floor + trigger` **and** `flat > 0.15`. Keystrokes are ignored for 300 ms. Holding space fakes a breath.
- **Breath to fog** (`FogLayer.bloom`): 12 soft gaussian blobs below your mouth, wider than tall, added with "over" compositing so the fog never goes past 1:
  ```python
  region += (1 - region) * add
  ```
- **Re-fog** (`FogLayer.refog`): wiped glass slowly fogs back to the starting level.
- **Ghost writing** (`FogLayer.grease`): every stroke also marks a grease grid. Fog condenses less on grease, so old drawings come back when you breathe. `x` cleans the grease, `c` does not.

## 2. Your hands (`hands.py`, `App.update_hands`)

- **`Tracker`:** MediaPipe HandLandmarker (2 hands, 21 points each) runs on a background thread, on the newest frame only, so the mirror never waits for it. The face detector runs every 5th time to find your mouth, which aims the breath.
- **`classify(lm)`:** turns 21 points into gestures. Everything is divided by hand size (wrist to middle knuckle), so near and far hands behave the same.
  - pinch = thumb tip to index tip / hand size
  - a finger is curled when its tip is closer to the wrist than its middle joint
  - fist = all four curled; thumbs up = fist with the thumb above the knuckles; peace = index and middle out; open = none curled
- **`Pen`:** pinch to draw.
  - Hysteresis: down below 0.22, up above 0.38, so it does not flicker at the edge.
  - Two-stage smoothing (`lerp` twice) and a tremor filter take out the shake.
  - Strokes are curves through the midpoints (`quad_points`), so there are no corners.
  - It only lifts after the hand is gone for 250 ms.
- **`Wiper`:** fist to wipe. One soft stamp (`FogLayer.stamp`) every half radius travelled, not one per frame, so fast swipes leave no gaps.
- **`HandInput`:** two hands plus the mouse, each with its own pen. `held(name, active, secs, now)` fires a gesture once after it is held: thumbs up 0.8 s takes a photo, peace 0.6 s changes the neon colour, both palms 1 s clears.

## 3. Polish and sound (`effects.py`, `audio.py` `Sfx`, `FogMode.update_drops`)

- **`Effects.apply`:** dark corners (vignette with `cv2.blendLinear`), a slow diagonal light sweep, breath puffs you can see, the star at your pinch point, and the mirror's bevel.
- **Droplets:** on thick fog, drops appear, run down, and cut a clear line through the fog grid.
- **`Sfx`:** no sound files. A sine wave around 1,900 Hz with stick-slip chatter is the glass squeak (louder the faster you draw), and low-passed noise is the sleeve whoosh. `m` mutes.

## 4. Four modes (`modes.py`)

The big idea: a **base class**. `Mode` does the common things (fog, breath, stroke, wipe, render). Each tab overrides only what is different. The App only ever talks to `self.mode`.

| Mode | Overrides | The idea |
| --- | --- | --- |
| `FogMode` | `update`, `render` | re-fog (`o`) and droplets |
| `NeonMode` | `stroke`, `wipe`, `render` | draws colour on its own layer; glow = that layer blurred at half size and added (`cv2.add`) |
| `RevealMode` | `update`, `render` | a word hides under thick fog; revealed % = how much of the word's mask is clear; 30 s round |
| `MotionMode` | `update` | OpenCV Farneback optical flow at 320 x 180; anything that moves wipes the fog; `,` `.` set the threshold |

To add a mode: write a class, add it to `MODES` at the bottom. The navbar tab appears by itself. A mode's own buttons go in `nav_extra`, which the UI draws in the sub-bar under the navbar.

## 5. The finished app: photos, gallery, debug (`app.py`, `ui.py`, `debug.py`)

- **Photo booth:** `p`, the shutter button or a held thumbs up sets `countdown` to 3 s. `update_booth` saves `self.clean` (the mirror without the UI) through `polaroid()`, then the screen flashes. `s` saves a plain PNG. Both go to `gallery/`.
- **Gallery** (`g`): the last 6 photos as thumbnails along the bottom.
- **Debug** (`d`): hand skeletons with the pinch ratio, the mouth point, FPS and timings, and the breath graph (mic level against the trigger line).
- **What OpenCV sees** (`v` cycles the panel):
  - **mask:** the mode's mask, or skin colour found with `cv2.inRange` in YCrCb
  - **hull + defects:** the biggest skin blob, its convex hull, and the gaps between fingers (`cv2.convexityDefects`)
  - **optical flow:** colour = direction, brightness = speed

## Try this (one number each, in `config.py`)

- `PINCH_DOWN, PINCH_UP = 0.22, 0.38`: make them closer together and the pen flickers.
- `EASE_TARGET, EASE_BRUSH`: lower is smoother but laggier.
- `BREATH_BLOBS, BLOB_ALPHA`: more fog per breath.
- `WIPE_STAMP`: a stronger sleeve.
- `REVEAL_WORDS`: your own words (or `--word "YOUR TEXT"`).
- `NEON_COLOURS`: add a colour as `("name", (B, G, R))`. OpenCV colours are blue, green, red.

The full line-by-line guides for each step are in `phases/` if you want to go deeper.
