"""Hands: MediaPipe tracking on a thread, gestures from landmarks, and the pen and wiper every mode shares."""
import os
import threading
import time

import cv2
import numpy as np

from .config import EASE_BRUSH, EASE_STAR, EASE_TARGET, H, MODELS, PINCH_DOWN, PINCH_UP, TREMOR, W
from .gfx import dist, lerp

os.environ.setdefault("GLOG_minloglevel", "2")  # keep MediaPipe quiet in the terminal
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")


class Tracker:
    """MediaPipe hand landmarks (and the face, to aim the breath) on its own thread, so the mirror stays smooth."""

    def __init__(self):
        self.ok, self.error = False, ""
        self.hands, self.mouth, self.ms = [], None, 0.0  # landmark arrays (21 x 2, render pixels), mouth point
        self._frame, self._lock, self._running, self._ts = None, threading.Lock(), True, 0
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions, vision
            self._mp, video = mp, vision.RunningMode.VIDEO
            self._hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=os.path.join(MODELS, "hand_landmarker.task")),
                running_mode=video, num_hands=2, min_hand_detection_confidence=0.6,
                min_hand_presence_confidence=0.5, min_tracking_confidence=0.5))
            face_model = os.path.join(MODELS, "blaze_face_short_range.tflite")
            self._face = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
                base_options=BaseOptions(model_asset_path=face_model), running_mode=video,
                min_detection_confidence=0.5)) if os.path.exists(face_model) else None
            self.ok = True
        except Exception as e:  # not installed, or a model is missing: the mirror still works without hands
            self.error = "%s: %s" % (type(e).__name__, e)
            return
        threading.Thread(target=self._run, daemon=True).start()

    def submit(self, frame):
        if self.ok:
            with self._lock:
                self._frame = frame  # only the newest frame matters

    def _run(self):
        count = 0
        while self._running:
            with self._lock:
                frame, self._frame = self._frame, None
            if frame is None:
                time.sleep(0.003)
                continue
            t0 = time.perf_counter()
            rgb = np.ascontiguousarray(cv2.cvtColor(cv2.resize(frame, (640, 360)), cv2.COLOR_BGR2RGB))
            try:
                self.hands = self._detect(rgb, face_too=count % 5 == 0)  # the face moves slowly: every 5th time
            except Exception as e:
                self.error, self.hands = "%s: %s" % (type(e).__name__, e), []
            count += 1
            self.ms = (time.perf_counter() - t0) * 1000

    def _detect(self, rgb, face_too):
        self._ts = max(self._ts + 1, int(time.monotonic() * 1000))  # timestamps must keep rising
        img = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        res = self._hands.detect_for_video(img, self._ts)
        if face_too and self._face is not None:
            faces = self._face.detect_for_video(img, self._ts).detections
            if faces:
                kp = faces[0].keypoints[3]  # the mouth
                self.mouth = (kp.x * W, kp.y * H)
        return [np.array([(p.x * W, p.y * H) for p in lm], np.float32) for lm in res.hand_landmarks]

    def stop(self):
        self._running = False


def classify(lm):
    """Gestures from 21 landmarks. Everything is relative to hand size, so near and far behave the same."""
    size = max(dist(lm[0], lm[9]), 1e-6)  # wrist to middle knuckle
    pinch = dist(lm[4], lm[8]) / size
    curled = [dist(lm[t], lm[0]) < dist(lm[p], lm[0]) for t, p in ((8, 6), (12, 10), (16, 14), (20, 18))]
    thumb_up = all(curled) and lm[4][1] < lm[5][1] - 0.45 * size and lm[4][1] < lm[3][1]
    palm = lm[[0, 5, 9, 13, 17]].mean(axis=0)
    return {
        "pinch": pinch,
        "index_ext": not curled[0],
        "fist": all(curled) and not thumb_up,
        "thumbs_up": thumb_up,
        "peace": not curled[0] and not curled[1] and curled[2] and curled[3] and pinch > 0.5,
        "open": not any(curled) and pinch > 0.6,
        "width": max(dist(lm[5], lm[17]), size),
        "pinch_point": ((lm[4][0] + lm[8][0]) / 2, (lm[4][1] + lm[8][1]) / 2),
        "palm": (float(palm[0]), float(palm[1])),
    }


def pinch_at(point):
    """A pretend pinch, so the mouse gets the same smooth, curved pen as a hand."""
    return {"pinch": 0.0, "index_ext": True, "pinch_point": point}


def quad_points(p0, p1, p2, step=2.0):
    """Points along the quadratic curve from p0 to p2 with control p1."""
    n = max(2, int((dist(p0, p1) + dist(p1, p2)) / step))
    t = np.linspace(0, 1, n)[:, None]
    a, b, c = np.array(p0), np.array(p1), np.array(p2)
    return (1 - t) ** 2 * a + 2 * (1 - t) * t * b + t ** 2 * c


