# Phase 4: polish and sound

Run it: `python run.py --windowed` (from this folder, with your venv active)

**New:**
- **Droplets** form in thick fog and run down the glass, leaving clear trails.
- **Darker corners** (a vignette) and a slow **light sweep** across the mirror.
- **Breath you can see:** soft puffs rise from your mouth when you breathe hard.
- **Sound, made live by maths** (no sound files): a glassy squeak when you draw fast and a soft whoosh when you wipe with a fist. `m` or the speaker button mutes it.

| File | What changed |
| --- | --- |
| `audio.py` | New class `Sfx`: the sound synthesiser |
| `effects.py` | The vignette, light sweep and breath puffs |
| `modes.py` | Droplets in `FogMode` |
| `ui.py` | The speaker button |
| `app.py` | Makes `Sfx`, sets the squeak and whoosh, updates the puffs |
| `config.py`, `gfx.py`, `hands.py`, `fog.py`, `camera.py` | Same as phase 3 |

---

## audio.py: class Sfx, a tiny synthesiser

**How computer sound works:** a speaker plays a list of numbers between -1 and 1, 44,100 of them every second. A sine wave of numbers is a pure tone. Random numbers are a hiss. We make the numbers ourselves, a block at a time.

```python
        self.on, self.ok = True, False
        self.squeak, self.whoosh = 0.0, 0.0
        self._sq, self._wh, self._phase, self._lp, self._t = 0.0, 0.0, 0.0, 0.0, 0.0
```
- `squeak` and `whoosh`: how loud each sound should be (0 to 1). The App sets them every frame.
- **The `_` values carry over from one block to the next:**
  - `_sq`, `_wh`: the volumes used last block.
  - `_phase`: where the squeak's wave was.
  - `_lp`: the whoosh filter's last value.
  - `_t`: the time in seconds.

```python
        try:
            import sounddevice as sd
            self.stream = sd.OutputStream(samplerate=44100, channels=1, blocksize=1024, callback=self._cb)
            self.stream.start()
            self.ok = True
        except Exception:
            self.stream = None
```
- An *output* stream: sounddevice calls `_cb` whenever the speaker needs the next 1,024 samples (about 23 ms). If there are no speakers, the app carries on silently.

### _cb: make 1,024 samples

```python
        n = frames
        t = self._t + np.arange(n) / 44100.0
        self._t = float(t[-1]) + 1 / 44100.0
```
- `t`: the time of each of the n samples, carrying on from the last block.

```python
        sq_target, wh_target = (self.squeak, self.whoosh) if self.on else (0.0, 0.0)
        sq, wh = np.linspace(self._sq, sq_target, n), np.linspace(self._wh, wh_target, n)
        self._sq, self._wh = sq_target, wh_target
```
- Muted means the targets are 0.
- `np.linspace(old, new, n)`: the volume slides from last block's value to the new one across the block. A sudden jump in volume makes an audible click; a slide does not.

```python
        freq = 1900 + 350 * np.sin(2 * np.pi * 7 * t)
        phase = self._phase + np.cumsum(2 * np.pi * freq / 44100.0)
        self._phase = float(phase[-1] % (2 * np.pi))
        stick = (np.sin(2 * np.pi * 38 * t) > -0.2).astype(np.float32)
```
- **The squeak's pitch** wobbles around 1,900 Hz, up and down by 350 Hz, 7 times a second. That wobble is what makes it sound like a wet finger on glass.
- **Phase:** with a changing pitch you cannot just use `sin(2 pi f t)`. Instead each sample adds its own small step `2 pi f / 44100` to the angle. `cumsum` adds them all up. We keep the last angle (`% 2 pi` keeps it small) so the next block carries on smoothly.
- `stick`: a 38 Hz on/off pattern (on about 56% of the time). It chops the tone into chatter, like stick-slip friction.

```python
        noise = np.random.uniform(-1, 1, n).astype(np.float32)
        low, acc = np.empty(n, np.float32), self._lp
        for i in range(0, n, 32):
            acc = acc * 0.8 + float(noise[i:i + 32].mean()) * 0.2 * 6
            low[i:i + 32] = acc
        self._lp = acc
```
- **The whoosh** is random noise made soft:
  - Average every 32 samples, and let a running value `acc` drift towards that average (keep 80%, take 20%).
  - This is a *low-pass filter*: it removes the high hiss and leaves a soft rushing sound.
  - `* 6` makes up for the volume lost by averaging.

```python
        out[:, 0] = np.clip(np.sin(phase) * stick * sq * 0.5 + low * wh * 0.6, -1, 1)
```
- The final sound: the squeak (a sine wave at our phase, chopped, at its volume) plus the whoosh at its volume, clipped to -1..1. Writing into `out` is how sounddevice gets the samples.

