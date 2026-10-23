# Phase 6: the finished app

Run it: `python run.py --windowed` (from this folder, with your venv active). It is the same app as `run_fog_studio.bat`.

The code for this phase is the real app in `fog-studio/studio/`. `run.py` here just starts it.

**New:**
- **Photo booth:** the camera button, `p`, or a thumbs up held for 0.8 s starts a 3-2-1 countdown. Then a flash, and a polaroid with the date is saved to `fog-studio/gallery/`. `s` saves a plain PNG straight away.
- **Gallery** (`g` or the grid button): the photos from this session, as a strip.
- **Help** (`h`) lists every gesture and key.
- **Debug view** (`d` or the `</>` button): hand skeletons, the pinch ratio, timings, a breath graph, and a live panel of what OpenCV sees. `v` switches the panel between mask, convex hull and optical flow.
- The breath ring moved from the mic button to the camera button, and the mic button is gone (`-` and `=` still set breath sensitivity).

| File | What changed |
| --- | --- |
| `debug.py` | **New.** The debug overlay and the OpenCV panel |
| `ui.py` | Camera, gallery and debug buttons, countdown, flash, gallery strip, `polaroid()`, the full help |
| `app.py` | `clean` frame, photos, gallery, thumbs-up gesture, FPS, keys `s p d v g` |
| `modes.py` | `mask` for the debug panel; Motion measures its own time |
| `config.py` | `GALLERY`, the folder photos go to |
| everything else | Same as phase 5 |

---

## config.py

```python
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GALLERY = os.path.join(HERE, "gallery")
MODELS = os.path.join(HERE, "models")
```
- In the finished app, `HERE` is the `fog-studio` folder, so photos go to `fog-studio/gallery/` and the models are in `fog-studio/models/`.

---

## app.py: photos

```python
        self.clean = self.frame
        self.frame_no, self.fps, self.cv_ms = 0, 0.0, 0.0
        ...
        self.show_help = self.show_gallery = False
        self.gallery = []
        self.countdown = None
```
- `clean`: the mirror picture of the last frame, **before** the navbar and debug were drawn on it. Photos use it, so they show the fog, not the buttons.
- **Debug numbers:** `fps` (frames per second) and `cv_ms` (how long the OpenCV work took).
- `gallery`: small thumbnails of this session's photos.
- `countdown`: the clock time the photo will be taken, or None.

```python
            "c": lambda: self.mode.clear(), "x": self.clean_glass, "s": lambda: self.save_png(self.clean),
            "p": self.booth_photo, "d": self.debugger.toggle, "v": self.debugger.next_view,
            "g": lambda: self.toggle("show_gallery"), "h": lambda: self.toggle("show_help"), "m": self.toggle_sound,
```
- **New keys:** `s` saves now, `p` starts the countdown, `d` and `v` control debug, and `g` shows the gallery.

```python
    def booth_photo(self):
        if self.countdown is None:
            self.countdown = time.time() + 3.0
```
- Start a 3 second countdown, unless one is already running.

```python
    def save_png(self, img, as_polaroid=False):
        os.makedirs(GALLERY, exist_ok=True)
        img = polaroid(img) if as_polaroid else img
        path = os.path.join(GALLERY, "fog_%s_%03d.png" % (time.strftime("%Y%m%d_%H%M%S"), int(time.time() * 1000) % 1000))
        cv2.imwrite(path, img)
        self.gallery = (self.gallery + [cv2.resize(img, (160, int(160 * img.shape[0] / img.shape[1])))])[-6:]
        self.toast("saved " + os.path.basename(path), 2.0)
        return path
```
- Make the `gallery` folder if needed (`exist_ok` means "no error if it is already there").
- **The file name** is the date and time plus the milliseconds, like `fog_20261023_005716_320.png`. Two photos in the same second still get different names.
- `cv2.imwrite` saves it (the `.png` ending picks the format).
- **The thumbnail** is 160 px wide with the same shape. Only the last 6 are kept (`[-6:]`).

