"""What the mirror does. Phase 1 has one mode: fog that the mouse wipes away."""
from .fog import FogLayer, frost_render


class FogMode:
    name, hint = "Fog", "drag the mouse to wipe the fog"

    def __init__(self, app):
        self.app = app
        self.fog = FogLayer()

    def stroke(self, pts, radius):
        self.fog.erase_path(pts, radius)

    def clear(self):
        self.fog.reset()

    def update(self, dt, now):
        pass  # phase 2 adds breath and re-fog here

    def render(self, frame):
        return frost_render(frame, self.fog.a)
