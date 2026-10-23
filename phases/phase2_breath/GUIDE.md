# Phase 2: breathe on the mirror

Run it: `python run.py --windowed` (from this folder, with your venv active)

**New:**
- Say a long "haaa" at the laptop and the mirror fogs up around where your mouth would be. Hold space if there is no microphone.
- Wiped glass slowly fogs back; `o` turns that on or off.
- **Ghost writing:** wipe a word, fog it again, and the word comes back. On real glass the grease from your finger stops fog from settling. `x` cleans the grease away.
- The mic button in the navbar has a ring that fills up as you breathe. `-` and `=` make breath detection less or more sensitive.

| File | What changed |
| --- | --- |
| `audio.py` | **New.** The breath detector |
| `config.py` | 3 breath numbers |
| `fog.py` | Grease, `bloom()` (a breath), `refog()`, two kernel helpers |
| `modes.py` | Breath and re-fog in `update()`, `clean()`, the `o` key |
| `ui.py` | The mic icon with the breath ring, a re-fog chip, more help rows |
| `app.py` | Makes the `Breath` object, frame counter, `drawing`, breath keys |
| `camera.py`, `gfx.py` | Same as phase 1 |

---

## config.py: new numbers

```python
BREATH_BLOBS, BLOB_ALPHA = 12, 0.36
BREATH_REACH = 0.43
```
- `BREATH_BLOBS`: one breath is drawn as 12 soft round blobs of fog.
- `BLOB_ALPHA`: how much fog one blob adds (36% of the way to full).
- `BREATH_REACH`: how big the breath cloud is, as a fraction of the screen height (0.43 x 540 = about 230 px).

---

## audio.py: the breath detector

**How do you tell a breath from talking?** Both are loud. But a breath ("haaa") is *noise*: every frequency is about equally loud, like a hiss. A voice or a hum is a few strong frequencies (a tone). So we check two things:
1. **Loud enough** compared to the room's normal noise.
2. **Hissy enough**, measured by *spectral flatness*.

### __init__

```python
        self.ok, self.level, self.flat, self.floor = False, 0.0, 0.0, None
        self.strength, self.hold_until, self.quiet_until, self.space_until = 0.0, 0.0, 0.0, 0.0
        self.trigger = 0.0025
        self.meter = 0.0
        self.history = deque(maxlen=160)
        self._window = np.hanning(512).astype(np.float32)
```
- **Measurements:**
  - `ok`: is there a working mic.
  - `level`: how loud right now.
  - `flat`: how hissy right now.
  - `floor`: the room's normal noise level, learned as we go.
- **Timers** (all clock times):
  - Keep fogging until `hold_until`.
  - Ignore the mic until `quiet_until`.
  - Space was held until `space_until`.
- `trigger`: how far above the floor counts as a breath. `-` and `=` change it.
- `meter`: 0 to 1, for the ring on the mic button.
- `history`: the last 160 (level, trigger line) pairs. A `deque(maxlen=160)` drops the oldest item by itself. Phase 6 draws it as a graph.
- `_window`: a Hann window: a curve that is 0 at both ends and 1 in the middle. Explained in `_cb`.

```python
        try:
            import sounddevice as sd
            self.stream = sd.InputStream(samplerate=16000, blocksize=512, channels=1, callback=self._cb)
            self.stream.start()
            self.ok = True
        except Exception:
            self.stream = None
```
- `import` inside `try`: if sounddevice is not installed, or there is no microphone, we end up in `except` and the app keeps working (space still fogs).
- `InputStream(...)`:
  - 16,000 samples per second, one channel (mono).
  - It hands us 512 samples at a time (32 ms of sound) by calling `self._cb`.
  - The calls come from sounddevice's own thread, about 31 times a second.

### _cb: called with every 32 ms of sound

```python
        x = indata[:, 0].astype(np.float32)
        self.level = float(np.sqrt(np.mean(x ** 2)))
```
- `indata` has shape (512, 1); `[:, 0]` takes the one channel.
- **RMS loudness**: square every sample, average, then square-root. It is the standard "how loud" number. Silence is near 0.

```python
        win = self._window if len(x) == len(self._window) else np.hanning(len(x))
        spec = np.abs(np.fft.rfft(x * win)) + 1e-9
        self.flat = float(np.exp(np.mean(np.log(spec))) / np.mean(spec))
```
- `x * win`: fades the clip in and out. Without it, the hard cut at each end of the 512 samples shows up as fake frequencies.
- `np.fft.rfft`: the Fourier transform. It turns 512 samples in time into 257 numbers, one per frequency, saying how strong that frequency is. `np.abs` takes the strength.
- `+ 1e-9`: a tiny number so `log(0)` never happens.
- **Spectral flatness** = (geometric mean) / (arithmetic mean):
  - The geometric mean is `exp(mean(log(...)))`.
  - If all frequencies are equally strong (hiss), the two means are equal and the flatness is near 1.
  - If a few frequencies are strong (a tone, a voice), the geometric mean is much smaller and the flatness is near 0.

