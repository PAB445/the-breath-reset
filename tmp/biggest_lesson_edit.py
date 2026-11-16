"""
Shared timeline logic for the "Biggest breathwork lesson" reel.

Loads edit.json from the reel folder and answers two questions every other
script needs:

  * where does a moment in the source land in the finished video (and back)?
    -- lengthened pauses ("holds") and the tail shift everything after them;
  * how is the source framed at a given source time? (crop zoom + offset)

Stdlib only, so it imports from both the system python and the DSP venv.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# BL_REEL_DIR selects a cut. Each of v1 and v2 has its own edit.json;
# source.mp4 stays in the parent folder. Defaults to v1.
REEL_DIR = os.environ.get(
    "BL_REEL_DIR",
    os.path.join(ROOT, "assets", "social", "instagram", "reflections",
                 "biggest-breathwork-lesson", "v1"))
EDIT_PATH = os.path.join(REEL_DIR, "edit.json")
CAPTIONS_PATH = os.path.join(REEL_DIR, "captions.srt")
WORDS_PATH = os.path.join(HERE, "biggest-lesson-words.json")

with open(EDIT_PATH) as f:
    EDIT = json.load(f)

SOURCE = os.path.normpath(os.path.join(REEL_DIR, EDIT["source"]))
SRC_DUR = float(EDIT["source_duration"])
FPS = int(EDIT["fps"])
HOLDS = sorted(EDIT["holds"], key=lambda h: h["from"])
TAIL = EDIT["tail"]

# Source frame geometry and the base 9:16 crop (full height).
SRC_W, SRC_H = 1620, 1080
BASE_CW = SRC_H * 9 / 16          # 607.5
FACE_X = float(EDIT["face"]["x"])
FACE_Y = float(EDIT["face"]["y"])


# ------------------------------------------------------------- time mapping
def _segments():
    """Piecewise-linear map as [(src0, src1, out0, out1)] covering the source."""
    segs, src, out = [], 0.0, 0.0
    for h in HOLDS:
        a, b, extra = h["from"], h["to"], h["extra"]
        segs.append((src, a, out, out + (a - src)))
        out += a - src
        segs.append((a, b, out, out + (b - a) + extra))
        out += (b - a) + extra
        src = b
    segs.append((src, SRC_DUR, out, out + (SRC_DUR - src)))
    return segs


SEGMENTS = _segments()
SPEECH_OUT_END = SEGMENTS[-1][3]                       # source end, out time
HOLD_END = SPEECH_OUT_END + TAIL["hold"]               # dark fade done here
END_CARD_START = HOLD_END
TOTAL_DUR = round(END_CARD_START + TAIL["end_card"], 3)


def out_time(s):
    """Source seconds -> finished-video seconds."""
    for s0, s1, o0, o1 in SEGMENTS:
        if s <= s1:
            return o0 + (max(s, s0) - s0) * (o1 - o0) / (s1 - s0)
    return SPEECH_OUT_END + (s - SRC_DUR)


def src_time(t):
    """Finished-video seconds -> source seconds (clamped to the source)."""
    for s0, s1, o0, o1 in SEGMENTS:
        if t <= o1:
            return s0 + (max(t, o0) - o0) * (s1 - s0) / (o1 - o0)
    return SRC_DUR


def in_hold(t):
    """True while the video is playing a lengthened pause (slowed)."""
    s = src_time(t)
    return any(h["from"] < s < h["to"] for h in HOLDS) and t < SPEECH_OUT_END


# ------------------------------------------------------------------ framing
SHOTS = sorted(EDIT["shots"], key=lambda s: s["at"])


def _ease_io(x):
    x = min(1.0, max(0.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def shot_index(s):
    i = 0
    for k, shot in enumerate(SHOTS):
        if shot["at"] <= s:
            i = k
    return i


def framing(t):
    """(zoom, dx) at finished-video time t. Push-ins are eased over the
    shot's duration in *output* time, so lengthened pauses keep moving."""
    s = src_time(t)
    i = shot_index(s)
    shot = SHOTS[i]
    o0 = out_time(shot["at"])
    o1 = out_time(SHOTS[i + 1]["at"]) if i + 1 < len(SHOTS) else TOTAL_DUR
    u = (t - o0) / max(1e-6, o1 - o0)
    z0, z1 = shot["zoom"]
    # mostly linear with soft ends: a push should never visibly start or stop
    z = z0 + (z1 - z0) * (0.75 * min(1.0, max(0.0, u)) + 0.25 * _ease_io(u))
    return z, float(shot.get("dx", 0))


def crop_box(zoom, dx):
    """Source-pixel box (x0, y0, x1, y1) for a zoom about the face."""
    cw, ch = BASE_CW / zoom, SRC_H / zoom
    # where the face sits in the unzoomed crop, as a fraction
    base_x0 = FACE_X + dx - BASE_CW / 2
    u = (FACE_X - base_x0) / BASE_CW
    v = FACE_Y / SRC_H
    x0 = FACE_X - u * cw
    y0 = FACE_Y - v * ch
    x0 = min(max(0.0, x0), SRC_W - cw)
    y0 = min(max(0.0, y0), SRC_H - ch)
    return (x0, y0, x0 + cw, y0 + ch)


def cut_times():
    """Finished-video times of every cut (shot change)."""
    return [out_time(s["at"]) for s in SHOTS[1:]]


if __name__ == "__main__":
    print(f"speech ends {SPEECH_OUT_END:.2f}s, end card {END_CARD_START:.2f}s, "
          f"total {TOTAL_DUR:.2f}s")
    for s in SHOTS:
        print(f"  shot @ src {s['at']:7.2f} -> out {out_time(s['at']):7.2f}  "
              f"{s['zoom']}  {s.get('_note', '')}")