```python
        if hands.held("thumbs", any(i["thumbs_up"] for i in live), 0.8, now):
            self.booth_photo()
```
- In `update_hands`: a thumbs up held for 0.8 s takes a photo, so you never touch the laptop.

```python
    def update_booth(self, now):
        if self.countdown is not None and now >= self.countdown:
            self.save_png(self.clean, as_polaroid=True)
            self.countdown, self.ui.flash = None, 1.0
```
- When the countdown runs out: save a polaroid of the clean mirror and start the white flash.

```python
        out = self.effects.apply(self.mode.render(frame), now, self.hands)
        self.clean = out.copy()
        self.update_booth(now)
        self.ui.draw(out)
        self.ui.draw_overlays(out, now)
```
- In `step`: `clean` is copied **after** the effects (photos look like the mirror) but **before** the UI (no buttons in photos). `.copy()` matters: without it, `clean` and `out` would be the same array and the UI would draw on both.

```python
                if dt > 0:
                    self.fps += (1 / dt - self.fps) * 0.1
```
- In `run`: frames per second is 1 / (seconds per frame), eased so the number does not jump around.

---

## ui.py: what is new

```python
        if kind == "shot":
            cv2.rectangle(img, (c[0] - 9, c[1] - 5), (c[0] + 9, c[1] + 7), ink, 1, cv2.LINE_AA)
            cv2.circle(img, c, 4, ink, 1, cv2.LINE_AA)
            cv2.rectangle(img, (c[0] - 4, c[1] - 8), (c[0] + 3, c[1] - 5), ink, -1)
            lvl = min(1.0, max(self.app.breath_strength, self.app.breath.meter))
            cv2.ellipse(img, c, (16, 16), -90, 0, 360 * lvl, (255, 220, 120), 2, cv2.LINE_AA)
```
- **A camera icon:** the body, the lens and the viewfinder bump. The breath ring from the mic button now goes around it.

```python
        elif kind == "debug":
            text(img, "</>", c[0] - 13, c[1] + 5, 0.45, ink, shadow=False)
        elif kind == "gallery":
            for dx in (-6, 2):
                for dy in (-6, 2):
                    cv2.rectangle(img, (c[0] + dx, c[1] + dy), (c[0] + dx + 4, c[1] + dy + 4), ink, -1)
```
- **Debug** is a `</>` sign, and **gallery** is a 2 x 2 grid of small squares (two loops give 4 positions).

```python
        rx = W - 44
        for kind, fn, active in (("help", lambda: app.toggle("show_help"), app.show_help),
                                 ("gallery", lambda: app.toggle("show_gallery"), app.show_gallery),
                                 ("debug", app.debugger.toggle, app.debugger.on),
                                 ("sound", app.toggle_sound, False),
                                 ("shot", app.booth_photo, app.countdown is not None)):
            rx = self.icon_button(img, rx, kind, fn, active)
```
- **All the right-hand buttons, as data:** (icon, action, is it lit up). One loop draws them right to left. Adding a button is one more line in the tuple.

```python
        if app.countdown is not None:
            left = app.countdown - now
            cv2.circle(img, (W // 2, H // 2), 70, (255, 255, 255), 3, cv2.LINE_AA)
            cv2.ellipse(img, (W // 2, H // 2), (70, 70), -90, 0, 360 * (left % 1), (120, 220, 255), 6, cv2.LINE_AA)
            text(img, str(int(math.ceil(left))), W // 2, H // 2 + 30, 3.0, (255, 255, 255), 5, center=True)
```
- **The countdown:**
  - A circle with an arc that empties once every second (`left % 1` is the fraction of the current second still left).
  - The big number is the seconds left, rounded up: 2.4 s left shows "3".

```python
        if self.flash > 0:
            cv2.addWeighted(img, 1 - self.flash, np.full_like(img, 255), self.flash, 0, dst=img)
            self.flash = max(0.0, self.flash - 0.12)
```
- **The flash:** mix the screen with pure white, starting fully white and fading by 0.12 per frame (about 8 frames).

