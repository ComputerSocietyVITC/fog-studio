# Phase 3: your hands

Run it: `python run.py --windowed` (from this folder, with your venv active)

**New:**
- **Pinch** thumb and index finger to draw in the fog. A little star shows where.
- **Make a fist** and swipe to wipe a wide area, like your sleeve.
- **Two hands** draw with two pens.
- **Both palms open**, held for 1 second, clears the mirror.
- **Breath follows your face:** MediaPipe finds your mouth, and the fog appears there.
- The mouse still works as a pen.
- **Without MediaPipe:** a red bar says hand tracking is off, and everything else still works.

| File | What changed |
| --- | --- |
| `hands.py` | **New.** MediaPipe on a thread, gestures, the pen, the wiper, two-hand input |
| `effects.py` | **New.** The pinch star and the mirror's bevel |
| `config.py` | Where the models are, pinch and smoothing numbers |
| `gfx.py` | `dist()` and `lerp()` |
| `fog.py` | `stamp()` (a fist wipe) and `soft_kernel()`; one kernel cache for both |
| `modes.py` | `wipe()` |
| `ui.py` | The red "hand tracking off" bar, more help rows |
| `app.py` | Makes the tracker; `update_hands()` replaces `update_mouse()` |
| `audio.py`, `camera.py` | Same as phase 2 |

---

## config.py: new lines

```python
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = next((p for p in (os.path.join(HERE, "models"), os.path.join(HERE, "..", "..", "models"))
               if os.path.isdir(p)), os.path.join(HERE, "models"))
```
- `__file__` is this file's path. Going up two folders (`dirname` twice) gives the phase folder.
- `MODELS`: the first of these that exists: `models/` in this phase's folder, or the shared `fog-studio/models/`. `next(... for ... if ...)` returns the first match, or the last argument if nothing matched.

```python
PINCH_DOWN, PINCH_UP = 0.22, 0.38
EASE_TARGET, EASE_BRUSH, EASE_STAR = 0.45, 0.22, 0.55
TREMOR = 0.0006 * W
WIPE_STAMP = 0.34
```
- **Pinch:** the pen goes down when the pinch is closer than 0.22, and up when it opens past 0.38. These are measured relative to hand size (see `classify`).
- **Smoothing:** each `EASE_` number is "move this fraction of the way per frame". Lower means smoother but laggier.
- `TREMOR`: moves smaller than about half a pixel are ignored, so a still hand does not wobble the line.
- `WIPE_STAMP`: each fist stamp removes 34% of the fog under it.

---

## gfx.py: two maths helpers

```python
def dist(a, b):
    return float(math.hypot(a[0] - b[0], a[1] - b[1]))

def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
```
- `dist`: the straight-line distance between two points (Pythagoras; `hypot(dx, dy)` = `sqrt(dx*dx + dy*dy)`).
- `lerp`: *linear interpolation*. The point `t` of the way from `a` to `b`: `t = 0` gives `a`, `t = 1` gives `b`, `t = 0.5` the middle. Easing is `lerp(current, target, 0.3)` every frame.

---

## hands.py: the hand tracking

**MediaPipe** finds hands in a picture and returns 21 *landmarks* per hand, the same 21 points every time:

```text
        8   12  16  20        tips
        7   11  15  19
   4    6   10  14  18        PIP joints (middle knuckles)
   3    5    9  13  17        MCP knuckles (where fingers join the hand)
   2
   1         0                0 = wrist, 1 to 4 = thumb
```

```python
os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
```
- MediaPipe prints a lot of messages when it starts. These two settings ask it to print only errors.

### class Tracker

