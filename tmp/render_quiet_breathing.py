#!/usr/bin/env python3
"""
Quiet breathing (Retrain) -- vertical talking-head render with annotations,
subtitles and end card.

  python3 tmp/make_quiet_breathing_audio.py        # music bed + mix (first)
  python3 tmp/render_quiet_breathing.py            # full render
  QB_STILLS=1 python3 tmp/render_quiet_breathing.py        # check stills
  QB_STILLS=14.9,41.5 python3 tmp/render_quiet_breathing.py  # specific times
  QB_PREVIEW=1 python3 tmp/render_quiet_breathing.py       # fast 540p proof

Source is 1620x1080 (3:2), so it is reframed to 9:16 with a fixed full-height
crop on the face (centre x ~760, measured -- he barely moves) and upscaled to
1080x1920. Frames are decoded by ffmpeg, composited here with Pillow, and
piped back to ffmpeg for the encode.

Visual system follows the founder video (render_founder_v2.py): warm-black
scrims, Instrument Serif hero lines with a sage italic turn, tracked Manrope
caps for labels. Colour code for the science: O2 = sage, CO2 = clay.

Layout bands in the 1080x1920 frame (measured from the reframed footage):
  face            y ~260-1010      never covered
  annotation zone y ~1150-1400     upper chest, under the collar
  subtitles       y ~1420-1530     lower-middle, above Instagram's caption UI
  x 90-950                         clear of the Reels action column

Subtitles are hidden while a hero line or word-overlay is saying the same
words -- two copies of one sentence on screen reads as over-produced.

Every timing below comes from tmp/quiet-breathing-words.json (faster-whisper
word stamps, see transcribe_quiet_breathing.py) checked against the pause
map. If the source is re-cut, re-run the transcript and re-time everything.

Outputs -> assets/social/youtube/retrain/quiet-breathing/
"""
import math
import os
import subprocess
import sys
import time
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

OUT_DIR = os.path.join(ROOT, "assets", "social", "youtube", "retrain",
                       "quiet-breathing")
SOURCE = os.path.join(OUT_DIR, "quiet-breathing-source.mp4")
FINAL = os.path.join(OUT_DIR, "quiet-breathing-final.mp4")
MIX = os.path.join(HERE, "quiet-breathing-mix.wav")
STILL_DIR = os.path.join(HERE, "quiet-breathing-frames")

W, H = 1080, 1920
CX = W // 2
FPS = 30

# Full-height 9:16 crop of the 1620x1080 source, centred on the face.
CROP_W, CROP_X = 608, 456

SRC_DUR = 117.05
TOTAL_DUR = 123.0          # must match DUR in make_quiet_breathing_audio.py
FADE_TO_DARK = (117.15, 118.8)
END_CARD = (118.85, 119.75)

# palette -- warm-black system (styles.css / founder video)
BG = (16, 13, 11)
BG_DEEP = (10, 8, 7)
OFF = (239, 231, 217)
MUTED = (198, 190, 176)
SAGE = (143, 165, 138)
SAGE_BRIGHT = (179, 199, 172)
SAGE_DARK = (95, 116, 94)
CLAY = (209, 144, 115)

# Lifted variants: brand sage/clay go muddy over the olive shirt.
O2_COL = (198, 218, 190)
CO2_COL = (236, 172, 140)

ZONE_Y = 1290              # centre of the annotation band
SUB_Y = 1478               # centre of the subtitle block

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


def ease_io(x):
    x = clamp(x)
    return 0.5 - 0.5 * math.cos(math.pi * x)


def env(t, start, end, fin=0.45, fout=0.45):
    """0..1 presence: fade in from `start`, fade out ending at `end`.
    A zero fade is a hard cut."""
    if t < start or t >= end:
        return 0.0
    a = smooth((t - start) / fin) if fin > 0 else 1.0
    b = smooth((end - t) / fout) if fout > 0 else 1.0
    return a * b


def lerp(a, b, u):
    return a + (b - a) * u


# ----------------------------------------------------------------- sprites
HALO_PAD = 28


def with_halo(content, strength=0.55, blur=11):
    """Dark blurred copy of the content's own alpha underneath it -- same
    support trick as the founder lower third, holds up over the olive shirt."""
    halo = Image.new("RGBA", content.size, BG_DEEP + (0,))
    halo.putalpha(content.getchannel("A").point(lambda v: int(v * strength)))
    out = halo.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(content)
    return out


def tracked_width(fnt, text, tracking):
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    return sum(d.textlength(ch, font=fnt) + tracking for ch in text) - tracking


@lru_cache(maxsize=None)
def label(text, size=28, weight=650, fill=OFF, tracking=None, halo=0.6):
    """Tracked caps label sprite (Manrope)."""
    fnt = manrope(size, weight)
    tracking = size * 0.2 if tracking is None else tracking
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


def _seg_width(d, seg):
    kind = seg[0]
    if kind == "text":
        _, txt, fnt, _ = seg
        return d.textlength(txt, font=fnt)
    if kind == "neq":
        return seg[1] * 0.62
    if kind == "sub2":
        return d.textlength("2", font=seg[1])
    if kind == "space":
        return seg[1]
    raise ValueError(kind)


