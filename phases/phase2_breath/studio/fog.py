"""The fog: a grid of how much fog is on each part of the glass, and the frosted look drawn from it."""
import math
import random

import cv2
import numpy as np

from .config import (BLOB_ALPHA, BREATH_BLOBS, BREATH_REACH, FH, FOG_START, FROST_BLUR, FROST_BRIGHT, FROST_TINT,
                     FROST_WHITE, FW, GS, H, W)

TINT_SMALL = np.full((H // 4, W // 4, 3), FROST_TINT, np.uint8)  # the frost's white, at quarter size


def gauss_kernel(radius):
    """A gaussian blob whose own blur is 0.6 of its radius."""
    r = max(2, int(radius))
    yy, xx = np.mgrid[-2 * r:2 * r + 1, -2 * r:2 * r + 1].astype(np.float32)
    return np.exp(-(xx ** 2 + yy ** 2) / (2 * (0.6 * r) ** 2))


def apply_kernel(grid, kernel, cx, cy, fn):
    """Run fn(region, kernel_part, slices) on the part of the grid the kernel covers (clipped at the edges)."""
    kh, kw = kernel.shape
    x0, y0 = int(round(cx)) - kw // 2, int(round(cy)) - kh // 2
    gx0, gy0, gx1, gy1 = max(0, x0), max(0, y0), min(grid.shape[1], x0 + kw), min(grid.shape[0], y0 + kh)
    if gx0 >= gx1 or gy0 >= gy1:
        return
    sl = (slice(gy0, gy1), slice(gx0, gx1))
    fn(grid[sl], kernel[gy0 - y0:gy1 - y0, gx0 - x0:gx1 - x0], sl)


class FogLayer:
    """How much fog is on each part of the glass (0 clear, 1 thick), plus finger grease for ghost writing."""

    def __init__(self, start=FOG_START):
        self.start = start
        self.a = np.full((FH, FW), start, np.float32)
        self.grease = np.zeros((FH, FW), np.float32)
        self._kernels = {}  # radius: gaussian blob, made once and reused

    def erase_path(self, pts, radius, strength=1.0):
        """Wipe along a path (render pixels), leaving grease behind."""
        mask = np.zeros((FH, FW), np.uint8)
        p = np.round(np.asarray(pts, np.float32) * GS * 16).astype(np.int32).reshape(-1, 1, 2)  # 4 bits subpixel
        th = max(1, int(round(2 * radius * GS)))
        if len(p) == 1:
            cv2.circle(mask, tuple(int(v) for v in p[0, 0]), max(1, th // 2), 255, -1, cv2.LINE_AA, 4)
        else:
            cv2.polylines(mask, [p], False, 255, th, cv2.LINE_AA, 4)
        m = cv2.GaussianBlur(mask, (0, 0), 1.2).astype(np.float32) * (strength / 255.0)
        self.a *= 1 - m
        np.maximum(self.grease, m, out=self.grease)

    def bloom(self, mouth, strength):
        """A breath: soft blobs below the mouth, wider than tall, overlapping into density."""
        reach = BREATH_REACH * H * GS
        cx, cy = mouth[0] * GS, mouth[1] * GS + 0.08 * reach  # breath falls a little
        a, g = BLOB_ALPHA * strength, self.grease

        def fn(region, kk, sl):
            add = a * kk * (1 - 0.7 * g[sl])  # fog condenses less on finger grease, so old drawings come back
            region += (1 - region) * add  # "over" compositing: never past 1
        for _ in range(BREATH_BLOBS):
            ang, rad = random.uniform(0, 2 * math.pi), reach * 0.55 * math.sqrt(random.random())
            r = int(reach * random.uniform(0.16, 0.3))
            if r not in self._kernels:
                self._kernels[r] = gauss_kernel(r)
            apply_kernel(self.a, self._kernels[r], cx + math.cos(ang) * rad * 1.45, cy + math.sin(ang) * rad, fn)

    def refog(self, rate):
        """Clear glass slowly fogs back up to the starting level (slower where there is grease)."""
        low = self.a < self.start
        self.a[low] += (self.start - self.a[low]) * rate * (1 - 0.7 * self.grease[low])

    def reset(self, keep_grease=True):
        self.a[:] = self.start
        if not keep_grease:
            self.grease[:] = 0


def frost_layer(frame):
    """The frost: the camera blurred, brightened and mixed with a little tinted white (made at quarter size)."""
    small = cv2.resize(frame, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), FROST_BLUR / 4)
    small = cv2.addWeighted(small, FROST_BRIGHT * (1 - FROST_WHITE), TINT_SMALL, FROST_WHITE, 0)  # saturates at 255
    return cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR)


def frost_render(frame, fog_grid, max_alpha=0.97):
    """The camera, with the frost shown wherever there is fog: alpha blending done by OpenCV."""
    a = cv2.resize(np.clip(fog_grid, 0, 1) * max_alpha, (W // 2, H // 2), interpolation=cv2.INTER_LINEAR)
    a = cv2.resize(cv2.GaussianBlur(a, (0, 0), 1), (W, H), interpolation=cv2.INTER_LINEAR)
    return cv2.blendLinear(frame, frost_layer(frame), 1 - a, a)