```python
        if app.show_gallery:
            self.draw_gallery(img)
        if app.debugger.on:
            app.debugger.draw(img, app)
        if app.show_help:
            draw_help(img)
```
- Help is drawn last, so it covers everything.

```python
    def draw_gallery(self, img):
        thumbs = self.app.gallery
        if not thumbs:
            text(img, "no photos yet: s, the shutter, or a thumbs up", W // 2, H - 80, 0.55, center=True)
            return
        total = sum(t.shape[1] + 10 for t in thumbs)
        x, th = W // 2 - total // 2, max(t.shape[0] for t in thumbs)
        blend_rect(img, x - 12, H - th - 90, x + total + 2, H - 66, (20, 20, 20), 0.55, 12)
        for t in thumbs:
            y = H - 78 - t.shape[0]
            img[y:y + t.shape[0], x:x + t.shape[1]] = t
            x += t.shape[1] + 10
```
- **No photos:** say how to take one.
- **Otherwise:** work out the strip's total width so it can be centred, draw a dark backing, then paste each thumbnail into the picture with a slice assignment, 10 px apart.

```python
def polaroid(img):
    pad, bottom = 24, 90
    pic = np.full((H + pad + bottom, W + 2 * pad, 3), 248, np.uint8)
    pic[pad:pad + H, pad:pad + W] = img
    text(pic, "Fog Studio", pad, pad + H + 48, 1.0, (60, 60, 60), 1, cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, shadow=False)
    text(pic, time.strftime("%d %b %Y  %H:%M"), W + pad - 220, pad + H + 48, 0.6, (120, 120, 120), shadow=False)
    return pic
```
- **An instant photo:**
  - A near-white card, 24 px border, 90 px at the bottom.
  - The photo pasted in.
  - "Fog Studio" in a handwriting font, and the date (`strftime` formats it, like "23 Oct 2026  00:57").

---

## modes.py: two small additions

```python
        self.mask = None  # an OpenCV mask for the debug panel (None: the panel shows the skin mask)
```
- In `Mode.__init__`. A mode that makes its own mask (Motion) can show it in the debug panel.

```python
        t0 = time.perf_counter()
        ...
        self.app.cv_ms = (time.perf_counter() - t0) * 1000
```
- In `MotionMode.update`: time the optical flow and report it, so the debug view can show how expensive it is.

---

## debug.py: see what the computer sees

```python
HAND_LINKS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), ...]
SKIN_LO, SKIN_HI = np.array([0, 135, 85]), np.array([255, 180, 135])
VIEWS = ["mask", "hull + defects", "optical flow"]
```
- `HAND_LINKS`: which landmarks to join with lines to draw a skeleton (thumb chain, each finger, across the knuckles).
- **Skin colour in YCrCb.** YCrCb splits a colour into brightness (Y) and two colour parts (Cr, Cb). Skin of every tone falls in a narrow Cr/Cb range at any brightness, so we accept any Y (0 to 255) but only Cr 135 to 180 and Cb 85 to 135.
- `VIEWS`: the panel's three views.

```python
def skin_mask(small):
    return cv2.inRange(cv2.cvtColor(small, cv2.COLOR_BGR2YCrCb), SKIN_LO, SKIN_HI)
```
- `inRange` gives 255 where all three channels are inside the range, and 0 elsewhere: a skin mask. This is how hand tracking was done before AI models like MediaPipe.

```python
class DebugView:
    def __init__(self):
        self.on, self.view, self._prev = False, 0, None

    def toggle(self):
        self.on = not self.on

    def next_view(self):
        self.view = (self.view + 1) % len(VIEWS)
```
- On or off, which view, and the last grey frame (for optical flow outside Motion mode).

### draw

