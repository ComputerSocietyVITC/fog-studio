"""What makes it look like a real mirror. Phase 3 has the pinch star and the mirror's bevel (phase 4 adds the rest)."""
import math

import cv2

from .config import H, W


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
    def apply(self, out, now, hands):
        for pen, info in zip(hands.pens, hands.infos):  # the star sits on the fingertips
            if info is not None and pen.star is not None and (pen.down or info["pinch"] < 0.5):
                draw_star(out, pen.star, 9 if pen.down else 6)
        cv2.rectangle(out, (1, 1), (W - 2, H - 2), (235, 235, 235), 2, cv2.LINE_AA)  # mirror bevel
        cv2.rectangle(out, (5, 5), (W - 6, H - 6), (60, 60, 60), 1, cv2.LINE_AA)
        return out
