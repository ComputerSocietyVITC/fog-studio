"""Sizes, tuning values and colours shared by every part of Fog Studio."""
WINDOW = "Fog Studio"

W, H = 960, 540  # render size (16:9); the window stretches it to the screen
FW, FH = 480, 270  # the fog grid (half size: 4 times less work)
GS = FW / W  # render pixels to grid pixels
NAV_H = 58  # navbar height

# Feel (tuned values, in render pixels)
FOG_START = 0.55
FROST_BLUR, FROST_BRIGHT, FROST_WHITE = 18, 1.18, 0.62
FROST_TINT = (231, 238, 242)  # rgb(242, 238, 231) as BGR
BRUSH_MIN, BRUSH_MAX = 7, 38
