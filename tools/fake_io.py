"""
Headless test harness (from the Fog Mirror workshop kit), used by check_studio.py.

It swaps the webcam, the windows, the keyboard, the mouse and the microphone
for fakes, without touching the scripts being tested. A script runs exactly
as written, but:

    cv2.VideoCapture   gives synthetic 640x480 frames (face, green blob, hand)
    cv2.imshow etc.    record the call and show nothing
    cv2.waitKey        plays a scripted key sequence, then esc
    cv2.setMouseCallback  keeps the callback so we can fire fake drags and clicks
    sounddevice        is a fake module that feeds scripted audio from a thread

Use it from Python:

    import fake_io
    result = fake_io.run_script("fog_studio.py", frames=300, keys=" cs")
    print(result.frames, result.error)
"""
import importlib.abc
import os
import queue
import sys
import threading
import traceback
import types

import cv2
import numpy as np

W, H = 640, 480
ESC = 27
SAMPLE_RATE = 16000

# Remember the real functions once, so installing twice is safe.
_REAL = {}
for _name in ("VideoCapture", "imshow", "namedWindow", "destroyAllWindows", "destroyWindow",
              "createTrackbar", "getTrackbarPos", "setTrackbarPos", "waitKey", "setMouseCallback",
              "moveWindow", "resizeWindow", "getWindowProperty", "setWindowProperty"):
    _REAL[_name] = getattr(cv2, _name, None)


class HarnessStop(BaseException):
    """Raised when a script keeps running after it was asked to quit."""


# ---------------------------------------------------------------- the fake scene

def skin_bgr():
    """A BGR color that sits inside the Level 5 YCrCb skin range."""
    px = np.array([[[165, 152, 112]]], np.uint8)  # Y, Cr, Cb
    return tuple(int(v) for v in cv2.cvtColor(px, cv2.COLOR_YCrCb2BGR)[0, 0])


SKIN = skin_bgr()
FACE = tuple(max(0, c - 12) for c in SKIN)
GREEN = (40, 200, 40)  # BGR, hue 60 in OpenCV HSV


