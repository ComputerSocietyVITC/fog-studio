# Phase 5: modes

Run it: `python run.py --windowed` (from this folder, with your venv active). Add `--word "YOUR WORD"` for the game.

**New:** tabs in the navbar (click, or keys 1 to 4):

| Tab | What happens |
| --- | --- |
| 1 Fog | Everything from phases 1 to 4 |
| 2 Neon | Pinch to draw glowing neon light in the air. The peace sign (held) or the colour dots change colour, including rainbow. A fist erases |
| 3 Reveal | A game: a word hides under thick fog. Press Enter (or click the tab again), then wipe to find it within 30 seconds |
| 4 Motion | No hands needed. OpenCV *optical flow* sees anything that moves (an arm, a book) and that motion wipes the fog |

Each mode has its own controls in a small bar under the navbar (the "sub-bar").

| File | What changed |
| --- | --- |
| `modes.py` | **Rebuilt.** A base class `Mode`, and four modes built on it |
| `ui.py` | Tabs, and the sub-bar for each mode's controls |
| `app.py` | A list of modes, `set_mode()`, keys 1 to 4, the peace gesture, `--word` |
| `fog.py` | `frost_render()` can draw the frost over a different picture (`under`), for Reveal |
| `gfx.py` | `card()`: a box of text in the middle of the screen |
| `config.py` | Neon colours and the Reveal words |
| `hands.py`, `audio.py`, `effects.py`, `camera.py` | Same as phase 4 |

---

## The big idea: a base class

Up to phase 4 there was one `FogMode`. Now there are four modes, and the App must treat them all the same way. It calls `update()`, `render()`, `stroke()`, `wipe()` and so on without knowing which mode is on.

So `class Mode` holds the **default** behaviour, and each mode *inherits* from it (`class NeonMode(Mode)`) and only rewrites (*overrides*) the methods that are different. This is *polymorphism*: the same call, a different behaviour per mode.

```python
class Mode:
    name, hint = "?", ""
    uses_fog = True

    def __init__(self, app):
        self.app = app
        self.fog = FogLayer()

    def enter(self):
        pass

    def stroke(self, pts, radius):
        self.fog.erase_path(pts, radius)

    def wipe(self, center, radius):
        self.fog.stamp(center, radius)

    def clear(self):
        self.fog.reset()

    def clean(self):
        self.fog.reset(keep_grease=False)

    def on_peace(self):
        pass

    def on_key(self, key):
        return False

    def update(self, dt, now):
        s = self.app.breath_strength
        if s > 0.02 and not self.app.drawing and self.app.frame_no % 2 == 0:
            self.fog.bloom(self.app.mouth, s)

    def render(self, frame):
        return frost_render(frame, self.fog.a)

    def nav_extra(self, ui, img, x):
        return x
```
- **The defaults** are what phase 4's FogMode did, minus the Fog-only extras. So any new mode gets fog, breath, drawing and wiping for free.
- `uses_fog`: Neon sets it to False, so the App skips the glass squeak and breath puffs there.
- `enter()`: called when you switch to this mode.
- `on_peace()`: called when a peace sign is held. It does nothing by default.
- `nav_extra(ui, img, x)`: draws the mode's own controls in the sub-bar, starting at `x`, and returns where they end. By default there are none.

## FogMode now

```python
class FogMode(Mode):
    ...
    def update(self, dt, now):
        super().update(dt, now)
        if self.refog_on and not self.app.drawing:
            self.fog.refog(0.004)
        self.update_drops()
```
- `super().update(dt, now)` runs `Mode.update` first (the breath), then adds Fog's own things. This is how a subclass *adds to* a default instead of replacing it.

```python
    def nav_extra(self, ui, img, x):
        return ui.chip(img, x, "re-fog " + ("on" if self.refog_on else "off"), self.refog_on, lambda: self.on_key(ord("o")))
```
- The re-fog chip moved from the navbar into Fog's sub-bar: it belongs to this mode only.

---

## NeonMode: draw with light

