# Phase 1: the mirror and its UI

Run it: `python run.py --windowed` (from this folder, with your venv active).

**What you get:**
- A start screen, then your webcam as a mirror covered in fog.
- Drag the mouse to wipe the fog.
- A navbar with a "clear (c)" button and a help button (`?` or `h`).
- A brush slider (or `[` `]`) and little messages ("toasts").
- `f` toggles full screen, `esc` goes back to the start screen and `q` quits.

Every file is new in this phase, so this guide covers all of them. Read them in this order:

`run.py` > `config.py` > `camera.py` > `fog.py` > `modes.py` > `gfx.py` > `ui.py` > `app.py`

---

## run.py: the starter

```python
from studio.app import App, parse_args


def main():
    App(parse_args()).run()


if __name__ == "__main__":
    main()
```

- `from studio.app import App, parse_args`: `studio` is the folder next to this file. Python treats a folder with an `__init__.py` as a *package*, so `studio.app` means the file `studio/app.py`.
- `App(parse_args())`: reads the command line options (like `--windowed`) and makes the App with them.
- `.run()`: opens the window and loops until you quit.
- `if __name__ == "__main__":`: true only when you run this file directly. It stays false if another file imports it, so importing never starts the app by accident.

---

## studio/config.py: the numbers

```python
WINDOW = "Fog Studio"
```
- The window's title. OpenCV finds a window by its title, so every `cv2.imshow(WINDOW, ...)` draws into the same window.

```python
W, H = 960, 540
FW, FH = 480, 270
GS = FW / W
NAV_H = 58
```
- `W, H`: everything is drawn at 960 x 540 (16:9). The window then stretches it to your screen. A fixed size means every position in the code (like "the slider is 52 px above the bottom") works on every laptop.
- `FW, FH`: the fog is stored as a grid of 480 x 270 numbers, half the width and half the height of the picture. That is 4 times fewer numbers, so the fog maths is 4 times faster. Fog is blurry anyway, so you cannot see the difference.
- `GS = FW / W` = 0.5: multiply a screen position by `GS` to get its position in the fog grid.
- `NAV_H`: the navbar is 58 px tall.

```python
FOG_START = 0.55
FROST_BLUR, FROST_BRIGHT, FROST_WHITE = 18, 1.18, 0.62
FROST_TINT = (231, 238, 242)
BRUSH_MIN, BRUSH_MAX = 7, 38
```
- `FOG_START`: how foggy the mirror is at the start and after a clear. 0 is clear glass, 1 is solid fog.
- **How the frost looks:**
  - `FROST_BLUR`: how blurry you look through the fog.
  - `FROST_BRIGHT`: how much brighter the fog makes the picture.
  - `FROST_WHITE`: how much white is mixed in, from 0 to 1.
- `FROST_TINT`: the colour of that white. OpenCV stores colours as **B, G, R** (blue first), not R, G, B. So this is a warm, slightly cream white.
- `BRUSH_MIN, BRUSH_MAX`: the smallest and biggest brush, in pixels.

---

## studio/camera.py: the webcam

```python
class Camera:
    def __init__(self, index):
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened() and os.name == "nt":
            self.cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
```
- `cv2.VideoCapture(index)` opens camera number `index`. 0 is the built-in one and 1 is usually a USB webcam.
- `isOpened()` is False if that failed. On Windows (`os.name == "nt"`) we try again with DirectShow (`CAP_DSHOW`), an older Windows camera system that some webcams need.

```python
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
```
- `FOURCC MJPG`: asks the webcam to send compressed (JPEG) frames. Many webcams only manage about 10 frames a second at 720p without compression, but 30 with it.
- `FRAME_WIDTH / HEIGHT`: asks for 1280 x 720. The camera may give something else; `read()` copes with any size.
- `BUFFERSIZE 1`: keep only the newest frame. Otherwise old frames queue up and the mirror lags behind you.
- A camera that does not support one of these settings just ignores it.

```python
    def read(self):
        ok, frame = self.cap.read()
        if not ok or frame is None:
            return None
        frame = cv2.flip(frame, 1)
```
- `cap.read()` returns two things: did it work (`ok`), and the picture (`frame`). A frame is a NumPy array of shape `(height, width, 3)`: one B, G, R number (0 to 255) for every pixel.
- `return None` tells the App the camera stopped.
- `cv2.flip(frame, 1)` flips left and right (1 = around the vertical axis). Now it behaves like a mirror: raise your right hand and the hand on the right side of the screen goes up.

