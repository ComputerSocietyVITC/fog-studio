"""The debug overlay (d): hand skeletons, timings, the breath graph, and a live panel of what OpenCV sees (v)."""
import cv2
import numpy as np

from .config import H, NAV_H, W
from .gfx import blend_rect, text

HAND_LINKS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10), (10, 11),
              (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (17, 18), (18, 19), (19, 20), (0, 17)]
SKIN_LO, SKIN_HI = np.array([0, 135, 85]), np.array([255, 180, 135])  # skin colour in YCrCb (workshop)
VIEWS = ["mask", "hull + defects", "optical flow"]


def skin_mask(small):
    return cv2.inRange(cv2.cvtColor(small, cv2.COLOR_BGR2YCrCb), SKIN_LO, SKIN_HI)


class DebugView:
    def __init__(self):
        self.on, self.view, self._prev = False, 0, None

    def toggle(self):
        self.on = not self.on

    def next_view(self):
        self.view = (self.view + 1) % len(VIEWS)

    def draw(self, img, app):
        for info, lm in zip(app.hands.infos, app.hands.lms):
            if lm is None:
                continue
            for a, b in HAND_LINKS:
                cv2.line(img, tuple(int(v) for v in lm[a]), tuple(int(v) for v in lm[b]), (120, 255, 120), 2, cv2.LINE_AA)
            for p in lm:
                cv2.circle(img, (int(p[0]), int(p[1])), 3, (255, 255, 255), -1, cv2.LINE_AA)
            tags = [k for k in ("fist", "thumbs_up", "peace", "open") if info[k]]
            text(img, "pinch %.2f %s" % (info["pinch"], " ".join(tags)), int(lm[0][0]) - 40, int(lm[0][1]) + 24, 0.5)
        cv2.circle(img, (int(app.mouth[0]), int(app.mouth[1])), 6, (255, 180, 80), 2, cv2.LINE_AA)
        t = app.tracker
        text(img, "%.0f fps   mediapipe %.0f ms   opencv %.1f ms" % (app.fps, t.ms, app.cv_ms), 16, NAV_H + 84, 0.5)
        if t.ok:
            n = len(t.hands)
            status = "hand tracking ON: %d hand%s seen" % (n, "" if n == 1 else "s") + ("   (%s)" % t.error if t.error else "")
        else:
            status = "hand tracking OFF: " + t.error
        text(img, status[:110], 16, NAV_H + 188, 0.45, (150, 255, 150) if t.ok else (120, 140, 255))
        self.draw_breath(img, app)
        panel = self.panel(app.frame, app.mode)
        ph, pw = panel.shape[:2]
        x, y = W - pw - 16, H - ph - 70
        img[y:y + ph, x:x + pw] = panel
        cv2.rectangle(img, (x, y), (x + pw, y + ph), (240, 240, 240), 1)
        text(img, VIEWS[self.view] + "   (v: next view)", x, y - 8, 0.45)

    @staticmethod
    def draw_breath(img, app):
        """Mic level (white) against the trigger line (orange)."""
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

    def panel(self, frame, mode):
        """What OpenCV sees: the mode's mask (or skin), the hull and defects of the skin, or the optical flow."""
        small = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
        if self.view == 0:
            return cv2.cvtColor(mode.mask if mode.mask is not None else skin_mask(small), cv2.COLOR_GRAY2BGR)
        if self.view == 1:
            return self.hull_view(small)
        flow = getattr(mode, "flow", None)
        if flow is None:
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            prev, self._prev = self._prev, gray
            if prev is None:
                return np.zeros((180, 320, 3), np.uint8)
            flow = cv2.calcOpticalFlowFarneback(prev, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        speed, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        hsv = np.zeros((flow.shape[0], flow.shape[1], 3), np.uint8)  # colour = direction, brightness = speed
        hsv[..., 0] = (ang * 90 / np.pi).astype(np.uint8)
        hsv[..., 1] = 255
        hsv[..., 2] = np.clip(speed * 30, 0, 255).astype(np.uint8)
        return cv2.resize(cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR), (320, 180))

    @staticmethod
    def hull_view(small):
        """The biggest skin blob, its convex hull, and the deep defects (the gaps between fingers)."""
        mask = cv2.morphologyEx(skin_mask(small), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        out = (small // 2).copy()
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return out
        c = max(contours, key=cv2.contourArea)
        if cv2.contourArea(c) <= 300:
            return out
        cv2.drawContours(out, [c], -1, (120, 255, 120), 1)
        cv2.polylines(out, [cv2.convexHull(c)], True, (0, 220, 255), 1)
        try:
            defects = cv2.convexityDefects(c, cv2.convexHull(c, returnPoints=False))
        except cv2.error:
            defects = None
        for _, _, f, d in ([] if defects is None else defects.reshape(-1, 4)):
            if d / 256 > 8:
                cv2.circle(out, tuple(int(v) for v in c[f][0]), 3, (60, 60, 255), -1)
        return out