```python
        self.ok, self.error = False, ""
        self.hands, self.mouth, self.ms = [], None, 0.0
        self._frame, self._lock, self._running, self._ts = None, threading.Lock(), True, 0
```
- `ok` and `error`: did MediaPipe load, and if not, why.
- `hands`: the newest landmarks, one 21 x 2 array per hand.
- `mouth`: where the mouth is, or None.
- `ms`: how long one detection took.
- `_frame`: the newest camera frame waiting to be checked.
- `_lock`: a lock, so two threads never touch `_frame` at the same moment.
- `_running`: set to False to stop the thread.
- `_ts`: the last timestamp sent to MediaPipe.

```python
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions, vision
            self._mp, video = mp, vision.RunningMode.VIDEO
            self._hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=os.path.join(MODELS, "hand_landmarker.task")),
                running_mode=video, num_hands=2, min_hand_detection_confidence=0.6,
                min_hand_presence_confidence=0.5, min_tracking_confidence=0.5))
```
- **MediaPipe's Tasks API**: load the hand model file and build a `HandLandmarker`.
  - `VIDEO` mode means "these frames are a video": it follows a hand from frame to frame, which is faster and steadier than looking afresh every time.
  - `num_hands=2`.
  - **The confidence numbers:** a hand must look at least 60% like a hand to be found, and 50% to keep being followed.

```python
            face_model = os.path.join(MODELS, "blaze_face_short_range.tflite")
            self._face = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
                base_options=BaseOptions(model_asset_path=face_model), running_mode=video,
                min_detection_confidence=0.5)) if os.path.exists(face_model) else None
            self.ok = True
        except Exception as e:
            self.error = "%s: %s" % (type(e).__name__, e)
            return
        threading.Thread(target=self._run, daemon=True).start()
```
- The same again for the face detector, but only if its model file exists. The face is optional.
- `except`: MediaPipe is not installed, or a model is missing. Remember why (`ModuleNotFoundError: No module named 'mediapipe'`) and give up quietly. The app still runs.
- **The thread:** detection takes about 15 to 30 ms, too slow to do in the main loop without making the mirror stutter. So `_run` loops on its own thread. `daemon=True` means the thread dies when the app ends.

```python
    def submit(self, frame):
        if self.ok:
            with self._lock:
                self._frame = frame
```
- The main loop hands over each new frame. If the thread is still busy, the next submit just replaces the waiting frame, so it always works on the newest one and never falls behind.
- `with self._lock:` holds the lock for just this one line.

```python
    def _run(self):
        count = 0
        while self._running:
            with self._lock:
                frame, self._frame = self._frame, None
            if frame is None:
                time.sleep(0.003)
                continue
```
- Takes the waiting frame and empties the slot, both while holding the lock. If there is no new frame, it sleeps 3 ms and checks again.

```python
            t0 = time.perf_counter()
            rgb = np.ascontiguousarray(cv2.cvtColor(cv2.resize(frame, (640, 360)), cv2.COLOR_BGR2RGB))
            try:
                self.hands = self._detect(rgb, face_too=count % 5 == 0)
            except Exception as e:
                self.error, self.hands = "%s: %s" % (type(e).__name__, e), []
            count += 1
            self.ms = (time.perf_counter() - t0) * 1000
```
- Shrink to 640 x 360 (faster, still plenty for hands) and convert to RGB, the colour order MediaPipe expects.
- `ascontiguousarray`: MediaPipe needs the pixels in one unbroken block of memory.
- The face moves slowly, so it is only checked every 5th time.
- `perf_counter` is a precise stopwatch, used to measure how many milliseconds detection took.

```python
    def _detect(self, rgb, face_too):
        self._ts = max(self._ts + 1, int(time.monotonic() * 1000))
        img = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        res = self._hands.detect_for_video(img, self._ts)
```
- VIDEO mode needs a timestamp in milliseconds that **always goes up**. `max(last + 1, now)` makes sure of that even if two calls land in the same millisecond.
- Wrap the picture as a MediaPipe `Image`, then detect.

