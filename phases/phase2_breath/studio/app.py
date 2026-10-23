"""The App: owns the camera, the microphone and the mode, handles keys and mouse, and runs one frame at a time."""
import argparse
import time

import cv2
import numpy as np

from .audio import Breath
from .camera import Camera
from .config import BRUSH_MAX, BRUSH_MIN, H, W, WINDOW
from .modes import FogMode
from .ui import UI


class App:
    def __init__(self, args):
        self.args = args
        self.state, self.error = "start", ""  # start, run or error
        self.fullscreen = not args.windowed
        self.camera = self.breath = self.mode = None  # made on the first launch()
        self.frame = np.zeros((H, W, 3), np.uint8)
        self.frame_no = 0
        self.mouse_down, self.mouse_pos, self.mouse_last = False, None, None
        self.drawing, self.brush = False, 15
        self.mouth = (W / 2, H * 0.62)  # where breath lands (phase 3 makes it follow your face)
        self.breath_strength = 0.0
        self.ui = UI(self)
        self.toasts = []  # (message, until)
        self.show_help = False
        self.keys = {  # the mode's keys (o) are tried first
            chr(27): self.to_start_screen, " ": lambda: self.breath.hold_space(time.time()),
            "c": lambda: self.mode.clear(), "x": self.clean_glass, "h": lambda: self.toggle("show_help"),
            "f": self.toggle_fullscreen, "[": lambda: self.set_brush(self.brush - 2), "]": lambda: self.set_brush(self.brush + 2),
            "-": lambda: self.scale_breath(1.25, "more"), "=": lambda: self.scale_breath(0.8, "less"),
        }

    # ---------------------------------------------------------- lifecycle
    def launch(self):
        if self.camera is not None:
            self.camera.release()
        self.camera = Camera(self.args.camera)
        first = self.camera.read()
        if first is None:
            self.camera.release()
            self.state, self.error = "error", "The camera was refused or is busy."
            return
        self.frame = first
        if self.breath is None:
            self.breath = Breath()
            if not self.breath.ok:
                self.toast("no microphone: hold space to fog", 3)
        if self.mode is None:
            self.mode = FogMode(self)
        self.state = "run"
        self.toast(self.mode.hint, 3)

    # ---------------------------------------------------------- actions (keys and buttons)
    def toast(self, msg, secs=1.6):
        self.toasts = [(m, t) for m, t in self.toasts if m != msg][-2:] + [(msg, time.time() + secs)]

    def toggle(self, attr):
        setattr(self, attr, not getattr(self, attr))

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN if self.fullscreen else cv2.WINDOW_NORMAL)

    def to_start_screen(self):
        self.state = "start"

    def clean_glass(self):
        self.mode.clean()
        self.toast("glass cleaned: no more ghosts")

    def set_brush(self, size):
        self.brush = int(min(BRUSH_MAX, max(BRUSH_MIN, size)))

    def scale_breath(self, factor, word):
        self.breath.trigger *= factor
        self.toast("breath needs %s: %.4f" % (word, self.breath.trigger))

    def show_breath(self):
        self.toast("breath needs %.4f   (- needs more, = needs less)" % self.breath.trigger, 2.5)

    # ---------------------------------------------------------- input
    def on_mouse(self, event, x, y, flags, param):
        self.ui.mouse = (x, y)
        if self.state != "run":
            if event == cv2.EVENT_LBUTTONDOWN:
                self.launch()
        elif event == cv2.EVENT_LBUTTONDOWN:
            if self.ui.in_slider(x, y):
                self.ui.dragging = True
                self.ui.slider_set(x)
            elif not self.ui.click(x, y):
                self.mouse_down, self.mouse_pos = True, (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            self.mouse_down, self.ui.dragging = False, False
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.ui.dragging:
                self.ui.slider_set(x)
            elif self.mouse_down:
                self.mouse_pos = (x, y)

    def on_key(self, key, now):
        """Returns False to quit."""
        if key < 0:
            return True
        k = key & 0xFF
        if self.state != "run":
            if k in (13, 10, 32):
                self.launch()
            return k not in (27, ord("q"))
        if k != 32:
            self.breath.keystroke(now)
        if k == ord("q"):
            return False
        if not self.mode.on_key(k) and chr(k) in self.keys:
            self.keys[chr(k)]()
        return True

    # ---------------------------------------------------------- per frame
    def update_mouse(self):
        """While the button is down, wipe along the path the mouse moved since the last frame."""
        if self.mouse_down and self.mouse_pos is not None:
            self.mode.stroke([self.mouse_last or self.mouse_pos, self.mouse_pos], self.brush)
            self.mouse_last = self.mouse_pos
        else:
            self.mouse_last = None
        self.drawing = self.mouse_down

    def step(self, now, dt):
        """One frame of the mirror: read, sense, update, render, decorate. Returns the image to show."""
        frame = self.camera.read()
        if frame is None:
            self.state, self.error = "error", "The camera stopped sending frames."
            return None
        self.frame = frame
        self.frame_no += 1
        self.breath_strength = self.breath.update(now)
        self.update_mouse()
        self.mode.update(dt, now)
        out = self.mode.render(frame)
        self.ui.draw(out)
        self.ui.draw_overlays(out, now)
        return out

    def run(self):
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
        if self.fullscreen:
            cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        else:
            cv2.resizeWindow(WINDOW, W, H)
        cv2.setMouseCallback(WINDOW, self.on_mouse)
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
        finally:
            if self.breath is not None:
                self.breath.stop()
            if self.camera is not None:
                self.camera.release()
            cv2.destroyAllWindows()


def window_open():
    try:
        return cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) >= 1
    except cv2.error:
        return False


def parse_args():
    parser = argparse.ArgumentParser(description="Fog Studio: breathe on the mirror, draw, wipe.")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--windowed", action="store_true", help="start in a window instead of full screen")
    return parser.parse_args()
