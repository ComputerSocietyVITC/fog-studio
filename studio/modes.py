"""The four modes (navbar tabs). Each owns its own layer, updates it every frame and renders the mirror."""
import random
import time

import cv2
import numpy as np

from .config import FH, FW, GS, H, NAV_H, NEON_COLOURS, REVEAL_WORDS, W
from .fog import FogLayer, frost_render
from .gfx import blend_rect, card, rounded_rect, text, text_width


class Mode:
    """One tab. The App calls update() then render() every frame, and stroke() / wipe() when a pen or fist moves."""
    name, hint = "?", ""
    uses_fog = True  # breath puffs and the glass squeak only make sense on fog

    def __init__(self, app):
        self.app = app
        self.fog = FogLayer()
        self.mask = None  # an OpenCV mask for the debug panel (None: the panel shows the skin mask)

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
        """Return True if this mode used the key."""
        return False

    def update(self, dt, now):
        s = self.app.breath_strength
        if s > 0.02 and not self.app.drawing and self.app.frame_no % 2 == 0:
            self.fog.bloom(self.app.mouth, s)

    def render(self, frame):
        return frost_render(frame, self.fog.a)

    def nav_extra(self, ui, img, x):
        """Draw this mode's own controls starting at x; return where they end."""
        return x


class FogMode(Mode):
    name, hint = "Fog", "breathe to fog, pinch to draw, fist to wipe"

    def __init__(self, app):
        super().__init__(app)
        self.drops = []  # [x, y, speed, radius] in grid pixels
        self.refog_on = True

    def update(self, dt, now):
        super().update(dt, now)
        if self.refog_on and not self.app.drawing:
            self.fog.refog(0.004)
        self.update_drops()

    def update_drops(self):
        a = self.fog.a
        if len(self.drops) < 28 and random.random() < 0.35:
            x, y = random.randrange(4, FW - 4), random.randrange(4, int(FH * 0.6))
            if a[y, x] > 0.78:
                self.drops.append([float(x), float(y), random.uniform(0.15, 0.4), random.uniform(1.2, 2.4)])
        for d in self.drops:
            if a[min(FH - 1, int(d[1])), min(FW - 1, int(d[0]))] < 0.6 and d[2] < 0.3:
                d[2] *= 0.96  # light drops stall on clear glass
            ox, oy = d[0], d[1]
            d[2] = min(3.0, d[2] + 0.02)
            d[1] += d[2]
            d[0] = min(FW - 2.0, max(1.0, d[0] + random.uniform(-0.35, 0.35)))
            cv2.line(a, (int(ox), int(oy)), (int(d[0]), int(d[1])), 0.12, max(1, int(d[3] * 0.9)), cv2.LINE_AA)
        self.drops = [d for d in self.drops if d[1] < FH - 1 and d[2] >= 0.05]

    def render(self, frame):
        out = frost_render(frame, self.fog.a)
        for x, y, _, r in self.drops:
            c, rr = (int(x / GS), int(y / GS)), max(2, int(r / GS * 0.7))
            cv2.circle(out, c, rr, (90, 90, 90), 1, cv2.LINE_AA)
            cv2.circle(out, (c[0] - rr // 3, c[1] - rr // 3), max(1, rr // 3), (255, 255, 255), -1, cv2.LINE_AA)
        return out

    def clear(self):
        super().clear()
        self.drops.clear()

    def on_key(self, key):
        if key != ord("o"):
            return False
        self.refog_on = not self.refog_on
        self.app.toast("re-fog " + ("on" if self.refog_on else "off"))
        return True

    def nav_extra(self, ui, img, x):
        return ui.chip(img, x, "re-fog " + ("on" if self.refog_on else "off"), self.refog_on, lambda: self.on_key(ord("o")))


class NeonMode(Mode):
    name, hint, uses_fog = "Neon", "pinch to draw light; peace sign changes colour; fist erases", False

    def __init__(self, app):
        super().__init__(app)
        self.layer = np.zeros((H, W, 3), np.uint8)
        self.colour = 0

    def current_bgr(self):
        bgr = NEON_COLOURS[self.colour][1]
        if bgr is None:  # rainbow: the hue walks with time
            hsv = np.uint8([[[int(time.time() * 60) % 180, 230, 255]]])
            return tuple(int(v) for v in cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0])
        return bgr

    def set_colour(self, i):
        self.colour = i
        self.app.toast("colour: " + NEON_COLOURS[i][0])

    def on_peace(self):
        self.set_colour((self.colour + 1) % len(NEON_COLOURS))

    def stroke(self, pts, radius):
        p = np.round(np.asarray(pts, np.float32) * 16).astype(np.int32).reshape(-1, 1, 2)
        th = max(2, int(radius * 0.55))
        if len(p) == 1:
            cv2.circle(self.layer, tuple(int(v) for v in p[0, 0]), th, self.current_bgr(), -1, cv2.LINE_AA, 4)
        else:
            cv2.polylines(self.layer, [p], False, self.current_bgr(), th, cv2.LINE_AA, 4)

    def wipe(self, center, radius):
        cv2.circle(self.layer, (int(center[0]), int(center[1])), int(radius * 0.8), (0, 0, 0), -1, cv2.LINE_AA)

    def clear(self):
        self.layer[:] = 0

    clean = clear

    def update(self, dt, now):
        pass

    def render(self, frame):
        out = cv2.convertScaleAbs(frame, alpha=0.55)
        small = cv2.resize(self.layer, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
        glow = cv2.resize(cv2.convertScaleAbs(cv2.GaussianBlur(small, (0, 0), 7), alpha=2.2), (W, H))
        out = cv2.add(cv2.add(out, glow), self.layer)
        core = cv2.threshold(cv2.cvtColor(self.layer, cv2.COLOR_BGR2GRAY), 0, 70, cv2.THRESH_BINARY)[1]
        return cv2.add(out, cv2.cvtColor(core, cv2.COLOR_GRAY2BGR))

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


class RevealMode(Mode):
    name, hint = "Reveal", "a word hides under the fog: wipe it clear in 30 s (Enter starts)"
    ROUND = 30.0

    def __init__(self, app):
        super().__init__(app)
        self.words = ([app.args.word.upper()] if app.args.word else []) + list(REVEAL_WORDS)
        self.word_i = 0
        self.state, self.t0, self.revealed, self.best, self.result = "ready", 0.0, 0.0, None, ""
        self._next_check = 0.0
        self.fog = FogLayer(1.0)
        self.make_word()

    def make_word(self):
        word, font, scale, thick = self.words[self.word_i], cv2.FONT_HERSHEY_TRIPLEX, 3.2, 14
        while text_width(word, scale, thick, font) > W * 0.82:
            scale -= 0.2
        self.word_layer = np.zeros((H, W, 3), np.uint8)
        x, y = W // 2 - text_width(word, scale, thick, font) // 2, H // 2 + int(30 * scale / 3.2) + 20
        cv2.putText(self.word_layer, word, (x, y), font, scale, (255, 220, 60), thick, cv2.LINE_AA)
        self.word_mask = cv2.resize((self.word_layer.max(axis=2) > 0).astype(np.uint8), (FW, FH),
                                    interpolation=cv2.INTER_NEAREST).astype(bool)

    def start_round(self):
        self.fog = FogLayer(1.0)
        self.state, self.t0, self.revealed = "playing", time.time(), 0.0
        self.app.toast("GO! find the word", 1.2)

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

    def update(self, dt, now):
        super().update(dt, now)
        if self.state != "playing":
            return
        if now >= self._next_check:  # 4 times a second is plenty
            self._next_check = now + 0.25
            self.revealed = float(np.mean(self.fog.a[self.word_mask] < 0.35))
        if self.revealed >= 0.9:
            took = now - self.t0
            self.best = took if self.best is None else min(self.best, took)
            self.state, self.result = "done", "FOUND in %.1f s" % took
            self.app.toast("you found it!", 2.0)
        elif now - self.t0 >= self.ROUND:
            self.state, self.result = "done", "time up: %d%% revealed" % int(self.revealed * 100)

    def render(self, frame):
        # the frost is made from the plain frame, so the word never shows through the fog
        out = frost_render(frame, self.fog.a, max_alpha=1.0, under=cv2.add(frame, self.word_layer))
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

    def nav_extra(self, ui, img, x):
        return ui.chip(img, x, "word: " + self.words[self.word_i], False, lambda: self.on_key(ord("w")))


class MotionMode(Mode):
    name, hint = "Motion", "OpenCV optical flow: anything that moves wipes ( , . change the threshold )"

    def __init__(self, app):
        super().__init__(app)
        self.fog = FogLayer(0.85)
        self.kernel = np.ones((3, 3), np.uint8)  # for morphology: removes single-pixel noise
        self.prev, self.flow, self.min_speed = None, None, 2.0

    def enter(self):
        self.prev = None

    def update(self, dt, now):
        super().update(dt, now)
        t0 = time.perf_counter()
        small = cv2.resize(self.app.frame, (320, 180), interpolation=cv2.INTER_AREA)  # flow is slow: work small
        gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        if self.prev is not None:
            self.flow = cv2.calcOpticalFlowFarneback(self.prev, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            speed, _ = cv2.cartToPolar(self.flow[..., 0], self.flow[..., 1])
            mask = cv2.morphologyEx((speed > self.min_speed).astype(np.uint8) * 255, cv2.MORPH_OPEN, self.kernel)
            self.mask = cv2.dilate(mask, self.kernel, iterations=2)
            self.fog.a *= 1 - 0.6 * cv2.GaussianBlur(cv2.resize(self.mask, (FW, FH)), (0, 0), 2).astype(np.float32) / 255
        self.prev = gray
        self.fog.refog(0.006)  # the glass closes back over you when you stand still
        self.app.cv_ms = (time.perf_counter() - t0) * 1000

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


MODES = [FogMode, NeonMode, RevealMode, MotionMode]