---

## effects.py: the mirror look

These are made **once**, when the file loads:

```python
_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIGNETTE = np.ascontiguousarray(1 - 0.32 * (((_xx - W / 2) / (W / 2)) ** 2 + ((_yy - H / 2) / (H / 2)) ** 2) / 2)
VIGNETTE_INV = 1 - VIGNETTE
BLACK = np.zeros((H, W, 3), np.uint8)
SWEEP_U = cv2.resize(_xx * 0.8 + _yy * 0.6, (W // 4, H // 4))
del _yy, _xx
```
- `_yy, _xx`: the y and the x of every pixel.
- **VIGNETTE:** for each pixel, its distance from the centre, scaled so the edges are 1 away.
  - The value is 1 in the centre and falls to 0.68 in the corners: 32% darker.
  - `VIGNETTE_INV` is the opposite weight, for `blendLinear`.
- `SWEEP_U = x * 0.8 + y * 0.6`: how far each pixel is along a diagonal direction (0.8 right, 0.6 down). The light band moves along this. It is made at quarter size because the band is soft.
- `del`: the full-size helper grids are not needed any more, so their memory is freed.

### Effects.update: the breath puffs

```python
        if on and breath > 0.25 and len(self.puffs) < 40:
            for _ in range(2):
                self.puffs.append([mouth[0] + random.uniform(-25, 25), mouth[1] + 20,
                                   random.uniform(-25, 25), random.uniform(-45, -20), 0.0, random.uniform(8, 16)])
```
- **During a strong breath, 2 new puffs per frame** (up to 40), near the mouth.
- **Each puff is a list:** x, y, x speed, y speed (negative, so it goes up), age, and radius. All speeds are in pixels per second.

```python
        for p in self.puffs:
            p[0], p[1], p[4], p[5] = p[0] + p[2] * dt, p[1] + p[3] * dt, p[4] + dt, p[5] + 18 * dt
        self.puffs = [p for p in self.puffs if p[4] <= 1.3]
```
- **Every frame:**
  - Move each puff by its speed times `dt` (the seconds since the last frame), so it moves at the same speed whatever the frame rate.
  - Make it older, and grow it 18 px per second.
  - Throw away puffs older than 1.3 s.

### Effects.apply: draw it all

```python
        out = cv2.blendLinear(out, BLACK, VIGNETTE, VIGNETTE_INV)
```
- Mix the picture with black, using the vignette as the weight: the corners get darker.

```python
        pos = ((now * 90) % (W * 1.6 + 600)) - 300
        light = np.exp(-((SWEEP_U - pos) / 70.0) ** 2) * 22
```
- `pos`: where the light band is along the diagonal. It moves 90 px per second.
  - `%` (remainder) makes it wrap around and start again.
  - `- 300` starts it off-screen.
- `light`: a bell curve around `pos`, about 70 px wide, at most 22 brighter. This is a soft stripe of light, like a reflection passing over the glass.

```python
        if self.puffs:
            layer = np.zeros((H // 4, W // 4), np.float32)
            for x, y, _, _, age, r in self.puffs:
                cv2.circle(layer, (int(x / 4), int(y / 4)), int(r / 4) + 1, float(0.5 * (1 - age / 1.3)), -1)
            light = light + cv2.GaussianBlur(layer, (0, 0), 3) * 140
```
- **The puffs**, drawn at quarter size as filled circles that fade as they age (`1 - age / 1.3`). They are blurred into soft clouds and added to the light.

```python
        light = cv2.resize(np.clip(light, 0, 255).astype(np.uint8), (W, H), interpolation=cv2.INTER_LINEAR)
        out = cv2.add(out, cv2.cvtColor(light, cv2.COLOR_GRAY2BGR))
```
- Scale the light up to full size and add it to the picture. `cv2.add` stops at 255 instead of wrapping around, so bright spots never turn black. `GRAY2BGR` copies the one grey channel into B, G and R.
- Then the stars and bevel from phase 3.

---

## modes.py: droplets

```python
        self.drops = []
```
- Each droplet is `[x, y, speed, radius]` in fog-grid pixels.

```python
    def update_drops(self):
        a = self.fog.a
        if len(self.drops) < 28 and random.random() < 0.35:
            x, y = random.randrange(4, FW - 4), random.randrange(4, int(FH * 0.6))
            if a[y, x] > 0.78:
                self.drops.append([float(x), float(y), random.uniform(0.15, 0.4), random.uniform(1.2, 2.4)])
```
- **35% of frames:** pick a random spot in the top 60% of the glass. If the fog there is thick (over 0.78), a droplet forms. At most 28 at once. Thin fog never makes drops, just like real glass.

