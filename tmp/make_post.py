#!/usr/bin/env python3
"""
The Breath Reset — Instagram carousel (static, 10 frames, 1080x1350 / 4:5).
"Your mind knows you're safe. Your body still feels on edge."

Same dark warm-black + sage language as the reels and the what-is-breathwork
deck. The visual thread here is the WINDOW OF TOLERANCE: two faint horizontal
lines mark the window, a state trace runs across it, and the orb rides that
trace — so the orb literally leaves the window when the copy says it does.

  frame 1  tense orb, tight ring            — body braced, mind fine
  frame 2  tense orb, rising particles      — tight chest, racing thoughts
  frame 3  orb on a state trace, no window  — your body has a state too
  frame 4  trace inside the window          — window of tolerance
  frame 5  trace spikes above, orb warm     — too activated
  frame 6  trace sinks below, orb cool/flat — too shut down
  frame 7  old window dashed, wider window  — build capacity
  frame 8  two traces converge into window  — breath down / breath up
  frame 9  orb in window, attention rings   — notice your state, match it
  frame 10 type-only end card               — one question to take away

Edit the frame copy at the bottom and re-run:  python3 tmp/make_post.py
Outputs -> assets/social/instagram/carousels/nervous-system/frame-01.png … frame-10.png
"""
import glob
import math
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350

# palette (matches the reels and the what-is-breathwork carousel)
BG, BG_LIFT, BG_DEEP = (16, 13, 11), (26, 21, 18), (10, 8, 7)
SAGE      = np.array([143, 165, 138], float)
SAGE_T    = (143, 165, 138)
SAGE_DARK = (95, 116, 94)
OFF       = (239, 231, 217)
MUTED     = (172, 164, 150)
CLAY      = (209, 144, 115)
CLAY_A    = np.array([209, 144, 115], float)
COOL      = np.array([118, 140, 150], float)     # shutdown: desaturated blue-grey
COOL_T    = (150, 170, 180)                      # lifted so it reads as text
WARMWHITE = np.array([232, 238, 226], float)

HERE  = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.dirname(HERE)
FONTS = os.path.join(ROOT, "breathing-reel", "fonts")
OUT   = os.path.join(ROOT, "assets", "social", "instagram", "carousels", "nervous-system")
os.makedirs(OUT, exist_ok=True)

def font(name, size): return ImageFont.truetype(os.path.join(FONTS, name), size)
def manrope(size, w=500):
    f = font("Manrope.ttf", size)
    try: f.set_variation_by_axes([w])
    except Exception: pass
    return f
def serif(size, it=False):
    return font("InstrumentSerif-Italic.ttf" if it else "InstrumentSerif-Regular.ttf", size)

ORB_CX, ORB_CY = W // 2, 420
BAND_CY, BAND_HALF = 420, 100          # the window of tolerance
TRACE_X0, TRACE_X1 = 100, W - 100

# --------------------------- background + orb ------------------------
def radial_alpha(size, stops):
    c = (size - 1) / 2
    yy, xx = np.mgrid[0:size, 0:size]
    r = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / (size / 2)
    xs = [s[0] for s in stops]; ys = [s[1] for s in stops]
    return np.clip(np.interp(r.ravel(), xs, ys).reshape(size, size), 0, 1)