```python
class NeonMode(Mode):
    name, hint, uses_fog = "Neon", "pinch to draw light; peace sign changes colour; fist erases", False

    def __init__(self, app):
        super().__init__(app)
        self.layer = np.zeros((H, W, 3), np.uint8)
        self.colour = 0
```
- `self.layer`: a black full-size picture. Neon lines are drawn into it and stay there.
- `colour`: which entry of `NEON_COLOURS` is in use.

```python
    def current_bgr(self):
        bgr = NEON_COLOURS[self.colour][1]
        if bgr is None:
            hsv = np.uint8([[[int(time.time() * 60) % 180, 230, 255]]])
            return tuple(int(v) for v in cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0])
        return bgr
```
- Each colour is a (name, BGR) pair. Rainbow has no fixed colour (`None`).
- **Rainbow:** use *HSV* colour, where H is the hue (the colour wheel; 0 to 179 in OpenCV). The hue walks with the clock (60 steps per second, wrapping at 180), and `cvtColor` turns that one pixel back into BGR.

```python
    def set_colour(self, i):
        self.colour = i
        self.app.toast("colour: " + NEON_COLOURS[i][0])

    def on_peace(self):
        self.set_colour((self.colour + 1) % len(NEON_COLOURS))
```
- **Peace sign:** the next colour. `%` wraps from the last back to the first.

```python
    def stroke(self, pts, radius):
        p = np.round(np.asarray(pts, np.float32) * 16).astype(np.int32).reshape(-1, 1, 2)
        th = max(2, int(radius * 0.55))
        if len(p) == 1:
            cv2.circle(self.layer, tuple(int(v) for v in p[0, 0]), th, self.current_bgr(), -1, cv2.LINE_AA, 4)
        else:
            cv2.polylines(self.layer, [p], False, self.current_bgr(), th, cv2.LINE_AA, 4)
```
- The same subpixel trick as `erase_path` (`* 16` with `shift=4`), but it draws coloured lines onto the layer instead of wiping fog. It uses full-size positions (no `GS`), because the layer is full size.
- Neon lines are about half as thick as the fog brush.

```python
    def wipe(self, center, radius):
        cv2.circle(self.layer, (int(center[0]), int(center[1])), int(radius * 0.8), (0, 0, 0), -1, cv2.LINE_AA)

    def clear(self):
        self.layer[:] = 0

    clean = clear

    def update(self, dt, now):
        pass
```
- **A fist paints black**, which on this layer means "no light", so it erases.
- `clean = clear`: in Neon, `x` does the same as `c`. Assigning a method to another name inside a class is allowed.
- `update` does nothing: no fog, so no breath here.

```python
    def render(self, frame):
        out = cv2.convertScaleAbs(frame, alpha=0.55)
        small = cv2.resize(self.layer, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
        glow = cv2.resize(cv2.convertScaleAbs(cv2.GaussianBlur(small, (0, 0), 7), alpha=2.2), (W, H))
        out = cv2.add(cv2.add(out, glow), self.layer)
        core = cv2.threshold(cv2.cvtColor(self.layer, cv2.COLOR_BGR2GRAY), 0, 70, cv2.THRESH_BINARY)[1]
        return cv2.add(out, cv2.cvtColor(core, cv2.COLOR_GRAY2BGR))
```
How to make light look like neon:
1. **Dim the room** to 55% (`convertScaleAbs` multiplies and keeps the result 0 to 255), so the light stands out.
2. **The glow:** blur the lines a lot (at half size, for speed) and brighten 2.2 times. This is the haze around a neon tube.
3. **Add** the camera, the glow and the sharp lines. `cv2.add` means light adds up, like real light.
4. **The white-hot core:** `threshold(..., 0, 70, BINARY)` gives 70 wherever there is any line and 0 elsewhere. Adding it pushes the centre of each line towards white, like a real tube.

