#!/usr/bin/env python3
"""
"Biggest breathwork lesson" -- vertical talking-head reel.

  tmp/.venv-dsp/bin/python tmp/make_biggest_lesson_audio.py   # audio first
  python3 tmp/render_biggest_lesson.py                  # full 1080x1920 render
  BL_PREVIEW=1 python3 tmp/render_biggest_lesson.py     # fast 540x960 proof
  BL_STILLS=1 python3 tmp/render_biggest_lesson.py      # check stills
  BL_STILLS=4.5,99.8 python3 tmp/render_biggest_lesson.py   # stills at times
  BL_COVER=1 python3 tmp/render_biggest_lesson.py       # Instagram cover.png

Everything editorial lives next to the footage, not in here:
  edit.json      holds, shots (push-ins / crops), start screen, message
                 bubbles, b-roll, music settings
  captions.srt   caption text + timing; <i>...</i> marks a highlighted line

Visual system is the founder / quiet-breathing one: warm-black scrims,
Instrument Serif with a sage italic turn, tracked Manrope caps, the same end
card. Layout bands in the 1080x1920 frame:
  face            y ~250-1010      never covered
  message bubbles y ~1160-1370     upper chest
  captions        y ~1420-1540     lower-middle, above Instagram's caption UI
  x 90-950                         clear of the Reels action column

Source is 1620x1080 (3:2); each frame is cropped (full-height 9:16 at zoom 1)
about the face with a sub-pixel box, so push-ins are smooth, and upscaled.

Outputs -> assets/social/instagram/reflections/biggest-breathwork-lesson/v1/
(or v2, when BL_REEL_DIR points there). source.mp4 stays in the parent.
"""
import io
import math
import os
import re
import subprocess
import sys
import time
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from biggest_lesson_edit import (CAPTIONS_PATH, EDIT, END_CARD_START, FPS,
                                 HOLD_END, REEL_DIR, ROOT, SOURCE,
                                 SPEECH_OUT_END, SRC_DUR, SRC_H, SRC_W, TAIL,
                                 TOTAL_DUR, crop_box, framing, in_hold,
                                 out_time, src_time)

HERE = os.path.dirname(os.path.abspath(__file__))
FINAL = os.path.join(REEL_DIR, "biggest-breathwork-lesson.mp4")
COVER = os.path.join(REEL_DIR, "cover.png")
MIX = os.path.join(HERE, "biggest-lesson-mix.wav")
STILL_DIR = os.path.join(HERE, "biggest-lesson-frames")

W, H = 1080, 1920
CX = W // 2

# palette -- warm-black system (styles.css / founder video)
BG = (16, 13, 11)
BG_DEEP = (10, 8, 7)
OFF = (239, 231, 217)
MUTED = (198, 190, 176)
SAGE = (143, 165, 138)
SAGE_BRIGHT = (179, 199, 172)
SAGE_DARK = (95, 116, 94)
CLAY = (209, 144, 115)

SUB_Y = 1478               # centre of a plain caption
HERO_Y = 1452              # centre of a highlighted line
GRID_TOP = 285             # Instagram 4:5 profile-grid crop is y 285..1635

FONTS = os.path.join(ROOT, "breathing-reel", "fonts")


# ------------------------------------------------------------------- fonts
@lru_cache(maxsize=None)
def manrope(size, weight=600):
    f = ImageFont.truetype(os.path.join(FONTS, "Manrope.ttf"), int(size))
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


@lru_cache(maxsize=None)
def serif(size, italic=False):
    name = "InstrumentSerif-Italic.ttf" if italic else "InstrumentSerif-Regular.ttf"
    return ImageFont.truetype(os.path.join(FONTS, name), int(size))