```python
    def keystroke(self, now):
        self.quiet_until = now + 0.3

    def hold_space(self, now):
        self.space_until = now + 0.18
```
- A keyboard click is loud and hissy, which looks like a breath, so every key press ignores the mic for 0.3 s.
- Holding space: the key repeats about every 30 ms, and each repeat pushes the end time 0.18 s ahead. When you let go, it runs out.

### update: called once per frame

```python
        lvl = self.level
        if self.floor is None:
            self.floor = lvl
        self.floor += (lvl - self.floor) * (0.05 if lvl < self.floor else 0.0008)
        margin = lvl - self.floor
```
- **The floating floor:** the floor moves towards the current level.
  - When it is quieter, the floor falls fast (5% per frame).
  - When it is louder, the floor rises very slowly (0.08% per frame).
  - So a fan or AC sets the floor within seconds, but a 2-second breath cannot drag it up.
- `margin`: how far above the room noise we are right now.

```python
        mic = 0.0
        if self.ok and now > self.quiet_until and self.flat > 0.15:
            mic = float(np.clip((margin - self.trigger) / 0.0005, 0, 1))
        if mic > 0:
            self.hold_until = now + 0.35
```
- **It is a breath only if:**
  - there is a mic,
  - no key was just pressed,
  - and the sound is hissy (flatness over 0.15).
- **Strength:** 0 at `trigger` above the floor, rising to 1 at 0.0005 higher, clipped to 0..1.
- Any breath keeps fogging for 0.35 s more, so short gaps between breaths do not flicker.

```python
        target = 1.0 if now < self.space_until else (max(mic, 0.6) if now < self.hold_until else 0.0)
        self.strength += (target - self.strength) * 0.35
```
- **Target:**
  - Space held: 1.
  - In a breath (or its 0.35 s hold): at least 0.6.
  - Otherwise: 0.
- `strength += (target - strength) * 0.35`: move 35% of the way to the target each frame. This *easing* is used all over the app; it makes numbers glide instead of jump.

```python
        self.meter += (float(np.clip(margin / (self.trigger * 2), 0, 1)) - self.meter) * 0.3
        self.history.append((lvl, self.floor + self.trigger))
        return self.strength
```
- `meter`: how close you are to triggering (half full = right at the trigger), eased the same way. It lets you *see* the mic working before it counts as a breath.

```python
    def stop(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
```
- Turns the microphone off when the app closes.

---

## fog.py: what is new

### gauss_kernel: one soft blob

```python
    r = max(2, int(radius))
    yy, xx = np.mgrid[-2 * r:2 * r + 1, -2 * r:2 * r + 1].astype(np.float32)
    return np.exp(-(xx ** 2 + yy ** 2) / (2 * (0.6 * r) ** 2))
```
- `np.mgrid`: two grids, the x and the y of every cell, from -2r to 2r. The centre is (0, 0).
- `exp(-(distance squared) / (2 sigma squared))` is the bell curve in 2D: 1 in the middle, smoothly falling to almost 0 at the edge. `sigma` = 0.6 x radius.
- This is the "stamp" for a breath blob.

### apply_kernel: stamp a kernel onto the grid, safely at the edges

```python
    kh, kw = kernel.shape
    x0, y0 = int(round(cx)) - kw // 2, int(round(cy)) - kh // 2
    gx0, gy0, gx1, gy1 = max(0, x0), max(0, y0), min(grid.shape[1], x0 + kw), min(grid.shape[0], y0 + kh)
    if gx0 >= gx1 or gy0 >= gy1:
        return
    sl = (slice(gy0, gy1), slice(gx0, gx1))
    fn(grid[sl], kernel[gy0 - y0:gy1 - y0, gx0 - x0:gx1 - x0], sl)
```
- `x0, y0`: where the kernel's top-left corner lands if its centre is at (cx, cy).
- `gx0 ... gy1`: the same box, cut to the grid's edges.
- If nothing overlaps, stop.
- `sl`: the overlapping part of the grid, as slices. `kernel[...]` cuts the same part out of the kernel. A blob half off the edge only uses its on-screen half.
- `fn(region, kernel_part, sl)`: we do not decide here *what* to do with the kernel. The caller passes a function. `bloom` adds fog; phase 3's `stamp` removes it.