def add_radial(canv, cx, cy, a2d, color, gain):
    ah, aw = a2d.shape
    x0, y0 = int(round(cx - aw / 2)), int(round(cy - ah / 2))
    cx0, cy0 = max(x0, 0), max(y0, 0); cx1, cy1 = min(x0 + aw, W), min(y0 + ah, H)
    if cx1 <= cx0 or cy1 <= cy0: return
    sub = a2d[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
    canv[cy0:cy1, cx0:cx1, :] += (sub[..., None] * gain) * color

def base_grad():
    c = np.array([W / 2, H * 0.30])
    yy, xx = np.mgrid[0:H, 0:W]
    maxd = np.hypot(max(c[0], W - c[0]), max(c[1], H - c[1]))
    r = np.sqrt((xx - c[0]) ** 2 + (yy - c[1]) ** 2) / maxd
    canv = np.zeros((H, W, 3), float)
    for i in range(3):
        canv[..., i] = np.interp(r.ravel(), [0, 0.46, 1],
                                 [BG_LIFT[i], BG[i], BG_DEEP[i]]).reshape(H, W)
    return canv

def orb(canv, cx, cy, r, glow, core, *, color=SAGE, warm=False):
    g = radial_alpha(int(r * 3), [(0, 0.55), (0.6, 0), (1, 0)])
    add_radial(canv, cx, cy, g, color, glow)
    if warm:                                        # activation: faint clay heat
        add_radial(canv, cx, cy, g, CLAY_A, 0.12)
    body = radial_alpha(int(r), [(0, 0.85), (0.3, 0.5), (0.55, 0.2),
                                 (0.72, 0.04), (0.82, 0), (1, 0)])
    add_radial(canv, cx, cy, body, color, 0.85)
    c = radial_alpha(int(r * 0.7), [(0, 0.6), (0.3, 0.14), (0.5, 0), (1, 0)])
    add_radial(canv, cx, cy, c, WARMWHITE, core)

def drift(canv, cx, cy, gain, *, n=16, spread=520, reach=400, seed=5):
    """Streaked particles rising off the orb — the felt lift of activation."""
    rng = np.random.RandomState(seed)
    spr = radial_alpha(40, [(0, 0.9), (0.4, 0.4), (1, 0)])
    for _ in range(n):
        x = cx + (rng.random() - 0.5) * spread
        y = cy - (40 + rng.random() * reach)
        s = int(14 + rng.random() * 26)
        a = np.asarray(Image.fromarray((spr * 255).astype(np.uint8), "L")
                       .resize((s, int(s * 1.7)), Image.BILINEAR), float) / 255.0
        add_radial(canv, x, y, a, SAGE * 1.3, gain * (0.4 + 0.6 * rng.random()))

def finish(canv):
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt((xx - W / 2) ** 2 + (yy - H / 2) ** 2) / np.hypot(W / 2, H / 2)
    vig = np.clip((r - 0.52) / 0.48, 0, 1) ** 1.5
    canv *= (1 - 0.5 * vig[..., None])
    img = Image.fromarray(np.clip(canv, 0, 255).astype(np.uint8), "RGB")
    noise = np.random.RandomState(11).randn(H, W) * 6
    arr = np.asarray(img, float) + noise[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

# --------------------------- window + trace motifs --------------------
def rings(img, cx, cy, base, specs):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for mult, op in specs:
        rr = base * mult
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                  outline=SAGE_T + (int(op * 255),), width=2)
    img.alpha_composite(ov)

def edge_fade(x, x0=TRACE_X0, x1=TRACE_X1, f=0.16):
    t = (x - x0) / (x1 - x0)
    return max(0.0, min(1.0, t / f, (1 - t) / f))

def hline(d, y, op, *, dash=None, width=2, color=SAGE_T):
    step = 2
    for x in range(TRACE_X0, TRACE_X1, step):
        if dash and (x // dash) % 2: continue
        d.line([x, y, x + step, y], fill=color + (int(op * edge_fade(x) * 255),), width=width)

def window(img, half=BAND_HALF, *, op=0.30, fill=0.045, dash=None):
    """Two faint lines and a barely-there fill: the window of tolerance."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    if fill:
        for x in range(TRACE_X0, TRACE_X1, 2):
            d.rectangle([x, BAND_CY - half, x + 2, BAND_CY + half],
                        fill=SAGE_T + (int(fill * edge_fade(x) * 255),))
    hline(d, BAND_CY - half, op, dash=dash)
    hline(d, BAND_CY + half, op, dash=dash)
    img.alpha_composite(ov)

def wiggle(x, amp=1.0, seed=0.0):
    return amp * (17 * math.sin(2 * math.pi * x / 270 + seed)
                  + 7 * math.sin(2 * math.pi * x / 101 + 1.3 + seed))

def gauss(x, xc, s): return math.exp(-((x - xc) / s) ** 2)

def trace(img, y_fn, *, op=0.55, width=3, color_fn=None, x0=TRACE_X0, x1=TRACE_X1):
    """The state line. y_fn(x) -> y; color_fn(x) -> rgb (defaults to sage)."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    prev = None
    for x in range(x0, x1 + 1, 2):
        p = (x, y_fn(x))
        if prev:
            c = color_fn(x) if color_fn else SAGE_T
            d.line([prev, p], fill=tuple(int(v) for v in c) + (int(op * edge_fade(x) * 255),),
                   width=width)
        prev = p
    img.alpha_composite(ov)

def mix(a, b, t): return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))

