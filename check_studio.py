"""
Headless checks for Fog Studio (no webcam, microphone or window needed).

    python check_studio.py

Uses the fake camera, keys, mouse and microphone from tools/fake_io.py.
Prints PASS or FAIL per check and exits non-zero on any failure.
"""
import glob
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
sys.path.insert(0, HERE)
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS  " if ok else "FAIL  ") + name + ("  (" + detail + ")" if detail else ""), flush=True)


# ------------------------------------------------------------------ synthetic hands
OPEN = {0: (300, 400), 1: (270, 380), 2: (250, 350), 3: (235, 325), 4: (225, 300),
        5: (275, 300), 6: (270, 260), 7: (268, 235), 8: (266, 210),
        9: (300, 295), 10: (300, 250), 11: (300, 222), 12: (300, 195),
        13: (325, 300), 14: (328, 260), 15: (330, 235), 16: (332, 212),
        17: (348, 310), 18: (355, 280), 19: (360, 262), 20: (364, 245)}
CURLED_TIPS = {8: (275, 330), 12: (300, 330), 16: (322, 332), 20: (342, 335)}
CURLED_DIPS = {7: (272, 300), 11: (300, 300), 15: (324, 302), 19: (346, 305)}


def hand(**changes):
    pts = dict(OPEN)
    pts.update(changes.get("pts", {}))
    for f in changes.get("curl", []):  # f is a fingertip index: 8, 12, 16, 20
        pts[f] = CURLED_TIPS[f]
        pts[f - 1] = CURLED_DIPS[f - 1]
    return np.array([pts[i] for i in range(21)], np.float32)


def gesture_tests(fs):
    cases = {
        "open palm": (hand(), "open"),
        "pinch": (hand(pts={4: (270, 214)}), "pinch"),
        "fist": (hand(curl=[8, 12, 16, 20], pts={4: (285, 335), 3: (265, 345)}), "fist"),
        "thumbs up": (hand(curl=[8, 12, 16, 20], pts={4: (240, 220), 3: (245, 260)}), "thumbs_up"),
        "peace": (hand(curl=[16, 20], pts={4: (300, 330), 3: (280, 345)}), "peace"),
    }
    for name, (lm, expect) in cases.items():
        info = fs.classify(lm)
        flags = {k: info[k] for k in ("open", "fist", "thumbs_up", "peace")}
        flags["pinch"] = info["pinch"] < fs.PINCH_DOWN and info["index_ext"]
        on = sorted(k for k, v in flags.items() if v)
        check("gesture: %s is recognised as only '%s'" % (name, expect), on == [expect], "got %s, pinch ratio %.2f" % (on, info["pinch"]))
    # same gesture, hand twice as far away: ratios do not change
    far = fs.classify(hand(pts={4: (270, 214)}) * 0.5)
    near = fs.classify(hand(pts={4: (270, 214)}))
    check("pinch ratio does not depend on distance from the camera", abs(far["pinch"] - near["pinch"]) < 1e-5)


def pen_tests(fs):
    pen, drawn = fs.Pen(), []
    pinch = lambda p: {"pinch": 0.05, "index_ext": True, "pinch_point": p}
    release = lambda p: {"pinch": 0.6, "index_ext": True, "pinch_point": p}
    t = 0.0
    pen.update(pinch((100, 100)), t, drawn.append)
    for i in range(1, 30):
        t += 0.033
        pen.update(pinch((100 + 10 * i, 100)), t, drawn.append)
    check("pen: pinch puts the pen down and draws curved segments", pen.down and len(drawn) > 10, "%d segments" % len(drawn))
    pen.update(None, t + 0.1, drawn.append)
    check("pen: a hand missing for one frame does not lift the pen", pen.down)
    pen.update(None, t + 0.4, drawn.append)
    check("pen: missing for more than 250 ms lifts it", not pen.down)
    pen2 = fs.Pen()
    pen2.update(pinch((50, 50)), 0, lambda p: None)
    pen2.update({"pinch": 0.3, "index_ext": True, "pinch_point": (52, 50)}, 0.03, lambda p: None)
    pen2.update(release((54, 50)), 0.06, lambda p: None)
    down_after_one = pen2.down
    pen2.update(release((56, 50)), 0.09, lambda p: None)
    check("pen: hysteresis (0.3 keeps it down) and 2 released frames lift it", down_after_one and not pen2.down)
    pen3 = fs.Pen()
    pen3.update({"pinch": 0.05, "index_ext": False, "pinch_point": (0, 0)}, 0, lambda p: None)
    check("pen: no drawing when the index finger is curled (a fist with the thumb on the index)", not pen3.down)