```python
        for info, lm in zip(app.hands.infos, app.hands.lms):
            if lm is None:
                continue
            for a, b in HAND_LINKS:
                cv2.line(img, tuple(int(v) for v in lm[a]), tuple(int(v) for v in lm[b]), (120, 255, 120), 2, cv2.LINE_AA)
            for p in lm:
                cv2.circle(img, (int(p[0]), int(p[1])), 3, (255, 255, 255), -1, cv2.LINE_AA)
            tags = [k for k in ("fist", "thumbs_up", "peace", "open") if info[k]]
            text(img, "pinch %.2f %s" % (info["pinch"], " ".join(tags)), int(lm[0][0]) - 40, int(lm[0][1]) + 24, 0.5)
```
- **For each tracked hand:** the green skeleton, a white dot on each of the 21 landmarks, and under the wrist the live pinch ratio plus any gesture it sees. This is the best way to learn the gesture numbers: watch them change as you move.

```python
        cv2.circle(img, (int(app.mouth[0]), int(app.mouth[1])), 6, (255, 180, 80), 2, cv2.LINE_AA)
        t = app.tracker
        text(img, "%.0f fps   mediapipe %.0f ms   opencv %.1f ms" % (app.fps, t.ms, app.cv_ms), 16, NAV_H + 84, 0.5)
```
- **A blue ring where the breath lands** (your mouth, if the face is found).
- **Timings:**
  - Frames per second.
  - How long MediaPipe took. It runs on its own thread, so this does not slow the fps.
  - How long Motion's OpenCV work took.

```python
        if t.ok:
            n = len(t.hands)
            status = "hand tracking ON: %d hand%s seen" % (n, "" if n == 1 else "s") + ("   (%s)" % t.error if t.error else "")
        else:
            status = "hand tracking OFF: " + t.error
        text(img, status[:110], 16, NAV_H + 188, 0.45, (150, 255, 150) if t.ok else (120, 140, 255))
```
- **Is tracking on, and how many hands it sees right now**, in green (or red if off). The first thing to check when "it does not see my hand".
- `status[:110]` cuts long errors to fit.

```python
        self.draw_breath(img, app)
        panel = self.panel(app.frame, app.mode)
        ph, pw = panel.shape[:2]
        x, y = W - pw - 16, H - ph - 70
        img[y:y + ph, x:x + pw] = panel
        cv2.rectangle(img, (x, y), (x + pw, y + ph), (240, 240, 240), 1)
        text(img, VIEWS[self.view] + "   (v: next view)", x, y - 8, 0.45)
```
- The breath graph, then the 320 x 180 OpenCV panel pasted into the bottom right corner with a border and its name.

### draw_breath: the breath graph

```python
        hist = list(app.breath.history)
        if len(hist) <= 2:
            return
        x0, y0, w, h = 16, NAV_H + 96, 200, 50
        blend_rect(img, x0, y0, x0 + w, y0 + h, (20, 20, 20), 0.5, 6)
        top = max(max(max(a, b) for a, b in hist), 1e-4)
        for col, colour in ((1, (80, 170, 255)), (0, (255, 255, 255))):
            pts = [(x0 + int(i * w / len(hist)), y0 + h - int(v[col] / top * (h - 4))) for i, v in enumerate(hist)]
            cv2.polylines(img, [np.array(pts, np.int32)], False, colour, 1, cv2.LINE_AA)
        text(img, "breath %.2f  flat %.2f" % (app.breath_strength, app.breath.flat), x0, y0 + h + 18, 0.45)
```
- The last 160 breath readings as two lines in a 200 x 50 box:
  - **White:** the mic level.
  - **Orange:** the trigger line (the floor plus the trigger).
  - When white goes above orange (and the sound is hissy), that is a breath.
- `top`: the biggest value, so the graph always fills its box.
- Each point's x is its position in the history. Its y is its value scaled to the box height and flipped, because screen y grows downwards.
- Below it: the breath strength and the live spectral flatness. Say "haaa" and then "mmmm" and watch the flatness.

### panel: three OpenCV views

```python
        small = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
        if self.view == 0:
            return cv2.cvtColor(mode.mask if mode.mask is not None else skin_mask(small), cv2.COLOR_GRAY2BGR)
        if self.view == 1:
            return self.hull_view(small)
```
- **View 0, mask:** Motion's motion mask, or the skin mask in other modes. Converted to 3 channels so it can be pasted into the colour picture.
- **View 1:** see `hull_view` below.