# ------------------------------------------------------------------ easing
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def smooth(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def env(t, start, end, fin=0.45, fout=0.45):
    if t < start or t >= end:
        return 0.0
    a = smooth((t - start) / fin) if fin > 0 else 1.0
    b = smooth((end - t) / fout) if fout > 0 else 1.0
    return a * b


# ----------------------------------------------------------------- sprites
HALO_PAD = 28


def with_halo(content, strength=0.55, blur=11):
    """Dark blurred copy of the content's own alpha underneath it -- the
    founder lower-third trick; holds type up over the pale shirt."""
    halo = Image.new("RGBA", content.size, BG_DEEP + (0,))
    halo.putalpha(content.getchannel("A").point(lambda v: int(v * strength)))
    out = halo.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(content)
    return out


def tracked_width(fnt, text, tracking):
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    return sum(d.textlength(ch, font=fnt) + tracking for ch in text) - tracking


@lru_cache(maxsize=None)
def label(text, size=26, weight=700, fill=OFF, tracking=None, halo=0.6):
    fnt = manrope(size, weight)
    tracking = size * 0.28 if tracking is None else tracking
    tw = tracked_width(fnt, text, tracking)
    asc, desc = fnt.getmetrics()
    img = Image.new("RGBA", (int(tw) + 2 * HALO_PAD, asc + desc + 2 * HALO_PAD),
                    (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = HALO_PAD
    for ch in text:
        d.text((x, HALO_PAD), ch, font=fnt, fill=fill)
        x += d.textlength(ch, font=fnt) + tracking
    return with_halo(img, halo) if halo else img


def paste(canvas, sprite, cx, cy, alpha=1.0, scale=1.0, anchor="mm"):
    if alpha <= 0.003:
        return
    s = sprite
    if abs(scale - 1.0) > 1e-3:
        s = s.resize((max(1, int(s.width * scale)), max(1, int(s.height * scale))),
                     Image.BICUBIC)
    if alpha < 0.997:
        s = s.copy()
        s.putalpha(s.getchannel("A").point(lambda v: int(v * alpha)))
    if anchor == "lm":
        x = int(round(cx - HALO_PAD * scale))
    elif anchor == "rm":
        x = int(round(cx - s.width + HALO_PAD * scale))
    else:
        x = int(round(cx - s.width / 2))
    y = int(round(cy - s.height / 2))
    canvas.alpha_composite(s, (max(0, x), max(0, y)),
                           (max(0, -x), max(0, -y)))


# ------------------------------------------------------------------ scrims
def ramp_mask(stops):
    small = Image.new("L", (1, 256))
    px = small.load()
    ys = [s[0] for s in stops]
    al = [s[1] for s in stops]
    for i in range(256):
        t = i / 255
        if t <= ys[0]:
            v = al[0]
        elif t >= ys[-1]:
            v = al[-1]
        else:
            for j in range(len(ys) - 1):
                if ys[j] <= t <= ys[j + 1]:
                    u = smooth((t - ys[j]) / (ys[j + 1] - ys[j]))
                    v = al[j] + (al[j + 1] - al[j]) * u
                    break
        px[0, i] = int(round(v))
    return small.resize((W, H), Image.BICUBIC)


def scrim_layer(stops):
    img = Image.new("RGBA", (W, H), BG_DEEP + (0,))
    img.putalpha(ramp_mask(stops))
    return img


# The shirt is pale blue (~200 luma), so the caption band is always pulled
# down a little -- it reads as part of the grade, not as a box.
BASE_SCRIM = [(0.0, 34), (0.10, 0), (0.56, 0), (0.68, 66), (0.77, 116),
              (0.88, 126), (1.0, 140)]
HERO_SCRIM = [(0.0, 0), (0.58, 0), (0.72, 62), (0.80, 84), (0.90, 44), (1.0, 0)]
MSG_SCRIM = [(0.0, 0), (0.54, 0), (0.63, 84), (0.72, 90), (0.82, 30), (1.0, 0)]
START_SCRIM = [(0.0, 150), (0.13, 96), (0.30, 0), (0.48, 0), (0.62, 120),
               (0.76, 220), (1.0, 240)]
LEVELS = 24


@lru_cache(maxsize=None)
def base_overlay():
    """Base scrim + soft radial vignette, merged once."""
    img = scrim_layer(BASE_SCRIM)
    strength = float(EDIT["grade"].get("vignette", 0.4))
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - CX) / (W * 0.62)) ** 2 + ((yy - H * 0.40) / (H * 0.62)) ** 2)
    vig = (np.clip((r - 0.55) / 0.75, 0, 1) ** 1.6 * 255 * strength).astype(np.uint8)
    v = Image.new("RGBA", (W, H), BG_DEEP + (0,))
    v.putalpha(Image.fromarray(vig))
    img.alpha_composite(v)
    return img