```python
    def nav_extra(self, ui, img, x):
        cy = NAV_H // 2
        for i, (_, bgr) in enumerate(NEON_COLOURS):
            cx = x + 11
            cv2.circle(img, (cx, cy), 9, bgr if bgr is not None else self.current_bgr(), -1, cv2.LINE_AA)
            if i == self.colour:
                cv2.circle(img, (cx, cy), 12, (255, 255, 255), 2, cv2.LINE_AA)
            ui.add_button((cx - 12, cy - 12, cx + 12, cy + 12), lambda i=i: self.set_colour(i))
            x += 28
        return x + 8
```
- A dot for each colour (the rainbow dot cycles live), with a white ring on the chosen one. Each dot is a button.
- `lambda i=i:` freezes the current `i` into each button. Without `=i`, every button would use the *last* `i`. This is a classic Python trap with lambdas in loops.

---

## RevealMode: the game

```python
    ROUND = 30.0

    def __init__(self, app):
        super().__init__(app)
        self.words = ([app.args.word.upper()] if app.args.word else []) + list(REVEAL_WORDS)
        self.word_i = 0
        self.state, self.t0, self.revealed, self.best, self.result = "ready", 0.0, 0.0, None, ""
        self._next_check = 0.0
        self.fog = FogLayer(1.0)
        self.make_word()
```
- **The word list:** your `--word` first (in capitals) if you gave one, then the built-in words.
- `state` is "ready", "playing" or "done".
- **Score:** `t0` is when the round started, `revealed` is the fraction of the word uncovered, and `best` is the best time.
- `FogLayer(1.0)`: completely solid fog, so no peeking.

```python
    def make_word(self):
        word, font, scale, thick = self.words[self.word_i], cv2.FONT_HERSHEY_TRIPLEX, 3.2, 14
        while text_width(word, scale, thick, font) > W * 0.82:
            scale -= 0.2
        self.word_layer = np.zeros((H, W, 3), np.uint8)
        x, y = W // 2 - text_width(word, scale, thick, font) // 2, H // 2 + int(30 * scale / 3.2) + 20
        cv2.putText(self.word_layer, word, (x, y), font, scale, (255, 220, 60), thick, cv2.LINE_AA)
        self.word_mask = cv2.resize((self.word_layer.max(axis=2) > 0).astype(np.uint8), (FW, FH),
                                    interpolation=cv2.INTER_NEAREST).astype(bool)
```
- Start with huge, thick text and shrink it until the word fits in 82% of the width, so long words fit too.
- Draw the word, centred, in light blue (BGR 255, 220, 60), on its own black layer.
- `word_mask`: True wherever the word has a pixel, shrunk to the fog grid's size.
  - `max(axis=2) > 0` means "any colour at all".
  - `INTER_NEAREST` keeps it True/False with no in-between values.

```python
    def start_round(self):
        self.fog = FogLayer(1.0)
        self.state, self.t0, self.revealed = "playing", time.time(), 0.0
        self.app.toast("GO! find the word", 1.2)
```
- New solid fog, start the clock.

```python
    def on_key(self, key):
        if key in (13, 10):
            self.start_round()
        elif key == ord("w"):
            self.word_i = (self.word_i + 1) % len(self.words)
            self.make_word()
            self.fog.reset()
            self.state = "ready"
        else:
            return False
        return True
```
- Enter starts a round, and `w` picks the next word and resets. Any other key is not ours.

```python
    def update(self, dt, now):
        super().update(dt, now)
        if self.state != "playing":
            return
        if now >= self._next_check:
            self._next_check = now + 0.25
            self.revealed = float(np.mean(self.fog.a[self.word_mask] < 0.35))
```
- Breathing still adds fog (from `super()`), which makes the game harder.
- **The score:** `self.fog.a[self.word_mask]` picks only the fog values over the word's pixels. `< 0.35` asks "is it clear enough to read", and the mean of True/False is the fraction that is clear.
- This is checked 4 times a second, not every frame, to save time.

```python
        if self.revealed >= 0.9:
            took = now - self.t0
            self.best = took if self.best is None else min(self.best, took)
            self.state, self.result = "done", "FOUND in %.1f s" % took
            self.app.toast("you found it!", 2.0)
        elif now - self.t0 >= self.ROUND:
            self.state, self.result = "done", "time up: %d%% revealed" % int(self.revealed * 100)
```
- **90% uncovered is a win:** record the time and keep the best. **30 seconds up is a loss**, with how much you found.
- In `"%d%%"`, `%%` prints a real % sign.