```python
        for d in self.drops:
            if a[min(FH - 1, int(d[1])), min(FW - 1, int(d[0]))] < 0.6 and d[2] < 0.3:
                d[2] *= 0.96
            ox, oy = d[0], d[1]
            d[2] = min(3.0, d[2] + 0.02)
            d[1] += d[2]
            d[0] = min(FW - 2.0, max(1.0, d[0] + random.uniform(-0.35, 0.35)))
            cv2.line(a, (int(ox), int(oy)), (int(d[0]), int(d[1])), 0.12, max(1, int(d[3] * 0.9)), cv2.LINE_AA)
        self.drops = [d for d in self.drops if d[1] < FH - 1 and d[2] >= 0.05]
```
- **For each drop:**
  - A slow drop on clear glass slows down more (it has nothing to feed on).
  - Otherwise it speeds up a little (gravity), up to 3 grid pixels per frame. It moves down and wiggles sideways a tiny bit.
  - `cv2.line(a, ..., 0.12, ...)` draws **into the fog grid itself**: the drop's path is set to 0.12 (nearly clear). That leaves the clear trail.
- Drops that reached the bottom, or stopped, are removed.

```python
        for x, y, _, r in self.drops:
            c, rr = (int(x / GS), int(y / GS)), max(2, int(r / GS * 0.7))
            cv2.circle(out, c, rr, (90, 90, 90), 1, cv2.LINE_AA)
            cv2.circle(out, (c[0] - rr // 3, c[1] - rr // 3), max(1, rr // 3), (255, 255, 255), -1, cv2.LINE_AA)
```
- In `render`: each drop is drawn as a tiny lens, with a dark rim and a white glint at its top left. `/ GS` turns grid pixels back into screen pixels.

```python
    def clear(self):
        self.fog.reset()
        self.drops.clear()
```
- Clearing the glass removes the drops too.

---

## ui.py: the speaker button

```python
        elif kind == "sound":
            pts = (np.array([[-8, -3], [-4, -3], [1, -8], [1, 8], [-4, 3], [-8, 3]]) + c).astype(np.int32)
            cv2.fillPoly(img, [pts], ink, cv2.LINE_AA)
            if self.app.sfx.on:
                cv2.ellipse(img, (c[0] + 2, c[1]), (7, 7), 0, -40, 40, ink, 1, cv2.LINE_AA)
            else:
                cv2.line(img, (c[0] + 4, c[1] - 5), (c[0] + 10, c[1] + 5), (80, 80, 255), 2, cv2.LINE_AA)
```
- **A speaker shape:** 6 corner points around the centre. `+ c` moves them all to the button's centre at once, and `fillPoly` fills it.
- **On:** a small arc (a sound wave). **Off:** a red slash.

```python
        rx = self.icon_button(img, rx, "sound", app.toggle_sound)
```
- In `draw`, between help and the mic.

---

## app.py: what is new

```python
        if self.breath is None:
            self.breath, self.sfx = Breath(), Sfx()
```
- The speakers start with the microphone.

```python
    def toggle_sound(self):
        self.sfx.on = not self.sfx.on
        self.toast("sound " + ("on" if self.sfx.on else "off"))
```
- `m` and the speaker button both call this.

```python
        self.sfx.squeak = float(np.clip((hands.speed - 4) / 20, 0, 1)) * 0.25
        self.sfx.whoosh = 0.5 if hands.wiping else 0.0
```
- In `update_hands`:
  - **The squeak** starts when the pen moves faster than 4 px per frame and is loudest at 24, at most 25% volume.
  - **The whoosh** plays while a fist is wiping.
- The audio thread reads these numbers about 43 times a second.

```python
        self.effects.update(dt, self.breath_strength, self.mouth, True)
```
- In `step`: move the puffs before drawing.

---

## Try this

1. In `audio.py`, change `1900 + 350 * ...` to `600 + 350 * ...`. The squeak becomes a low hum. Change the `7` to `30` for a fast warble.
2. In `_cb`, change `acc * 0.8 + ... * 0.2` to `acc * 0.2 + ... * 0.8`. The whoosh turns into a harsh hiss: the filter is weaker.
3. In `effects.py`, change `0.32` in VIGNETTE to `0.9`. The corners go almost black.
4. Change the sweep's `* 22` to `* 80`, and `now * 90` to `now * 400`. You get a bright, fast reflection.
5. In `modes.py`, change `a[y, x] > 0.78` to `> 0.3`. Drops form even in light fog. Also try `len(self.drops) < 200`.
6. In the drop line, change `0.12` to `0.6`. The trails stay foggy and are hard to see.
7. In `Effects.update`, change `breath > 0.25` to `breath > 0.01` and `range(2)` to `range(6)`. Every breath makes a big cloud.