### FogLayer: grease

```python
        self.grease = np.zeros((FH, FW), np.float32)
        self._kernels = {}
```
- A second grid: where your finger has been (0 none, 1 a lot).
- `_kernels`: blobs already made, by radius, so the same blob is never computed twice.

```python
        self.a *= 1 - m
        np.maximum(self.grease, m, out=self.grease)
```
- New last line of `erase_path`: wherever you wipe, the grease becomes at least as strong as the wipe. `out=self.grease` writes the answer straight back into the grid, with no new array.

### bloom: one breath

```python
        reach = BREATH_REACH * H * GS
        cx, cy = mouth[0] * GS, mouth[1] * GS + 0.08 * reach
        a, g = BLOB_ALPHA * strength, self.grease
```
- `reach`: the breath cloud's size, in grid pixels.
- `cx, cy`: the centre, a little below the mouth, because warm breath falls slightly.
- `a`: how much fog each blob adds; a gentle breath adds less.

```python
        def fn(region, kk, sl):
            add = a * kk * (1 - 0.7 * g[sl])
            region += (1 - region) * add
```
- The function `apply_kernel` will call for each blob:
  - `a * kk`: the blob's shape times its strength.
  - `* (1 - 0.7 * g[sl])`: where there is grease, only 30% as much fog settles. **This one line is the ghost writing.**
  - `region += (1 - region) * add`: "over" compositing. Add `add` of the *remaining* clear glass, so fog gets thicker and thicker but never goes past 1.
- `region` is a view into `self.a`, so `+=` changes the real fog.

```python
        for _ in range(BREATH_BLOBS):
            ang, rad = random.uniform(0, 2 * math.pi), reach * 0.55 * math.sqrt(random.random())
            r = int(reach * random.uniform(0.16, 0.3))
            if r not in self._kernels:
                self._kernels[r] = gauss_kernel(r)
            apply_kernel(self.a, self._kernels[r], cx + math.cos(ang) * rad * 1.45, cy + math.sin(ang) * rad, fn)
```
- **12 blobs at random spots around the centre:**
  - A random angle and a random distance. `sqrt(random())` spreads points evenly over a disc instead of crowding the middle.
  - `* 1.45` on x makes the cloud wider than tall, like breath on a mirror.
- Each blob has a random size, made once and cached. Random blobs every frame make the fog grow in a natural, cloudy way.

### refog: the glass slowly fogs back

```python
        low = self.a < self.start
        self.a[low] += (self.start - self.a[low]) * rate * (1 - 0.7 * self.grease[low])
```
- `low`: a True/False grid of every spot thinner than the starting fog.
- Only those spots move towards the start level, by `rate` (0.4%) of the gap each frame. Greasy spots move 70% slower.
- Spots that are already thicker (you breathed on them) are left alone.

### reset(keep_grease)

```python
        self.a[:] = self.start
        if not keep_grease:
            self.grease[:] = 0
```
- `c` keeps the grease (the ghosts come back when you breathe). `x` cleans it too.

---

## modes.py: FogMode in phase 2

```python
        self.refog_on = True
```
- Re-fog starts on.

```python
    def clean(self):
        self.fog.reset(keep_grease=False)

    def on_key(self, key):
        if key != ord("o"):
            return False
        self.refog_on = not self.refog_on
        self.app.toast("re-fog " + ("on" if self.refog_on else "off"))
        return True
```
- `on_key` lets a mode have its own keys. It returns True if it used the key, so the App does not also use it.

```python
    def update(self, dt, now):
        s = self.app.breath_strength
        if s > 0.02 and not self.app.drawing and self.app.frame_no % 2 == 0:
            self.fog.bloom(self.app.mouth, s)
        if self.refog_on and not self.app.drawing:
            self.fog.refog(0.004)
```
- **Breathe, but:**
  - not while you are drawing (fog filling your stroke as you draw feels broken);
  - only every 2nd frame (`frame_no % 2 == 0`), which is plenty and saves time.
- Re-fog also pauses while drawing.

---

## ui.py: what is new

```python
        elif kind == "mic":
            rounded_rect(img, c[0] - 4, c[1] - 10, c[0] + 4, c[1] + 3, ink, -1, 4)
            cv2.ellipse(img, (c[0], c[1]), (7, 7), 0, 0, 180, ink, 1, cv2.LINE_AA)
            cv2.line(img, (c[0], c[1] + 7), (c[0], c[1] + 10), ink, 1, cv2.LINE_AA)
            lvl = min(1.0, max(self.app.breath_strength, self.app.breath.meter))
            cv2.ellipse(img, c, (16, 16), -90, 0, 360 * lvl, (255, 220, 120), 2, cv2.LINE_AA)
```
- **A microphone icon:**
  - A rounded capsule.
  - A U-shaped holder: an arc from 0 to 180 degrees is the bottom half of a circle.
  - A short stand.
