"""Small maths and drawing helpers used everywhere."""
import math

import cv2


def dist(a, b):
    return float(math.hypot(a[0] - b[0], a[1] - b[1]))


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def blend_rect(img, x0, y0, x1, y1, color, alpha, radius=0):
    """Draw a translucent (rounded) rectangle."""
    x0, y0, x1, y1 = max(0, int(x0)), max(0, int(y0)), min(img.shape[1], int(x1)), min(img.shape[0], int(y1))
    if x0 >= x1 or y0 >= y1:
        return
    roi = img[y0:y1, x0:x1]
    over = roi.copy()
    rounded_rect(over, 0, 0, x1 - x0 - 1, y1 - y0 - 1, color, -1, radius)
    cv2.addWeighted(over, alpha, roi, 1 - alpha, 0, dst=roi)


def rounded_rect(img, x0, y0, x1, y1, color, thickness, radius):
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    r = int(min(radius, (x1 - x0) // 2, (y1 - y0) // 2))
    if r <= 0:
        cv2.rectangle(img, (x0, y0), (x1, y1), color, thickness, cv2.LINE_AA)
        return
    corners = (((x0 + r, y0 + r), 180), ((x1 - r, y0 + r), 270), ((x0 + r, y1 - r), 90), ((x1 - r, y1 - r), 0))
    if thickness < 0:
        cv2.rectangle(img, (x0 + r, y0), (x1 - r, y1), color, -1)
        cv2.rectangle(img, (x0, y0 + r), (x1, y1 - r), color, -1)
        for c, _ in corners:
            cv2.circle(img, c, r, color, -1, cv2.LINE_AA)
        return
    for a, b in (((x0 + r, y0), (x1 - r, y0)), ((x0 + r, y1), (x1 - r, y1)),
                 ((x0, y0 + r), (x0, y1 - r)), ((x1, y0 + r), (x1, y1 - r))):
        cv2.line(img, a, b, color, thickness, cv2.LINE_AA)
    for c, ang in corners:
        cv2.ellipse(img, c, (r, r), ang, 0, 90, color, thickness, cv2.LINE_AA)


def text(img, s, x, y, scale=0.55, color=(255, 255, 255), thick=1, font=cv2.FONT_HERSHEY_DUPLEX, center=False, shadow=True):
    if center:
        x = x - text_width(s, scale, thick, font) / 2
    if shadow:
        cv2.putText(img, s, (int(x) + 1, int(y) + 1), font, scale, (0, 0, 0), thick, cv2.LINE_AA)
    cv2.putText(img, s, (int(x), int(y)), font, scale, color, thick, cv2.LINE_AA)


def text_width(s, scale=0.55, thick=1, font=cv2.FONT_HERSHEY_DUPLEX):
    return cv2.getTextSize(s, font, scale, thick)[0][0]
