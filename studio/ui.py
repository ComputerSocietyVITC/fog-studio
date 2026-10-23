"""Everything drawn on top of the mirror: navbar, mode sub-bar, brush slider, toasts, help, start screen."""
import math
import time

import cv2
import numpy as np

from .config import BRUSH_MAX, BRUSH_MIN, H, NAV_H, W
from .gfx import blend_rect, rounded_rect, text, text_width

HELP_ROWS = [("pinch thumb + index", "draw (index finger out to start)"),
             ("fist and swipe", "wipe a wide area, like your sleeve"),
             ("pinch with both hands", "two pens at once"),
             ("thumbs up (hold)", "3-2-1 polaroid photo"),
             ("peace sign (hold)", "next neon colour"),
             ("both palms open (hold)", "clear everything"),
             ("breathe 'haaa' / hold space", "fog the mirror"),
             ("1 to 4 or click a tab", "switch mode"),
             ("c  x  s  p", "clear, clean ghosts, save, photo"),
             ("d  v  g  m  f", "debug, debug view, gallery, sound, full screen"),
             ("[ ]  - =  , .  w  o", "brush, breath, motion, reveal word, re-fog"),
             ("esc   q", "start screen, quit")]


class UI:
    def __init__(self, app):
        self.app = app
        self.buttons = []  # (rect, fn) for everything clickable drawn this frame
        self.mouse = (0, 0)
        self.slider_rect = (18, H - 52, 250, H - 16)
        self.dragging = False
        self.flash = 0.0

    def add_button(self, rect, fn):
        self.buttons.append((rect, fn))

    def hover(self, rect):
        x, y = self.mouse
        return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]

    def click(self, x, y):
        """Run the button under (x, y). True if the click belongs to the UI (a button or the navbar)."""
        for rect, fn in self.buttons:
            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                fn()
                return True
        return y < NAV_H

    def in_slider(self, x, y):
        x0, y0, x1, y1 = self.slider_rect
        return x0 <= x <= x1 and y0 <= y <= y1

    def slider_set(self, x):
        x0, _, x1, _ = self.slider_rect
        f = min(1.0, max(0.0, (x - (x0 + 70)) / (x1 - 18 - (x0 + 70))))
        self.app.brush = int(round(BRUSH_MIN + f * (BRUSH_MAX - BRUSH_MIN)))

    def chip(self, img, x, label, active, fn):
        """A pill button; returns where the next one starts."""
        w = text_width(label, 0.48) + 24
        rect = (x, NAV_H // 2 - 14, x + w, NAV_H // 2 + 14)
        fill = (255, 255, 255) if active else (70, 70, 70)
        blend_rect(img, *rect, fill, 0.9 if active else (0.6 if self.hover(rect) else 0.4), 14)
        text(img, label, x + 12, NAV_H // 2 + 5, 0.48, (30, 30, 30) if active else (240, 240, 240), shadow=False)
        self.add_button(rect, fn)
        return x + w + 8

    def icon_button(self, img, x, kind, fn, active=False):
        """A round icon button; returns where the next one (to the left) goes."""
        rect = (x, NAV_H // 2 - 17, x + 34, NAV_H // 2 + 17)
        blend_rect(img, *rect, (255, 255, 255) if active else (80, 80, 80), 0.85 if active else (0.6 if self.hover(rect) else 0.35), 17)
        c = (x + 17, NAV_H // 2)
        ink = (40, 40, 40) if active else (245, 245, 245)
        if kind == "shot":
            cv2.rectangle(img, (c[0] - 9, c[1] - 5), (c[0] + 9, c[1] + 7), ink, 1, cv2.LINE_AA)
            cv2.circle(img, c, 4, ink, 1, cv2.LINE_AA)
            cv2.rectangle(img, (c[0] - 4, c[1] - 8), (c[0] + 3, c[1] - 5), ink, -1)
            lvl = min(1.0, max(self.app.breath_strength, self.app.breath.meter))
            cv2.ellipse(img, c, (16, 16), -90, 0, 360 * lvl, (255, 220, 120), 2, cv2.LINE_AA)
        elif kind == "debug":
            text(img, "</>", c[0] - 13, c[1] + 5, 0.45, ink, shadow=False)
        elif kind == "gallery":
            for dx in (-6, 2):
                for dy in (-6, 2):
                    cv2.rectangle(img, (c[0] + dx, c[1] + dy), (c[0] + dx + 4, c[1] + dy + 4), ink, -1)
        elif kind == "help":
            text(img, "?", c[0] - 5, c[1] + 6, 0.6, ink, shadow=False)
        elif kind == "sound":
            pts = (np.array([[-8, -3], [-4, -3], [1, -8], [1, 8], [-4, 3], [-8, 3]]) + c).astype(np.int32)
            cv2.fillPoly(img, [pts], ink, cv2.LINE_AA)
            if self.app.sfx.on:
                cv2.ellipse(img, (c[0] + 2, c[1]), (7, 7), 0, -40, 40, ink, 1, cv2.LINE_AA)
            else:
                cv2.line(img, (c[0] + 4, c[1] - 5), (c[0] + 10, c[1] + 5), (80, 80, 255), 2, cv2.LINE_AA)
        self.add_button(rect, fn)
        return x - 42

    def draw(self, img):
        """Navbar, the mode's sub-bar and the brush slider."""
        app = self.app
        self.buttons = []
        frosted = cv2.GaussianBlur(cv2.resize(img[:NAV_H], (W // 4, NAV_H // 4 + 1)), (0, 0), 3)
        img[:NAV_H] = (cv2.resize(frosted, (W, NAV_H)).astype(np.float32) * 0.45 + 18).astype(np.uint8)
        cv2.line(img, (0, NAV_H), (W, NAV_H), (200, 200, 200), 1, cv2.LINE_AA)
        cv2.circle(img, (24, NAV_H // 2 + 3), 8, (255, 230, 200), -1, cv2.LINE_AA)
        cv2.fillPoly(img, [np.array([[17, NAV_H // 2], [24, NAV_H // 2 - 13], [31, NAV_H // 2]], np.int32)], (255, 230, 200), cv2.LINE_AA)
        text(img, "Fog Studio", 40, NAV_H // 2 + 2, 0.62, (255, 255, 255), 1, shadow=False)
        text(img, "on-device", 41, NAV_H // 2 + 17, 0.35, (170, 230, 170), shadow=False)
        x = 150
        for i, mode in enumerate(app.modes):
            x = self.chip(img, x, "%d %s" % (i + 1, mode.name), i == app.mode_i, lambda i=i: app.set_mode(i))
        self.draw_subbar(img)
        rx = W - 44
        for kind, fn, active in (("help", lambda: app.toggle("show_help"), app.show_help),
                                 ("gallery", lambda: app.toggle("show_gallery"), app.show_gallery),
                                 ("debug", app.debugger.toggle, app.debugger.on),
                                 ("sound", app.toggle_sound, False),
                                 ("shot", app.booth_photo, app.countdown is not None)):
            rx = self.icon_button(img, rx, kind, fn, active)
        self.draw_slider(img)

    def draw_subbar(self, img):
        """The mode's own controls, in a frosted pill under the navbar. Drawn once to measure, then for real."""
        y0, mouse, before = NAV_H + 6, self.mouse, len(self.buttons)
        self.mouse = (mouse[0], mouse[1] - y0)  # so hover works inside the strip
        end = self.app.mode.nav_extra(self, img[y0:y0 + NAV_H].copy(), 20)
        self.buttons = self.buttons[:before]
        if end > 20:
            blend_rect(img, 8, y0 + 7, end + 6, y0 + NAV_H - 7, (25, 25, 25), 0.5, 22)
            rounded_rect(img, 8, y0 + 7, end + 6, y0 + NAV_H - 7, (200, 200, 200), 1, 22)
            strip = img[y0:y0 + NAV_H].copy()
            self.app.mode.nav_extra(self, strip, 20)
            img[y0:y0 + NAV_H] = strip
            self.buttons[before:] = [((r[0], r[1] + y0, r[2], r[3] + y0), fn) for r, fn in self.buttons[before:]]
        self.mouse = mouse

    def draw_slider(self, img):
        x0, y0, x1, y1 = self.slider_rect
        blend_rect(img, x0, y0, x1, y1, (235, 235, 235), 0.22, 18)
        rounded_rect(img, x0, y0, x1, y1, (245, 245, 245), 1, 18)
        text(img, "brush", x0 + 14, y1 - 12, 0.5, (255, 255, 255), shadow=False)
        tx0, tx1, ty = x0 + 70, x1 - 18, (y0 + y1) // 2
        kx = int(tx0 + (self.app.brush - BRUSH_MIN) / (BRUSH_MAX - BRUSH_MIN) * (tx1 - tx0))
        cv2.line(img, (tx0, ty), (tx1, ty), (200, 200, 200), 2, cv2.LINE_AA)
        cv2.line(img, (tx0, ty), (kx, ty), (255, 255, 255), 3, cv2.LINE_AA)
        cv2.circle(img, (kx, ty), 8, (255, 255, 255), -1, cv2.LINE_AA)

    def draw_overlays(self, img, now):
        app = self.app
        if not app.tracker.ok:  # never fail silently: say it on screen, always
            msg = "HAND TRACKING OFF: MediaPipe not found. Start with run_fog_studio.bat"
            w = text_width(msg, 0.5) + 30
            blend_rect(img, W // 2 - w // 2 + 60, H - 50, W // 2 + w // 2 + 60, H - 20, (40, 40, 200), 0.85, 15)
            text(img, msg, W // 2 + 60, H - 30, 0.5, center=True, shadow=False)
        app.toasts = [(m, t) for m, t in app.toasts if t > now]
        for i, (msg, until) in enumerate([] if app.show_help else app.toasts[-3:]):
            w, y, a = text_width(msg, 0.55) + 36, NAV_H + 74 + 38 * i, min(1.0, (until - now) * 2)
            blend_rect(img, W // 2 - w // 2, y, W // 2 + w // 2, y + 30, (20, 20, 20), 0.6 * a, 15)
            if a > 0.3:
                text(img, msg, W // 2, y + 21, 0.55, center=True, shadow=False)
        if app.countdown is not None:
            left = app.countdown - now
            cv2.circle(img, (W // 2, H // 2), 70, (255, 255, 255), 3, cv2.LINE_AA)
            cv2.ellipse(img, (W // 2, H // 2), (70, 70), -90, 0, 360 * (left % 1), (120, 220, 255), 6, cv2.LINE_AA)
            text(img, str(int(math.ceil(left))), W // 2, H // 2 + 30, 3.0, (255, 255, 255), 5, center=True)
        if self.flash > 0:
            cv2.addWeighted(img, 1 - self.flash, np.full_like(img, 255), self.flash, 0, dst=img)
            self.flash = max(0.0, self.flash - 0.12)
        if app.show_gallery:
            self.draw_gallery(img)
        if app.debugger.on:
            app.debugger.draw(img, app)
        if app.show_help:
            draw_help(img)

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

    def start_screen(self, now):
        """A dark gradient with drifting fog, the title, and Start (or the camera error with Try again)."""
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        img = np.float32([60, 40, 30]) * (1 - g) + np.float32([110, 90, 70]) * g + np.zeros((H, W, 3), np.float32)
        fog = np.zeros((H // 4, W // 4), np.float32)
        for i in range(9):
            x = (W // 4) * (0.5 + 0.45 * math.sin(now * 0.2 + i * 1.7))
            y = (H // 4) * (0.5 + 0.4 * math.cos(now * 0.15 + i * 2.3))
            cv2.circle(fog, (int(x), int(y)), 30 + 4 * i, 0.35, -1)
        fog = cv2.resize(cv2.GaussianBlur(fog, (0, 0), 12), (W, H))[..., None]
        img = np.clip(img * (1 - fog) + 235 * fog, 0, 255).astype(np.uint8)
        text(img, "Fog Studio", W // 2, H // 2 - 70, 2.2, (255, 255, 255), 3, cv2.FONT_HERSHEY_TRIPLEX, center=True)
        text(img, "a bathroom mirror you can breathe on, draw on and wipe", W // 2, H // 2 - 25, 0.65, (235, 235, 235), center=True)
        if self.app.state == "error":
            text(img, self.app.error, W // 2, H // 2 + 30, 0.7, (120, 140, 255), 2, center=True)
            text(img, "close other apps using the camera, check privacy settings, or try --camera 1", W // 2, H // 2 + 60, 0.5, center=True)
        rect = (W // 2 - 90, H // 2 + 85, W // 2 + 90, H // 2 + 135)
        blend_rect(img, *rect, (255, 255, 255), 0.95 if self.hover(rect) else 0.8, 25)
        text(img, "Try again" if self.app.state == "error" else "Start", W // 2, H // 2 + 118, 0.8, (40, 40, 40), 2,
             center=True, shadow=False)
        text(img, "Everything runs on this laptop. No frames, audio or data ever leave it.", W // 2, H - 40, 0.55,
             (190, 240, 190), center=True)
        text(img, "click Start or press Enter     esc quits", W // 2, H - 16, 0.45, (200, 200, 200), center=True)
        return img


def draw_help(img):
    w, h = 720, 60 + 30 * len(HELP_ROWS)
    x0, y0 = W // 2 - w // 2, H // 2 - h // 2 + 20
    blend_rect(img, x0, y0, x0 + w, y0 + h, (20, 20, 20), 0.82, 16)
    rounded_rect(img, x0, y0, x0 + w, y0 + h, (230, 230, 230), 1, 16)
    text(img, "how to use the mirror", x0 + 24, y0 + 36, 0.75, (255, 255, 255), 1)
    for i, (a, b) in enumerate(HELP_ROWS):
        y = y0 + 70 + 30 * i
        text(img, a, x0 + 24, y, 0.5, (255, 220, 150), shadow=False)
        text(img, b, x0 + 330, y, 0.5, (235, 235, 235), shadow=False)


def polaroid(img):
    """A white frame with a thick bottom edge and the date, like an instant photo."""
    pad, bottom = 24, 90
    pic = np.full((H + pad + bottom, W + 2 * pad, 3), 248, np.uint8)
    pic[pad:pad + H, pad:pad + W] = img
    text(pic, "Fog Studio", pad, pad + H + 48, 1.0, (60, 60, 60), 1, cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, shadow=False)
    text(pic, time.strftime("%d %b %Y  %H:%M"), W + pad - 220, pad + H + 48, 0.6, (120, 120, 120), shadow=False)
    return pic