```python
        h, w = frame.shape[:2]
        if w / h > W / H:
            nw = int(h * W / H)
            frame = frame[:, (w - nw) // 2:(w - nw) // 2 + nw]
        else:
            nh = int(w * H / W)
            frame = frame[(h - nh) // 2:(h - nh) // 2 + nh]
        return cv2.resize(frame, (W, H), interpolation=cv2.INTER_AREA)
```
- `frame.shape[:2]` is (height, width).
- **Wider than 16:9:** keep the full height and work out the 16:9 width `nw`. Then cut equal strips off the left and right. `frame[:, a:b]` means "all rows, columns a to b". This is a *slice*: no copying, just a view.
- **Taller than 16:9** (old 4:3 webcams): cut the top and bottom instead.
- `cv2.resize(..., (W, H))`: scale to exactly 960 x 540. Note OpenCV wants the size as **(width, height)**, while `shape` is (height, width). `INTER_AREA` is the best way to shrink a picture: it averages pixels, so nothing shimmers.

```python
    def release(self):
        self.cap.release()
```
- Gives the camera back to Windows, so other apps (or the next launch) can use it.

---

## studio/fog.py: the fog and the frosted glass

The big idea: **the fog is just a grid of numbers.** `fog.a[y, x]` says how foggy that spot is (0 clear, 1 thick). Wiping makes the numbers smaller. Every frame, we turn the numbers into a picture.

```python
TINT_SMALL = np.full((H // 4, W // 4, 3), FROST_TINT, np.uint8)
```
- A small picture (240 x 135) filled with the frost colour. It is made once, when the file loads, so we never rebuild it every frame. `np.uint8` means whole numbers from 0 to 255: the normal pixel type.

### class FogLayer

```python
    def __init__(self, start=FOG_START):
        self.start = start
        self.a = np.full((FH, FW), start, np.float32)
```
- `self.a` is the grid: 270 rows x 480 columns, every value `start`. `float32` lets it hold numbers like 0.37.

```python
    def erase_path(self, pts, radius, strength=1.0):
        mask = np.zeros((FH, FW), np.uint8)
```
- A black picture the size of the grid. We will draw the stroke on it in white, then use it to remove fog.

```python
        p = np.round(np.asarray(pts, np.float32) * GS * 16).astype(np.int32).reshape(-1, 1, 2)
```
Read it from the inside out:
- `np.asarray(pts, np.float32)`: the list of (x, y) points as an array.
- `* GS`: screen position to grid position (halve it).
- `* 16` and `np.round(...).astype(np.int32)`: OpenCV draws with whole numbers. But if we multiply by 16 and later tell OpenCV `shift=4` (2 to the power 4 = 16), it divides back by 16 itself. So positions keep 1/16 of a pixel of precision, and slow strokes look smooth instead of jumping pixel to pixel.
- `.reshape(-1, 1, 2)`: the shape `polylines` wants (N points, 1, x and y).

```python
        th = max(1, int(round(2 * radius * GS)))
        if len(p) == 1:
            cv2.circle(mask, tuple(int(v) for v in p[0, 0]), max(1, th // 2), 255, -1, cv2.LINE_AA, 4)
        else:
            cv2.polylines(mask, [p], False, 255, th, cv2.LINE_AA, 4)
```
- `th`: line thickness in grid pixels (the brush is a radius, so the diameter is 2 x radius).
- **One point** (you just clicked): draw a filled dot. Here `-1` thickness means filled, and `255` is white.
- **Several points:** draw the line through them. `False` means "do not join the last point back to the first".
- `cv2.LINE_AA` is anti-aliasing (soft edges). The last `4` is the `shift` from above.

```python
        m = cv2.GaussianBlur(mask, (0, 0), 1.2).astype(np.float32) * (strength / 255.0)
        self.a *= 1 - m
```
- `GaussianBlur`: softens the stroke's edges by 1.2 pixels, like a finger's edge on glass. `(0, 0)` means "work out the blur size from the 1.2".
- `* (strength / 255.0)`: white (255) becomes `strength` (1.0), and black stays 0. Now `m` is "how much to wipe" at every spot.
- `self.a *= 1 - m`: where `m` is 1, the fog is multiplied by 0 (gone). Where `m` is 0, it is multiplied by 1 (unchanged). Multiplying instead of subtracting means fog can never go below 0.
- This line works on all 129,600 numbers at once. That is NumPy: no Python loop, so it is fast.

```python
    def reset(self):
        self.a[:] = self.start
```
- `[:]` means "fill the existing grid". It changes every value without making a new array.

### frost_layer(frame): what fogged glass looks like

```python
    small = cv2.resize(frame, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), FROST_BLUR / 4)
    small = cv2.addWeighted(small, FROST_BRIGHT * (1 - FROST_WHITE), TINT_SMALL, FROST_WHITE, 0)
    return cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR)
```
- **Line 1:** shrink the camera picture to a quarter (240 x 135). Blurring a small picture is 16 times less work, and the result is blurry anyway.
- **Line 2:** blur it. The picture is 4 times smaller, so a blur of 18 / 4 = 4.5 here looks like a blur of 18 on the full picture.
- **Line 3:** `addWeighted(A, a, B, b, 0)` computes `A*a + B*b` for every pixel.
  - With the numbers in config, that is camera x 0.45 + cream white x 0.62.
  - The result: a pale, milky version of you. Values over 255 are cut to 255 ("saturate").