# ----------------------------- text ----------------------------------
def center_tracked(d, cy, text, fnt, fill, track, cx=None):
    cx = W / 2 if cx is None else cx
    w = sum(d.textlength(c, font=fnt) + track for c in text) - track
    x = cx - w / 2
    for c in text:
        d.text((x, cy), c, font=fnt, fill=fill); x += d.textlength(c, font=fnt) + track

def wrap(d, text, fnt, max_w):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=fnt) > max_w and cur: lines.append(cur); cur = w
        else: cur = t
    if cur: lines.append(cur)
    return lines

def line_h(it): return it["lh"] + it.get("gap", 0)

def draw_block(d, items, center_y):
    total = sum(line_h(it) for it in items)
    y = center_y - total / 2
    for it in items:
        cx = it.get("cx", W / 2)
        if it["kind"] == "seg":                      # mixed inline segments
            segs = it["segs"]
            tw = sum(d.textlength(s[0], font=s[1]) for s in segs)
            x = cx - tw / 2
            for t, f, fill in segs:
                d.text((x, y), t, font=f, fill=fill); x += d.textlength(t, font=f)
        elif it["kind"] == "track":
            center_tracked(d, y, it["text"], it["font"], it["fill"], it["track"], cx=cx)
        else:
            d.text((cx, y), it["text"], font=it["font"], fill=it["fill"], anchor="ma")
        y += line_h(it)
    return y

# item builders -------------------------------------------------------
def L(text, font, fill, lh, gap=0, cx=None):
    return dict(kind="line", text=text, font=font, fill=fill, lh=lh, gap=gap, cx=cx or W / 2)
def T(text, font, fill, track, lh, gap=0, cx=None):
    return dict(kind="track", text=text, font=font, fill=fill, track=track, lh=lh, gap=gap, cx=cx or W / 2)
def S(segs, lh, gap=0):
    return dict(kind="seg", segs=segs, lh=lh, gap=gap)

def para(d, text, font, fill, lh, max_w=860, gap=0):
    lines = wrap(d, text, font, max_w)
    return [L(ln, font, fill, lh, gap if i == len(lines) - 1 else 0) for i, ln in enumerate(lines)]

# type scale — every frame draws from these, nothing ad hoc
def f_hook(it=False): return serif(78, it)     # the one big statement per frame
def f_lead(it=False): return serif(56, it)     # secondary serif lines, column heads
def f_body():         return manrope(34, 400)  # supporting prose
def f_item():         return manrope(36, 500)  # list items
def f_item_sm():      return manrope(30, 500)  # list items in two side-by-side columns
def f_head():         return manrope(28, 600)  # tracked labels (matches what-is-breathwork)

TOTAL = 10

def build(idx, art_fn, region_y, items_fn, *, chrome=True):
    """art_fn paints the canvas pass and returns an optional RGBA overlay pass."""
    canv = base_grad()
    overlay = art_fn(canv)
    img = finish(canv)
    if overlay: overlay(img)

    d = ImageDraw.Draw(img)
    if chrome:
        center_tracked(d, 74, "THE BREATH RESET", manrope(22, 600), SAGE_DARK, 6)
        center_tracked(d, 1258, f"{idx:02d}  /  {TOTAL}", manrope(20, 500), (110, 104, 95), 4)

    draw_block(d, items_fn(d), region_y)
    out = os.path.join(OUT, f"frame-{idx:02d}.png")
    img.convert("RGB").save(out); print("saved", os.path.relpath(out, ROOT))