```python
        if face_too and self._face is not None:
            faces = self._face.detect_for_video(img, self._ts).detections
            if faces:
                kp = faces[0].keypoints[3]
                self.mouth = (kp.x * W, kp.y * H)
        return [np.array([(p.x * W, p.y * H) for p in lm], np.float32) for lm in res.hand_landmarks]
```
- **The face detector gives 6 keypoints:** right eye, left eye, nose, **mouth (index 3)**, right ear and left ear.
- MediaPipe positions are fractions (0 to 1) of the picture, so `x * W, y * H` turns them into our 960 x 540 pixels. The resize to 640 x 360 does not matter.
- The last line turns each hand's 21 landmarks into a 21 x 2 NumPy array.

### classify: landmarks to gestures

```python
    size = max(dist(lm[0], lm[9]), 1e-6)
    pinch = dist(lm[4], lm[8]) / size
```
- `size`: wrist to the middle knuckle, the hand's size on screen. `1e-6` avoids dividing by 0.
- `pinch`: thumb tip to index tip, **divided by the hand's size**. A hand near the camera looks big and far away looks small, but this ratio stays the same. So 0.22 means "pinching" at any distance.

```python
    curled = [dist(lm[t], lm[0]) < dist(lm[p], lm[0]) for t, p in ((8, 6), (12, 10), (16, 14), (20, 18))]
```
- **For index, middle, ring and pinky:** a finger is *curled* if its tip is closer to the wrist than its middle knuckle is. A straight finger's tip is far from the wrist; a bent one folds back.
- Gives 4 True/False values.

```python
    thumb_up = all(curled) and lm[4][1] < lm[5][1] - 0.45 * size and lm[4][1] < lm[3][1]
    palm = lm[[0, 5, 9, 13, 17]].mean(axis=0)
```
- **Thumbs up:** a fist, and the thumb tip clearly above the index knuckle and above its own joint. On screen, smaller y is higher.
- `palm`: the average of the wrist and the 4 knuckles, the middle of the palm. `lm[[...]]` picks those rows.

```python
    return {
        "pinch": pinch,
        "index_ext": not curled[0],
        "fist": all(curled) and not thumb_up,
        "thumbs_up": thumb_up,
        "peace": not curled[0] and not curled[1] and curled[2] and curled[3] and pinch > 0.5,
        "open": not any(curled) and pinch > 0.6,
        "width": max(dist(lm[5], lm[17]), size),
        "pinch_point": ((lm[4][0] + lm[8][0]) / 2, (lm[4][1] + lm[8][1]) / 2),
        "palm": (float(palm[0]), float(palm[1])),
    }
```
- `index_ext`: the index finger is straight.
- `fist`: all 4 curled, and not a thumbs up.
- `peace`: index and middle straight, ring and pinky curled, thumb away.
- `open`: nothing curled, thumb away from the index.
- `width`: knuckle to knuckle across the hand, used to size the fist wipe.
- `pinch_point`: halfway between thumb tip and index tip. That is where the pen draws.

### pinch_at and quad_points

```python
def pinch_at(point):
    return {"pinch": 0.0, "index_ext": True, "pinch_point": point}
```
- A fake "fully pinched" hand at a point. The mouse uses it, so the mouse gets the same smooth pen as a hand.

```python
def quad_points(p0, p1, p2, step=2.0):
    n = max(2, int((dist(p0, p1) + dist(p1, p2)) / step))
    t = np.linspace(0, 1, n)[:, None]
    a, b, c = np.array(p0), np.array(p1), np.array(p2)
    return (1 - t) ** 2 * a + 2 * (1 - t) * t * b + t ** 2 * c
```
- A *quadratic Bezier curve*: a smooth curve from `p0` to `p2` that bends towards `p1`.
- `n`: one point about every 2 pixels along the way.
- The last line is the Bezier formula, worked out for all `n` values of `t` at once.

### class Pen: pinch to draw