- **Line 4:** scale back up to 960 x 540. `INTER_LINEAR` blends neighbours smoothly.

### frost_render(frame, fog_grid, max_alpha): fog on top of the camera

```python
    a = cv2.resize(np.clip(fog_grid, 0, 1) * max_alpha, (W // 2, H // 2), interpolation=cv2.INTER_LINEAR)
    a = cv2.resize(cv2.GaussianBlur(a, (0, 0), 1), (W, H), interpolation=cv2.INTER_LINEAR)
    return cv2.blendLinear(frame, frost_layer(frame), 1 - a, a)
```
- `np.clip(fog_grid, 0, 1)`: keep every value between 0 and 1.
- `* max_alpha` (0.97): even the thickest fog lets 3% of the camera through, like real fog.
- **Line 1:** makes the alpha half size. With the default grid it already is; this keeps it correct if you change `FW, FH`.
- **Line 2:** blur 1 pixel so stroke edges are soft, then scale to full size. `a` is now one number per screen pixel: how much frost to show there.
- `cv2.blendLinear(A, B, wA, wB)` gives, for every pixel, `(A*wA + B*wB) / (wA + wB)`.
  - Our weights are `1 - a` and `a`, which add up to 1.
  - So where the fog is 0 you see the camera, and where it is 1 you see the frost. Halfway is a mix.
  - This one OpenCV call is the whole "fog" effect.

---

## studio/modes.py: what the mirror does

```python
class FogMode:
    name, hint = "Fog", "drag the mouse to wipe the fog"

    def __init__(self, app):
        self.app = app
        self.fog = FogLayer()
```
- A *mode* owns its fog and decides what drawing and rendering mean. Phase 1 has one mode, and phase 5 adds three more with the same methods.
- `name, hint = ...`: two class attributes in one line. `hint` is shown as a toast when the mode starts.
- `self.app = app`: the mode keeps a link to the App, so later it can read things like the breath strength.

```python
    def stroke(self, pts, radius):
        self.fog.erase_path(pts, radius)

    def clear(self):
        self.fog.reset()

    def update(self, dt, now):
        pass

    def render(self, frame):
        return frost_render(frame, self.fog.a)
```
- `stroke`: the App calls it when you draw. Here drawing wipes fog.
- `clear`: fogs the whole mirror again.
- `update`: called every frame; empty for now. `dt` is the seconds since the last frame and `now` is the clock.
- `render`: turns the camera frame into the mirror picture.

---

## studio/gfx.py: drawing helpers

### blend_rect: a see-through box

```python
def blend_rect(img, x0, y0, x1, y1, color, alpha, radius=0):
    x0, y0, x1, y1 = max(0, int(x0)), max(0, int(y0)), min(img.shape[1], int(x1)), min(img.shape[0], int(y1))
    if x0 >= x1 or y0 >= y1:
        return
    roi = img[y0:y1, x0:x1]
    over = roi.copy()
    rounded_rect(over, 0, 0, x1 - x0 - 1, y1 - y0 - 1, color, -1, radius)
    cv2.addWeighted(over, alpha, roi, 1 - alpha, 0, dst=roi)
```
- **Line 1:** keeps the box inside the picture, so a box half off-screen does not crash.
- **Line 2:** if nothing is left (the box is fully off-screen), stop.
- `roi = img[y0:y1, x0:x1]`: the "region of interest". A slice is a **view**: changing `roi` changes `img`.
- `over = roi.copy()`: a real copy, with a solid rounded box drawn on it.
- `addWeighted(over, alpha, roi, 1 - alpha, 0, dst=roi)`: mixes the solid box into the original, `alpha` of the way. Writing the result into `roi` writes it straight into `img`. Only the small box area is touched, which is fast.

### rounded_rect: a box with round corners

```python
    r = int(min(radius, (x1 - x0) // 2, (y1 - y0) // 2))
    if r <= 0:
        cv2.rectangle(img, (x0, y0), (x1, y1), color, thickness, cv2.LINE_AA)
        return
    corners = (((x0 + r, y0 + r), 180), ((x1 - r, y0 + r), 270), ((x0 + r, y1 - r), 90), ((x1 - r, y1 - r), 0))
```
- `r`: the corner radius. It can never be more than half the box, or the corners would overlap.
- No radius: just a normal rectangle.
- `corners`: the centre of each corner circle, with the angle where that corner's quarter-arc starts.
  - Order: top left, top right, bottom left, bottom right.
  - OpenCV angles go clockwise from the right (0), so 90 points down.

