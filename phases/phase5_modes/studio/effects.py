"""What makes it look like a real mirror: dark corners, a slow light sweep, visible breath, the pinch star, the bevel."""
import math
import random

import cv2
import numpy as np

from .config import H, W

_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIGNETTE = np.ascontiguousarray(1 - 0.32 * (((_xx - W / 2) / (W / 2)) ** 2 + ((_yy - H / 2) / (H / 2)) ** 2) / 2)
VIGNETTE_INV = 1 - VIGNETTE
BLACK = np.zeros((H, W, 3), np.uint8)
SWEEP_U = cv2.resize(_xx * 0.8 + _yy * 0.6, (W // 4, H // 4))  # position along the diagonal sweep
del _yy, _xx


def draw_star(img, p, r):
    """A soft glow and a sparkle where the pinch is."""
    x, y = int(p[0]), int(p[1])
    g = 2 * r + 2  # the glow only touches this square, so only blend that
    x0, y0, x1, y1 = max(0, x - g), max(0, y - g), min(W, x + g + 1), min(H, y + g + 1)
    if x0 < x1 and y0 < y1:
        roi = img[y0:y1, x0:x1]
        glow = roi.copy()
        cv2.circle(glow, (x - x0, y - y0), r * 2, (255, 240, 200), -1, cv2.LINE_AA)
        cv2.addWeighted(glow, 0.25, roi, 0.75, 0, dst=roi)
    for ang in (0, 90, 45, 135):
        L = r if ang % 90 == 0 else r // 2
        dx, dy = int(L * math.cos(math.radians(ang))), int(L * math.sin(math.radians(ang)))
        cv2.line(img, (x - dx, y - dy), (x + dx, y + dy), (255, 255, 255), 2, cv2.LINE_AA)


class Effects:
    def __init__(self):
        self.puffs = []  # breath you can see: [x, y, vx, vy, age, radius]

    def update(self, dt, breath, mouth, on):
        if on and breath > 0.25 and len(self.puffs) < 40:
            for _ in range(2):
                self.puffs.append([mouth[0] + random.uniform(-25, 25), mouth[1] + 20,
                                   random.uniform(-25, 25), random.uniform(-45, -20), 0.0, random.uniform(8, 16)])
        for p in self.puffs:  # drift up, grow, fade
            p[0], p[1], p[4], p[5] = p[0] + p[2] * dt, p[1] + p[3] * dt, p[4] + dt, p[5] + 18 * dt
        self.puffs = [p for p in self.puffs if p[4] <= 1.3]

    def apply(self, out, now, hands):
        out = cv2.blendLinear(out, BLACK, VIGNETTE, VIGNETTE_INV)  # darker corners
        # the light sweep and the breath puffs, both made at quarter size
        pos = ((now * 90) % (W * 1.6 + 600)) - 300
        light = np.exp(-((SWEEP_U - pos) / 70.0) ** 2) * 22
        if self.puffs:
            layer = np.zeros((H // 4, W // 4), np.float32)
            for x, y, _, _, age, r in self.puffs:
                cv2.circle(layer, (int(x / 4), int(y / 4)), int(r / 4) + 1, float(0.5 * (1 - age / 1.3)), -1)
            light = light + cv2.GaussianBlur(layer, (0, 0), 3) * 140
        light = cv2.resize(np.clip(light, 0, 255).astype(np.uint8), (W, H), interpolation=cv2.INTER_LINEAR)
        out = cv2.add(out, cv2.cvtColor(light, cv2.COLOR_GRAY2BGR))
        for pen, info in zip(hands.pens, hands.infos):  # the star sits on the fingertips
            if info is not None and pen.star is not None and (pen.down or info["pinch"] < 0.5):
                draw_star(out, pen.star, 9 if pen.down else 6)
        cv2.rectangle(out, (1, 1), (W - 2, H - 2), (235, 235, 235), 2, cv2.LINE_AA)  # mirror bevel
        cv2.rectangle(out, (5, 5), (W - 6, H - 6), (60, 60, 60), 1, cv2.LINE_AA)
        return out