```python
        self.down = False
        self.target = self.brush = self.star = None
        self.pts, self.released, self.last_seen, self.speed = [], 0, 0.0, 0.0
```
- `down`: is the pen touching the glass.
- `target` and `brush`: the two smoothing stages.
- `star`: where the star is drawn.
- `pts`: the last 3 brush points.
- `released`: frames in a row with the pinch open.
- `last_seen`: when the hand was last seen.
- `speed`: how far the brush moved this frame (for the squeak sound in phase 4).

```python
    def update(self, info, now, draw):
        self.speed = 0.0
        if info is None:
            if self.down and now - self.last_seen > 0.25:
                self.lift()
            return
```
- **No hand this frame:** MediaPipe often loses a hand for a frame or two. The pen only lifts if the hand has been gone for more than 0.25 s. Otherwise a flicker would break your line.

```python
        self.last_seen = now
        raw = info["pinch_point"]
        self.star = raw if self.star is None else lerp(self.star, raw, EASE_STAR)
```
- The star follows the pinch point, eased.

```python
        if not self.down:
            if info["pinch"] < PINCH_DOWN and info["index_ext"]:
                self.down, self.released = True, 0
                self.target = self.brush = raw
                self.pts = [raw]
                draw([raw])
            return
```
- **Pen up:** start drawing when the pinch closes below 0.22, *and* the index finger is straight. In a fist the thumb rests on the index and looks like a pinch; this stops a fist from drawing.
- The first point is drawn as a dot.

```python
        self.released = self.released + 1 if info["pinch"] > PINCH_UP else 0
        if self.released >= 2:
            self.lift()
            return
```
- **Pen down:** it lifts only when the pinch opens past 0.38 for 2 frames in a row.
- **Two different thresholds (0.22 down, 0.38 up) is called *hysteresis*.** A pinch hovering around 0.3 does not flicker on and off, because once down it stays down until clearly open.

```python
        self.target = lerp(self.target, raw, EASE_TARGET)
        new = lerp(self.brush, self.target, EASE_BRUSH)
        if dist(new, self.pts[-1]) < TREMOR:
            return
```
- **Two-stage smoothing:** the target chases the real finger (45% per frame), then the brush chases the target (22% per frame). Two gentle stages remove MediaPipe's jitter better than one strong one, with less lag.
- Tiny moves are ignored (tremor filter).

```python
        self.speed = dist(new, self.brush)
        self.brush = new
        self.pts.append(new)
        if len(self.pts) >= 3:
            a, b, c = self.pts[-3:]
            draw(quad_points(lerp(a, b, 0.5), b, lerp(b, c, 0.5)))
        else:
            draw([self.pts[-2], new])
        self.pts = self.pts[-3:]
```
- **Smooth curves:** with points a, b, c, draw a curve from the middle of a-b to the middle of b-c, bending through b. Each piece starts where the last one ended, in the same direction, so the stroke has no corners.
- Only the last 3 points are kept.

### class Wiper: fist to wipe

```python
    def update(self, center, radius, stamp):
        if center is None:
            self.last = None
            return 0
        if self.last is None or dist(center, self.last) > 0.3 * W:
            stamp(center, radius)
            self.last = center
            return 1
```
- **No fist:** forget the last position.
- **A new fist, or one that jumped across 30% of the screen** (tracking glitch): one stamp only. A glitch would otherwise wipe a long streak.

```python
        step, d = radius * 0.5, dist(center, self.last)
        n = min(40, int(d // step))
        for i in range(1, n + 1):
            stamp(lerp(self.last, center, i * step / d), radius)
        if n:
            self.last = lerp(self.last, center, n * step / d)
        return n
```
- **One soft stamp every half radius you move**, along the line from the last stamp to here. A fast swipe gives a solid band, not separate circles. A fist held still adds nothing, so it does not dig a hole.
- At most 40 stamps per frame, to stay fast.
- `last` moves to the last stamp actually made, not to the hand. The leftover distance counts towards the next frame.