```python
    def render(self, frame):
        out = frost_render(frame, self.fog.a, max_alpha=1.0, under=cv2.add(frame, self.word_layer))
```
- **The trick of the game:** the word is added to the camera picture *under* the fog.
  - `frost_render` makes the frost from the plain `frame` (so the word is never visible through the frost) but shows `under` wherever the fog is wiped away.
  - `max_alpha=1.0`: solid fog really hides it.

```python
        if self.state == "ready":
            card(out, ["REVEAL", "a word is hiding under the fog", "press Enter (or the tab again) to start", "w: next word"])
        elif self.state == "playing":
            left = max(0.0, self.ROUND - (time.time() - self.t0))
            text(out, "%4.1f s" % left, W - 120, NAV_H + 40, 0.9, (255, 255, 255), 2)
            blend_rect(out, 20, H - 26, W - 20, H - 14, (40, 40, 40), 0.5, 6)
            bar_w = int((W - 40) * self.revealed)
            if bar_w > 0:
                rounded_rect(out, 20, H - 26, 20 + bar_w, H - 14, (80, 220, 255), -1, 6)
            text(out, "%d%%" % int(self.revealed * 100), W // 2, H - 34, 0.6, center=True)
        else:
            best = ["best: %.1f s" % self.best] if self.best is not None else []
            card(out, ["REVEAL", self.result] + best + ["Enter: play again   w: next word"])
        return out
```
- **Ready:** an instructions card.
- **Playing:** the seconds left (top right), and a progress bar along the bottom that fills as you reveal.
- **Done:** a result card, with the best time if there is one.

```python
    def nav_extra(self, ui, img, x):
        return ui.chip(img, x, "word: " + self.words[self.word_i], False, lambda: self.on_key(ord("w")))
```

---

## MotionMode: OpenCV optical flow

**Optical flow** compares two frames in a row and works out, for every pixel, which way and how far things moved. It needs no hands, no AI model: just maths on pixels.

```python
    def __init__(self, app):
        super().__init__(app)
        self.fog = FogLayer(0.85)
        self.kernel = np.ones((3, 3), np.uint8)
        self.prev, self.flow, self.min_speed = None, None, 2.0

    def enter(self):
        self.prev = None
```
- Thicker fog (0.85) so the motion shows clearly.
- `kernel`: a 3 x 3 square used for cleaning the mask (below).
- `prev`: the last frame.
- `min_speed`: how many pixels per frame counts as "moving".
- `enter`: forget the old frame when you switch here. A frame from a minute ago would look like a huge movement.

```python
    def update(self, dt, now):
        super().update(dt, now)
        small = cv2.resize(self.app.frame, (320, 180), interpolation=cv2.INTER_AREA)
        gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (5, 5), 0)
```
- Flow is slow, so work on a 320 x 180 copy (9 times fewer pixels than full size).
- Grey only: brightness is enough to see motion.
- A small blur removes camera noise that would look like tiny motion.

```python
        if self.prev is not None:
            self.flow = cv2.calcOpticalFlowFarneback(self.prev, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            speed, _ = cv2.cartToPolar(self.flow[..., 0], self.flow[..., 1])
```
- **Farneback optical flow:** for every pixel, an (x, y) movement between `prev` and `gray`. The numbers:
  - `0.5, 3`: look at the picture at 3 sizes, each half the last, so it catches big moves too.
  - `15`: the area averaged around each pixel.
  - `3`: iterations.
  - `5, 1.2`: the size and smoothness of the local fit.
  - `0`: no special flags.
- `cartToPolar`: turns each (x, y) movement into a length (the speed) and an angle. We only need the speed.