@lru_cache(maxsize=None)
def scrim(kind, level):
    stops = {"hero": HERO_SCRIM, "msg": MSG_SCRIM, "start": START_SCRIM}[kind]
    k = level / LEVELS
    return scrim_layer([(y, a * k) for y, a in stops])


# --------------------------------------------------------------- captions
def parse_srt(path):
    def secs(stamp):
        h, m, rest = stamp.split(":")
        s, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    with open(path, encoding="utf-8") as f:
        blocks = re.split(r"\n\s*\n", f.read().strip())
    cues = []
    for b in blocks:
        lines = b.strip().splitlines()
        if len(lines) < 3:
            continue
        a, z = [x.strip() for x in lines[1].split("-->")]
        cues.append((secs(a), secs(z), "\n".join(lines[2:])))
    return cues


CUES = parse_srt(CAPTIONS_PATH)
START = EDIT["start_screen"]
START_END = out_time(START["until"])
# captions the start-screen title already says are not drawn twice
CUES = [c for c in CUES if c[1] > START_END + 0.1]

SUB_SIZE = 42
SUB_MAX_W = 820
SUB_LINE_H = 56


def wrap_balanced(text, fnt, max_w):
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    if d.textlength(text, font=fnt) <= max_w:
        return [text]
    words = text.split(" ")
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        wa, wb = d.textlength(a, font=fnt), d.textlength(b, font=fnt)
        if max(wa, wb) > max_w:
            continue
        score = abs(wa - wb) + (0 if wa <= wb else 40)
        if best is None or score < best[0]:
            best = (score, [a, b])
    if best is None:
        raise ValueError(f"caption too long for two lines: {text}")
    return best[1]