### class HandInput: two hands plus the mouse

```python
        self.pens, self.wipers, self.mouse_pen = [Pen(), Pen()], [Wiper(), Wiper()], Pen()
        self.slots = [None, None]
        self.lms, self.infos = [None, None], [None, None]
        self.holds = {}
        self.drawing, self.wiping, self.speed = False, False, 0.0
```
- **Two slots:** each has its own pen and wiper. `slots` holds each slot's last wrist position.
- `holds`: when each held gesture started (used by `held`).

```python
    def match(self, hands):
        out, free = [None, None], [0, 1]
        for lm in hands[:2]:
            wrist = (float(lm[0][0]), float(lm[0][1]))
            best = min(free, key=lambda s: dist(wrist, self.slots[s]) if self.slots[s] else 1e9)
            out[best] = lm
            free.remove(best)
            self.slots[best] = wrist
        for s in free:
            self.slots[s] = None
        return out
```
- MediaPipe does not promise to list hands in the same order every frame. If the order swapped, your two pens would swap hands mid-stroke.
- So each hand goes to the free slot whose last wrist position is **nearest** to its wrist now. `min(..., key=...)` picks the slot with the smallest distance; an empty slot counts as very far (1e9).
- Slots with no hand this frame are emptied.

```python
    def update(self, hands, mouse, now, stroke, wipe):
        self.lms = self.match(hands)
        self.infos = [classify(lm) if lm is not None else None for lm in self.lms]
        self.speed, self.wiping = 0.0, False
        for info, pen, wiper in zip(self.infos, self.pens, self.wipers):
            if info is not None and info["fist"] and not pen.down:
                self.wiping |= wiper.update(info["palm"], 1.6 * info["width"], wipe) > 0
                pen.update(None, now, stroke)
                continue
            wiper.update(None, 0, None)
            pen.update(info, now, stroke)
            self.speed = max(self.speed, pen.speed)
```
- Classify each hand.
- **A fist** (and the pen is not mid-stroke) wipes at the palm with a radius of 1.6 hand-widths, and the pen gets "no hand".
  - `|=` means "or-equals": `wiping` becomes True if any hand wiped.
  - `continue` skips to the next hand.
- **Not a fist:** reset the wiper and update the pen. `stroke` and `wipe` are functions from the App (see `app.py`), so this file never needs to know about modes or fog.

```python
        if mouse is not None:
            self.mouse_pen.update(pinch_at(mouse), now, stroke)
            self.speed = max(self.speed, self.mouse_pen.speed)
        elif self.mouse_pen.down:
            self.mouse_pen.lift()
        self.drawing = any(p.down for p in self.pens) or self.mouse_pen.down
```
- The mouse is a third pen: always "pinched" while the button is held, and lifted when it is not.
- `drawing` is True if any pen is down.

```python
    def held(self, name, active, secs, now):
        if not active:
            self.holds.pop(name, None)
            return False
        start = self.holds.setdefault(name, now)
        if start is not None and now - start >= secs:
            self.holds[name] = None
            return True
        return False
```
- **Hold a gesture to trigger it,** so a gesture that flashes past for one frame does nothing.
  - **Not active:** forget it.
  - **Active:** `setdefault` stores the start time the first time and returns it after that.
  - **Held long enough:** return True **once**, and store None so it does not fire again until you let go and do it again.

```python
    def lift_all(self):
        for p in self.pens:
            p.lift()
```

---

## fog.py: the fist wipe

```python
def soft_kernel(radius, power=1.6):
    r = max(1, int(radius))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1].astype(np.float32)
    return np.clip(1 - np.sqrt(xx ** 2 + yy ** 2) / r, 0, 1) ** power
```
- A round brush: 1 in the middle, falling to 0 at the edge (`1 - distance / radius`).
- `** power` makes the fall-off curved, so the centre wipes hard and the edge softly, like a sleeve.