class Pen:
    """Pinch-to-draw for one hand: hysteresis, two-stage smoothing, tremor filter, curved strokes."""

    def __init__(self):
        self.down = False
        self.target = self.brush = self.star = None
        self.pts, self.released, self.last_seen, self.speed = [], 0, 0.0, 0.0

    def lift(self):
        self.down, self.pts, self.released = False, [], 0

    def update(self, info, now, draw):
        """info is classify() output, or None when the hand is missing. draw(points) erases along a path."""
        self.speed = 0.0
        if info is None:
            if self.down and now - self.last_seen > 0.25:  # gone for 250 ms: now we lift
                self.lift()
            return
        self.last_seen = now
        raw = info["pinch_point"]
        self.star = raw if self.star is None else lerp(self.star, raw, EASE_STAR)
        if not self.down:
            # index must be extended to start: in a fist the thumb rests on the index and looks like a pinch
            if info["pinch"] < PINCH_DOWN and info["index_ext"]:
                self.down, self.released = True, 0
                self.target = self.brush = raw
                self.pts = [raw]
                draw([raw])
            return
        self.released = self.released + 1 if info["pinch"] > PINCH_UP else 0
        if self.released >= 2:
            self.lift()
            return
        self.target = lerp(self.target, raw, EASE_TARGET)
        new = lerp(self.brush, self.target, EASE_BRUSH)
        if dist(new, self.pts[-1]) < TREMOR:
            return
        self.speed = dist(new, self.brush)
        self.brush = new
        self.pts.append(new)
        if len(self.pts) >= 3:  # curve through the midpoints: no visible corners
            a, b, c = self.pts[-3:]
            draw(quad_points(lerp(a, b, 0.5), b, lerp(b, c, 0.5)))
        else:
            draw([self.pts[-2], new])
        self.pts = self.pts[-3:]


class Wiper:
    """Fist wipe: one soft stamp every half radius travelled, never per frame."""

    def __init__(self):
        self.last = None

    def update(self, center, radius, stamp):
        """Returns how many stamps were made."""
        if center is None:
            self.last = None
            return 0
        if self.last is None or dist(center, self.last) > 0.3 * W:  # new, or tracking jumped: stamp once
            stamp(center, radius)
            self.last = center
            return 1
        step, d = radius * 0.5, dist(center, self.last)
        n = min(40, int(d // step))
        for i in range(1, n + 1):
            stamp(lerp(self.last, center, i * step / d), radius)
        if n:
            self.last = lerp(self.last, center, n * step / d)
        return n


class HandInput:
    """Up to two hands plus the mouse, each with its own pen. A fist wipes instead of drawing."""

    def __init__(self):
        self.pens, self.wipers, self.mouse_pen = [Pen(), Pen()], [Wiper(), Wiper()], Pen()
        self.slots = [None, None]  # last wrist position per slot, so each hand keeps its own pen
        self.lms, self.infos = [None, None], [None, None]  # landmarks and classify() per slot
        self.holds = {}  # gesture name: when the hold started (None once it has fired)
        self.drawing, self.wiping, self.speed = False, False, 0.0

    def match(self, hands):
        """Give each hand the slot whose last wrist position is nearest."""
        out, free = [None, None], [0, 1]
        for lm in hands[:2]:
            wrist = (float(lm[0][0]), float(lm[0][1]))
            best = min(free, key=lambda s: dist(wrist, self.slots[s]) if self.slots[s] else 1e9)
            out[best] = lm
            free.remove(best)
            self.slots[best] = wrist
        for s in free:
            self.slots[s] = None
        return out

    def update(self, hands, mouse, now, stroke, wipe):
        """mouse is the pointer while the button is down, else None. stroke(points) draws, wipe(center, radius) wipes."""
        self.lms = self.match(hands)
        self.infos = [classify(lm) if lm is not None else None for lm in self.lms]
        self.speed, self.wiping = 0.0, False
        for info, pen, wiper in zip(self.infos, self.pens, self.wipers):
            if info is not None and info["fist"] and not pen.down:
                self.wiping |= wiper.update(info["palm"], 1.6 * info["width"], wipe) > 0
                pen.update(None, now, stroke)
                continue
            wiper.update(None, 0, None)
            pen.update(info, now, stroke)
            self.speed = max(self.speed, pen.speed)
        if mouse is not None:  # the mouse is a pen too (handy for demos without hands)
            self.mouse_pen.update(pinch_at(mouse), now, stroke)
            self.speed = max(self.speed, self.mouse_pen.speed)
        elif self.mouse_pen.down:
            self.mouse_pen.lift()
        self.drawing = any(p.down for p in self.pens) or self.mouse_pen.down

    def held(self, name, active, secs, now):
        """True once when a gesture has been held for secs; it must be let go before it fires again."""
        if not active:
            self.holds.pop(name, None)
            return False
        start = self.holds.setdefault(name, now)
        if start is not None and now - start >= secs:
            self.holds[name] = None
            return True
        return False

    def lift_all(self):
        for p in self.pens:
            p.lift()