```python
    if thickness < 0:
        cv2.rectangle(img, (x0 + r, y0), (x1 - r, y1), color, -1)
        cv2.rectangle(img, (x0, y0 + r), (x1, y1 - r), color, -1)
        for c, _ in corners:
            cv2.circle(img, c, r, color, -1, cv2.LINE_AA)
        return
```
- **Filled** (thickness -1): a tall box, a wide box, and four filled circles in the corners. Together they make a rounded box.

```python
    for a, b in (((x0 + r, y0), (x1 - r, y0)), ((x0 + r, y1), (x1 - r, y1)),
                 ((x0, y0 + r), (x0, y1 - r)), ((x1, y0 + r), (x1, y1 - r))):
        cv2.line(img, a, b, color, thickness, cv2.LINE_AA)
    for c, ang in corners:
        cv2.ellipse(img, c, (r, r), ang, 0, 90, color, thickness, cv2.LINE_AA)
```
- **Outline only:**
  - Four straight lines (top, bottom, left, right), each stopping `r` short of the corner.
  - Four quarter circles. `ellipse(img, centre, (r, r), rotation, start angle, end angle, ...)` draws an arc from 0 to 90 degrees, turned by `ang`.

### text and text_width

```python
def text(img, s, x, y, scale=0.55, color=(255, 255, 255), thick=1, font=cv2.FONT_HERSHEY_DUPLEX, center=False, shadow=True):
    if center:
        x = x - text_width(s, scale, thick, font) / 2
    if shadow:
        cv2.putText(img, s, (int(x) + 1, int(y) + 1), font, scale, (0, 0, 0), thick, cv2.LINE_AA)
    cv2.putText(img, s, (int(x), int(y)), font, scale, color, thick, cv2.LINE_AA)
```
- `center=True`: move left by half the text's width so the text is centred on `x`.
- `shadow`: draw the text in black 1 px down and right first. White text stays readable on a white fog.
- `cv2.putText(img, text, (x, y), font, scale, colour, thickness, ...)`: `(x, y)` is the **bottom left** of the text, not the top.

```python
def text_width(s, scale=0.55, thick=1, font=cv2.FONT_HERSHEY_DUPLEX):
    return cv2.getTextSize(s, font, scale, thick)[0][0]
```
- `getTextSize` returns `((width, height), baseline)`, and `[0][0]` is the width in pixels. We need it to size buttons to fit their label.

---

## studio/ui.py: everything drawn on top

**How buttons work in OpenCV:** OpenCV has no buttons, only pictures and mouse clicks. So every frame, the UI draws each button *and* writes down its rectangle and what it does in `self.buttons`. When you click, `click()` looks for a rectangle under the mouse and runs its function.

```python
HELP_ROWS = [("drag the mouse", "wipe the fog"), ...]
```
- The help panel's rows: (what you do, what happens). It is just data, so adding a row adds a line to the panel.

### UI.__init__

```python
        self.app = app
        self.buttons = []
        self.mouse = (0, 0)
        self.slider_rect = (18, H - 52, 250, H - 16)
        self.dragging = False
```
- `buttons`: rebuilt every frame as `(rect, function)` pairs.
- `mouse`: where the pointer is, used to light up a button you hover.
- `slider_rect`: the brush slider's box (left, top, right, bottom), bottom left of the screen.
- `dragging`: True while you hold the slider's knob.

### Input helpers

```python
    def add_button(self, rect, fn):
        self.buttons.append((rect, fn))

    def hover(self, rect):
        x, y = self.mouse
        return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]
```
- `hover`: is the mouse inside this rectangle? Python lets you chain comparisons: `a <= x <= b`.

```python
    def click(self, x, y):
        for rect, fn in self.buttons:
            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                fn()
                return True
        return y < NAV_H
```
- Finds the first button under the click, runs it (`fn()`), and says "yes, the UI used this click".
- If no button was hit but the click was on the navbar, it still returns True, so clicking the navbar never wipes fog.

```python
    def in_slider(self, x, y):
        x0, y0, x1, y1 = self.slider_rect
        return x0 <= x <= x1 and y0 <= y <= y1

    def slider_set(self, x):
        x0, _, x1, _ = self.slider_rect
        f = min(1.0, max(0.0, (x - (x0 + 70)) / (x1 - 18 - (x0 + 70))))
        self.app.brush = int(round(BRUSH_MIN + f * (BRUSH_MAX - BRUSH_MIN)))
```
- The slider's track runs from `x0 + 70` (after the word "brush") to `x1 - 18`.
- `f`: how far along the track the mouse is, from 0 to 1, clamped so dragging past the end stays at the end.
- The brush size becomes the same fraction of the way from 7 to 38.

### chip: a pill-shaped button

