"""Sound in: the breath detector (microphone)."""
from collections import deque

import numpy as np


class Breath:
    """Mic loudness above a floating noise floor, AND hissy (spectrally flat) like a breath."""

    def __init__(self):
        self.ok, self.level, self.flat, self.floor = False, 0.0, 0.0, None
        self.strength, self.hold_until, self.quiet_until, self.space_until = 0.0, 0.0, 0.0, 0.0
        self.trigger = 0.0025  # above the floor; full strength 0.0005 higher
        self.meter = 0.0  # 0 to 1, for the ring around the mic button
        self.history = deque(maxlen=160)  # (level, trigger line), for a graph
        self._window = np.hanning(512).astype(np.float32)
        try:
            import sounddevice as sd
            # Raw mic: sounddevice does not run noise suppression, which would delete the sound of breathing.
            self.stream = sd.InputStream(samplerate=16000, blocksize=512, channels=1, callback=self._cb)
            self.stream.start()
            self.ok = True
        except Exception:
            self.stream = None

    def _cb(self, indata, frames, time_info, status):
        x = indata[:, 0].astype(np.float32)
        self.level = float(np.sqrt(np.mean(x ** 2)))
        win = self._window if len(x) == len(self._window) else np.hanning(len(x))
        spec = np.abs(np.fft.rfft(x * win)) + 1e-9
        self.flat = float(np.exp(np.mean(np.log(spec))) / np.mean(spec))  # 1 = hiss, near 0 = a tone

    def keystroke(self, now):
        self.quiet_until = now + 0.3  # typing is loud and hissy: ignore it

    def hold_space(self, now):
        self.space_until = now + 0.18  # key repeat keeps this alive while space is held

    def update(self, now):
        """Returns the breath strength, 0 to 1."""
        lvl = self.level
        if self.floor is None:
            self.floor = lvl
        # the floor chases the level: fast down, very slow up, so a breath cannot drag it up
        self.floor += (lvl - self.floor) * (0.05 if lvl < self.floor else 0.0008)
        margin = lvl - self.floor
        mic = 0.0
        if self.ok and now > self.quiet_until and self.flat > 0.15:
            mic = float(np.clip((margin - self.trigger) / 0.0005, 0, 1))
        if mic > 0:
            self.hold_until = now + 0.35
        target = 1.0 if now < self.space_until else (max(mic, 0.6) if now < self.hold_until else 0.0)
        self.strength += (target - self.strength) * 0.35
        self.meter += (float(np.clip(margin / (self.trigger * 2), 0, 1)) - self.meter) * 0.3
        self.history.append((lvl, self.floor + self.trigger))
        return self.strength

    def stop(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
