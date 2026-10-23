"""Sizes, tuning values and colours shared by every part of Fog Studio."""
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GALLERY = os.path.join(HERE, "gallery")
MODELS = os.path.join(HERE, "models")
WINDOW = "Fog Studio"

W, H = 960, 540  # render size (16:9); the window stretches it to the screen
FW, FH = 480, 270  # fog and grease grids (half size: 4 times less work)
GS = FW / W  # render pixels to grid pixels
NAV_H = 58

FOG_START = 0.55
FROST_BLUR, FROST_BRIGHT, FROST_WHITE = 18, 1.18, 0.62
FROST_TINT = (231, 238, 242)  # rgb(242, 238, 231) as BGR
BREATH_BLOBS, BLOB_ALPHA = 12, 0.36
BREATH_REACH = 0.43  # of the short edge
PINCH_DOWN, PINCH_UP = 0.22, 0.38
EASE_TARGET, EASE_BRUSH, EASE_STAR = 0.45, 0.22, 0.55
TREMOR = 0.0006 * W
WIPE_STAMP = 0.34
BRUSH_MIN, BRUSH_MAX = 7, 38

NEON_COLOURS = [("cyan", (255, 230, 40)), ("pink", (180, 60, 255)), ("lime", (60, 255, 120)),
                ("gold", (40, 200, 255)), ("violet", (255, 90, 160)), ("rainbow", None)]
REVEAL_WORDS = ["IEEE CS", "VIT CHENNAI", "FOG MIRROR", "HELLO!"]