```python
            mask = cv2.morphologyEx((speed > self.min_speed).astype(np.uint8) * 255, cv2.MORPH_OPEN, self.kernel)
            self.mask = cv2.dilate(mask, self.kernel, iterations=2)
            self.fog.a *= 1 - 0.6 * cv2.GaussianBlur(cv2.resize(self.mask, (FW, FH)), (0, 0), 2).astype(np.float32) / 255
        self.prev = gray
```
- **Moving pixels** are white (255) and still ones black: a *mask*.
- `MORPH_OPEN`: an erode then a dilate. It deletes white specks smaller than the 3 x 3 kernel (noise) but keeps real shapes.
- `dilate` twice: grow what is left, so the wiped area is a bit bigger than the moving thing.
- Scale the mask to the fog grid, soften it, and wipe up to 60% of the fog where there was motion.
- Remember this frame for next time.

```python
        self.fog.refog(0.006)
```
- The fog closes back over you when you stand still, a bit faster than in Fog mode.

```python
    def on_key(self, key):
        if key == ord(","):
            self.min_speed = max(0.5, self.min_speed - 0.25)
        elif key == ord("."):
            self.min_speed += 0.25
        else:
            return False
        self.app.toast("motion threshold %.2f" % self.min_speed)
        return True

    def nav_extra(self, ui, img, x):
        x = ui.chip(img, x, "-", False, lambda: self.on_key(ord(",")))
        text(img, "%.2f" % self.min_speed, x, NAV_H // 2 + 6, 0.5, shadow=False)
        return ui.chip(img, x + 40, "+", False, lambda: self.on_key(ord(".")))
```
- `,` makes it more sensitive and `.` less. The sub-bar shows `- 2.00 +`.

```python
MODES = [FogMode, NeonMode, RevealMode, MotionMode]
```
- The tab order. **The App, tabs, number keys and help all read this list**, so adding a mode is: write a class, add it here.

---

## fog.py and gfx.py

```python
def frost_render(frame, fog_grid, max_alpha=0.97, under=None):
    ...
    return cv2.blendLinear(frame if under is None else under, frost_layer(frame), 1 - a, a)
```
- `under`: what to show where the fog is clear. Normally the camera; for Reveal, the camera plus the word.

```python
def card(img, lines):
    w = max(text_width(s, 0.7 if i else 1.2, 2 if i == 0 else 1) for i, s in enumerate(lines)) + 70
    h = 40 + 40 * len(lines)
    x0, y0 = W // 2 - w // 2, H // 2 - h // 2
    blend_rect(img, x0, y0, x0 + w, y0 + h, (25, 25, 25), 0.65, 18)
    rounded_rect(img, x0, y0, x0 + w, y0 + h, (230, 230, 230), 1, 18)
    for i, s in enumerate(lines):
        text(img, s, W // 2, y0 + 48 + 40 * i, 1.2 if i == 0 else 0.7, (255, 255, 255), 2 if i == 0 else 1, center=True)
```
- A centred card sized to fit its widest line. The first line is the big title (`0.7 if i else 1.2`: `i` is 0 for the first line, and 0 counts as False).

---

## ui.py: tabs and the sub-bar

```python
        x = 150
        for i, mode in enumerate(app.modes):
            x = self.chip(img, x, "%d %s" % (i + 1, mode.name), i == app.mode_i, lambda i=i: app.set_mode(i))
        self.draw_subbar(img)
```
- **One chip per mode:** "1 Fog", "2 Neon" and so on. The chosen one is white. They replace phase 4's "clear" and "re-fog" chips.

```python
    def draw_subbar(self, img):
        y0, mouse, before = NAV_H + 6, self.mouse, len(self.buttons)
        self.mouse = (mouse[0], mouse[1] - y0)
        end = self.app.mode.nav_extra(self, img[y0:y0 + NAV_H].copy(), 20)
        self.buttons = self.buttons[:before]
```
- **A puzzle:** we want a dark pill *behind* the mode's controls, but we only know how wide the controls are after drawing them.
- **So draw them once on a throwaway copy** of the strip under the navbar, just to learn where they end (`end`). Then throw away the buttons that drawing added.
- `nav_extra` draws as if the strip starts at y = 0, so the mouse is shifted up by `y0` too. That way hover lights up the right chip.