frames = []

# 1 — the mind is fine, the body is braced -----------------------------
def art1(canv):
    orb(canv, ORB_CX, ORB_CY, 300, 0.42, 0.50)
    # a ring pulled in tight to the body: held, braced
    return lambda img: rings(img, ORB_CX, ORB_CY, 150, [(0.86, 0.20), (0.98, 0.10)])

frames.append(lambda: build(1, art1, 980, lambda d: [
    L("Your mind knows", f_hook(), OFF, 88),
    L("you’re safe.", f_hook(), OFF, 88, gap=40),
    L("Your body still", f_hook(), OFF, 88),
    S([("feels ", f_hook(), OFF), ("on edge.", f_hook(True), SAGE_T)], 88),
]))

# 2 — what it feels like: type only, the question up top ----------------
ROW_Y = [700, 860, 1020]            # centre of each line

def art2(canv):
    def ov(img):
        o = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(o)
        for y in (ROW_Y[0] + 80, ROW_Y[1] + 80):                   # hairline dividers
            dd.line([300, y, W - 300, y], fill=SAGE_T + (50,), width=1)
        img.alpha_composite(o)
    return ov

def frame2_items(d):
    draw_block(d, [L("Ever noticed that?", f_hook(), OFF, 88, gap=28),
                   L("Nothing is actually wrong. But…", f_body(), MUTED, 52)], 330)
    rows = [("your chest is ", "tight."),
            ("your thoughts are ", "racing."),
            ("you just don’t feel ", "present.")]
    for (lead, key), cy in zip(rows, ROW_Y):
        draw_block(d, [S([(lead, f_lead(), OFF), (key, f_lead(True), SAGE_T)], 70)], cy)
    return []

frames.append(lambda: build(2, art2, 0, frame2_items))

# 3 — the body has a state of its own ----------------------------------
def art3(canv):
    orb(canv, ORB_CX, ORB_CY, 260, 0.44, 0.54)
    return lambda img: trace(img, lambda x: BAND_CY + wiggle(x, 1.4), op=0.42)

frames.append(lambda: build(3, art3, 960, lambda d: [
    L("That’s because anxiety", f_hook(), OFF, 88),
    L("isn’t only about what", f_hook(), OFF, 88),
    L("you’re thinking.", f_hook(), OFF, 88, gap=50),
    S([("Your body has a ", f_lead(), MUTED), ("state", f_lead(True), SAGE_T),
       (" too.", f_lead(), MUTED)], 72),
]))

# 4 — the window of tolerance ------------------------------------------
def art4(canv):
    orb(canv, ORB_CX, ORB_CY, 250, 0.44, 0.56)
    def ov(img):
        window(img)
        trace(img, lambda x: BAND_CY + wiggle(x, 1.8))
    return ov

frames.append(lambda: build(4, art4, 940, lambda d: (
    [L("One useful way to think about this:", f_body(), MUTED, 52, gap=14),
     S([("your ", f_hook(), OFF), ("window of tolerance.", f_hook(True), SAGE_T)], 92, gap=36)] +
    para(d, "The range where you can feel stress, pressure or emotion "
            "without being overwhelmed by it.", f_body(), MUTED, 52, max_w=780, gap=30) +
    para(d, "Inside it, you can think clearly, stay present, and respond "
            "rather than react.", f_body(), OFF, 52, max_w=780)
)))

# 5 — out the top: too activated ---------------------------------------
SPIKE = 176