```python
        w = text_width(label, 0.48) + 24
        rect = (x, NAV_H // 2 - 14, x + w, NAV_H // 2 + 14)
        fill = (255, 255, 255) if active else (70, 70, 70)
        blend_rect(img, *rect, fill, 0.9 if active else (0.6 if self.hover(rect) else 0.4), 14)
        text(img, label, x + 12, NAV_H // 2 + 5, 0.48, (30, 30, 30) if active else (240, 240, 240), shadow=False)
        self.add_button(rect, fn)
        return x + w + 8
```
- **Width:** the label's width plus 12 px of padding on each side.
- **Height:** 28 px, centred in the navbar (`NAV_H // 2` is the middle; `//` divides and drops the fraction).
- **Look:**
  - Active chips are almost solid white with dark text.
  - Others are see-through grey, a bit stronger (0.6) when the mouse is over them.
  - `*rect` unpacks the 4 numbers into 4 arguments.
- `add_button`: remembers the rectangle and the function.
- `return x + w + 8`: where the next chip should start, so chips line up without you working out positions.

### icon_button: a round icon button

```python
        rect = (x, NAV_H // 2 - 17, x + 34, NAV_H // 2 + 17)
        blend_rect(img, *rect, (255, 255, 255) if active else (80, 80, 80), 0.85 if active else (0.6 if self.hover(rect) else 0.35), 17)
        c = (x + 17, NAV_H // 2)
        ink = (40, 40, 40) if active else (245, 245, 245)
        if kind == "help":
            text(img, "?", c[0] - 5, c[1] + 6, 0.6, ink, shadow=False)
        self.add_button(rect, fn)
        return x - 42
```
- A 34 x 34 box with radius 17 is a circle.
- `c` is its centre, and `ink` is the icon colour (dark on an active white button, light otherwise).
- `kind` picks which icon to draw. Phase 1 has only "help" (a question mark). Later phases add more `elif kind == ...` branches.
- `return x - 42`: icons line up from the right edge towards the left.

### draw: the navbar

```python
        self.buttons = []
        frosted = cv2.GaussianBlur(cv2.resize(img[:NAV_H], (W // 4, NAV_H // 4 + 1)), (0, 0), 3)
        img[:NAV_H] = (cv2.resize(frosted, (W, NAV_H)).astype(np.float32) * 0.45 + 18).astype(np.uint8)
        cv2.line(img, (0, NAV_H), (W, NAV_H), (200, 200, 200), 1, cv2.LINE_AA)
```
- `self.buttons = []`: forget last frame's buttons. They are added again as we draw.
- **Frosted glass bar:**
  1. Take the top 58 rows of the picture (`img[:NAV_H]`), shrink them, and blur them.
  2. Scale them back, darken them (`* 0.45`), and lift them slightly (`+ 18`).
  3. Write the result back into the top rows.
  
  This is the same "blur what is behind" trick as phone UIs.
- Then a thin light line along the bottom edge of the bar.

```python
        cv2.circle(img, (24, NAV_H // 2 + 3), 8, (255, 230, 200), -1, cv2.LINE_AA)
        cv2.fillPoly(img, [np.array([[17, NAV_H // 2], [24, NAV_H // 2 - 13], [31, NAV_H // 2]], np.int32)], (255, 230, 200), cv2.LINE_AA)
        text(img, "Fog Studio", 40, NAV_H // 2 + 2, 0.62, (255, 255, 255), 1, shadow=False)
        text(img, "on-device", 41, NAV_H // 2 + 17, 0.35, (170, 230, 170), shadow=False)
```
- **The logo:** a circle plus a triangle on top (`fillPoly` fills a shape given its corner points) make a water drop.
- Then the name, and "on-device" in small green text.

```python
        self.chip(img, 150, "clear (c)", False, lambda: app.mode.clear())
        self.icon_button(img, W - 44, "help", lambda: app.toggle("show_help"), app.show_help)
        self.draw_slider(img)
```
- `lambda: app.mode.clear()`: a tiny function with no name. It is not run now; it is stored and run when the button is clicked.
- The help button is active (white) while the help panel is open.

### draw_slider

```python
        blend_rect(img, x0, y0, x1, y1, (235, 235, 235), 0.22, 18)
        rounded_rect(img, x0, y0, x1, y1, (245, 245, 245), 1, 18)
        text(img, "brush", x0 + 14, y1 - 12, 0.5, (255, 255, 255), shadow=False)
        tx0, tx1, ty = x0 + 70, x1 - 18, (y0 + y1) // 2
        kx = int(tx0 + (self.app.brush - BRUSH_MIN) / (BRUSH_MAX - BRUSH_MIN) * (tx1 - tx0))
        cv2.line(img, (tx0, ty), (tx1, ty), (200, 200, 200), 2, cv2.LINE_AA)
        cv2.line(img, (tx0, ty), (kx, ty), (255, 255, 255), 3, cv2.LINE_AA)
        cv2.circle(img, (kx, ty), 8, (255, 255, 255), -1, cv2.LINE_AA)
```
- A faint pill with a thin border, and the word "brush".
- `kx`: the knob's x position. It is `slider_set` backwards: brush size to a position on the track.
- A grey track, a white filled part up to the knob, and the knob itself.

