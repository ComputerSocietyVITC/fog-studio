"""The webcam, as a mirrored 960 x 540 frame."""
import os

import cv2

from .config import H, W


class Camera:
    def __init__(self, index):
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened() and os.name == "nt":
            self.cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        # MJPG: many webcams only manage about 10 fps at 720p in their default raw format
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # always the newest frame: less lag behind your hand

    def read(self):
        """The next frame, flipped like a mirror and centre-cropped to 16:9, or None."""
        ok, frame = self.cap.read()
        if not ok or frame is None:
            return None
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        if w / h > W / H:
            nw = int(h * W / H)
            frame = frame[:, (w - nw) // 2:(w - nw) // 2 + nw]
        else:
            nh = int(w * H / W)
            frame = frame[(h - nh) // 2:(h - nh) // 2 + nh]
        return cv2.resize(frame, (W, H), interpolation=cv2.INTER_AREA)

    def release(self):
        self.cap.release()