def art5(canv):
    oy = BAND_CY - SPIKE
    orb(canv, ORB_CX, oy, 290, 0.70, 0.86, warm=True)
    drift(canv, ORB_CX, oy, 0.26, n=12, spread=420, reach=110, seed=8)
    def y(x):
        g = gauss(x, ORB_CX, 150)
        return BAND_CY + wiggle(x, 1.4) * (1 - g) - SPIKE * g \
               + g * 9 * math.sin(2 * math.pi * x / 34)           # jittery at the peak
    def col(x): return mix(SAGE_T, CLAY, gauss(x, ORB_CX, 170))
    def ov(img):
        window(img)
        trace(img, y, color_fn=col)
    return ov

frames.append(lambda: build(5, art5, 985, lambda d: [
    L("When you move outside that window,", f_lead(), OFF, 70),
    L("your system shifts into protection.", f_lead(), OFF, 70, gap=46),
    T("TOO ACTIVATED  ·  FIGHT / FLIGHT", f_head(), CLAY, 3, 44, gap=28),
    L("racing thoughts", f_item(), OFF, 58),
    L("tight chest", f_item(), OFF, 58),
    L("urgency", f_item(), OFF, 58),
    L("always “on”", f_item(), OFF, 58),
]))

# 6 — out the bottom: too shut down ------------------------------------
DIP = 210

def art6(canv):
    oy = BAND_CY + DIP
    orb(canv, ORB_CX, oy, 240, 0.24, 0.18, color=COOL)
    def y(x):
        g = gauss(x, ORB_CX, 170)
        return BAND_CY + wiggle(x, 1.4) * (1 - 0.92 * g) + DIP * g  # flat at the bottom
    def col(x): return mix(SAGE_T, COOL_T, gauss(x, ORB_CX, 190))
    def ov(img):
        window(img)
        trace(img, y, color_fn=col, op=0.45)
    return ov

frames.append(lambda: build(6, art6, 1015, lambda d: [
    L("Or you can go the other way.", f_lead(), OFF, 70, gap=40),
    T("TOO SHUT DOWN  ·  FREEZE", f_head(), COOL_T, 3, 44, gap=28),
    L("numbness", f_item(), OFF, 58),
    L("flatness", f_item(), OFF, 58),
    L("brain fog", f_item(), OFF, 58),
    L("feeling disconnected", f_item(), OFF, 58),
]))

# 7 — capacity: the window gets wider ----------------------------------
WIDE = 160

def art7(canv):
    orb(canv, ORB_CX, ORB_CY, 280, 0.50, 0.66)
    def y(x):   # bigger swings, a real stress bump — and it still stays inside
        return BAND_CY + wiggle(x, 2.2) - 112 * gauss(x, 380, 70) + 92 * gauss(x, 760, 80)
    def ov(img):
        window(img, BAND_HALF, op=0.20, fill=0, dash=10)
        window(img, WIDE, op=0.34, fill=0.04)
        trace(img, y)
    return ov

frames.append(lambda: build(7, art7, 985, lambda d: (
    [L("And over time,", f_hook(), OFF, 86),
     S([("your window can ", f_hook(), OFF), ("widen.", f_hook(True), SAGE_T)], 86, gap=46)] +
    para(d, "More capacity means stress can move through you "
            "without throwing you completely off centre.",
         f_body(), MUTED, 52, max_w=800)
)))

# 8 — two ways back in: breath down, breath up -------------------------
CONVERGE = ORB_CX

def art8(canv):
    orb(canv, ORB_CX, ORB_CY, 250, 0.48, 0.62)
    def approach(x):            # 1 far out on the left -> 0 at the convergence point
        t = max(0.0, min(1.0, (CONVERGE - x) / (CONVERGE - TRACE_X0)))
        return t * t * (3 - 2 * t)
    def from_above(x):          # fast and jagged, slowing as it comes down
        a = approach(x)
        return BAND_CY - 220 * a + 11 * a * math.sin(2 * math.pi * x / (30 + 220 * (1 - a))) \
               + wiggle(x, 0.9) * (1 - a)
    def from_below(x):          # nearly flat, gaining movement as it rises
        a = approach(x)
        return BAND_CY + 220 * a + wiggle(x, 0.9 * (1 - 0.85 * a))
    def ov(img):
        window(img)
        trace(img, from_above, color_fn=lambda x: mix(SAGE_T, CLAY, approach(x)))
        trace(img, from_below, color_fn=lambda x: mix(SAGE_T, COOL_T, approach(x)),
              x1=CONVERGE)
    return ov