### draw_overlays: toasts and help

```python
        app.toasts = [(m, t) for m, t in app.toasts if t > now]
        for i, (msg, until) in enumerate([] if app.show_help else app.toasts[-3:]):
            w, y, a = text_width(msg, 0.55) + 36, NAV_H + 74 + 38 * i, min(1.0, (until - now) * 2)
            blend_rect(img, W // 2 - w // 2, y, W // 2 + w // 2, y + 30, (20, 20, 20), 0.6 * a, 15)
            if a > 0.3:
                text(img, msg, W // 2, y + 21, 0.55, center=True, shadow=False)
        if app.show_help:
            draw_help(img)
```
- **Line 1:** a *list comprehension*. It keeps only the toasts whose end time `t` is still in the future.
- The loop shows the newest 3 (`[-3:]`), stacked 38 px apart, and none while help is open.
- `a` = remaining seconds x 2, capped at 1. So a toast is solid until its last half second, then fades out.
- The text is hidden once it is mostly faded, so it does not float on an invisible box.

### start_screen

```python
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        img = np.float32([60, 40, 30]) * (1 - g) + np.float32([110, 90, 70]) * g + np.zeros((H, W, 3), np.float32)
```
- `np.linspace(0, 1, H)`: 540 numbers from 0 (top) to 1 (bottom).
- `[:, None, None]` makes the shape (540, 1, 1). NumPy *broadcasts*: a (540, 1, 1) array times a colour (3,) gives (540, 1, 3).
- Adding a (540, 960, 3) zero picture stretches it across the width.
- The result is a vertical gradient from dark navy (B 60, G 40, R 30) to a lighter blue-grey.

```python
        fog = np.zeros((H // 4, W // 4), np.float32)
        for i in range(9):
            x = (W // 4) * (0.5 + 0.45 * math.sin(now * 0.2 + i * 1.7))
            y = (H // 4) * (0.5 + 0.4 * math.cos(now * 0.15 + i * 2.3))
            cv2.circle(fog, (int(x), int(y)), 30 + 4 * i, 0.35, -1)
        fog = cv2.resize(cv2.GaussianBlur(fog, (0, 0), 12), (W, H))[..., None]
        img = np.clip(img * (1 - fog) + 235 * fog, 0, 255).astype(np.uint8)
```
- **Nine fog blobs** that drift slowly. `sin` and `cos` of the time go smoothly back and forth, and `i * 1.7` gives each blob a different starting point.
- They are drawn small, blurred a lot, and scaled up: soft clouds.
- `[..., None]` adds a last axis so `fog` (540, 960, 1) can multiply a colour picture (540, 960, 3).
- The mix: where `fog` is 0 you see the gradient, and where it is high you see near-white (235).

```python
        text(img, "Fog Studio", W // 2, H // 2 - 70, 2.2, (255, 255, 255), 3, cv2.FONT_HERSHEY_TRIPLEX, center=True)
        ...
        if self.app.state == "error":
            text(img, self.app.error, ...)
        rect = (W // 2 - 90, H // 2 + 85, W // 2 + 90, H // 2 + 135)
        blend_rect(img, *rect, (255, 255, 255), 0.95 if self.hover(rect) else 0.8, 25)
        text(img, "Try again" if self.app.state == "error" else "Start", ...)
```
- The title, the tagline, and the camera error if there was one.
- The Start button gets brighter when hovered. It is not in `self.buttons`, because on the start screen *any* click starts (see `App.on_mouse`).

### draw_help

```python
    w, h = 720, 60 + 30 * len(HELP_ROWS)
    x0, y0 = W // 2 - w // 2, H // 2 - h // 2 + 20
    blend_rect(img, x0, y0, x0 + w, y0 + h, (20, 20, 20), 0.82, 16)
    rounded_rect(img, x0, y0, x0 + w, y0 + h, (230, 230, 230), 1, 16)
    text(img, "how to use the mirror", x0 + 24, y0 + 36, 0.75, (255, 255, 255), 1)
    for i, (a, b) in enumerate(HELP_ROWS):
        y = y0 + 70 + 30 * i
        text(img, a, x0 + 24, y, 0.5, (255, 220, 150), shadow=False)
        text(img, b, x0 + 330, y, 0.5, (235, 235, 235), shadow=False)
```
- The panel's height grows with the number of rows (30 px each). It is centred, with a dark see-through box, a thin border and a title.
- `enumerate` gives each row's number `i`, used to move each row down 30 px.
- Two columns: the gesture or key in light orange, and what it does in white.

---

## studio/app.py: the App

The App is the boss. It owns the camera and the mode, turns mouse and keys into actions, and runs the main loop.

