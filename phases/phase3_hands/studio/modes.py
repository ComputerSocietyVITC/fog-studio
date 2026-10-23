"""What the mirror does. Phase 3: fog you breathe onto, draw in with a pinch and wipe with a fist."""
from .fog import FogLayer, frost_render


class FogMode:
    name, hint = "Fog", "breathe to fog, pinch to draw, fist to wipe"

    def __init__(self, app):
        self.app = app
        self.fog = FogLayer()
        self.refog_on = True

    def stroke(self, pts, radius):
        self.fog.erase_path(pts, radius)

    def wipe(self, center, radius):
        self.fog.stamp(center, radius)

    def clear(self):
        self.fog.reset()

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

    def render(self, frame):
        return frost_render(frame, self.fog.a)