LCOL, RCOL = W / 2 - 250, W / 2 + 250

def column(cx, label, color, head, lines):
    return [T(label, f_head(), color, 3, 40, gap=10, cx=cx),
            L(head, f_lead(True), SAGE_T, 70, gap=8, cx=cx)] + \
           [L(ln, f_item_sm(), OFF, 46, cx=cx) for ln in lines]

def frame8_items(d):
    lead = [L("And this is where", f_hook(), OFF, 86),
            L("the breath can help.", f_hook(), OFF, 86, gap=52)]
    left = column(LCOL, "TOO ACTIVATED", CLAY, "Bring it down.",
                  ["Slower breathing", "Nose breathing", "Smaller, softer breaths"])
    right = column(RCOL, "TOO SHUT DOWN", COOL_T, "Gently energise.",
                   ["More activating breathing", "Deeper, more expansive breaths",
                    "A slightly quicker rhythm"])
    # draw the two columns side by side: same top, each its own height
    head_h = sum(line_h(it) for it in lead)
    col_h = max(sum(line_h(it) for it in left), sum(line_h(it) for it in right))
    top = 945 - (head_h + col_h) / 2
    draw_block(d, lead, top + head_h / 2)
    for col in (left, right):
        h = sum(line_h(it) for it in col)
        draw_block(d, col, top + head_h + h / 2)
    return []

frames.append(lambda: build(8, art8, 0, frame8_items))

# 9 — the point: notice, then match -------------------------------------
def art9(canv):
    orb(canv, ORB_CX, ORB_CY, 280, 0.52, 0.70)
    def ov(img):
        window(img, op=0.22, fill=0.03)
        trace(img, lambda x: BAND_CY + wiggle(x, 1.6), op=0.40)
        rings(img, ORB_CX, ORB_CY, 140, [(1.18, 0.18), (1.46, 0.10), (1.78, 0.05)])
    return ov

frames.append(lambda: build(9, art9, 990, lambda d: (
    [L("That’s why breathwork", f_hook(), OFF, 86),
     L("isn’t just", f_hook(), OFF, 86),
     L("“take a deep breath.”", f_hook(True), SAGE_T, 86, gap=48)] +
    para(d, "It’s learning to notice your state — and use the breath in a way "
            "that actually matches it.", f_body(), MUTED, 52, max_w=800)
)))

# 10 — end card: settled, back inside the window ------------------------
def art10(canv):
    orb(canv, ORB_CX, ORB_CY, 380, 0.58, 0.82)
    def ov(img):
        window(img, op=0.20, fill=0.03)
        trace(img, lambda x: BAND_CY + wiggle(x, 1.2), op=0.34)
    return ov

frames.append(lambda: build(10, art10, 960, lambda d: [
    L("The goal isn’t to feel", f_hook(), OFF, 86),
    S([("calm", f_hook(True), SAGE_T), (" all the time.", f_hook(), OFF)], 86, gap=34),
    L("It’s to notice the state you’re in —", f_body(), MUTED, 52),
    L("and respond in a way that helps.", f_body(), MUTED, 52, gap=84),
    L("The Breath Reset", serif(96), OFF, 104, gap=14),
    L("Relax. Retrain. Release.", serif(46, True), SAGE_T, 64),
], chrome=False))

if __name__ == "__main__":
    for old in glob.glob(os.path.join(OUT, "frame-*.png")):
        os.remove(old)
    for fr in frames:
        fr()
    print(f"Done — {TOTAL} frames in", os.path.relpath(OUT, ROOT))