### __init__

```python
        self.args = args
        self.state, self.error = "start", ""
        self.fullscreen = not args.windowed
        self.camera = self.mode = None
        self.frame = np.zeros((H, W, 3), np.uint8)
        self.mouse_down, self.mouse_pos, self.mouse_last = False, None, None
        self.brush = 15
        self.ui = UI(self)
        self.toasts = []
        self.show_help = False
```
- `state` is one of three screens:
  - `"start"`: the start screen.
  - `"run"`: the mirror.
  - `"error"`: the start screen with the camera error.
- `self.camera = self.mode = None`: they are made later, in `launch()`, so the camera light only turns on when you press Start.
- `self.frame`: a black picture until the camera sends one.
- **The mouse:** is the button held, where it is now, and where it was last frame.
- `UI(self)`: the UI gets the App, so it can read `app.brush`, `app.toasts` and the rest.

```python
        self.keys = {
            chr(27): self.to_start_screen, "c": lambda: self.mode.clear(), "h": lambda: self.toggle("show_help"),
            "f": self.toggle_fullscreen, "[": lambda: self.set_brush(self.brush - 2), "]": lambda: self.set_brush(self.brush + 2),
        }
```
- **The key table:** a dictionary from a key's character to the function it runs.
  - `chr(27)` is the Escape key's character.
  - `self.to_start_screen` (no brackets) is the method itself, stored to be called later.
- Adding a key is one entry here, not a new `if`.

### launch: press Start

```python
        if self.camera is not None:
            self.camera.release()
        self.camera = Camera(self.args.camera)
        first = self.camera.read()
        if first is None:
            self.camera.release()
            self.state, self.error = "error", "The camera was refused or is busy."
            return
        self.frame = first
        if self.mode is None:
            self.mode = FogMode(self)
        self.state = "run"
        self.toast(self.mode.hint, 3)
```
- Releases an old camera first (after "Try again"), then opens the camera and reads one frame to check it works.
- **No frame:** show the error on the start screen instead of crashing. This is usually another app using the camera, or the Windows camera privacy setting.
- The mode is made once. Going back to the start screen and in again keeps your drawing.
- Then switch to the mirror and show the mode's hint for 3 seconds.

### Actions

```python
    def toast(self, msg, secs=1.6):
        self.toasts = [(m, t) for m, t in self.toasts if m != msg][-2:] + [(msg, time.time() + secs)]
```
- Removes any older copy of the same message (so pressing a key 5 times shows it once), keeps the last 2, and adds this one with its end time.

```python
    def toggle(self, attr):
        setattr(self, attr, not getattr(self, attr))
```
- `toggle("show_help")` flips `self.show_help` between True and False. `getattr` and `setattr` read and write an attribute by its name as text.

```python
    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN if self.fullscreen else cv2.WINDOW_NORMAL)

    def to_start_screen(self):
        self.state = "start"

    def set_brush(self, size):
        self.brush = int(min(BRUSH_MAX, max(BRUSH_MIN, size)))
```
- Full screen on or off, back to the start screen, and the brush size clamped between 7 and 38 (`min(max(...))` is the usual "clamp").

### on_mouse: OpenCV calls this for every mouse event

```python
    def on_mouse(self, event, x, y, flags, param):
        self.ui.mouse = (x, y)
        if self.state != "run":
            if event == cv2.EVENT_LBUTTONDOWN:
                self.launch()
```
- OpenCV calls this function itself, because `run()` registered it with `setMouseCallback`. `x, y` are already in our 960 x 540 picture's pixels, even in full screen.
- On the start screen, any left click starts.

```python
        elif event == cv2.EVENT_LBUTTONDOWN:
            if self.ui.in_slider(x, y):
                self.ui.dragging = True
                self.ui.slider_set(x)
            elif not self.ui.click(x, y):
                self.mouse_down, self.mouse_pos = True, (x, y)
```
- **Left button pressed:**
  - On the slider, start dragging it.
  - On a button, the button runs.
  - Anywhere else, start drawing.

```python
        elif event == cv2.EVENT_LBUTTONUP:
            self.mouse_down, self.ui.dragging = False, False
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.ui.dragging:
                self.ui.slider_set(x)
            elif self.mouse_down:
                self.mouse_pos = (x, y)
```
- **Released:** stop both drawing and dragging.
- **Moved:** move the slider, or remember the new pen position. The actual wiping happens once per frame in `update_mouse`, not here.

### on_key

```python
        if key < 0:
            return True
        k = key & 0xFF
        if self.state != "run":
            if k in (13, 10, 32):
                self.launch()
            return k not in (27, ord("q"))
        if k == ord("q"):
            return False
        if chr(k) in self.keys:
            self.keys[chr(k)]()
        return True
```
- `cv2.waitKey` gives -1 when no key was pressed.
- `& 0xFF` keeps the lowest 8 bits, the plain key code. Some systems add extra bits.
- **On the start screen:** Enter (13 or 10) or space (32) starts, and Escape or `q` quits (by returning False).
- **In the mirror:** `q` quits. Any key in the table runs its function: `self.keys[chr(k)]` looks it up, and `()` calls it.