def draw_hand(img, cx, cy, fingers, color=255):
    """Palm plus 0 to 3 finger rectangles pointing up. Used by the camera and by tests."""
    cv2.ellipse(img, (int(cx), int(cy)), (45, 55), 0, 0, 360, color, -1)
    width, step = 16, 28
    left = cx - (fingers - 1) * step / 2.0
    middle = (fingers - 1) / 2.0
    for i in range(fingers):
        fx = int(left + i * step)
        length = int(70 - 14 * abs(i - middle))  # middle fingers are longer, like a real hand
        cv2.rectangle(img, (fx - width // 2, int(cy) - 40 - length), (fx + width // 2, int(cy) - 30), color, -1)
    return img


def blob_position(t):
    """Where the green blob is in the raw (unflipped) camera frame at frame t."""
    a = t / 15.0
    return int(200 + 90 * np.cos(a)), int(200 + 70 * np.sin(a))


def hand_position(t):
    return int(450 + 110 * np.sin(t / 22.0)), int(330 + 35 * np.cos(t / 31.0))


def hand_fingers(t):
    return (t // 75) % 4


def _background():
    rng = np.random.default_rng(3)
    base = np.zeros((H, W, 3), np.float32)
    base[:] = (120, 105, 95)  # grey blue wall
    grain = cv2.resize(rng.random((H // 8, W // 8)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    base += (grain[..., None] - 0.5) * 40
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    base *= 0.85 + 0.3 * yy  # light from below, like a laptop screen
    base += rng.normal(0, 3, base.shape).astype(np.float32)
    return np.clip(base, 0, 255).astype(np.uint8)


class Scene:
    def __init__(self, face=True, blob=True, hand=True, noise=True):
        self.face, self.blob, self.hand, self.noise = face, blob, hand, noise
        self.bg = _background()
        self.rng = np.random.default_rng(11)

    def frame(self, t):
        img = self.bg.copy()
        if self.face:
            cx = 320 + int(3 * np.sin(t / 40.0))
            cv2.ellipse(img, (cx, 210), (70, 95), 0, 0, 360, FACE, -1)
            cv2.circle(img, (cx - 25, 190), 8, (40, 40, 40), -1)
            cv2.circle(img, (cx + 25, 190), 8, (40, 40, 40), -1)
        if self.blob:
            cv2.circle(img, blob_position(t), 22, GREEN, -1)
        if self.hand:
            x, y = hand_position(t)
            draw_hand(img, x, y, hand_fingers(t), SKIN)
        if self.noise:
            n = self.rng.integers(-2, 3, img.shape, dtype=np.int16)
            img = np.clip(img.astype(np.int16) + n, 0, 255).astype(np.uint8)
        return img


# ---------------------------------------------------------------- shared state

class _State:
    def reset(self, frames, keys, mouse, mic, camera, scene, probe, key_start, key_every, frame_source):
        self.frames = frames
        self.keys = _parse_keys(keys, key_start, key_every)
        self.mouse = _parse_mouse(mouse)
        self.mic = mic
        self.camera = camera
        self.scene = Scene(**(scene or {}))
        self.frame_source = frame_source
        self.probe = probe
        self.trace = []
        self.t = 0  # frames finished (waitKey calls)
        self.reads = 0
        self.extra_calls = 0
        self.calls = {}
        self.mouse_callbacks = {}
        self.trackbars = {}
        self.streams = []
        self.audio_errors = []
        self.audio_samples = 0
        self.audio_rng = np.random.default_rng(5)

    def note(self, name):
        self.calls[name] = self.calls.get(name, 0) + 1


_state = _State()


def _parse_keys(keys, start, every):
    if keys is None:
        return {}
    if isinstance(keys, dict):
        return {int(k): (ord(v) if isinstance(v, str) else int(v)) for k, v in keys.items()}
    return {start + i * every: ord(ch) for i, ch in enumerate(keys)}


def default_mouse():
    """A left drag across the middle of the window, then a right click on the green blob."""
    events = [(30, cv2.EVENT_LBUTTONDOWN, 100, 240, cv2.EVENT_FLAG_LBUTTON)]
    for i, x in enumerate(range(160, 560, 80)):
        events.append((31 + i, cv2.EVENT_MOUSEMOVE, x, 240, cv2.EVENT_FLAG_LBUTTON))
    events.append((37, cv2.EVENT_LBUTTONUP, 540, 240, 0))
    events.append((38, cv2.EVENT_MOUSEMOVE, 540, 250, 0))
    bx, by = blob_position(50)
    events.append((50, cv2.EVENT_RBUTTONDOWN, W - 1 - bx, by, cv2.EVENT_FLAG_RBUTTON))
    return events


def _parse_mouse(mouse):
    if mouse == "default":
        mouse = default_mouse()
    table = {}
    for frame, event, x, y, flags in (mouse or []):
        table.setdefault(int(frame), []).append((event, x, y, flags))
    return table


# ---------------------------------------------------------------- fake cv2

class FakeCapture:
    def __init__(self, index=0, backend=None):
        _state.note("VideoCapture")
        self.index = index
        self.opened = _state.camera != "fail"

    def isOpened(self):
        return self.opened

    def set(self, prop, value):
        return True

    def get(self, prop):
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return float(W)
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return float(H)
        if prop == cv2.CAP_PROP_FPS:
            return 30.0
        return 0.0

    def read(self):
        if not self.opened:
            return False, None
        _state.reads += 1
        if _state.frame_source is not None:
            return True, _state.frame_source(_state.t)
        return True, _state.scene.frame(_state.t)

    def release(self):
        self.opened = False


def _record(name):
    def fn(*args, **kwargs):
        _state.note(name)
        return None
    return fn


def _create_trackbar(name, window, value, count, onchange=None):
    _state.note("createTrackbar")
    _state.trackbars[(name, window)] = value
    if onchange is not None:
        onchange(value)


def _get_trackbar_pos(name, window):
    _state.note("getTrackbarPos")
    return _state.trackbars.get((name, window), 0)


def _set_trackbar_pos(name, window, value):
    _state.trackbars[(name, window)] = value


def _set_mouse_callback(window, callback, param=None):
    _state.note("setMouseCallback")
    _state.mouse_callbacks[window] = (callback, param)


def _get_window_property(*args):
    return 1.0


def _audio_block(n):
    """Scripted audio for the current frame: silence, then breath noise, then a tone."""
    mode = audio_mode_at(_state.t)
    start = _state.audio_samples
    _state.audio_samples += n
    rng = _state.audio_rng
    if mode == "noise":
        x = rng.normal(0, 0.1, n)
    elif mode == "tone":
        t = (start + np.arange(n)) / SAMPLE_RATE
        x = 0.3 * np.sin(2 * np.pi * 220 * t)
    else:
        x = rng.normal(0, 0.001, n)
    return x.astype(np.float32)


def audio_mode_at(t):
    mic = _state.mic
    if mic == "noise":
        return "silence" if t < 30 else "noise"
    if mic == "tone":
        return "silence" if t < 30 else "tone"
    if mic == "script":
        if t < 60:
            return "silence"
        return "noise" if t < 180 else "tone"
    return "silence"


def _wait_key(delay=0):
    t = _state.t
    _state.note("waitKey")
    # 1. mouse events scheduled for this frame
    for event, x, y, flags in _state.mouse.get(t, []):
        for callback, param in list(_state.mouse_callbacks.values()):
            callback(event, x, y, flags, param)
    # 2. one block of audio to every running stream
    for stream in list(_state.streams):
        if stream.active:
            stream.deliver(_audio_block(stream.blocksize))
    # 3. let the test look at the script's variables
    if _state.probe is not None:
        _state.trace.append(_state.probe(t, _state.globals))
    _state.t += 1
    # 4. the key for this frame
    if t >= _state.frames:
        _state.extra_calls += 1
        if _state.extra_calls <= 5:
            return ESC
        if _state.extra_calls <= 10:
            return ord("q")
        raise HarnessStop()
    if delay is not None and delay <= 0:
        return ESC  # image demos wait for any key: answer straight away
    return _state.keys.get(t, -1)


# ---------------------------------------------------------------- fake sounddevice

class _FakeStream:
    def __init__(self, samplerate=SAMPLE_RATE, blocksize=1024, channels=1, callback=None, dtype="float32", **kwargs):
        self.samplerate = samplerate
        self.blocksize = blocksize or 1024
        self.channels = channels
        self.callback = callback
        self.active = False
        self._q = queue.Queue()
        self._done = threading.Event()
        _state.streams.append(self)

    def start(self):
        if self.active:
            return
        self.active = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            block = self._q.get()
            if block is None:
                return
            try:
                if self.callback is not None:
                    self.callback(np.repeat(block[:, None], self.channels, axis=1), len(block), None, None)
            except Exception:
                _state.audio_errors.append(traceback.format_exc())
            self._done.set()

    def deliver(self, block):
        self._done.clear()
        self._q.put(block)
        self._done.wait(2.0)

    def stop(self):
        if self.active:
            self.active = False
            self._q.put(None)

    def close(self):
        self.stop()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()


def _fake_rec(frames, samplerate=SAMPLE_RATE, channels=1, dtype="float32", **kwargs):
    rng = np.random.default_rng(9)
    x = rng.normal(0, 0.1, (int(frames), channels)).astype(np.float32)
    return x


def _make_fake_sounddevice():
    mod = types.ModuleType("sounddevice")
    mod.__version__ = "fake"
    mod.InputStream = _FakeStream
    mod.rec = _fake_rec
    mod.wait = lambda: None
    mod.query_devices = lambda *a, **k: "0 Fake Microphone, 1 in"
    mod.PortAudioError = OSError
    return mod


class _NoMicFinder(importlib.abc.MetaPathFinder):
    """Makes `import sounddevice` fail the way Linux does without PortAudio."""

    def find_spec(self, name, path=None, target=None):
        if name == "sounddevice":
            raise OSError("PortAudio library not found (fake: --mic none)")
        return None


_NO_MIC = _NoMicFinder()


# ---------------------------------------------------------------- install and run

def install(frames=300, keys=None, mouse=None, mic="script", camera="ok", scene=None, probe=None,
            key_start=20, key_every=10, frame_source=None):
    _state.reset(frames, keys, mouse, mic, camera, scene, probe, key_start, key_every, frame_source)
    _state.globals = {}
    cv2.VideoCapture = FakeCapture
    for name in ("imshow", "namedWindow", "destroyAllWindows", "destroyWindow", "moveWindow", "resizeWindow",
                 "setWindowProperty"):
        setattr(cv2, name, _record(name))
    cv2.createTrackbar = _create_trackbar
    cv2.getTrackbarPos = _get_trackbar_pos
    cv2.setTrackbarPos = _set_trackbar_pos
    cv2.waitKey = _wait_key
    cv2.setMouseCallback = _set_mouse_callback
    cv2.getWindowProperty = _get_window_property
    if _NO_MIC in sys.meta_path:
        sys.meta_path.remove(_NO_MIC)
    sys.modules.pop("sounddevice", None)
    if mic == "none":
        sys.meta_path.insert(0, _NO_MIC)
    else:
        sys.modules["sounddevice"] = _make_fake_sounddevice()


def uninstall():
    for name, fn in _REAL.items():
        if fn is not None:
            setattr(cv2, name, fn)
    if _NO_MIC in sys.meta_path:
        sys.meta_path.remove(_NO_MIC)
    sys.modules.pop("sounddevice", None)
    for stream in list(_state.streams):
        stream.stop()


class Result:
    def __init__(self):
        self.frames = 0
        self.reads = 0
        self.error = None  # traceback text if the script crashed
        self.exit_message = None  # text of SystemExit, if any
        self.forced_stop = False
        self.globals = {}
        self.trace = []
        self.calls = {}
        self.audio_errors = []

    @property
    def ok(self):
        return self.error is None and not self.audio_errors


def run_script(path, frames=300, keys=None, mouse=None, mic="script", camera="ok", scene=None, probe=None,
               argv=None, key_start=20, key_every=10, frame_source=None):
    """Run one script under the fakes and return a Result."""
    path = os.path.abspath(path)
    folder = os.path.dirname(path)
    install(frames, keys, mouse, mic, camera, scene, probe, key_start, key_every, frame_source)
    g = {"__name__": "__main__", "__file__": path, "__builtins__": __builtins__}
    _state.globals = g
    result = Result()
    old_cwd, old_argv, old_path = os.getcwd(), sys.argv, list(sys.path)
    os.chdir(folder)
    sys.argv = [path] + list(argv or [])
    sys.path.insert(0, folder)
    try:
        with open(path, encoding="utf-8") as f:
            code = compile(f.read(), path, "exec")
        exec(code, g)
    except SystemExit as e:
        if e.code not in (None, 0):
            result.exit_message = str(e.code)
    except HarnessStop:
        result.forced_stop = True
    except Exception:
        result.error = traceback.format_exc()
    finally:
        os.chdir(old_cwd)
        sys.argv = old_argv
        sys.path[:] = old_path
        result.frames = _state.t
        result.reads = _state.reads
        result.globals = g
        result.trace = _state.trace
        result.calls = dict(_state.calls)
        result.audio_errors = list(_state.audio_errors)
        uninstall()
    return result


def load_script(path, frames=1, **kwargs):
    """Run a script for a few frames and hand back its variables and functions."""
    result = run_script(path, frames=frames, **kwargs)
    if result.error:
        raise RuntimeError("script crashed while loading:\n" + result.error)
    return result.globals