def wiper_tests(fs):
    w, stamps = fs.Wiper(), []
    w.update((100, 100), 40, lambda c, r: stamps.append(c))
    n_first = len(stamps)
    w.update((300, 100), 40, lambda c, r: stamps.append(c))
    check("fist wipe: one stamp every half radius travelled", n_first == 1 and len(stamps) - 1 == 10, "%d stamps for 200 px at radius 40" % (len(stamps) - 1))
    stamps.clear()
    w.update((300, 100), 40, lambda c, r: stamps.append(c))
    check("fist wipe: a hand that stays still adds no stamps", len(stamps) == 0)
    w2, s2 = fs.Wiper(), []
    w2.update((0, 0), 4, lambda c, r: None)
    w2.update((280, 0), 4, lambda c, r: s2.append(c))
    check("fist wipe: never more than 40 stamps in one frame", len(s2) == 40, "%d" % len(s2))
    w3, s3 = fs.Wiper(), []
    w3.update((0, 0), 20, lambda c, r: None)
    w3.update((900, 0), 20, lambda c, r: s3.append(c))
    check("fist wipe: a jump over 30% of the screen stamps once, no streak", len(s3) == 1)


def breath_tests(fs):
    saved = sys.modules.get("sounddevice")
    sys.modules["sounddevice"] = None  # no real microphone for this test
    try:
        b = fs.Breath()
    finally:
        if saved is not None:
            sys.modules["sounddevice"] = saved
        else:
            sys.modules.pop("sounddevice", None)
    b.ok = True
    t = 0.0
    for _ in range(200):  # a quiet room
        b.level, b.flat = 0.002, 0.5
        t += 0.033
        b.update(t)
    check("breath: the floor settles on the room noise", abs(b.floor - 0.002) < 0.0005, "floor %.4f" % b.floor)
    quiet = b.strength
    for _ in range(10):  # a breath: louder and hissy
        b.level, b.flat = 0.012, 0.6
        t += 0.033
        s = b.update(t)
    check("breath: quiet room 0, a hissy breath fogs", quiet < 0.05 and s > 0.6, "quiet %.2f, breath %.2f" % (quiet, s))
    floor_after = b.floor
    check("breath: a breath barely moves the floor up (0.08% per frame)", floor_after < 0.0025, "floor %.4f" % floor_after)
    for _ in range(40):
        b.level, b.flat = 0.002, 0.5
        t += 0.033
        b.update(t)
    for _ in range(10):  # talking or humming: loud but not hissy
        b.level, b.flat = 0.02, 0.05
        t += 0.033
        v = b.update(t)
    check("breath: a loud hum (not hissy) does not fog", v < 0.05, "%.2f" % v)
    for _ in range(40):
        b.level, b.flat = 0.002, 0.5
        t += 0.033
        b.update(t)
    b.keystroke(t)
    b.level, b.flat = 0.02, 0.6
    k = b.update(t + 0.1)
    check("breath: ignored for 300 ms after a keystroke", k < 0.05, "%.2f" % k)


def app_run(fake_io, mic="script", camera="ok", frames=420):
    script = os.path.join(HERE, "fog_studio.py")
    L = 1  # left button flag
    keys = {0: 13}  # Enter on the start screen
    mouse = []
    for m in range(4):  # each mode gets 60 frames
        f = 10 + 65 * m
        keys[f] = str(m + 1)
        for j in range(4):
            keys[f + 3 + j] = " "  # hold space: fog
        keys[f + 40] = "d"  # debug on, then cycle the OpenCV panel
        keys[f + 44] = "v"
        keys[f + 48] = "v"
        keys[f + 52] = "d"
        mouse += [(f + 20, 1, 300, 300, L)] + [(f + 21 + j, 0, 300 + 60 * j, 300 + 10 * j, L) for j in range(6)]
        mouse += [(f + 28, 4, 660, 360, 0)]
    keys[400] = "h"
    keys[402] = "g"
    keys[404] = "s"
    keys[406] = "x"
    mouse += [(395, 1, 200, 506, L), (396, 0, 230, 506, L), (397, 4, 230, 506, 0)]  # drag the brush slider
    mouse += [(398, 1, 180, 29, L), (399, 4, 180, 29, 0)]  # click the first tab

    def probe(t, g):
        app = g.get("_APP")
        if app is None or app.modes is None:
            return None
        m = app.mode
        if m.name == "Neon":
            return (t, m.name, float(app.modes[1].layer.mean()))
        if hasattr(m, "fog"):
            return (t, m.name, float(m.fog.a.mean()))
        return (t, m.name, 0.0)

    before = set(glob.glob(os.path.join(HERE, "gallery", "*")))
    # expose the App object to the probe: wrap main() so the instance lands in the script's globals
    src = open(script, encoding="utf-8").read().replace(
        "    App(parse_args()).run()", "    global _APP\n    _APP = App(parse_args())\n    _APP.run()")
    tmp = os.path.join(HERE, "_check_copy.py")
    open(tmp, "w", encoding="utf-8").write(src)
    try:
        t0 = time.time()
        r = fake_io.run_script(tmp, frames=frames, keys=keys, mouse=mouse, mic=mic, camera=camera,
                               probe=probe, argv=["--windowed"])
        secs = time.time() - t0
    finally:
        os.remove(tmp)
    after = set(glob.glob(os.path.join(HERE, "gallery", "*")))
    new = after - before
    for f in new:
        os.remove(f)
    return r, secs, new


