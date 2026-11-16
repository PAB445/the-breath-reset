#!/usr/bin/env python3
"""
Breathe Light -- 16:9 cinematic YouTube render (1920x1080, 24 fps).

  tmp/.venv-dsp/bin/python tmp/make_breathe_light_audio.py   # edit + score + mix (first)
  tmp/.venv-dsp/bin/python tmp/render_breathe_light.py       # full render
  BL_STILLS=1 tmp/.venv-dsp/bin/python tmp/render_breathe_light.py         # check stills
  BL_STILLS=62,300 tmp/.venv-dsp/bin/python tmp/render_breathe_light.py    # specific times
  BL_PREVIEW=1 ...                                           # 960x540 proof

All timing comes from breathe-light-edit.json (written by the audio script), so
re-cutting the audio never needs hand re-timing here.

Picture: two stills of the same mountain lake (dawn, sunrise -- same framing,
aligned to 1 px) crossfaded over the practice, with procedural motion on top:
  - two drifting mist layers on the water + a high valley haze, thinning as
    the practice softens (the mist "lifts")
  - faint moving cloud light in the sky
  - very small horizontal ripple displacement on the reflection, and an
    expanding ring from the odd drop every 14-32 s
  - twinkling glints on the sun's reflection and slow rays from behind the peak
  - specks of light drifting up through the air
  - a slow camera push-in, easing back out for Let Go, with a gentle float
  - film grain, so the upscaled stills read as footage
Nothing pulses with a breath rhythm -- participants breathe on their own.

Type: Instrument Serif for display lines, Manrope for labels and the timer
(digits set in fixed cells so the timer never jitters).
"""
import json
import math
import os
import subprocess
import sys
import time
from functools import lru_cache
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# BL_SRC points the renderer at a variant folder (edit json, mix, source plates).
# Unset, it renders the original Breathe Light film. Variants never write here.
BASE_DIR = os.path.join(ROOT, "assets", "social", "youtube", "relax", "breathe-light")
OUT_DIR = os.environ.get("BL_SRC", BASE_DIR)
SRC_DIR = os.path.join(OUT_DIR, "source")
EDIT = json.load(open(os.path.join(OUT_DIR, "breathe-light-edit.json")))
MIX = os.path.join(OUT_DIR, "breathe-light-mix.wav")
FINAL = os.path.join(OUT_DIR, "breathe-light-youtube.mp4")
CLOSE_LINE = EDIT.get("close_line", "Breathe better. Feel more.")
CLOSE_SIZE = int(EDIT.get("close_size", 92 if CLOSE_LINE == "Breathe better. Feel more." else 104))
NO_SAFETY = EDIT.get("safety") is False
STILL_DIR = os.path.join(HERE, "breathe-light-frames")
FONTS = os.path.join(ROOT, "breathing-reel", "fonts")

W, H = 1920, 1080
FPS = 24
TOTAL = EDIT["total"]
N_FRAMES = int(round(TOTAL * FPS))
HORIZON = 0.634           # water line in the plate, fraction of height

OFF = (239, 231, 217)
SAGE = (143, 165, 138)
SAGE_BRIGHT = (179, 199, 172)
CLAY = (209, 144, 115)
INK = (16, 13, 11)

SECTIONS = {s["name"]: (s["start"], s["end"]) for s in EDIT["sections"]}
BOLTS = EDIT["bolts"]
LAST_WORD = EDIT["last_word_end"]