```python
        flow = getattr(mode, "flow", None)
        if flow is None:
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            prev, self._prev = self._prev, gray
            if prev is None:
                return np.zeros((180, 320, 3), np.uint8)
            flow = cv2.calcOpticalFlowFarneback(prev, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
```
- **View 2, optical flow:** reuse Motion mode's flow if we are in it (`getattr(..., None)` gives None if the mode has no `flow`). Otherwise work it out here, the same way.

```python
        speed, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        hsv = np.zeros((flow.shape[0], flow.shape[1], 3), np.uint8)
        hsv[..., 0] = (ang * 90 / np.pi).astype(np.uint8)
        hsv[..., 1] = 255
        hsv[..., 2] = np.clip(speed * 30, 0, 255).astype(np.uint8)
        return cv2.resize(cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR), (320, 180))
```
- **The classic way to draw flow:**
  - The **direction** of movement becomes the **colour** (hue). The angle 0 to 2 pi maps to OpenCV's hue 0 to 180, so `* 90 / pi`.
  - The **speed** becomes the **brightness**.
  - So: still is black, moving left is one colour, moving right is another.

### hull_view: convex hull and defects

```python
        mask = cv2.morphologyEx(skin_mask(small), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        out = (small // 2).copy()
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return out
        c = max(contours, key=cv2.contourArea)
        if cv2.contourArea(c) <= 300:
            return out
```
- Clean the skin mask and dim the background picture (`// 2` halves it).
- `findContours`: the outline of every white blob.
  - `RETR_EXTERNAL`: outer outlines only.
  - `CHAIN_APPROX_SIMPLE`: straight runs are stored as just their two ends.
- **Keep the biggest blob** (hopefully your hand), if it is big enough.

```python
        cv2.drawContours(out, [c], -1, (120, 255, 120), 1)
        cv2.polylines(out, [cv2.convexHull(c)], True, (0, 220, 255), 1)
```
- **Green:** the blob's outline.
- **Yellow:** its *convex hull*, like a rubber band stretched around the hand. It touches the fingertips and skips the gaps between fingers.

```python
        try:
            defects = cv2.convexityDefects(c, cv2.convexHull(c, returnPoints=False))
        except cv2.error:
            defects = None
        for _, _, f, d in ([] if defects is None else defects.reshape(-1, 4)):
            if d / 256 > 8:
                cv2.circle(out, tuple(int(v) for v in c[f][0]), 3, (60, 60, 255), -1)
        return out
```
- **Convexity defects:** the places where the outline dips in away from the rubber band. On a hand, the deep ones are the valleys **between the fingers**.
  - Each defect is (start, end, deepest point, depth x 256).
  - **Red dots** mark defects deeper than 8 pixels.
- **Count the red dots and add one: that is how many fingers are up.** This is the pre-AI finger counter from the workshop's Level 5. Compare it with MediaPipe's skeleton next to it.
- `try/except`: `convexityDefects` sometimes fails on odd shapes; we just skip the dots then.

---

## Try this

1. Press `d`, hold up your hand, and watch the pinch number. Slowly close your pinch and see where the pen goes down (0.22) and comes up (0.38).
2. Press `v` until "hull + defects". Hold up 1, 2, 3, 4 fingers and count the red dots. Try it against a skin-coloured wall to see why AI models replaced this.
3. Press `v` again for optical flow. Wave left, then right, and watch the colours.
4. Say "haaa", then hum "mmmm", and watch the flatness number in the breath graph.
5. In `app.py` `booth_photo`, change `+ 3.0` to `+ 10.0` for a 10 second self-timer.
6. In `ui.py` `polaroid`, change `"Fog Studio"` to your club's name, and `bottom = 90` to `140`.
7. In `debug.py`, change `d / 256 > 8` to `> 2`. Many more red dots appear, mostly noise along the edge.