```python
    def _kernel(self, kind, r):
        key = (kind, r)
        if key not in self._kernels:
            self._kernels[key] = soft_kernel(r, 1.4) if kind == "stamp" else gauss_kernel(r)
        return self._kernels[key]
```
- The phase 2 cache, now for two kinds of kernel: `"stamp"` for wipes and `"blob"` for breath. `bloom` now gets its blobs from here.

```python
    def stamp(self, center, radius, strength=WIPE_STAMP):
        def fn(region, kk, sl):
            region *= 1 - strength * kk
        apply_kernel(self.a, self._kernel("stamp", max(2, int(radius * GS))), center[0] * GS, center[1] * GS, fn)
```
- **One sleeve stamp:** multiply the fog under the brush by `1 - 0.34 x brush`. That removes up to 34% in the middle and nothing at the edge.
- It is the same `apply_kernel` as breath, with a function that *removes* instead of adds.

---

## effects.py: the star and the bevel

```python
def draw_star(img, p, r):
    x, y = int(p[0]), int(p[1])
    g = 2 * r + 2
    x0, y0, x1, y1 = max(0, x - g), max(0, y - g), min(W, x + g + 1), min(H, y + g + 1)
    if x0 < x1 and y0 < y1:
        roi = img[y0:y1, x0:x1]
        glow = roi.copy()
        cv2.circle(glow, (x - x0, y - y0), r * 2, (255, 240, 200), -1, cv2.LINE_AA)
        cv2.addWeighted(glow, 0.25, roi, 0.75, 0, dst=roi)
```
- **A soft glow:** draw a solid circle on a copy of the small square around the point, then mix 25% of it back. Only that square is touched (blending the whole picture for one small glow would waste time).
- `(x - x0, y - y0)`: the point's position inside the small square.

```python
    for ang in (0, 90, 45, 135):
        L = r if ang % 90 == 0 else r // 2
        dx, dy = int(L * math.cos(math.radians(ang))), int(L * math.sin(math.radians(ang)))
        cv2.line(img, (x - dx, y - dy), (x + dx, y + dy), (255, 255, 255), 2, cv2.LINE_AA)
```
- **A sparkle:** 4 lines through the centre. The horizontal and vertical ones are long, the diagonals half as long. `cos` and `sin` turn an angle into a direction.

```python
class Effects:
    def apply(self, out, now, hands):
        for pen, info in zip(hands.pens, hands.infos):
            if info is not None and pen.star is not None and (pen.down or info["pinch"] < 0.5):
                draw_star(out, pen.star, 9 if pen.down else 6)
        cv2.rectangle(out, (1, 1), (W - 2, H - 2), (235, 235, 235), 2, cv2.LINE_AA)
        cv2.rectangle(out, (5, 5), (W - 6, H - 6), (60, 60, 60), 1, cv2.LINE_AA)
        return out
```
- A star appears when your fingers get close (pinch under 0.5): small while aiming, bigger when drawing. You can see where you will draw *before* you touch.
- **The bevel:** a light outer line and a dark inner line make the edge look like a mirror's cut glass.

---

## modes.py and ui.py

```python
    def wipe(self, center, radius):
        self.fog.stamp(center, radius)
```
- `FogMode` now knows what a fist wipe means: a sleeve stamp.

```python
        if not app.tracker.ok:
            msg = "HAND TRACKING OFF: MediaPipe not found. Start with run_fog_studio.bat"
            w = text_width(msg, 0.5) + 30
            blend_rect(img, W // 2 - w // 2 + 60, H - 50, W // 2 + w // 2 + 60, H - 20, (40, 40, 200), 0.85, 15)
            text(img, msg, W // 2 + 60, H - 30, 0.5, center=True, shadow=False)
```
- At the top of `draw_overlays`: if MediaPipe did not load, show a red bar every frame. **Never fail silently:** without this, people think the app is broken when it just started with the wrong Python. It is shifted 60 px right so it does not cover the brush slider.

