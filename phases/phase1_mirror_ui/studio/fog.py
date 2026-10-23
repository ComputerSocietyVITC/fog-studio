"""The fog: a grid of how much fog is on each part of the glass, and the frosted look drawn from it."""
import cv2
import numpy as np

from .config import FH, FOG_START, FROST_BLUR, FROST_BRIGHT, FROST_TINT, FROST_WHITE, FW, GS, H, W

TINT_SMALL = np.full((H // 4, W // 4, 3), FROST_TINT, np.uint8)  # the frost's white, at quarter size


class FogLayer:
    """How much fog is on each part of the glass: 0 is clear glass, 1 is thick fog."""

    def __init__(self, start=FOG_START):
        self.start = start
        self.a = np.full((FH, FW), start, np.float32)

    def erase_path(self, pts, radius, strength=1.0):
        """Wipe along a path (render pixels)."""
        mask = np.zeros((FH, FW), np.uint8)
        p = np.round(np.asarray(pts, np.float32) * GS * 16).astype(np.int32).reshape(-1, 1, 2)  # 4 bits subpixel
        th = max(1, int(round(2 * radius * GS)))
        if len(p) == 1:
            cv2.circle(mask, tuple(int(v) for v in p[0, 0]), max(1, th // 2), 255, -1, cv2.LINE_AA, 4)
        else:
            cv2.polylines(mask, [p], False, 255, th, cv2.LINE_AA, 4)
        m = cv2.GaussianBlur(mask, (0, 0), 1.2).astype(np.float32) * (strength / 255.0)
        self.a *= 1 - m

    def reset(self):
        self.a[:] = self.start


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