### update_mouse

```python
        if self.mouse_down and self.mouse_pos is not None:
            self.mode.stroke([self.mouse_last or self.mouse_pos, self.mouse_pos], self.brush)
            self.mouse_last = self.mouse_pos
        else:
            self.mouse_last = None
```
- Each frame, wipe a line from where the mouse was last frame to where it is now. Fast moves still give a solid line, not dots.
- `self.mouse_last or self.mouse_pos`: on the first frame there is no last position (None), so the line is just a dot.

### step: one frame

```python
        frame = self.camera.read()
        if frame is None:
            self.state, self.error = "error", "The camera stopped sending frames."
            return None
        self.frame = frame
        self.update_mouse()
        self.mode.update(dt, now)
        out = self.mode.render(frame)
        self.ui.draw(out)
        self.ui.draw_overlays(out, now)
        return out
```
The heart of the app. In order:
1. Read the camera; if it stopped, go to the error screen.
2. Apply the mouse.
3. Let the mode update.
4. Render the mirror.
5. Draw the navbar and slider on top.
6. Draw toasts and help on top of that.
7. Return the finished picture.

### run: the main loop

```python
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
        if self.fullscreen:
            cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        else:
            cv2.resizeWindow(WINDOW, W, H)
        cv2.setMouseCallback(WINDOW, self.on_mouse)
```
- `WINDOW_NORMAL` makes a window you can resize, and `KEEPRATIO` keeps 16:9 when you do. `|` combines the two flags.
- Full screen or a 960 x 540 window, then "send mouse events to `self.on_mouse`".

```python
        last = time.time()
        try:
            while True:
                now = time.time()
                dt, last = min(0.1, now - last), now
                running = self.state == "run"
                out = self.step(now, dt) if running else self.ui.start_screen(now)
                if out is not None:
                    cv2.imshow(WINDOW, out)
                if not self.on_key(cv2.waitKey(1 if running else 30), now) or not window_open():
                    break
```
- `dt`: the seconds since the last frame, capped at 0.1 so a hiccup does not make things jump.
- Make the mirror picture, or the start screen, and show it.
- `cv2.waitKey(ms)` does two jobs. It waits up to `ms` milliseconds for a key, and it **lets the window draw and handle the mouse**. Without it the window freezes.
  - In the mirror we wait only 1 ms, because the camera already sets the pace.
  - On the start screen we wait 30 ms to save power.
- Stop when `on_key` says quit, or when you closed the window with its X.

```python
        finally:
            if self.camera is not None:
                self.camera.release()
            cv2.destroyAllWindows()
```
- `finally` runs even if the code crashes, so the camera is always given back and the window always closes.

```python
def window_open():
    try:
        return cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) >= 1
    except cv2.error:
        return False
```
- After you click the window's X, its "visible" property drops below 1 (or reading it fails). Either way the window is gone.

```python
def parse_args():
    parser = argparse.ArgumentParser(description="Fog Studio: breathe on the mirror, draw, wipe.")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--windowed", action="store_true", help="start in a window instead of full screen")
    return parser.parse_args()
```
- `argparse` reads the command line.
  - `--camera 1` becomes `args.camera == 1`.
  - `--windowed` becomes `args.windowed == True`. `store_true` means "a flag with no value".
- `python run.py --help` prints these options.

---

## Try this

1. In `config.py`, set `FOG_START = 0.95`. The mirror starts almost white. Try `0.2` too.
2. Set `FROST_WHITE = 0.2`, then `0.9`. Watch the fog go from "blurry glass" to "white paint".
3. In `fog.py`, change the blur in `erase_path` from `1.2` to `6`. Strokes get very soft edges.
4. In `erase_path`, change `self.a *= 1 - m` to `self.a *= 1 - 0.3 * m`. Now one pass only thins the fog, like a dry cloth. Go over the same spot again.
5. In `config.py`, set `FW, FH = 120, 68`. The fog grid is tiny; draw and look at the blocky stroke edges. That is why the grid is half size and not smaller.
6. In `ui.py`, add a second chip after the clear button. Note that `chip` returns the next x:
   ```python
   x = self.chip(img, 150, "clear (c)", False, lambda: app.mode.clear())
   self.chip(img, x, "help", app.show_help, lambda: app.toggle("show_help"))
   ```
7. In `app.py`, add a key to the table: `"b": lambda: self.set_brush(38),` and press `b`.
8. In `camera.py`, delete the `cv2.flip` line. Raise your right hand: it is not a mirror any more.