# ------------------------------------------------------------------ easing
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def smooth(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_io(x):
    x = clamp(x)
    return 0.5 - 0.5 * math.cos(math.pi * x)


def env(t, start, end, fin=1.0, fout=1.0):
    if t < start or t >= end:
        return 0.0
    a = smooth((t - start) / fin) if fin > 0 else 1.0
    b = smooth((end - t) / fout) if fout > 0 else 1.0
    return a * b


def curve(t, pts):
    """Eased piecewise curve through (time, value) points."""
    if t <= pts[0][0]:
        return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * ease_io((t - t0) / max(t1 - t0, 1e-6))
    return pts[-1][1]


S = SECTIONS
# the v2 script adds Breathe Less between Soften and Let Go
SOFT_END = S["lessair"][1] if "lessair" in S else S["soften"][1]
MID = [(S["soften"][1], 0.32)] if "lessair" in S else []
# 0 = dawn plate, 1 = sunrise plate
WARMTH = [(0, 0.0), (S["notice"][0], 0.06), (S["soften"][0], 0.10)] + MID + \
         [(SOFT_END, 0.62), (S["letgo"][1] - 10, 0.85), (TOTAL, 0.9)]
MIST = [(0, 1.0), (S["soften"][0], 0.95)] + \
       ([(S["soften"][1], 0.72)] if MID else []) + \
       [(SOFT_END, 0.50), (S["letgo"][1], 0.36), (TOTAL, 0.42)]
ZOOM = [(0, 1.015), (S["letgo"][0], 1.085), (S["letgo"][1], 1.045),
        (TOTAL, 1.06)]
PAN_X = [(0, 0.50), (SOFT_END, 0.535), (S["letgo"][1], 0.52), (TOTAL, 0.525)]
PAN_Y = [(0, 0.50), (S["letgo"][0], 0.475), (S["letgo"][1], 0.50), (TOTAL, 0.49)]


def bolt_card_alpha(t):
    a = 0.0
    for b in BOLTS:
        a = max(a, env(t, b["card_in"], b["timer_end"] + 1.5, 1.6, 1.3))
    return a


def subdue(t):
    """Landscape dims slightly behind the BOLT timer."""
    a = 0.0
    for b in BOLTS:
        a = max(a, env(t, b["card_in"] - 1.0, b["timer_end"] + 3.0, 3.0, 3.5))
    return a


# ------------------------------------------------------------------ plates
def load_plate(name):
    im = Image.open(os.path.join(SRC_DIR, name)).convert("RGB")
    im = im.resize((W, H), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.6, percent=40, threshold=2))
    return np.asarray(im, np.float32) / 255.0


def grade_sunrise(x):
    """Bring the sunrise plate onto the brand palette: less orange, softer."""
    lum = (x * np.array([0.2126, 0.7152, 0.0722], np.float32)).sum(2, keepdims=True)
    x = lum + (x - lum) * 0.74                                   # desaturate
    x = (x - 0.5) * 1.07 + 0.5                                   # keep depth as it warms
    x = 0.035 + np.clip(x, 0, 1) * 0.955                         # lift blacks (filmic)
    return x.astype(np.float32)


def grade_dawn(x):
    lum = (x * np.array([0.2126, 0.7152, 0.0722], np.float32)).sum(2, keepdims=True)
    x = lum + (x - lum) * 0.92
    return np.clip(0.035 + x * 0.965, 0, 1)