- **The breath ring:** an arc around the button from the top (`-90` rotation) through `360 * lvl` degrees. It is a full circle while you breathe and fills partly as the mic hears you.

```python
        x = self.chip(img, 150, "clear (c)", False, lambda: app.mode.clear())
        self.chip(img, x, "re-fog " + ("on" if app.mode.refog_on else "off"), app.mode.refog_on,
                  lambda: app.mode.on_key(ord("o")))
        rx = self.icon_button(img, W - 44, "help", lambda: app.toggle("show_help"), app.show_help)
        self.icon_button(img, rx, "mic", app.show_breath)
```
- **The re-fog chip** reuses the `o` key's code by calling `on_key(ord("o"))`, so the key and the button can never disagree.
- **The mic button** sits to the left of help (`rx` is where `icon_button` said the next one goes).

---

## app.py: what is new

```python
        self.camera = self.breath = self.mode = None
        self.frame_no = 0
        self.drawing, self.brush = False, 15
        self.mouth = (W / 2, H * 0.62)
        self.breath_strength = 0.0
```
- `frame_no`: counts frames (used for "every 2nd frame").
- `drawing`: True while the pen is down. The mode reads it to pause breath and re-fog.
- `mouth`: where breath lands. For now it is a fixed guess: middle, a bit below centre. Phase 3 finds your real mouth.

```python
            chr(27): self.to_start_screen, " ": lambda: self.breath.hold_space(time.time()),
            "c": lambda: self.mode.clear(), "x": self.clean_glass, ...
            "-": lambda: self.scale_breath(1.25, "more"), "=": lambda: self.scale_breath(0.8, "less"),
```
- **New keys:**
  - Space fogs.
  - `x` cleans the glass.
  - `-` raises the trigger by 25% (needs more breath).
  - `=` lowers it by 20% (needs less).

```python
        if self.breath is None:
            self.breath = Breath()
            if not self.breath.ok:
                self.toast("no microphone: hold space to fog", 3)
```
- In `launch`: start the microphone once. If it failed, say so instead of silently doing nothing.

```python
    def scale_breath(self, factor, word):
        self.breath.trigger *= factor
        self.toast("breath needs %s: %.4f" % (word, self.breath.trigger))

    def show_breath(self):
        self.toast("breath needs %.4f   (- needs more, = needs less)" % self.breath.trigger, 2.5)
```
- `"%.4f" % number` formats a number with 4 decimals.
- `show_breath` runs when you click the mic button.

```python
        if k != 32:
            self.breath.keystroke(now)
        if k == ord("q"):
            return False
        if not self.mode.on_key(k) and chr(k) in self.keys:
            self.keys[chr(k)]()
```
- Every key except space mutes the mic for 0.3 s.
- The mode gets the key first; only if it did not use it does the App's table run.

```python
        self.drawing = self.mouse_down
```
- At the end of `update_mouse`: the mouse button being held means we are drawing.

```python
        self.frame_no += 1
        self.breath_strength = self.breath.update(now)
        self.update_mouse()
        self.mode.update(dt, now)
```
- In `step`: count the frame and read the breath *before* the mode updates, so `FogMode.update` sees this frame's breath.

```python
        finally:
            if self.breath is not None:
                self.breath.stop()
```
- The mic is switched off when the app ends.

---

## Try this

1. Press `-` five times and breathe: it now needs a much stronger breath. Then press `=` until a normal breath works again.
2. In `audio.py`, change `self.flat > 0.15` to `self.flat > 0.0`. Now talking and humming fog the mirror too. That is what the flatness test is for.
3. In `audio.py`, change the floor's `0.0008` to `0.05`. Breathe for 3 seconds: the fog stops after a moment, because the floor catches up with your breath.
4. In `fog.py` `bloom`, change `* 1.45` to `* 0.6`. The breath cloud becomes tall and thin.
5. In `bloom`, change `(1 - 0.7 * g[sl])` to `1`. The ghost writing is gone; old drawings never come back.
6. In `modes.py`, change `self.fog.refog(0.004)` to `self.fog.refog(0.05)`. The glass fogs back almost at once.
7. In `config.py`, set `BREATH_BLOBS = 2` and then `40`. Watch how the breath cloud fills in.
