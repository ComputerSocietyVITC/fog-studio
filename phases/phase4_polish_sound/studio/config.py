"""Sizes, tuning values and colours shared by every part of Fog Studio."""
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # this phase's folder
# the hand-tracking models: in this folder's models/, or in the shared fog-studio/models/
MODELS = next((p for p in (os.path.join(HERE, "models"), os.path.join(HERE, "..", "..", "models"))
               if os.path.isdir(p)), os.path.join(HERE, "models"))
WINDOW = "Fog Studio"

W, H = 960, 540  # render size (16:9); the window stretches it to the screen
FW, FH = 480, 270  # fog and grease grids (half size: 4 times less work)
GS = FW / W  # render pixels to grid pixels
NAV_H = 58  # navbar height

# Feel (tuned values, in render pixels)
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