```python
        if end > 20:
            blend_rect(img, 8, y0 + 7, end + 6, y0 + NAV_H - 7, (25, 25, 25), 0.5, 22)
            rounded_rect(img, 8, y0 + 7, end + 6, y0 + NAV_H - 7, (200, 200, 200), 1, 22)
            strip = img[y0:y0 + NAV_H].copy()
            self.app.mode.nav_extra(self, strip, 20)
            img[y0:y0 + NAV_H] = strip
            self.buttons[before:] = [((r[0], r[1] + y0, r[2], r[3] + y0), fn) for r, fn in self.buttons[before:]]
        self.mouse = mouse
```
- **If the mode has controls:** draw the pill, then draw the controls for real on a copy of the strip, and paste the strip back.
- The new buttons' rectangles were measured inside the strip, so move them down by `y0` to real screen positions.
- Put the real mouse position back.

---

## app.py: what is new

```python
        self.modes, self.mode_i = None, 0
        ...
        if self.modes is None:
            self.modes = [cls(self) for cls in MODES]
        self.state = "run"
        self.mode.enter()
```
- **Make one of each mode** from the list of classes. `cls(self)` calls each class like a function. Every mode keeps its own drawing when you switch away and back.

```python
    @property
    def mode(self):
        return self.modes[self.mode_i]
```
- `@property` makes `self.mode` look like a variable but run this code. Everything that said `self.mode` in phase 4 still works: it is now "the chosen mode".

```python
    def set_mode(self, i):
        if i == self.mode_i and self.mode.name == "Reveal":
            self.mode.start_round()
            return
        self.mode_i = i
        self.hands.lift_all()
        self.mode.enter()
        self.toast("%s: %s" % (self.mode.name, self.mode.hint), 2.5)
```
- Clicking the Reveal tab while in Reveal starts a round, which is handy on a touch screen with no keyboard.
- **Switching:** lift all pens (a stroke must not carry into another mode), tell the new mode, and show its hint.

```python
        if ord("1") <= k < ord("1") + len(self.modes):
            self.set_mode(k - ord("1"))
        elif not self.mode.on_key(k) and chr(k) in self.keys:
```
- Keys 1 to 4 pick a tab. `ord("1")` is the key code of "1", so `k - ord("1")` gives 0 to 3.

```python
        self.sfx.squeak = float(np.clip((hands.speed - 4) / 20, 0, 1)) * 0.25 if self.mode.uses_fog else 0.0
        ...
        if hands.held("peace", any(i["peace"] for i in live), 0.6, now):
            self.mode.on_peace()
        ...
        self.effects.update(dt, self.breath_strength, self.mouth, self.mode.uses_fog)
```
- No glass squeak and no breath puffs in Neon.
- **A peace sign held for 0.6 s** calls the mode's `on_peace`. Only Neon uses it, but the App does not need to know that.

```python
    parser.add_argument("--word", default="", help="your own word for Reveal mode")
```

---

## Try this

1. **Add your own mode.** In `modes.py`, before `MODES = [...]`:
   ```python
   class ThickMode(Mode):
       name, hint = "Thick", "very thick fog that never comes back"

       def __init__(self, app):
           super().__init__(app)
           self.fog = FogLayer(1.0)
   ```
   Then add `ThickMode` to the end of `MODES`. A 5th tab and key 5 appear by themselves.
2. In `NeonMode.render`, change `alpha=0.55` to `alpha=0.0`. The room goes black and only the light is left.
3. In Neon, change the glow blur `7` to `20`. You get a huge soft haze.
4. In Reveal, change `ROUND = 30.0` to `10.0`, and `self.revealed >= 0.9` to `>= 0.5`.
5. In Motion, change `0.6 * cv2.GaussianBlur(...)` to `1.0 * ...`. Moving wipes the fog in one go.
6. In Motion, delete the `MORPH_OPEN` step (use the `speed > ...` mask directly). In a dim room, noise speckles start eating the fog.
7. Run with `--word "HELLO WORLD"` and play Reveal with your own word.