def fbm(h, w, octaves, seed, base=4):
    """Tileable-in-x fractal noise via summed upsampled random grids."""
    r = np.random.RandomState(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        gh, gw = base * 2 ** o // 2 + 2, base * 2 ** o
        g = r.rand(gh, gw).astype(np.float32)
        g = np.concatenate([g, g[:, :1]], axis=1)               # wrap in x
        img = Image.fromarray((g * 255).astype(np.uint8))
        up = img.resize((w + w // gw, h), Image.BICUBIC)
        a = np.asarray(up, np.float32)[:, :w] / 255.0
        out += amp * a
        tot += amp
        amp *= 0.5
    out /= tot
    # the resize leaves a step at the wrap; hide it under a half-width roll
    x = np.arange(w, dtype=np.float32) / w
    wgt = np.clip(np.minimum(x, 1 - x) / 0.15, 0, 1)
    wgt = wgt * wgt * (3 - 2 * wgt)
    out = out * wgt + np.roll(out, w // 2, axis=1) * (1 - wgt)
    return (out - out.min()) / (out.max() - out.min())


class Assets:
    def __init__(self):
        self.dawn = grade_dawn(load_plate("bl-lake-dawn.jpg"))
        self.rise = grade_sunrise(load_plate("bl-lake-sunrise.jpg"))
        y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        x = np.linspace(0, 1, W, dtype=np.float32)[None, :]
        # mist masks
        hz = HORIZON
        self.m_water = (np.exp(-((y - (hz + 0.012)) / 0.045) ** 2) +
                        0.45 * np.exp(-((y - (hz + 0.07)) / 0.06) ** 2)).astype(np.float32)
        self.m_valley = np.exp(-((y - 0.535) / 0.07) ** 2).astype(np.float32)
        self.m_sky = (np.clip((0.42 - y) / 0.2, 0, 1) ** 1.2).astype(np.float32)
        # wide noise textures (2x width so they can scroll)
        self.n1 = fbm(H // 2, W * 2 // 2, 6, 11, base=6)
        self.n2 = fbm(H // 2, W * 2 // 2, 5, 23, base=4)
        self.n3 = fbm(H // 4, W * 2 // 4, 4, 37, base=3)
        # ripple field
        self.yw0 = int(hz * H) + 2
        yy = np.arange(self.yw0, H, dtype=np.float32)
        d = (yy - self.yw0) / (H - self.yw0)
        self.r_amp = (0.25 + 1.9 * d ** 1.4)[:, None]
        self.r_phase = (2 * np.pi * 9.0 * np.log1p(d * 40))[:, None]
        self.xs = np.arange(W, dtype=np.float32)[None, :]
        self.rows = np.arange(self.yw0, H)[:, None]
        # glow + vignette
        gx, gy = 0.625, 0.425
        r = np.sqrt(((x - gx) * 1.6) ** 2 + (y - gy) ** 2)
        self.glow = (np.exp(-(r / 0.22) ** 2) * 0.6 + np.exp(-(r / 0.5) ** 2) * 0.4)[..., None]
        rv = np.sqrt(((x - 0.5) * 1.15) ** 2 + ((y - 0.5) * 1.3) ** 2)
        self.vignette = (1 - 0.32 * smooth_arr((rv - 0.35) / 0.55))[..., None].astype(np.float32)
        # darkened sunlight turns olive, so scrims back off around the sun
        self.sun_protect = (1 - 0.9 * self.glow / self.glow.max()).astype(np.float32)
        card = np.sqrt(((x - 0.5) / 0.30) ** 2 + ((y - 0.5) / 0.26) ** 2)
        self.card_scrim = np.exp(-card ** 2 * 1.2)[..., None].astype(np.float32)
        lower = np.clip((y - 0.62) / 0.38, 0, 1)
        self.lower_scrim = (lower ** 1.3)[..., None].astype(np.float32)
        gr = np.random.RandomState(5)
        self.grain = [(gr.randn(H // 2, W // 2) * 1.0).astype(np.float32) for _ in range(6)]

        # --- extra life: glints, sun rays, light motes, ripple rings
        # glints: bright, horizontally stretched sparkle along the sun's
        # reflection, from two noise fields drifting past each other
        wh = H - self.yw0
        self.g_a = glint_texture(wh, W, 41)
        self.g_b = glint_texture(wh, W, 43)
        self.g_tw = fbm(wh // 4, W // 2, 3, 47, base=24)
        yy = np.linspace(0, 1, wh, dtype=np.float32)[:, None]
        col = np.exp(-((x - 0.60) / 0.09) ** 2) * 0.8 + np.exp(-((x - 0.60) / 0.28) ** 2) * 0.2
        self.g_mask = (col * np.exp(-((yy - 0.45) / 0.30) ** 2)).astype(np.float32)
        # sun rays: angle around the sun, sampled from a 1D table each frame
        hy, hx = H // 2, W // 2
        ry = np.linspace(0, 1, hy, dtype=np.float32)[:, None]
        rx = np.linspace(0, 1, hx, dtype=np.float32)[None, :]
        ang = np.arctan2((ry - gy) * H, (rx - gx) * W)
        self.ray_idx = ((ang + np.pi) / (2 * np.pi) * 4095).astype(np.int32)
        rr = np.sqrt(((rx - gx) * 1.78) ** 2 + (ry - gy) ** 2)
        above = np.clip((HORIZON + 0.06 - ry) / 0.12, 0, 1)
        self.ray_fall = (np.exp(-rr / 0.42) * (1 - np.exp(-(rr / 0.05) ** 2)) * above).astype(np.float32)
        # motes: soft specks of light drifting up through the air
        mr = np.random.RandomState(77)
        k = 90
        self.motes = dict(
            x=mr.uniform(0, W, k), y=mr.uniform(0, H, k), z=mr.uniform(0.25, 1.0, k),
            vx=mr.uniform(1.5, 7.0, k), vy=-mr.uniform(1.2, 5.0, k),
            wf=mr.uniform(0.02, 0.06, k), wp=mr.uniform(0, 6.3, k),
            tf=mr.uniform(0.03, 0.11, k), tp=mr.uniform(0, 6.3, k))
        self.mote_sprites = {}
        for r in range(1, 8):
            s = np.arange(-4 * r, 4 * r + 1, dtype=np.float32)
            self.mote_sprites[r] = np.exp(-(s[:, None] ** 2 + s[None, :] ** 2) / (2 * (r * 0.8) ** 2))
        # rings: a drop or a fish now and then, never on a regular beat
        rg = np.random.RandomState(9)
        self.rings, t = [], 6.0
        while t < TOTAL + 600:
            self.rings.append((t, rg.uniform(0.25, 0.75) * W,
                               self.yw0 + rg.uniform(0.35, 0.85) * wh))
            t += rg.uniform(14, 32)


def glint_texture(h, w, seed):
    """Sparse short horizontal streaks of light (wraps in x)."""
    r = np.random.RandomState(seed)
    pts = (r.rand(h, w) > 0.9975).astype(np.float32) * r.uniform(0.4, 1.0, (h, w)).astype(np.float32)
    k = np.hanning(15).astype(np.float32)
    out = np.zeros_like(pts)
    for i, v in enumerate(k):
        out += np.roll(pts, i - 7, axis=1) * v
    out = 0.6 * out + 0.2 * (np.roll(out, 1, axis=0) + np.roll(out, -1, axis=0))
    return np.clip(out, 0, 1)


def smooth_arr(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def scroll(tex, offset, out_w):
    """Sub-pixel horizontal scroll of a wide texture, wrapped."""
    tw = tex.shape[1]
    o = offset % tw
    i = int(o)
    f = o - i
    idx = (np.arange(out_w) + i) % tw
    a = tex[:, idx]
    b = tex[:, (idx + 1) % tw]
    return a * (1 - f) + b * f


def upsize(a, w, h):
    return np.asarray(Image.fromarray(a).resize((w, h), Image.BILINEAR))


def landscape(A, t):
    warm = curve(t, WARMTH)
    img = A.dawn * (1 - warm) + A.rise * warm

    # ripples on the reflection
    ph = A.r_phase - t * 1.15
    shift = A.r_amp * 1.25 * (0.65 * np.sin(ph + 0.004 * A.xs + 0.3 * np.sin(A.xs / 230 + t * 0.21))
                              + 0.35 * np.sin(1.7 * ph - 0.006 * A.xs + 1.3))
    rings = ring_field(A, t)
    shift = shift + 8.0 * rings
    xsrc = np.clip(A.xs + shift, 0, W - 1.001)
    x0 = xsrc.astype(np.int32)
    f = (xsrc - x0)[..., None]
    water = img[A.rows, x0] * (1 - f) + img[A.rows, x0 + 1] * f
    water = water * (1 + 0.14 * np.abs(rings)[..., None])
    img = img.copy()
    img[A.yw0:] = water

    # glints on the sun's reflection, livelier as the sun comes up
    tw = upsize(scroll(A.g_tw, t * 7.0, W // 2), W, H - A.yw0)
    tw = np.clip((tw - 0.45) / 0.25, 0, 1)
    sparkle = (scroll(A.g_a, t * 5.0, W) + scroll(A.g_b, -t * 3.5 + 500, W)) * tw
    gl = np.clip(A.g_mask * sparkle * (0.35 + 0.65 * smooth(warm / 0.7)), 0, 0.6)
    img[A.yw0:] = 1 - (1 - water) * (1 - gl[..., None] * np.array([1.0, 0.92, 0.78], np.float32))

    # mist + haze
    dens = curve(t, MIST)
    m1 = upsize(scroll(A.n1, t * 4.6, W // 2), W, H)
    m2 = upsize(scroll(A.n2, -t * 2.7 + 300, W // 2), W, H)
    m3 = upsize(scroll(A.n3, t * 2.2 + 100, W // 4), W, H)
    water_mist = A.m_water * (0.55 * m1 + 0.45 * m2) ** 1.6 * 0.62 * dens
    valley = A.m_valley * m2 ** 2 * 0.32 * (0.35 + 0.65 * dens)
    a = np.clip(water_mist + valley, 0, 0.75)[..., None]
    mist_col = np.array([0.90, 0.88, 0.83], np.float32) * (1 - warm) + \
        np.array([0.95, 0.86, 0.75], np.float32) * warm
    img = img * (1 - a) + mist_col * a

    # cloud light drifting across the sky
    cl = (m3 - 0.5) * A.m_sky * 0.16
    img = img * (1 + cl[..., None])

    # sunlight
    g = 0.10 * smooth(warm / 0.8) + 0.02
    glow = A.glow * g * np.array([1.0, 0.86, 0.66], np.float32)
    img = 1 - (1 - np.clip(img, 0, 1)) * (1 - glow)              # screen: never clips

    # soft rays from behind the peak, turning very slowly
    a = np.linspace(0, 2 * np.pi, 4096, endpoint=False)
    table = (0.5 + 0.5 * np.sin(a * 11 + t * 0.045)) * (0.5 + 0.5 * np.sin(a * 17 - t * 0.031 + 1.9)) \
        + 0.6 * (0.5 + 0.5 * np.sin(a * 6 + t * 0.022 + 0.7)) ** 3
    rays = table[A.ray_idx] * A.ray_fall * (0.05 + 0.13 * smooth(warm / 0.8))
    rays = upsize(rays.astype(np.float32), W, H)[..., None] * np.array([1.0, 0.9, 0.74], np.float32)
    img = 1 - (1 - img) * (1 - rays)

    return motes(A, img, t, warm)


def ring_field(A, t):
    """Expanding rings from the odd drop on the lake: signed wave per water pixel,
    used both to displace the reflection and to catch a little light."""
    out = np.zeros((H - A.yw0, W), np.float32)
    for t0, cx, cy in A.rings:
        age = t - t0
        if not 0 < age < 7.0:
            continue
        persp = 0.35 + 0.65 * (cy - A.yw0) / (H - A.yw0)      # nearer water, bigger ring
        R = (14 + 46 * age) * persp
        r_max = R + 30 * persp
        y0, y1 = int(max(A.yw0, cy - r_max * 0.22)), int(min(H, cy + r_max * 0.22 + 1))
        x0, x1 = int(max(0, cx - r_max)), int(min(W, cx + r_max + 1))
        if y1 <= y0 or x1 <= x0:
            continue
        yy = np.arange(y0, y1, dtype=np.float32)[:, None]
        xx = np.arange(x0, x1, dtype=np.float32)[None, :]
        d = np.sqrt((xx - cx) ** 2 + ((yy - cy) / 0.22) ** 2)
        band = np.exp(-((d - R) / (11 * persp)) ** 2)
        wave = np.sin((d - R) / (3.2 * persp)) * band
        fade = smooth(age / 0.6) * (1 - smooth((age - 2.5) / 4.5))
        out[y0 - A.yw0:y1 - A.yw0, x0:x1] += persp * fade * wave * np.sign(xx - cx)
    return out


def motes(A, img, t, warm):
    """Drifting specks of light, screened over the picture."""
    m = A.motes
    x = (m["x"] + m["vx"] * m["z"] * t + 18 * np.sin(t * m["wf"] * 6.283 + m["wp"])) % (W + 80) - 40
    y = (m["y"] + m["vy"] * m["z"] * t) % (H + 80) - 40
    tw = 0.5 + 0.5 * np.sin(t * m["tf"] * 6.283 + m["tp"])
    lvl = (0.09 + 0.22 * m["z"]) * tw ** 2 * (0.6 + 0.5 * smooth(warm / 0.7))
    acc = np.zeros((H, W), np.float32)
    for xi, yi, zi, li in zip(x, y, m["z"], lvl):
        if li < 0.004:
            continue
        sp = A.mote_sprites[max(1, min(7, int(round(1 + 6 * zi ** 2))))]
        h = sp.shape[0] // 2
        cx, cy = int(xi), int(yi)
        ya, yb = max(0, cy - h), min(H, cy + h + 1)
        xa, xb = max(0, cx - h), min(W, cx + h + 1)
        if ya >= yb or xa >= xb:
            continue
        acc[ya:yb, xa:xb] += li * sp[ya - cy + h:yb - cy + h, xa - cx + h:xb - cx + h]
    col = np.array([1.0, 0.93, 0.80], np.float32)
    return 1 - (1 - img) * (1 - np.clip(acc, 0, 0.6)[..., None] * col)


def camera(img, t, out_w, out_h):
    # slow float on top of the push-in, on unrelated long periods
    z = curve(t, ZOOM) + 0.006 * math.sin(2 * math.pi * t / 83 + 0.4)
    cx = curve(t, PAN_X) * W + 0.007 * W * math.sin(2 * math.pi * t / 47 + 1.1)
    cy = curve(t, PAN_Y) * H + 0.005 * H * math.sin(2 * math.pi * t / 61 + 2.3)
    cw, ch = W / z, H / z
    x0 = clamp(cx - cw / 2, 0, W - cw)
    y0 = clamp(cy - ch / 2, 0, H - ch)
    pil = Image.fromarray((img * 255 + 0.5).astype(np.uint8))
    return pil.resize((out_w, out_h), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


# -------------------------------------------------------------------- type
@lru_cache(maxsize=None)
def manrope(size, weight=500):
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


PAD = 40


def with_halo(img, strength=0.5, blur=14, spread=0):
    halo = Image.new("RGBA", img.size, INK + (0,))
    a = img.getchannel("A")
    if spread:
        a = a.filter(ImageFilter.MaxFilter(spread))
    halo.putalpha(a.point(lambda v: int(v * strength)))
    out = halo.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(img)
    return out


@lru_cache(maxsize=None)
def caps(text, size, weight=600, fill=OFF, track=0.32, halo=0.45):
    fnt = manrope(size, weight)
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    tr = size * track
    w = sum(d.textlength(c, font=fnt) + tr for c in text) - tr
    asc, desc = fnt.getmetrics()
    img = Image.new("RGBA", (int(w) + 2 * PAD, asc + desc + 2 * PAD), (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    x = PAD
    for c in text:
        dd.text((x, PAD), c, font=fnt, fill=fill)
        x += d.textlength(c, font=fnt) + tr
    return with_halo(img, halo, 16, spread=9) if halo else img


@lru_cache(maxsize=None)
def line(text, fnt_key, fill=OFF, halo=0.45, blur=14):
    kind, size, flag = fnt_key
    fnt = serif(size, flag) if kind == "serif" else manrope(size, flag)
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    w = d.textlength(text, font=fnt)
    asc, desc = fnt.getmetrics()
    img = Image.new("RGBA", (int(w) + 2 * PAD, asc + desc + 2 * PAD), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((PAD, PAD), text, font=fnt, fill=fill)
    return with_halo(img, halo, blur) if halo else img


@lru_cache(maxsize=None)
def timer_sprite(secs, size=168):
    """mm:ss with each digit in a fixed-width cell (no tabular figures in PIL)."""
    fnt = manrope(size, 300)
    d = ImageDraw.Draw(Image.new("L", (1, 1)))
    cell = max(d.textlength(str(k), font=fnt) for k in range(10))
    colon = d.textlength(":", font=fnt) + size * 0.06
    text = f"{secs // 60:02d}:{secs % 60:02d}"
    w = cell * 4 + colon
    asc, desc = fnt.getmetrics()
    img = Image.new("RGBA", (int(w) + 2 * PAD, asc + desc + 2 * PAD), (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    x = PAD
    for ch in text:
        if ch == ":":
            dd.text((x + colon / 2, PAD + asc * 0.52), ":", font=fnt, fill=OFF, anchor="mm")
            x += colon
        else:
            dd.text((x + cell / 2, PAD), ch, font=fnt, fill=OFF, anchor="ma")
            x += cell
    return with_halo(img, 0.4, 18)


@lru_cache(maxsize=None)
def rule(w=56, fill=SAGE_BRIGHT, thick=2):
    img = Image.new("RGBA", (w + 2 * PAD, thick + 2 * PAD), (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle([PAD, PAD, PAD + w, PAD + thick - 1], fill=fill)
    return with_halo(img, 0.35, 8)


def paste(canvas, sprite, cx, cy, alpha, scale):
    if alpha <= 0.004:
        return
    s = sprite
    if scale != 1.0:
        s = s.resize((max(1, round(s.width * scale)), max(1, round(s.height * scale))),
                     Image.LANCZOS)
    if alpha < 0.996:
        s = s.copy()
        s.putalpha(s.getchannel("A").point(lambda v: int(v * alpha)))
    x, y = int(round(cx * scale_x(canvas) - s.width / 2)), int(round(cy * scale_y(canvas) - s.height / 2))
    canvas.alpha_composite(s, (max(0, x), max(0, y)), (max(0, -x), max(0, -y)))


def scale_x(c):
    return c.width / W


def scale_y(c):
    return c.height / H


# ---------------------------------------------------------------- overlays
SAFETY = ["Practise seated in a safe place. Breath holds are optional.",
          "Stop at your first urge to breathe, never your maximum.",
          "Skip breath holds if they are unsuitable for you."]
SAFETY_T = (1.4, EDIT["voice_start"] - 1.6)
TITLE_T = (EDIT["voice_start"] - 0.9, EDIT["voice_start"] + 10.2)
CLOSE_T = (LAST_WORD + 2.6, TOTAL - 0.2)


def section_titles():
    out = []
    for name, label in (("notice", "NOTICE"), ("soften", "SOFTEN"),
                        ("lessair", "BREATHE LESS"), ("letgo", "LET GO")):
        if name not in SECTIONS:
            continue
        s = SECTIONS[name][0]
        out.append((s - 0.6, s + 6.4, label))
    return out


TITLES = section_titles()


def lift(t, start, px=10, dur=1.6):
    return px * (1 - smooth((t - start) / dur))


def draw_overlays(c, t, k):
    # safety notice (omitted when the cut has no breath holds)
    a = 0.0 if NO_SAFETY else env(t, *SAFETY_T, 1.4, 1.2)
    if a > 0:
        paste(c, caps("BEFORE YOU BEGIN", 21, 700, OFF, 0.34, 0.7), W / 2, 432, a, k)
        paste(c, rule(40), W / 2, 462, a * 0.9, k)
        for i, l in enumerate(SAFETY):
            paste(c, line(l, ("sans", 31, 500), OFF, 0.75), W / 2,
                  500 + i * 50 + lift(t, SAFETY_T[0], 6), a, k)

    # opening title
    a = env(t, *TITLE_T, 2.2, 2.2)
    if a > 0:
        paste(c, caps("THE BREATH RESET", 24, 600, OFF, 0.42), W / 2, 438, a, k)
        paste(c, rule(), W / 2, 486, a, k)
        paste(c, line("Breathe Light", ("serif", 132, True), SAGE_BRIGHT, 0.4, 20),
              W / 2, 572 + lift(t, TITLE_T[0], 12, 2.4), a, k)

    # BOLT timer cards
    for i, b in enumerate(BOLTS):
        a = env(t, b["card_in"], b["timer_end"] + 1.5, 1.6, 1.3)
        if a <= 0:
            continue
        label = "BOLT SCORE  —  BEFORE" if i == 0 else "BOLT SCORE  —  AFTER"
        el = t - b["timer_start"]
        secs = 0 if el < 0 else min(60, int(el + 1e-6))
        paste(c, caps(label, 23, 700, OFF, 0.36, 0.85), W / 2, 396, a, k)
        paste(c, timer_sprite(secs), W / 2, 540, a, k)
        paste(c, line("Stop at your first clear urge to breathe.", ("serif", 44, True),
                      OFF, 0.5), W / 2, 680, a * 0.95, k)

    # section titles
    for s, e, label in TITLES:
        a = env(t, s, e, 1.8, 2.2)
        if a > 0:
            paste(c, rule(40), W / 2, 806, a * 0.9, k)
            paste(c, caps(label, 30, 600, OFF, 0.55), W / 2, 852 + lift(t, s, 8, 2.0), a, k)

    # closing title
    a = env(t, CLOSE_T[0], CLOSE_T[1] + 10, 3.0, 0.1)
    if a > 0:
        paste(c, caps("THE BREATH RESET", 26, 650, OFF, 0.42, 0.75), W / 2, 470, a, k)
        paste(c, rule(), W / 2, 520, a, k)
        a2 = a * smooth((t - CLOSE_T[0] - 1.0) / 2.6)
        paste(c, line(CLOSE_LINE, ("serif", CLOSE_SIZE, True), SAGE_BRIGHT, 0.4, 18),
              W / 2, 598 + lift(t, CLOSE_T[0] + 1.0, 10, 2.6), a2, k)


def text_scrim(t):
    """How much to darken behind centred text (0..1)."""
    safety_a = 0.0 if NO_SAFETY else env(t, *SAFETY_T, 1.4, 1.2) * 1.5
    return max(safety_a, env(t, *TITLE_T, 2.2, 2.2) * 0.7,
               env(t, CLOSE_T[0] - 1, TOTAL + 5, 3.5, 0.1) * 1.3, bolt_card_alpha(t))


def lower_scrim(t):
    return max((env(t, s, e, 1.8, 2.2) for s, e, _ in TITLES), default=0.0)


# ------------------------------------------------------------------ compose
def compose(A, t, out_w=W, out_h=H, frame_index=0):
    img = landscape(A, t)
    sd = subdue(t)
    if sd > 0:
        lum = (img * np.array([0.2126, 0.7152, 0.0722], np.float32)).sum(2, keepdims=True)
        img = (lum + (img - lum) * (1 - 0.18 * sd)) * (1 - 0.20 * sd * (0.4 + 0.6 * A.sun_protect))
    ts = text_scrim(t)
    if ts > 0:
        img = img * (1 - 0.30 * ts * A.card_scrim * A.sun_protect)
    ls = lower_scrim(t)
    if ls > 0:
        img = img * (1 - 0.28 * ls * A.lower_scrim)
    img = img * A.vignette

    fade = smooth(t / 3.0) * smooth((TOTAL - t) / 3.5)
    img = img * fade

    pil = camera(img, t, out_w, out_h).convert("RGBA")
    draw_overlays(pil, t, out_w / W)
    arr = np.asarray(pil.convert("RGB"), np.float32)
    g = A.grain[frame_index % len(A.grain)]
    g = np.asarray(Image.fromarray(g).resize((out_w, out_h), Image.BILINEAR))
    arr += g[..., None] * (2.6 * fade)
    return np.clip(arr + 0.5, 0, 255).astype(np.uint8)


# -------------------------------------------------------------------- render
_A = None


def _init():
    global _A
    _A = Assets()


def _chunk(args):
    ci, f0, f1, out_w, out_h, path, preview = args
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{out_w}x{out_h}", "-r", str(FPS), "-i", "-",
         "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast" if preview else "slow",
         "-crf", "24" if preview else "16", "-tune", "grain",
         "-g", str(FPS * 4), "-bf", "2",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         path], stdin=subprocess.PIPE)
    t0 = time.time()
    for i in range(f0, f1):
        enc.stdin.write(compose(_A, i / FPS, out_w, out_h, i).tobytes())
        if ci == 0 and (i - f0) % 240 == 0:
            done = (i - f0) / max(1, f1 - f0)
            print(f"  chunk0 {done * 100:5.1f}%  ({time.time() - t0:5.0f}s)", flush=True)
    enc.stdin.close()
    enc.wait()
    return path


def render(preview=False, workers=7):
    out_w, out_h = (960, 540) if preview else (W, H)
    out = FINAL.replace(".mp4", "-preview.mp4") if preview else FINAL
    tmpdir = os.path.join(HERE, "bl-chunks-" + os.path.basename(OUT_DIR.rstrip("/")))
    os.makedirs(tmpdir, exist_ok=True)
    n_chunks = workers * 3
    f0 = int(os.environ.get("BL_START_FRAME", "0"))
    bounds = np.linspace(f0, N_FRAMES, n_chunks + 1).astype(int)
    jobs = [(i, bounds[i], bounds[i + 1], out_w, out_h,
             os.path.join(tmpdir, f"c{i:03d}.mp4"), preview) for i in range(n_chunks)]
    t0 = time.time()
    with Pool(workers, initializer=_init) as pool:
        paths = pool.map(_chunk, jobs, chunksize=1)
    lst = os.path.join(tmpdir, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in paths)
    mux = ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst]
    if os.environ.get("BL_VIDEO_ONLY") == "1":
        mux += ["-c:v", "copy", "-an", out]
    else:
        mux += ["-i", MIX, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
                "-t", f"{TOTAL:.3f}", "-movflags", "+faststart", out]
    subprocess.run(mux, check=True)
    for p in paths:
        os.remove(p)
    mb = os.path.getsize(out) / 1e6
    print(f"saved {os.path.relpath(out, ROOT)} ({mb:.0f} MB, {time.time() - t0:.0f}s)")


def stills(times):
    os.makedirs(STILL_DIR, exist_ok=True)
    A = Assets()
    for t in times:
        p = os.path.join(STILL_DIR, f"t{t:07.2f}-{int(time.time()) % 100000}.jpg")
        Image.fromarray(compose(A, t)).save(p, quality=90)
        print("saved", os.path.relpath(p, ROOT))


def default_stills():
    times = [2.0, EDIT["voice_start"] + 4, SECTIONS["notice"][0] + 3,
             SECTIONS["soften"][0] + 3, SECTIONS["letgo"][0] + 3, CLOSE_T[0] + 6,
             TOTAL - 1.0]
    if len(BOLTS) >= 2:
        b1, b2 = BOLTS
        times += [b1["timer_start"] + 23.4, b2["timer_start"] + 41.2]
    return times


def thumbnail():
    """YouTube thumbnail: the Let Go landscape with the title set large."""
    A = Assets()
    t = SECTIONS["letgo"][0] + 40
    img = landscape(A, t) * A.vignette
    img = img * (1 - 0.32 * A.card_scrim * A.sun_protect)
    pil = camera(img, t, W, H).convert("RGBA")
    paste(pil, caps("THE BREATH RESET", 34, 650, OFF, 0.42, 0.8), W / 2, 380, 1, 1)
    paste(pil, rule(70), W / 2, 440, 1, 1)
    paste(pil, line("Breathe Light", ("serif", 230, True), SAGE_BRIGHT, 0.55, 26),
          W / 2, 580, 1, 1)
    paste(pil, caps("GUIDED BREATHING PRACTICE", 26, 650, OFF, 0.42, 0.8), W / 2, 760, 1, 1)
    out = os.path.join(OUT_DIR, "breathe-light-thumbnail.jpg")
    pil.convert("RGB").resize((1280, 720), Image.LANCZOS).save(out, quality=92)
    print("saved", os.path.relpath(out, ROOT))


if __name__ == "__main__":
    spec = os.environ.get("BL_STILLS")
    if os.environ.get("BL_THUMB"):
        thumbnail()
    elif spec:
        stills(default_stills() if spec == "1" else [float(x) for x in spec.split(",")])
    else:
        render(preview=bool(os.environ.get("BL_PREVIEW")))