@lru_cache(maxsize=None)
def plain_sprite(text):
    fnt = manrope(SUB_SIZE, 560)
    lines = []
    for part in text.split("\n"):
        lines += wrap_balanced(part, fnt, SUB_MAX_W)
    if len(lines) > 2:
        raise ValueError(f"caption wraps to {len(lines)} lines: {text}")
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    wmax = max(d.textlength(l, font=fnt) for l in lines)
    img = Image.new("RGBA", (int(wmax) + 2 * HALO_PAD,
                             SUB_LINE_H * len(lines) + 2 * HALO_PAD), (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    for i, l in enumerate(lines):
        dd.text((img.width / 2, HALO_PAD + SUB_LINE_H * (i + 0.5)), l,
                font=fnt, fill=OFF, anchor="mm")
    return with_halo(img, 0.62, blur=9)


def runs(line):
    """'a <i>b</i> c' -> [(text, italic)]"""
    out, italic = [], False
    for tok in re.split(r"(</?i>)", line):
        if tok == "<i>":
            italic = True
        elif tok == "</i>":
            italic = False
        elif tok:
            out.append((tok, italic))
    return out


@lru_cache(maxsize=None)
def hero_sprite(text, size=66, max_w=900):
    """Highlighted line: Instrument Serif, the <i> words in sage italic.
    Shrinks to fit rather than wrapping to a third line."""
    lines = text.replace("<i>\n", "\n<i>").split("\n")
    # keep italic state across an explicit line break
    fixed, open_i = [], False
    for l in lines:
        l2 = ("<i>" if open_i else "") + l
        open_i = l2.count("<i>") > l2.count("</i>")
        fixed.append(l2 + ("</i>" if open_i else ""))
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    while True:
        reg, ital = serif(size), serif(size, True)
        widths = [sum(d.textlength(t, font=ital if it else reg) for t, it in runs(l))
                  for l in fixed]
        if max(widths) <= max_w or size <= 48:
            break
        size -= 2
    line_h = int(size * 1.14)
    ss = 2
    img = Image.new("RGBA", (int((max(widths) + 2 * HALO_PAD) * ss),
                             int((line_h * len(fixed) + 2 * HALO_PAD) * ss)),
                    (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    reg2, ital2 = serif(size * ss), serif(size * ss, True)
    for i, (l, w) in enumerate(zip(fixed, widths)):
        x = (img.width / ss - w) / 2
        y = HALO_PAD + line_h * (i + 0.5)
        for t, it in runs(l):
            dd.text((x * ss, y * ss), t, font=ital2 if it else reg2,
                    fill=SAGE_BRIGHT if it else OFF, anchor="lm")
            x += d.textlength(t, font=ital if it else reg)
    img = img.resize((img.width // ss, img.height // ss), Image.LANCZOS)
    return with_halo(img, 0.6, blur=12)


def is_hero(text):
    return "<i>" in text


def caption_states(t):
    """[(sprite, cy, alpha)] for captions visible at t. Back-to-back plain
    cues cut; highlighted lines fade and settle upward a few px."""
    out = []
    for i, (s, e, text) in enumerate(CUES):
        if not (s - 0.5 <= t <= e + 0.5):
            continue
        prev_end = CUES[i - 1][1] if i else -1.0
        next_start = CUES[i + 1][0] if i + 1 < len(CUES) else 1e9
        if is_hero(text):
            a = env(t, s - 0.10, e + 0.10, 0.40, 0.45)
            rise = 8 * (1 - ease_out((t - s + 0.1) / 0.8))
            out.append((hero_sprite(text), HERO_Y + rise, a))
        else:
            fin = 0.14 if s - prev_end > 0.15 else 0.0
            fout = 0.16 if next_start - e > 0.15 else 0.0
            a = env(t, s - 0.06 if fin else s, e + 0.04 if fout else e, fin, fout)
            out.append((plain_sprite(text), SUB_Y, a))
    return out


def hero_presence(t):
    p = 0.0
    for s, e, text in CUES:
        if is_hero(text):
            p = max(p, env(t, s - 0.4, e + 0.4, 0.6, 0.6))
    return p


# ------------------------------------------------------------ start screen
def title_runs(line, ital_fill=SAGE):
    """'plain |accent|' -> [(text, font_italic, fill)] (cover syntax)."""
    out = []
    for k, part in enumerate(line.split("|")):
        if part:
            out.append((part, k % 2 == 1, ital_fill if k % 2 else OFF))
    return out


@lru_cache(maxsize=None)
def title_block(lines, size=72, line_h=92):
    """Left-aligned cover headline with the clay rule above it. Returns
    (sprite, top-left x, top-left y) in frame coordinates."""
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    reg, ital = serif(size), serif(size, True)
    block_h = line_h * len(lines)
    top_y = 1480 - block_h
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    rule_y = top_y - 46
    dd.line([(90, rule_y), (156, rule_y)], fill=CLAY, width=3)
    for i, line in enumerate(lines):
        x = 90
        for txt, it, fill in title_runs(line):
            fnt = ital if it else reg
            dd.text((x, top_y + i * line_h), txt, font=fnt, fill=fill)
            x += d.textlength(txt, font=fnt)
    return img


@lru_cache(maxsize=None)
def eyebrow():
    return label(START["eyebrow"], 26, 700, OFF, 7.5, halo=0.5)


def start_alpha(t):
    """Full strength on frame one (it doubles as the reel's first frame),
    gone just as the first caption arrives."""
    return 1.0 - smooth((t - (START_END - 0.30)) / 0.42)


def draw_start(canvas, t):
    a = start_alpha(t)
    if a <= 0:
        return
    canvas.alpha_composite(scrim("start", round(a * LEVELS)))
    paste(canvas, eyebrow(), CX, GRID_TOP + 58 + eyebrow().height / 2 - HALO_PAD, a)
    block = title_block(tuple(START["title"]))
    if a < 0.997:
        block = block.copy()
        block.putalpha(block.getchannel("A").point(lambda v: int(v * a)))
    canvas.alpha_composite(block)


# ------------------------------------------------------- message bubbles
MSG = EDIT["messages"]
M_FIRST, M_READ = out_time(MSG["first"]), out_time(MSG["read"])
M_SECOND, M_OUT = out_time(MSG["second"]), out_time(MSG["out"])
BUBBLE_R = 40              # right edge of the bubble column
BUBBLE_X1 = 896


@lru_cache(maxsize=None)
def bubble(w, h, bars):
    """Outgoing message: sage bubble, placeholder bars instead of words --
    it stands for any message, not a real one."""
    ss = 3
    img = Image.new("RGBA", ((w + 2 * HALO_PAD) * ss, (h + 2 * HALO_PAD) * ss),
                    (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    p = HALO_PAD * ss
    fill = (88, 108, 86, 238)
    d.rounded_rectangle([p, p, p + w * ss, p + h * ss], radius=34 * ss, fill=fill)
    # little tail, bottom right
    d.polygon([(p + (w - 26) * ss, p + (h - 22) * ss), (p + (w + 8) * ss, p + h * ss),
               (p + (w - 46) * ss, p + h * ss)], fill=fill)
    by = p + 30 * ss
    for bw in bars:
        d.rounded_rectangle([p + 34 * ss, by, p + (34 + bw) * ss, by + 12 * ss],
                            radius=6 * ss, fill=OFF + (150,))
        by += 26 * ss
    img = img.resize((img.width // ss, img.height // ss), Image.LANCZOS)
    return with_halo(img, 0.45, blur=14)


def draw_messages(canvas, t):
    out_a = env(t, M_FIRST - 0.2, M_OUT, 0.01, 0.55)
    if out_a <= 0:
        return
    b1 = bubble(430, 86, (330, 210))
    b2 = bubble(330, 60, (230,))
    y1 = 1205
    y2 = 1305

    a1 = smooth((t - M_FIRST) / 0.35) * out_a
    s1 = 0.94 + 0.06 * ease_out((t - M_FIRST) / 0.45)
    paste(canvas, b1, BUBBLE_X1 - 215, y1, a1, s1)

    second = t >= M_SECOND
    if not second:
        # receipt under the first bubble: Delivered, then Read -- and nothing
        delivered = env(t, M_FIRST + 0.5, M_READ + 0.05, 0.3, 0.2)
        read = smooth((t - M_READ) / 0.3)
        paste(canvas, label("DELIVERED", 17, 700, MUTED, 3.4, 0.5),
              BUBBLE_X1 - 4, y1 + 70, delivered * out_a, anchor="rm")
        paste(canvas, label("READ", 17, 700, MUTED, 3.4, 0.5),
              BUBBLE_X1 - 4, y1 + 70, read * out_a, anchor="rm")
    else:
        a2 = smooth((t - M_SECOND) / 0.35) * out_a
        s2 = 0.94 + 0.06 * ease_out((t - M_SECOND) / 0.45)
        paste(canvas, b2, BUBBLE_X1 - 165, y2, a2, s2)
        paste(canvas, label("DELIVERED", 17, 700, MUTED, 3.4, 0.5),
              BUBBLE_X1 - 4, y2 + 58, smooth((t - M_SECOND - 0.6) / 0.3) * out_a,
              anchor="rm")


def msg_presence(t):
    return env(t, M_FIRST - 0.5, M_OUT + 0.3, 0.6, 0.6)


# ---------------------------------------------------------------- end card
def radial_glow(size, color, peak_alpha):
    layer = Image.new("L", (64, 64), 0)
    px = layer.load()
    c = 31.5
    for yy in range(64):
        for xx in range(64):
            r = math.hypot(xx - c, yy - c) / c
            px[xx, yy] = int(peak_alpha * max(0.0, 1.0 - r) ** 2.2)
    glow = Image.new("RGBA", (size, size), color + (0,))
    glow.putalpha(layer.resize((size, size), Image.BICUBIC))
    return glow


@lru_cache(maxsize=None)
def end_card():
    """Same card as the founder and quiet-breathing videos."""
    img = Image.new("RGBA", (W, H), BG + (255,))
    cy = 930
    img.alpha_composite(radial_glow(1600, (92, 112, 88), 66), (CX - 800, cy - 800))
    d = ImageDraw.Draw(img)
    d.text((CX, cy), "The Breath Reset", font=serif(104), fill=OFF, anchor="mm")
    d.text((CX, cy + 104), "Relax. Retrain. Release.", font=serif(58, True),
           fill=SAGE, anchor="mm")
    rule_y = cy + 186
    d.line([(CX - 46, rule_y), (CX + 46, rule_y)], fill=SAGE_DARK, width=2)
    sub = manrope(27, 600)
    for i, line in enumerate(["Follow for simple breathwork practices",
                              "and nervous system education."]):
        d.text((CX, rule_y + 62 + i * 40), line, font=sub, fill=(172, 164, 150),
               anchor="mm")
    return img


# ------------------------------------------------------------------ b-roll
class BRoll:
    """Optional cutaways from edit.json. Each clip is cover-fitted to 9:16,
    given the same grade, and crossfaded in and out over the talking head;
    the voice keeps running underneath."""
    XF = 0.4

    def __init__(self, spec):
        self.path = os.path.join(REEL_DIR, spec["file"])
        self.t0 = out_time(spec["at"])
        self.t1 = self.t0 + float(spec["dur"])
        self.src_in = float(spec.get("in", 0.0))
        self.proc = None
        self.frame = None
        self.n_read = 0

    def alpha(self, t):
        return env(t, self.t0, self.t1, self.XF, self.XF)

    def get(self, t, size):
        if self.proc is None:
            w, h = size
            vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
                  f"crop={w}:{h},fps={FPS},{grade_filter()},format=rgb24")
            self.proc = subprocess.Popen(
                ["ffmpeg", "-v", "error", "-ss", f"{self.src_in:.3f}", "-i", self.path,
                 "-t", f"{self.t1 - self.t0 + 1:.3f}", "-vf", vf, "-an",
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
            self.size = size
        want = int((t - self.t0) * FPS)
        w, h = self.size
        while self.n_read <= want:
            buf = self.proc.stdout.read(w * h * 3)
            if len(buf) < w * h * 3:
                break
            self.frame = Image.frombuffer("RGB", (w, h), buf, "raw", "RGB", 0, 1)
            self.n_read += 1
        return self.frame


BROLL = [BRoll(b) for b in EDIT.get("broll", []) if b.get("file")]
for b in BROLL:
    if not os.path.exists(b.path):
        sys.exit(f"b-roll file missing: {b.path}")


# ------------------------------------------------------------------ source
def grade_filter():
    g = EDIT["grade"]
    w = float(g.get("warmth", 0.0))
    return (f"eq=saturation={g['saturation']}:contrast={g['contrast']}"
            f":brightness={g['brightness']},"
            f"colorbalance=rs={w * 0.5:.3f}:bs={-w * 0.6:.3f}"
            f":rm={w * 0.35:.3f}:bm={-w * 0.45:.3f}:pl=1")


def decode_cmd(start=None, frames=None):
    vf = (f"unsharp=5:5:0.45:5:5:0,{grade_filter()},format=rgb24")
    cmd = ["ffmpeg", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", SOURCE, "-vf", vf, "-an"]
    if frames is not None:
        cmd += ["-frames:v", str(frames)]
    return cmd + ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"]


FRAME_BYTES = SRC_W * SRC_H * 3
SETTLE_IDX = int(round(TAIL["settle_frame"] * FPS))


class Reader:
    """Sequential source reader that can hand back frame i and i+1 (for the
    slowed pauses) and keeps the settle frame for the tail."""

    def __init__(self):
        self.proc = subprocess.Popen(decode_cmd(), stdout=subprocess.PIPE)
        self.frames = {}
        self.next_idx = 0
        self.settle = None
        self.last = None

    def _read_one(self):
        buf = self.proc.stdout.read(FRAME_BYTES)
        if len(buf) < FRAME_BYTES:
            return False
        arr = np.frombuffer(buf, np.uint8).reshape(SRC_H, SRC_W, 3)
        self.frames[self.next_idx] = arr
        if self.next_idx == SETTLE_IDX:
            self.settle = arr
        self.last = arr
        self.next_idx += 1
        return True

    def get(self, idx):
        while self.next_idx <= idx:
            if not self._read_one():
                break
        for k in [k for k in self.frames if k < idx - 2]:
            del self.frames[k]
        return self.frames.get(idx, self.last)


def source_array(reader, t):
    """Graded source pixels for output time t (blended inside holds)."""
    if t >= SPEECH_OUT_END:
        last = reader.get(10 ** 9)
        u = smooth((t - SPEECH_OUT_END) / TAIL["settle_xfade"])
        settle = reader.settle if reader.settle is not None else last
        if u >= 1:
            return settle
        return (last * (1 - u) + settle * u).astype(np.uint8)
    f = src_time(t) * FPS
    if in_hold(t):
        i = int(math.floor(f))
        u = f - i
        a, b = reader.get(i), reader.get(i + 1)
        if u < 0.02:
            return a
        return (a.astype(np.float32) * (1 - u) + b.astype(np.float32) * u).astype(np.uint8)
    return reader.get(int(round(f)))


def reframe(arr, t):
    zoom, dx = framing(t)
    img = Image.fromarray(arr)
    return img.resize((W, H), Image.LANCZOS, box=crop_box(zoom, dx))


# ------------------------------------------------------------------ compose
def compose(frame, t):
    """frame: reframed RGB talking head at t -> finished RGB frame."""
    img = frame.convert("RGBA")
    for b in BROLL:
        a = b.alpha(t)
        if a > 0:
            clip = b.get(t, (W, H))
            if clip is not None:
                img = Image.blend(img, clip.convert("RGBA"), a)

    img.alpha_composite(base_overlay())
    hero = hero_presence(t)
    if hero > 0.01:
        img.alpha_composite(scrim("hero", round(hero * LEVELS)))
    msg = msg_presence(t)
    if msg > 0.01:
        img.alpha_composite(scrim("msg", round(msg * LEVELS)))

    draw_start(img, t)
    draw_messages(img, t)
    for sprite, cy, a in caption_states(t):
        paste(img, sprite, CX, cy, a)

    dark = smooth((t - (HOLD_END - TAIL["fade_to_dark"])) / TAIL["fade_to_dark"])
    if dark > 0:
        img.alpha_composite(Image.new("RGBA", (W, H), BG + (int(255 * dark),)))
    ec = smooth((t - END_CARD_START) / 0.9)
    if ec > 0:
        card = end_card()
        if ec < 1:
            card = card.copy()
            card.putalpha(int(255 * ec))
        img.alpha_composite(card)
    return img.convert("RGB")


# -------------------------------------------------------------------- render
def render(preview=False):
    if not os.path.exists(MIX):
        sys.exit("Run tmp/make_biggest_lesson_audio.py first (mix missing)")
    out_h = 960 if preview else H
    out_w = out_h * 9 // 16
    out_path = FINAL.replace(".mp4", "-preview.mp4") if preview else FINAL
    enc_vf = (f"scale={out_w}:{out_h}:flags=lanczos:out_color_matrix=bt709:out_range=tv,"
              "format=yuv420p")
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-i", MIX,
         "-map", "0:v", "-map", "1:a", "-vf", enc_vf,
         "-c:v", "libx264", "-preset", "veryfast" if preview else "slow",
         "-crf", "23" if preview else "17", "-profile:v", "high",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-t", f"{TOTAL_DUR:.3f}",
         "-movflags", "+faststart", out_path],
        stdin=subprocess.PIPE)
    reader = Reader()
    n_frames = int(round(TOTAL_DUR * FPS))
    t0 = time.time()
    for i in range(n_frames):
        t = i / FPS
        if t >= END_CARD_START + 1.0:
            frame = Image.new("RGB", (W, H))          # fully under the card
        else:
            frame = reframe(source_array(reader, t), t)
        enc.stdin.write(compose(frame, t).tobytes())
        if i % 300 == 0:
            print(f"  {t:6.1f}s / {TOTAL_DUR:.0f}s  ({time.time() - t0:4.0f}s elapsed)",
                  flush=True)
    enc.stdin.close()
    enc.wait()
    reader.proc.kill()
    mb = os.path.getsize(out_path) / 1e6
    print(f"saved {os.path.relpath(out_path, ROOT)}  ({mb:.1f} MB, "
          f"{time.time() - t0:.0f}s)")


def grab(src_t):
    raw = subprocess.run(decode_cmd(start=min(src_t, SRC_DUR - 0.05), frames=1),
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw[:FRAME_BYTES], np.uint8).reshape(SRC_H, SRC_W, 3)


def stills(times):
    os.makedirs(STILL_DIR, exist_ok=True)
    for t in times:
        if t >= SPEECH_OUT_END:
            arr = grab(TAIL["settle_frame"])
        else:
            arr = grab(src_time(t))
        out = os.path.join(STILL_DIR, f"t{t:06.2f}.png")
        compose(reframe(arr, t), t).resize((540, 960), Image.LANCZOS).save(out)
        print("saved", os.path.relpath(out, ROOT))


# --------------------------------------------------------------------- cover
COVER_TIME = float(os.environ.get("BL_COVER_TIME", TAIL["settle_frame"]))
COVER_HEADLINE = ("I go into my head", "|to avoid feeling.|")


def cover():
    """Instagram cover: a graded still, type inside the 4:5 grid crop --
    same treatment as the quiet-breathing and founder covers."""
    from PIL import ImageEnhance
    arr = grab(COVER_TIME)
    z, dx = framing(out_time(min(COVER_TIME, SRC_DUR - 0.1)))
    img = Image.fromarray(arr).resize((W, H), Image.LANCZOS, box=crop_box(z, dx))
    img = ImageEnhance.Brightness(img).enhance(0.84).convert("RGBA")
    img.alpha_composite(base_overlay())
    img.alpha_composite(scrim("start", LEVELS))
    paste(img, eyebrow(), CX, GRID_TOP + 58 + eyebrow().height / 2 - HALO_PAD)
    img.alpha_composite(title_block(COVER_HEADLINE))
    img.convert("RGB").save(COVER, "PNG")
    print("saved", os.path.relpath(COVER, ROOT))


DEFAULT_STILLS = [0.0, 1.5, 2.8, 5.0, 10.0, 22.5, 46.4, 55.0, 69.5, 84.0,
                  87.5, 92.0, 100.5, 108.0, 129.0, 140.0, 144.5, 145.6, 146.4,
                  149.0]

if __name__ == "__main__":
    for _, _, text in CUES:
        hero_sprite(text) if is_hero(text) else plain_sprite(text)
    print(f"{len(CUES)} captions, total {TOTAL_DUR:.2f}s "
          f"(speech ends {SPEECH_OUT_END:.2f}s, end card {END_CARD_START:.2f}s)")
    spec = os.environ.get("BL_STILLS")
    if spec:
        stills(DEFAULT_STILLS if spec == "1" else [float(x) for x in spec.split(",")])
    elif os.environ.get("BL_COVER"):
        cover()
    else:
        render(preview=bool(os.environ.get("BL_PREVIEW")))