---

## app.py: what is new

```python
        self.camera = self.tracker = self.breath = self.mode = None
        self.hands = HandInput()
        self.mouse_down, self.mouse_pos = False, None
        self.effects, self.ui = Effects(), UI(self)
```
- The tracker is made in `launch` like the camera. `HandInput` replaces phase 2's `mouse_last` and `update_mouse`.

```python
        if self.tracker is None:
            self.tracker = Tracker()
            print("Hand tracking ON (MediaPipe)" if self.tracker.ok else "Hand tracking OFF: %s\n"
                  "Fix: pip install -r requirements.txt, or start with run_fog_studio.bat" % self.tracker.error)
```
- In `launch`: start MediaPipe once, and say in the terminal whether it worked and, if not, why and how to fix it.

### update_hands

```python
        t = self.tracker
        if t.mouth is not None:
            self.mouth = lerp(self.mouth, t.mouth, 0.4)
```
- If the face was found, the breath spot moves 40% of the way to your mouth each frame. It trails you smoothly instead of snapping.

```python
        hands = self.hands
        hands.update(t.hands if t.ok else [], self.mouse_pos if self.mouse_down else None, now,
                     lambda pts: self.mode.stroke(pts, self.brush), self.mode.wipe)
        self.drawing = hands.drawing
```
- **Feed HandInput:** the tracker's hands (none if it is off), the mouse (only while held), the time, and two functions:
  - `stroke`: draw with the current brush size.
  - `wipe`: the mode's wipe.
- `lambda pts: ...` adds the brush size, since `HandInput` only passes the points.

```python
        live = [i for i in hands.infos if i is not None]
        if hands.held("palms", len(live) == 2 and all(i["open"] for i in live), 1.0, now):
            self.mode.clear()
            self.toast("both palms: cleared")
```
- `live`: the hands that are actually there.
- **Two open palms held for 1 second clears the mirror.** Two hands are needed so a wave never clears it by accident.

### step

```python
        self.tracker.submit(frame)
        self.breath_strength = self.breath.update(now)
        self.update_hands(now)
        self.mode.update(dt, now)
        out = self.effects.apply(self.mode.render(frame), now, self.hands)
```
- **Send the frame to the tracker thread.** Its answer arrives a frame or so later in `tracker.hands`, so the mirror never waits for MediaPipe.
- After rendering, the effects (star, bevel) go on top, before the UI.

```python
            for part in (self.tracker, self.breath):
                if part is not None:
                    part.stop()
```
- On exit, stop the tracker thread and the microphone.

---

## Try this

1. In `config.py`, set `PINCH_DOWN, PINCH_UP = 0.3, 0.32`. The thresholds are almost equal, so there is no hysteresis. Draw slowly: the line breaks up when your pinch hovers near 0.3.
2. Set `EASE_TARGET, EASE_BRUSH = 1.0, 1.0` (no smoothing). Lines get shaky. Try `0.2, 0.1`: very smooth, but laggy.
3. In `hands.py` `Pen.update`, replace the `if len(self.pts) >= 3:` block with just `draw([self.pts[-2], new])`. Draw a fast circle and look for corners.
4. In `classify`, print the pinch: add `print(round(pinch, 2))` before `return`. Pinch and open your fingers and watch the numbers. Move your hand nearer and further: the numbers stay the same.
5. In `HandInput.update`, change `1.6 * info["width"]` to `4 * info["width"]`. The fist becomes a huge sponge.
6. In `Wiper.update`, change `radius * 0.5` to `radius * 3`. Swipe fast: you get separate circles instead of a smooth band.
7. Add a gesture: in `App.update_hands`, add
   ```python
   if hands.held("thumbs", any(i["thumbs_up"] for i in live), 0.8, now):
       self.toast("nice!")
   ```
   (Phase 6 uses this gesture to take a photo.)