@lru_cache(maxsize=None)
def rich(segments, halo=0.55):
    """One line of mixed runs. Segments (hashable tuples):
         ("text", str, font, fill)
         ("neq", size, fill)         -- hand-drawn not-equal sign
         ("sub2", font, fill)        -- subscript 2 (Instrument Serif lacks one)
         ("space", px)
    Instrument Serif has no glyphs for subscript 2 or the not-equal sign, so
    those are drawn, not typed."""
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    ref = next(s[2] for s in segments if s[0] == "text")
    asc, desc = ref.getmetrics()
    width = sum(_seg_width(d, s) for s in segments)
    ss = 3
    img = Image.new("RGBA", (int((width + 2 * HALO_PAD) * ss),
                             int((asc + desc + 2 * HALO_PAD) * ss)), (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    x = HALO_PAD
    base = HALO_PAD + asc                     # baseline
    for s in segments:
        kind = s[0]
        if kind == "text":
            _, txt, fnt, fill = s
            big = ImageFont.truetype(fnt.path, fnt.size * ss)
            dd.text((x * ss, base * ss), txt, font=big, fill=fill, anchor="ls")
        elif kind == "neq":
            size, fill = s[1], s[2]
            w = size * 0.46
            x0 = x + size * 0.08
            mid = base - size * 0.30
            gap = size * 0.085
            lw = max(2, size * 0.045)
            for yy in (mid - gap, mid + gap):
                dd.line([(x0 * ss, yy * ss), ((x0 + w) * ss, yy * ss)],
                        fill=fill, width=int(lw * ss))
            dd.line([((x0 + w * 0.68) * ss, (mid - size * 0.25) * ss),
                     ((x0 + w * 0.32) * ss, (mid + size * 0.25) * ss)],
                    fill=fill, width=int(lw * ss))
        elif kind == "sub2":
            fnt, fill = s[1], s[2]
            small = ImageFont.truetype(fnt.path, int(fnt.size * 0.62 * ss))
            dd.text((x * ss, (base + fnt.size * 0.12) * ss), "2", font=small,
                    fill=fill, anchor="ls")
        x += _seg_width(d, s)
    img = img.resize((img.width // ss, img.height // ss), Image.LANCZOS)
    return with_halo(img, halo) if halo else img


def T(txt, fnt, fill):
    return ("text", txt, fnt, fill)


def paste(canvas, sprite, cx, cy, alpha=1.0, scale=1.0, anchor="mm"):
    """Composite `sprite` centred (or left-anchored) at cx, cy."""
    if alpha <= 0.003:
        return
    s = sprite
    if abs(scale - 1.0) > 1e-3:
        s = s.resize((max(1, int(s.width * scale)), max(1, int(s.height * scale))),
                     Image.BICUBIC)
    if alpha < 0.997:
        s = s.copy()
        a = s.getchannel("A").point(lambda v: int(v * alpha))
        s.putalpha(a)
    if anchor == "lm":
        x = int(round(cx - HALO_PAD * scale))
    else:
        x = int(round(cx - s.width / 2))
    y = int(round(cy - s.height / 2))
    canvas.alpha_composite(s, (max(0, x), max(0, y)),
                           (max(0, -x), max(0, -y)))


class Strokes:
    """Supersampled vector layer for thin animated lines -- PIL's own lines
    are aliased, which is what makes overlay graphics look cheap."""

    def __init__(self, box, ss=3):
        self.x0, self.y0, x1, y1 = box
        self.ss = ss
        self.img = Image.new("RGBA", ((x1 - self.x0) * ss, (y1 - self.y0) * ss),
                             (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def _p(self, pts):
        return [((x - self.x0) * self.ss, (y - self.y0) * self.ss) for x, y in pts]

    def line(self, pts, fill, width=2.0, alpha=1.0):
        col = fill + (int(255 * clamp(alpha)),)
        w = max(1, int(width * self.ss))
        self.d.line(self._p(pts), fill=col, width=w, joint="curve")
        r = w / 2
        for px, py in (self._p(pts)[0], self._p(pts)[-1]):
            self.d.ellipse([px - r, py - r, px + r, py + r], fill=col)

    def circle(self, cx, cy, r, fill, width=2.0, alpha=1.0):
        col = fill + (int(255 * clamp(alpha)),)
        (px, py), = self._p([(cx, cy)])
        rr = r * self.ss
        self.d.ellipse([px - rr, py - rr, px + rr, py + rr], outline=col,
                       width=max(1, int(width * self.ss)))

    def dot(self, cx, cy, r, fill, alpha=1.0):
        col = fill + (int(255 * clamp(alpha)),)
        (px, py), = self._p([(cx, cy)])
        rr = r * self.ss
        self.d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=col)

    def composite(self, canvas, halo=0.0):
        img = self.img.resize((self.img.width // self.ss,
                               self.img.height // self.ss), Image.LANCZOS)
        if halo:
            img = with_halo(img, halo, blur=7)
        canvas.alpha_composite(img, (self.x0, self.y0))


def partial(pts, u):
    """First fraction `u` of a polyline, by length -- for draw-on strokes."""
    if u >= 1:
        return pts
    segs = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(segs) * clamp(u)
    out = [pts[0]]
    for i, L in enumerate(segs):
        if total <= L:
            f = total / L if L else 0
            out.append((lerp(pts[i][0], pts[i + 1][0], f),
                        lerp(pts[i][1], pts[i + 1][1], f)))
            return out
        total -= L
        out.append(pts[i + 1])
    return out


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


# The shirt is bright olive (~183,185,174), so off-white type needs the area
# under it pulled down. The base ramp is always on (it reads as a grade);
# the boost rides in with each annotation.
BASE_SCRIM = [(0.0, 0), (0.56, 0), (0.68, 70), (0.77, 118), (0.88, 128), (1.0, 140)]
BOOST_SCRIM = [(0.0, 0), (0.52, 0), (0.61, 118), (0.72, 104), (0.84, 34), (1.0, 0)]
HERO_SCRIM = [(0.0, 0), (0.50, 0), (0.60, 120), (0.74, 110), (0.86, 40), (1.0, 0)]

SCRIM_LEVELS = 24


@lru_cache(maxsize=None)
def scrim(kind, level):
    stops = {"base": BASE_SCRIM, "boost": BOOST_SCRIM, "hero": HERO_SCRIM}[kind]
    k = level / SCRIM_LEVELS
    return scrim_layer([(y, a * k) for y, a in stops])


# --------------------------------------------------------------- subtitles
# (start, end, text). Text follows what is actually said, not the script.
SUBS = [
    (2.38, 3.85, "Was it something like this?"),
    (6.60, 8.40, "Most of us hear ‘deep breath’ and think…"),
    (12.20, 14.25, "But if the goal is to calm yourself down,"),
    (16.50, 18.02, "So your blood is probably already carrying"),
    (18.02, 19.95, "close to as much oxygen as it can."),
    (20.40, 21.85, "For a healthy individual,"),
    (21.90, 25.40, "oxygen saturation sits around 95–99%."),
    (25.45, 27.42, "So taking bigger and bigger breaths"),
    (27.42, 29.75, "doesn’t necessarily mean you’re getting more useful oxygen."),
    (30.30, 33.25, "In fact, if you breathe more than your body actually needs,"),
    (33.28, 36.10, "you can breathe out too much carbon dioxide."),
    (38.75, 40.82, "If CO₂ drops too low,"),
    (40.85, 42.85, "the blood vessels in the brain constrict."),
    (42.90, 45.28, "Which is one reason over-breathing can make you feel"),
    (49.10, 52.02, "CO₂ also helps oxygen move from the blood into the tissues"),
    (52.02, 54.65, "where your body can actually use it."),
    (54.80, 59.00, "So rather than trying to take a huge breath, the goal is often to…"),
    (66.55, 68.45, "Quiet breathing helps you breathe closer"),
    (68.45, 70.10, "to what your body actually needs,"),
    (70.25, 72.30, "which helps maintain a better balance"),
    (72.30, 74.45, "between oxygen and carbon dioxide."),
    (80.40, 82.00, "Breathe gently through the nose."),
    (82.30, 85.65, "Let the belly and the lower ribs expand naturally."),
    (85.90, 87.75, "Keep your shoulders relaxed."),
    (88.80, 92.35, "And don’t try to fill your lungs all the way."),
    (93.65, 95.40, "Let’s try one together."),
    (97.20, 99.85, "Gentle inhale through the nose…"),
    (102.85, 104.45, "Easy exhale…"),
    (105.85, 107.55, "No forcing."),
    (109.80, 112.55, "Next time someone tells you to take a deep breath, remember:"),
]

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
        # prefer balanced lines, slightly shorter top line
        score = abs(wa - wb) + (0 if wa <= wb else 40)
        if best is None or score < best[0]:
            best = (score, [a, b])
    if best is None:
        raise ValueError(f"subtitle too long for two lines: {text}")
    return best[1]


@lru_cache(maxsize=None)
def subtitle_sprite(text):
    fnt = manrope(SUB_SIZE, 560)
    lines = wrap_balanced(text, fnt, SUB_MAX_W)
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    wmax = max(d.textlength(l, font=fnt) for l in lines)
    hgt = SUB_LINE_H * len(lines)
    img = Image.new("RGBA", (int(wmax) + 2 * HALO_PAD, hgt + 2 * HALO_PAD),
                    (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    for i, l in enumerate(lines):
        dd.text((img.width / 2, HALO_PAD + SUB_LINE_H * (i + 0.5)), l,
                font=fnt, fill=OFF, anchor="mm")
    return with_halo(img, 0.62, blur=9)


def draw_subtitles(canvas, t):
    # Back-to-back cues cut rather than crossfade, so two never overlap.
    for i, (s, e, text) in enumerate(SUBS):
        prev_end = SUBS[i - 1][1] if i else -1.0
        next_start = SUBS[i + 1][0] if i + 1 < len(SUBS) else 1e9
        fin = 0.14 if s - prev_end > 0.15 else 0.0
        fout = 0.16 if next_start - e > 0.15 else 0.0
        a = env(t, s - 0.06 if fin else s, e + 0.04 if fout else e, fin, fout)
        if a > 0:
            paste(canvas, subtitle_sprite(text), CX, SUB_Y, a)


# ---------------------------------------------------------------- overlays
# Each overlay: (start, end, kind, draw_fn). kind drives the scrim boost:
# "label" (small), "graphic" (diagram), "hero" (large serif), "breath".
OVERLAYS = []


def overlay(start, end, kind="label"):
    def deco(fn):
        OVERLAYS.append((start, end, kind, fn))
        return fn
    return deco


def rise(t, start, px=10, dur=0.6):
    """Small upward settle on entry."""
    return px * (1 - ease_out((t - start) / dur))


# 1 -- "Take a deep breath for me." ----------------------------------------
@overlay(0.25, 1.95)
def o_take(c, t):
    a = env(t, 0.25, 1.95, 0.60, 0.50)
    paste(c, label("TAKE A DEEP BREATH", 31, 650), CX, ZONE_Y + rise(t, 0.25, 8, 0.9), a)


# Shoulder contour (left side, read off the reframed footage at rest) and how
# far each point rose at the top of the demo breath. Right side mirrors about
# the face centre; the hand hides it in the footage.
SHOULDER_X = [0, 60, 120, 180, 240, 300]
SHOULDER_Y = [1168, 1150, 1128, 1104, 1080, 1058]
SHOULDER_LIFT = [135, 122, 104, 86, 70, 56]
# measured lift fraction over the demo (3.8-5.2s), sampled every 0.1s
DEMO_LIFT = [0, 0.08, 0.30, 0.46, 0.59, 0.74, 0.83, 0.88, 0.97, 1.0, 0.98,
             0.90, 0.63, 0.16, 0.03]
SHOULDER_GAP = 24          # line sits just above the shirt edge, not on it


def demo_lift(t):
    u = (t - 3.8) / 0.1
    if u <= 0 or u >= len(DEMO_LIFT) - 1:
        return 0.0
    i = int(u)
    return lerp(DEMO_LIFT[i], DEMO_LIFT[i + 1], u - i)


def shoulder_pts(lift, side, drop=0.0):
    pts = []
    for x, y, d in zip(SHOULDER_X, SHOULDER_Y, SHOULDER_LIFT):
        yy = y - lift * d - SHOULDER_GAP + drop
        pts.append((x if side < 0 else W - x, yy))
    return pts


@overlay(3.75, 5.45, "graphic")
def o_demo(c, t):
    a = env(t, 3.75, 5.45, 0.30, 0.40)
    lift = demo_lift(t)
    draw = ease_out((t - 3.75) / 0.55)
    st = Strokes((0, 860, W, 1220))
    for side in (-1, 1):
        st.line(partial(shoulder_pts(lift, side), draw), O2_COL, 3.0, a)
    st.composite(c, halo=0.45)

    la = env(t, 3.95, 5.35, 0.35, 0.40)
    sy = SHOULDER_Y[2] - lift * SHOULDER_LIFT[2] - SHOULDER_GAP - 40
    paste(c, label("SHOULDERS", 22, 700, OFF, 4.4), 64, sy, la, anchor="lm")
    paste(c, label("CHEST", 22, 700, OFF, 4.4), CX, ZONE_Y + 30 - lift * 30, la)


# 2 -- "more air, bigger inhale, lift the chest" ----------------------------
WORDS_2 = [(8.46, "MORE AIR"), (9.42, "BIGGER INHALE"), (10.22, "LIFT THE CHEST")]


@overlay(8.40, 11.60)
def o_more_air(c, t):
    out = env(t, 0, 11.60, 0.01, 0.50)
    for i, (s, w) in enumerate(WORDS_2):
        if t < s:
            continue
        a = smooth((t - s) / 0.45) * out
        nxt = WORDS_2[i + 1][0] if i + 1 < len(WORDS_2) else None
        if nxt is not None and t > nxt:
            a *= lerp(1.0, 0.5, smooth((t - nxt) / 0.4))
        y = ZONE_Y - 60 + i * 60 + rise(t, s, 9, 0.55)
        paste(c, label(w, 30, 650), CX, y, a)


# 3 -- "bigger isn't always better" ------------------------------------------
@overlay(14.25, 16.10, "hero")
def o_bigger(c, t):
    a = env(t, 14.25, 16.10, 0.40, 0.45)
    s = 106
    spr = rich((T("Bigger", serif(s), OFF), ("space", 22), ("neq", s, SAGE_BRIGHT),
                ("space", 14), T("better.", serif(s, True), SAGE_BRIGHT)))
    paste(c, spr, CX, ZONE_Y, a, scale=lerp(0.985, 1.0, ease_out((t - 14.25) / 0.9)))


# 4 -- oxygen saturation -----------------------------------------------------
def pleth(x0, y0, w, h):
    """One beat of a pulse waveform as a polyline: upstroke, peak, notch."""
    pts = []
    for i in range(61):
        u = i / 60
        if u < 0.18:
            v = 0
        elif u < 0.32:
            v = smooth((u - 0.18) / 0.14)
        elif u < 0.52:
            v = 1 - 0.55 * smooth((u - 0.32) / 0.20)
        elif u < 0.60:
            v = 0.45 + 0.12 * math.sin(math.pi * (u - 0.52) / 0.08)
        else:
            v = 0.45 * (1 - smooth((u - 0.60) / 0.32))
        pts.append((x0 + u * w, y0 - v * h))
    return pts


@overlay(21.95, 24.60, "graphic")
def o_sat(c, t):
    a = env(t, 21.95, 24.60, 0.45, 0.45)
    dy = rise(t, 21.95, 8, 0.7)
    lab = label("O₂ SATURATION", 23, 700, OFF, 5)
    lw = lab.width - 2 * HALO_PAD
    icon_w = 58
    total = icon_w + 18 + lw
    x0 = CX - total / 2
    ly = ZONE_Y - 74 + dy
    st = Strokes((int(x0) - 4, int(ly) - 24, int(x0 + icon_w) + 6, int(ly) + 18))
    st.line(partial(pleth(x0, ly + 10, icon_w, 22), ease_io((t - 22.1) / 0.9)),
            O2_COL, 2.6, a)
    st.composite(c, halo=0.4)
    paste(c, lab, x0 + icon_w + 18, ly, a, anchor="lm")

    num = rich((T("95–99%", serif(112), OFF),))
    paste(c, num, CX, ZONE_Y + 18 + dy, a)
    paste(c, label("TYPICAL IN A HEALTHY ADULT", 18, 650, MUTED, 3.6), CX,
          ZONE_Y + 92 + dy, a * 0.9)


@overlay(26.25, 28.40, "graphic")
def o_near(c, t):
    a = env(t, 26.25, 28.40, 0.45, 0.45)
    dy = rise(t, 26.25, 8, 0.7)
    bw = 520
    x0, x1 = CX - bw / 2, CX + bw / 2
    by = ZONE_Y + 8 + dy
    fill = 0.97 * ease_out((t - 26.35) / 1.1)

    paste(c, rich((T("O", serif(64), O2_COL), ("sub2", serif(64), O2_COL))),
          x0 - 6, by - 52, a, anchor="lm")
    st = Strokes((int(x0) - 8, int(by) - 22, int(x1) + 8, int(by) + 22))
    st.line([(x0, by), (x1, by)], OFF, 2.2, 0.38 * a)
    st.line([(x1, by - 12), (x1, by + 12)], OFF, 2.2, 0.6 * a)
    if fill > 0.002:
        st.line([(x0, by), (x0 + bw * fill, by)], O2_COL, 4.5, a)
    st.composite(c, halo=0.45)
    paste(c, label("100%", 17, 650, MUTED, 2.5), x1, by - 34, a * 0.9)
    paste(c, label("ALREADY NEAR SATURATION", 22, 700, OFF, 4.6), CX, by + 52, a)


# 5 -- "breathe out too much carbon dioxide" --------------------------------
@overlay(33.30, 35.75, "graphic")
def o_co2_out(c, t):
    a = env(t, 33.30, 35.75, 0.35, 0.50)
    spr = label("CO₂", 27, 750, CO2_COL, 2, halo=0.75)
    spawn_every, life = 0.40, 1.7
    last_spawn = 34.70             # stop feeding the stream: CO2 running low
    k0 = int((t - 33.30 - life) / spawn_every) - 1
    for k in range(max(0, k0), int((t - 33.30) / spawn_every) + 1):
        s = 33.30 + k * spawn_every
        if s > last_spawn or t < s:
            continue
        u = (t - s) / life
        if u >= 1:
            continue
        side = -1 if k % 2 == 0 else 1
        lane = (k // 2) % 3
        x = CX + side * lerp(70, 400, ease_out(u))
        y = ZONE_Y - 34 + lane * 34
        fa = math.sin(math.pi * clamp(u)) ** 0.8
        # later molecules are fainter -- the stream is thinning out
        thin = lerp(1.0, 0.35, clamp((s - 33.3) / (last_spawn - 33.3)))
        paste(c, spr, x, y, a * fa * thin)


# 6 -- "And CO2 matters." -----------------------------------------------------
@overlay(36.70, 38.45, "hero")
def o_matters(c, t):
    a = env(t, 36.70, 38.45, 0.40, 0.40)
    s = 110
    spr = rich((T("CO", serif(s), OFF), ("sub2", serif(s), OFF), ("space", 26),
                T("matters.", serif(s, True), SAGE_BRIGHT)))
    paste(c, spr, CX, ZONE_Y, a, scale=lerp(0.985, 1.0, ease_out((t - 36.7) / 0.9)))


# 7 -- low CO2 -> cerebral vessels --------------------------------------------
def catmull(ctrl, closed=True, per=10):
    """Smooth curve through control points."""
    n = len(ctrl)
    pts = []
    rng_ = range(n) if closed else range(n - 1)
    for i in rng_:
        p0 = ctrl[(i - 1) % n] if closed else ctrl[max(i - 1, 0)]
        p1, p2 = ctrl[i], ctrl[(i + 1) % n]
        p3 = ctrl[(i + 2) % n] if closed else ctrl[min(i + 2, n - 1)]
        for k in range(per):
            u = k / per
            u2, u3 = u * u, u * u * u
            pts.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * u
                                    + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * u2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * u3)
                             for j in range(2)))
    pts.append(pts[0] if closed else ctrl[-1])
    return pts


# Side-view brain, unit coordinates (front is left). Deliberately plain:
# cerebrum, a small cerebellum and the stem -- enough to read, nothing more.
CEREBRUM = [(-0.98, 0.12), (-1.0, -0.22), (-0.78, -0.62), (-0.30, -0.86),
            (0.25, -0.84), (0.72, -0.60), (0.98, -0.20), (0.92, 0.18),
            (0.62, 0.34), (0.22, 0.30), (-0.05, 0.42), (-0.42, 0.44),
            (-0.78, 0.34)]
CEREBELLUM = [(0.34, 0.36), (0.62, 0.34), (0.86, 0.44), (0.80, 0.62),
              (0.52, 0.66), (0.34, 0.52)]
FISSURE = [(-0.42, 0.20), (-0.10, 0.08), (0.30, -0.04)]
SULCUS = [(0.06, -0.84), (-0.02, -0.52), (0.10, -0.18)]


def brain_paths(cx, cy, s):
    def tf(pts):
        return [(cx + x * s, cy + y * s) for x, y in pts]
    return (catmull(tf(CEREBRUM)), catmull(tf(CEREBELLUM)),
            catmull(tf(FISSURE), closed=False), catmull(tf(SULCUS), closed=False))


def vessel(x0, x1, y, half, pinch, n=48):
    """Two lines forming a vessel; `pinch` narrows its middle."""
    top, bot = [], []
    for i in range(n + 1):
        u = i / n
        x = lerp(x0, x1, u)
        bump = math.exp(-((u - 0.55) / 0.2) ** 2)
        hw = half * (1 - pinch * bump)
        top.append((x, y - hw))
        bot.append((x, y + hw))
    return top, bot


@overlay(39.40, 42.75, "graphic")
def o_vessels(c, t):
    a = env(t, 39.40, 42.75, 0.45, 0.45)
    dy = rise(t, 39.4, 8, 0.7)
    gx, gy = 300, ZONE_Y - 60 + dy
    pinch = 0.62 * ease_io((t - 40.95) / 1.1)

    st = Strokes((150, int(gy) - 90, 460, int(gy) + 150))
    draw_on = ease_io((t - 39.4) / 1.1)
    cer, cbl, fis, sul = brain_paths(gx, gy, 92)
    st.line(partial(cer, draw_on), OFF, 2.2, 0.9 * a)
    st.line(partial(cbl, draw_on), OFF, 2.0, 0.75 * a)
    st.line(fis, OFF, 1.6, 0.45 * a * draw_on)
    st.line(sul, OFF, 1.6, 0.35 * a * draw_on)
    # vessel under the brain, with blood moving through it; the stream
    # thins and slows as the vessel narrows
    vy, vx0, vx1, half = gy + 118, gx - 132, gx + 132, 15
    top, bot = vessel(vx0, vx1, vy, half, pinch)
    st.line(top, O2_COL, 2.2, a)
    st.line(bot, O2_COL, 2.2, a)
    speed = lerp(110, 50, pinch / 0.62)
    for k in range(6):
        x = vx0 + ((t * speed + k * 46) % (vx1 - vx0))
        u = (x - vx0) / (vx1 - vx0)
        edge = smooth(u / 0.12) * smooth((1 - u) / 0.12)
        thin = 1.0 if k % 2 == 0 else 1 - pinch / 0.62
        st.dot(x, vy, 3.0, O2_COL, a * edge * thin * 0.9)
    st.composite(c, halo=0.45)

    tx = 505
    paste(c, label("LOW CO₂", 27, 750, CO2_COL, 3, halo=0.75), tx, ZONE_Y - 92 + dy,
          a, anchor="lm")
    b = a * smooth((t - 41.25) / 0.45)
    paste(c, label("↓", 28, 600, OFF, 0), tx + 2, ZONE_Y - 42 + dy, b, anchor="lm")
    paste(c, label("LESS CEREBRAL", 23, 700, OFF, 4.2), tx, ZONE_Y + 8 + dy, b,
          anchor="lm")
    paste(c, label("BLOOD FLOW", 23, 700, OFF, 4.2), tx, ZONE_Y + 46 + dy, b,
          anchor="lm")


@overlay(45.25, 48.60)
def o_symptoms(c, t):
    out = env(t, 0, 48.60, 0.01, 0.50)
    words = [(45.32, "LIGHTHEADED"), (46.38, "TINGLY"), (47.46, "MORE WIRED")]
    sprites = [label(w, 23, 650, OFF, 4.6) for _, w in words]
    gap = 54
    widths = [s.width - 2 * HALO_PAD for s in sprites]
    x = CX - (sum(widths) + gap * 2) / 2
    for (s, _), spr, w in zip(words, sprites, widths):
        a = smooth((t - s) / 0.45) * out
        paste(c, spr, x + w / 2, ZONE_Y + rise(t, s, 8, 0.55), a)
        x += w + gap


# 8 -- CO2 helps O2 unload ----------------------------------------------------
@overlay(49.90, 53.95, "graphic")
def o_unload(c, t):
    """BLOOD lane above, TISSUE lane below; with CO2 present the O2 tokens
    step down from one to the other."""
    a = env(t, 49.90, 53.95, 0.45, 0.50)
    x0, x1 = 200, 880
    yb, yt = ZONE_Y - 62, ZONE_Y + 64
    st = Strokes((x0 - 10, yb - 20, x1 + 10, yt + 20))
    st.line([(x0, yb), (x1, yb)], OFF, 2.0, 0.5 * a)
    st.line([(x0, yt), (x1, yt)], OFF, 2.0, 0.5 * a)
    st.composite(c, halo=0.35)
    paste(c, label("BLOOD", 20, 750, OFF, 4.5), x0, yb - 28, a * 0.9, anchor="lm")
    paste(c, label("TISSUE", 20, 750, OFF, 4.5), x0, yt + 30, a * 0.9, anchor="lm")

    co2 = a * smooth((t - 50.10) / 0.5)
    paste(c, label("CO₂", 27, 750, CO2_COL, 2, halo=0.75), 800, (yb + yt) / 2, co2)

    o2 = label("O₂", 30, 750, O2_COL, 2, halo=0.75)
    for i, x in enumerate((430, 545, 660)):
        s = 50.60 + i * 0.50
        u = ease_io((t - s) / 1.2)
        y = lerp(yb - 30, yt + 32, u)
        # dip slightly while crossing the gap so it reads as moving through
        cross = 1 - 0.3 * math.sin(math.pi * u)
        paste(c, o2, x, y, a * cross)


# 9 -- breathe less / smaller. slower. quieter. -------------------------------
@overlay(58.98, 60.75, "hero")
def o_less(c, t):
    a = env(t, 58.98, 60.75, 0.38, 0.40)
    s = 110
    spr = rich((T("Breathe", serif(s), OFF), ("space", 26),
                T("less.", serif(s, True), SAGE_BRIGHT)))
    paste(c, spr, CX, ZONE_Y, a, scale=lerp(0.985, 1.0, ease_out((t - 58.98) / 0.9)))


SSQ = [(60.95, "Smaller.", False), (62.42, "Slower.", False), (63.92, "Quieter.", True)]


@overlay(60.90, 66.10, "hero")
def o_ssq(c, t):
    out = env(t, 0, 66.10, 0.01, 0.60)
    s = 100
    lh = 104
    top = ZONE_Y - lh + 6
    # short sage rule draws in above, the founder-cover gesture
    st = Strokes((CX - 50, int(top) - 92, CX + 50, int(top) - 72))
    st.line(partial([(CX - 34, top - 82), (CX + 34, top - 82)],
                    ease_out((t - 60.95) / 0.7)), SAGE, 2.4, out)
    st.composite(c)
    for i, (st_t, w, ital) in enumerate(SSQ):
        a = smooth((t - st_t) / 0.5) * out
        fill = SAGE_BRIGHT if ital else OFF
        spr = rich((T(w, serif(s, ital), fill),))
        paste(c, spr, CX, top + i * lh + rise(t, st_t, 10, 0.7), a)


# 10 -- balance ----------------------------------------------------------------
@overlay(71.40, 74.15, "graphic")
def o_balance(c, t):
    a = env(t, 71.40, 74.15, 0.45, 0.45)
    # settles from a slight tilt to level -- damped, not bouncy
    u = clamp((t - 71.5) / 1.8)
    ang = math.radians(-7) * (1 - ease_out(u)) * math.cos(u * math.pi * 0.5)
    L = 210
    cy = ZONE_Y + 4
    dx, dy = math.cos(ang) * L, math.sin(ang) * L
    lx, ly = CX - dx, cy - dy
    rx, ry = CX + dx, cy + dy
    st = Strokes((CX - L - 20, cy - 60, CX + L + 20, cy + 40))
    st.line([(lx, ly), (rx, ry)], OFF, 2.4, 0.85 * a)
    st.line([(CX - 14, cy + 28), (CX, cy + 4), (CX + 14, cy + 28), (CX - 14, cy + 28)],
            OFF, 2.0, 0.7 * a)
    st.dot(lx, ly, 4.0, O2_COL, a)
    st.dot(rx, ry, 4.0, CO2_COL, a)
    st.composite(c, halo=0.45)
    paste(c, label("O₂", 32, 750, O2_COL, 2, halo=0.75), lx, ly - 44, a)
    paste(c, label("CO₂", 32, 750, CO2_COL, 2, halo=0.75), rx, ry - 44, a)


# 11 -- deep breath -> quiet breath ----------------------------------------------
@overlay(76.60, 79.95, "hero")
def o_quiet(c, t):
    out = env(t, 0, 79.95, 0.01, 0.50)
    a1 = smooth((t - 76.60) / 0.45) * out
    strike = ease_io((t - 77.75) / 0.55)
    a1 *= lerp(1.0, 0.42, strike)
    y1 = ZONE_Y - 72
    deep = rich((T("Deep breath", serif(76), OFF),))
    paste(c, deep, CX, y1, a1)
    if strike > 0:
        w = deep.width - 2 * HALO_PAD
        st = Strokes((int(CX - w / 2) - 10, int(y1) - 10, int(CX + w / 2) + 10, int(y1) + 20))
        st.line(partial([(CX - w / 2 - 4, y1 + 6), (CX + w / 2 + 4, y1 + 6)], strike),
                CLAY, 2.6, out * 0.95)
        st.composite(c)
    a2 = smooth((t - 78.42) / 0.55) * out
    q = rich((T("Quiet", serif(124, True), SAGE_BRIGHT), ("space", 26),
              T("breath.", serif(124), OFF)))
    paste(c, q, CX, ZONE_Y + 52 + rise(t, 78.42, 10, 0.8), a2)


# 12 -- practical cues -------------------------------------------------------------
CUES = [(80.62, 81.98, "NOSE"), (82.70, 85.05, "LOW + WIDE"),
        (85.95, 87.45, "RELAX SHOULDERS"), (89.10, 90.65, "DON’T FORCE")]

for _s, _e, _w in CUES:
    def _mk(s=_s, e=_e, w=_w):
        @overlay(s, e)
        def o_cue(c, t):
            a = env(t, s, e, 0.40, 0.40)
            paste(c, label(w, 32, 700, OFF, 7.5), CX, ZONE_Y + rise(t, s, 8, 0.6), a)
    _mk()


@overlay(83.40, 85.65, "graphic")
def o_ribs(c, t):
    """Lower-rib arcs at the sides of the torso widen once, slowly, on
    'expand naturally'. Kept below the subtitles and small."""
    a = env(t, 83.40, 85.65, 0.5, 0.6) * 0.8
    grow = ease_io((t - 83.9) / 1.4) * 16
    st = Strokes((90, 1560, 990, 1800))
    for side in (-1, 1):
        pts = []
        for i in range(21):
            u = i / 20
            ang = lerp(-0.75, 0.75, u)
            x = CX + side * (330 + grow + 46 * math.cos(ang))
            y = 1680 + math.sin(ang) * 90
            pts.append((x, y))
        st.line(pts, O2_COL, 2.4, a)
    st.composite(c, halo=0.45)


@overlay(85.95, 87.55, "graphic")
def o_relax_shoulders(c, t):
    """Callback to the opening demo: the same shoulder line, easing down."""
    a = env(t, 85.95, 87.55, 0.45, 0.50) * 0.8
    drop = ease_io((t - 86.1) / 1.2) * 14
    st = Strokes((0, 1000, W, 1200))
    for side in (-1, 1):
        st.line(shoulder_pts(0, side, drop), O2_COL, 2.6, a)
    st.composite(c, halo=0.45)


# 13 -- guided breath ring ------------------------------------------------------
INHALE = (99.40, 102.90)
EXHALE = (102.90, 107.20)
R_MIN, R_MAX = 58, 112
RING_Y = 1290


def ring_radius(t):
    if t < INHALE[0]:
        return R_MIN
    if t < INHALE[1]:
        return lerp(R_MIN, R_MAX, ease_io((t - INHALE[0]) / (INHALE[1] - INHALE[0])))
    if t < EXHALE[1]:
        return lerp(R_MAX, R_MIN, ease_io((t - EXHALE[0]) / (EXHALE[1] - EXHALE[0])))
    return R_MIN


@overlay(97.20, 108.60, "breath")
def o_ring(c, t):
    a = env(t, 97.20, 108.60, 1.2, 1.3)
    r = ring_radius(t)
    st = Strokes((CX - R_MAX - 12, RING_Y - R_MAX - 12, CX + R_MAX + 12, RING_Y + R_MAX + 12))
    st.circle(CX, RING_Y, R_MAX, OFF, 1.4, 0.16 * a)
    st.circle(CX, RING_Y, r, OFF, 2.2, 0.72 * a)
    st.composite(c, halo=0.25)


# 14 -- final hero ----------------------------------------------------------------
@overlay(112.88, 118.95, "hero")
def o_final(c, t):
    out = 1 - smooth((t - 118.25) / 0.7)
    s1, s2 = 78, 88
    y = ZONE_Y - 120
    a1 = smooth((t - 112.88) / 0.5) * out
    a1 *= lerp(1.0, 0.5, smooth((t - 115.2) / 0.6))
    paste(c, rich((T("You might not need", serif(s1), OFF),)), CX,
          y + rise(t, 112.88, 8, 0.7), a1)
    paste(c, rich((T("a bigger breath.", serif(s1), OFF),)), CX,
          y + 84 + rise(t, 112.88, 8, 0.7), a1)
    a2 = smooth((t - 115.22) / 0.6) * out
    paste(c, rich((T("You might need", serif(s2), OFF),)), CX,
          y + 206 + rise(t, 115.22, 10, 0.8), a2)
    paste(c, rich((T("a quieter one.", serif(s2, True), SAGE_BRIGHT),)), CX,
          y + 298 + rise(t, 115.22, 10, 0.8), a2)


# end card ----------------------------------------------------------------------
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
    img = Image.new("RGBA", (W, H), BG + (255,))
    cy = 930
    img.alpha_composite(radial_glow(1600, (92, 112, 88), 66), (CX - 800, cy - 800))
    d = ImageDraw.Draw(img)
    eyebrow = label("BREATH LAB", 22, 700, SAGE, 7, halo=0)
    img.alpha_composite(eyebrow, (int(CX - eyebrow.width / 2),
                                  int(cy - 128 - eyebrow.height / 2)))
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


# ------------------------------------------------------------------ compose
BOOST = {"label": 0.75, "graphic": 1.0, "hero": 0.0, "breath": 0.55}


def presence(t, kind_filter):
    p = 0.0
    for s, e, kind, _ in OVERLAYS:
        if kind in kind_filter and s - 0.4 < t < e + 0.4:
            p = max(p, env(t, s - 0.25, e + 0.25, 0.7, 0.7) * BOOST.get(kind, 1))
    return p


def compose(frame, t):
    """frame: RGB PIL image of the reframed source at time t -> RGB image."""
    img = frame.convert("RGBA")
    img.alpha_composite(scrim("base", SCRIM_LEVELS))
    boost = presence(t, ("label", "graphic", "breath"))
    hero = max(presence(t, ("hero",)) * 1.0, 0.0)
    if boost > 0.01:
        img.alpha_composite(scrim("boost", round(boost * SCRIM_LEVELS)))
    if hero > 0.01:
        img.alpha_composite(scrim("hero", round(hero * SCRIM_LEVELS)))

    draw_subtitles(img, t)
    for s, e, _, fn in OVERLAYS:
        if s <= t <= e:
            fn(img, t)

    dark = smooth((t - FADE_TO_DARK[0]) / (FADE_TO_DARK[1] - FADE_TO_DARK[0]))
    if dark > 0:
        veil = Image.new("RGBA", (W, H), BG + (int(255 * dark),))
        img.alpha_composite(veil)
        if t >= FADE_TO_DARK[0]:
            for s, e, _, fn in OVERLAYS:
                if fn is o_final and s <= t <= e:
                    fn(img, t)          # hero line stays above the veil
    ec = smooth((t - END_CARD[0]) / (END_CARD[1] - END_CARD[0]))
    if ec > 0:
        card = end_card()
        if ec < 1:
            card = card.copy()
            card.putalpha(int(255 * ec))
        img.alpha_composite(card)
    return img.convert("RGB")


def coverage(exclude=()):
    """Share of the spoken runtime carrying an annotation (subtitles and end
    card aside). `exclude` drops overlay functions from the count."""
    step = 1 / FPS
    n = on = 0
    t = 0.0
    while t < SRC_DUR:
        n += 1
        if any(s <= t <= e for s, e, _, fn in OVERLAYS if fn not in exclude):
            on += 1
        t += step
    return on / n


# -------------------------------------------------------------------- render
def decode_cmd(start=None, frames=None, height=H):
    width = height * 9 // 16
    vf = (f"crop={CROP_W}:1080:{CROP_X}:0,"
          f"scale={width}:{height}:flags=lanczos:in_color_matrix=bt709:out_color_matrix=bt709,"
          f"unsharp=5:5:0.35:5:5:0,eq=saturation=0.94:contrast=1.02,"
          f"tpad=stop_mode=clone:stop_duration={TOTAL_DUR - SRC_DUR + 0.5:.2f},"
          f"format=rgb24")
    cmd = ["ffmpeg", "-v", "error"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", SOURCE, "-vf", vf, "-an"]
    if frames is not None:
        cmd += ["-frames:v", str(frames)]
    else:
        cmd += ["-t", f"{TOTAL_DUR:.3f}"]
    return cmd + ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"]


def render(preview=False):
    out_h = 960 if preview else H
    out_w = out_h * 9 // 16
    out_path = FINAL.replace(".mp4", "-preview.mp4") if preview else FINAL
    dec = subprocess.Popen(decode_cmd(), stdout=subprocess.PIPE)
    enc_vf = (f"scale={out_w}:{out_h}:flags=lanczos:out_color_matrix=bt709:out_range=tv,"
              "format=yuv420p")
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-i", MIX,
         "-map", "0:v", "-map", "1:a", "-vf", enc_vf,
         "-c:v", "libx264", "-preset", "veryfast" if preview else "slow",
         "-crf", "23" if preview else "18",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-c:a", "aac", "-b:a", "192k", "-t", f"{TOTAL_DUR:.3f}",
         "-movflags", "+faststart", out_path],
        stdin=subprocess.PIPE)
    n_frames = int(round(TOTAL_DUR * FPS))
    size = W * H * 3
    t0 = time.time()
    last = None
    for i in range(n_frames):
        buf = dec.stdout.read(size)
        if len(buf) < size:
            if last is None:
                sys.exit("decoder produced no frames")
            buf = last
        last = buf
        frame = Image.frombuffer("RGB", (W, H), buf, "raw", "RGB", 0, 1)
        enc.stdin.write(compose(frame, i / FPS).tobytes())
        if i % 300 == 0:
            el = time.time() - t0
            print(f"  {i / FPS:6.1f}s  ({el:5.0f}s elapsed)", flush=True)
    enc.stdin.close()
    enc.wait()
    dec.stdout.close()
    dec.wait()
    mb = os.path.getsize(out_path) / 1e6
    print(f"saved {os.path.relpath(out_path, ROOT)}  ({mb:.1f} MB, "
          f"{time.time() - t0:.0f}s)")


def stills(times):
    os.makedirs(STILL_DIR, exist_ok=True)
    for t in times:
        src_t = min(t, SRC_DUR - 0.5)
        raw = subprocess.run(decode_cmd(start=src_t, frames=1),
                             capture_output=True, check=True).stdout
        frame = Image.frombuffer("RGB", (W, H), raw[:W * H * 3], "raw", "RGB", 0, 1)
        out = os.path.join(STILL_DIR, f"t{t:06.2f}.png")
        compose(frame, t).resize((540, 960), Image.LANCZOS).save(out)
        print("saved", os.path.relpath(out, ROOT))


DEFAULT_STILLS = [1.2, 4.6, 10.6, 15.2, 23.4, 27.6, 34.4, 37.6, 41.9, 47.9,
                  52.4, 59.9, 65.0, 73.0, 79.2, 84.6, 86.9, 101.5, 116.2, 121.0]

if __name__ == "__main__":
    print(f"annotation coverage: {coverage() * 100:.1f}% of {SRC_DUR:.0f}s "
          f"({coverage((o_ring, o_final)) * 100:.1f}% without the guided-breath "
          f"ring and closing line)")
    for _, _, text in SUBS:
        subtitle_sprite(text)
    spec = os.environ.get("QB_STILLS")
    if spec:
        times = DEFAULT_STILLS if spec == "1" else [float(x) for x in spec.split(",")]
        stills(times)
    else:
        if not os.path.exists(MIX):
            sys.exit("Run tmp/make_quiet_breathing_audio.py first (mix missing)")
        render(preview=bool(os.environ.get("QB_PREVIEW")))