PHASES = ["phase1_mirror_ui", "phase2_breath", "phase3_hands", "phase4_polish_sound", "phase5_modes", "phase6_complete"]


def phase_run(fake_io, name):
    """Run one phase of phases/ for 100 frames: space fogs, a mouse drag wipes, the first navbar chip is clicked."""
    folder = os.path.join(HERE, "phases", name)
    for mod in [m for m in sys.modules if m == "studio" or m.startswith("studio.")]:
        del sys.modules[mod]  # every phase has its own studio/ package: forget the last one
    keys, f = {0: 13}, 10
    for k in ["h", "h", "[", "]", " ", " ", " ", " "]:
        keys[f] = k
        f += 5
    mouse = [(f + 5, 1, 300, 300, 1)] + [(f + 6 + j, 0, 300 + 50 * j, 300 + 8 * j, 1) for j in range(8)]
    mouse += [(f + 16, 4, 700, 360, 0), (f + 20, 1, 180, 29, 1), (f + 21, 4, 180, 29, 0)]

    def probe(t, g):
        app = g.get("_APP")
        if app is None or getattr(app, "modes", 1) is None or getattr(app, "mode", None) is None:
            return None
        return (t, float(app.mode.fog.a.mean()))

    src = open(os.path.join(folder, "run.py"), encoding="utf-8").read().replace(
        "    App(parse_args()).run()", "    global _APP\n    _APP = App(parse_args())\n    _APP.run()")
    tmp = os.path.join(folder, "_check_copy.py")
    open(tmp, "w", encoding="utf-8").write(src)
    try:
        r = fake_io.run_script(tmp, frames=f + 40, keys=keys, mouse=mouse, probe=probe, argv=["--windowed"])
    finally:
        os.remove(tmp)
    trace = [x for x in r.trace if x]
    drag = [v for t, v in trace if f + 4 <= t <= f + 18]
    return r, drag


def main():
    import fake_io
    from studio import audio, hands
    gesture_tests(hands)
    pen_tests(hands)
    wiper_tests(hands)
    breath_tests(audio)

    r, secs, new = app_run(fake_io)
    check("app runs all 4 modes for %d frames with keys, mouse, debug views, help, gallery" % r.frames,
          r.error is None and not r.audio_errors and r.frames >= 400, (r.error or "")[-600:])
    if r.error is None:
        print("      %.1f s for %d frames headless (%.0f fps without a window)" % (secs, r.frames, r.frames / secs))
        trace = [x for x in r.trace if x]
        seen = sorted(set(x[1] for x in trace))
        check("all four modes were visited", seen == sorted(["Fog", "Neon", "Reveal", "Motion"]), str(seen))
        fog = [x for x in trace if x[1] == "Fog"]
        drag = [x[2] for x in fog if 30 <= x[0] <= 40]
        check("Fog mode: a mouse drag wipes fog", len(drag) > 2 and drag[-1] < drag[0], "fog %.3f to %.3f" % (drag[0], drag[-1]) if drag else "")
        neon = [x[2] for x in trace if x[1] == "Neon"]
        check("Neon mode: a drag paints light", bool(neon) and max(neon) > 0, "layer mean %.3f" % (max(neon) if neon else 0))
        check("s saved a PNG to gallery/ (removed again after the check)", any(f.endswith(".png") for f in new), str(len(new)))
        app = r.globals.get("_APP")
        check("the brush slider drag and the tab click worked", app is not None and app.brush != 15 and app.mode_i == 0,
              "brush %s, mode %s" % (getattr(app, "brush", "?"), getattr(app, "mode_i", "?")))
    r2, _, _ = app_run(fake_io, mic="none", frames=150)
    check("app runs with no microphone (space still fogs)", r2.error is None, (r2.error or "")[-400:])
    r3, _, _ = app_run(fake_io, camera="fail", frames=20)
    app3 = r3.globals.get("_APP")
    check("a refused camera shows the error screen instead of crashing",
          r3.error is None and app3 is not None and app3.state == "error", getattr(app3, "error", ""))

    for name in PHASES:
        rp, drag = phase_run(fake_io, name)
        ok = rp.error is None and not rp.audio_errors and len(drag) > 2 and drag[-1] < drag[0]
        check("phases/%s runs, and a mouse drag wipes its fog" % name, ok,
              (rp.error or "")[-500:] or ("fog %.3f to %.3f" % (drag[0], drag[-1]) if drag else "no fog seen"))

    print("\n%d of %d checks passed" % (sum(results), len(results)))
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
