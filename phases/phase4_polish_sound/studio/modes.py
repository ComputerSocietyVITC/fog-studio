"""What the mirror does. Phase 4: the fog mode gets droplets that run down thick fog."""
import random

import cv2

from .config import FH, FW, GS
from .fog import FogLayer, frost_render


class FogMode:
    name, hint = "Fog", "breathe to fog, pinch to draw, fist to wipe"

    def __init__(self, app):
        self.app = app
        self.fog = FogLayer()
        self.drops = []  # [x, y, speed, radius] in grid pixels
        self.refog_on = True

    def stroke(self, pts, radius):
        self.fog.erase_path(pts, radius)

    def wipe(self, center, radius):
        self.fog.stamp(center, radius)

    def clear(self):
        self.fog.reset()
        self.drops.clear()

    def clean(self):
        self.fog.reset(keep_grease=False)

    def on_key(self, key):
        """Return True if this mode used the key."""
        if key != ord("o"):
            return False
        self.refog_on = not self.refog_on
        self.app.toast("re-fog " + ("on" if self.refog_on else "off"))
        return True

    def update(self, dt, now):
        s = self.app.breath_strength
        if s > 0.02 and not self.app.drawing and self.app.frame_no % 2 == 0:
            self.fog.bloom(self.app.mouth, s)
        if self.refog_on and not self.app.drawing:
            self.fog.refog(0.004)
        self.update_drops()

    def update_drops(self):
        a = self.fog.a
        if len(self.drops) < 28 and random.random() < 0.35:
            x, y = random.randrange(4, FW - 4), random.randrange(4, int(FH * 0.6))
            if a[y, x] > 0.78:  # heavy fog grows a droplet
                self.drops.append([float(x), float(y), random.uniform(0.15, 0.4), random.uniform(1.2, 2.4)])
        for d in self.drops:
            if a[min(FH - 1, int(d[1])), min(FW - 1, int(d[0]))] < 0.6 and d[2] < 0.3:
                d[2] *= 0.96  # light drops stall on clear glass
            ox, oy = d[0], d[1]
            d[2] = min(3.0, d[2] + 0.02)
            d[1] += d[2]
            d[0] = min(FW - 2.0, max(1.0, d[0] + random.uniform(-0.35, 0.35)))
            cv2.line(a, (int(ox), int(oy)), (int(d[0]), int(d[1])), 0.12, max(1, int(d[3] * 0.9)), cv2.LINE_AA)  # its trail
        self.drops = [d for d in self.drops if d[1] < FH - 1 and d[2] >= 0.05]

    def render(self, frame):
        out = frost_render(frame, self.fog.a)
        for x, y, _, r in self.drops:  # little lenses: a dark rim and a bright glint
            c, rr = (int(x / GS), int(y / GS)), max(2, int(r / GS * 0.7))
            cv2.circle(out, c, rr, (90, 90, 90), 1, cv2.LINE_AA)
            cv2.circle(out, (c[0] - rr // 3, c[1] - rr // 3), max(1, rr // 3), (255, 255, 255), -1, cv2.LINE_AA)
        return out
