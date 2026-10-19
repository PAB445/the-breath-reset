#!/usr/bin/env python3
"""
The Breath Reset — Instagram carousel (static, 10 frames, 1080x1350 / 4:5).
"What actually is breathwork?"

Same dark warm-black + sage language as the nervous-system carousel, but the
visual thread is different because the story is different. That deck tracked
nervous-system STATES; this one is about the breath itself, so the motif is
RHYTHM: a wave under the orb whose speed, depth and inhale/exhale ratio match
the copy on the frame.

  frame 1  one orb, faint count ticks      — breathing happens unnoticed
  frame 2  two orbs, fast vs slow wave     — stress breath vs calm breath
  frame 3  one orb inside a circulation    — it works both ways
  frame 4  one orb, one crisp chosen wave  — deliberate
  frame 5  five orbs, none highlighted     — no single "right" breath
  frame 6  wide orb, long exhale, settling — relax
  frame 7  small orb, light even wave      — retrain
  frame 8  bright orb, rising, connected   — release
  frame 9  three orbs, one per pathway     — relax / retrain / release
  frame 10 type-only end card

Edit the frame copy at the bottom and re-run: python3 tmp/make_post_breathwork.py
Outputs -> assets/social/instagram/carousels/what-is-breathwork/frame-01.png … frame-10.png
"""
import math
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350

# palette (matches the reels and the nervous-system carousel)
BG, BG_LIFT, BG_DEEP = (16, 13, 11), (26, 21, 18), (10, 8, 7)
SAGE      = np.array([143, 165, 138], float)
SAGE_T    = (143, 165, 138)
SAGE_DARK = (95, 116, 94)
OFF       = (239, 231, 217)
MUTED     = (172, 164, 150)
CLAY      = (209, 144, 115)
CLAY_A    = np.array([209, 144, 115], float)
WARMWHITE = np.array([232, 238, 226], float)

HERE  = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.dirname(HERE)
FONTS = os.path.join(ROOT, "breathing-reel", "fonts")
OUT   = os.path.join(ROOT, "assets", "social", "instagram", "carousels", "what-is-breathwork")
os.makedirs(OUT, exist_ok=True)

def font(name, size): return ImageFont.truetype(os.path.join(FONTS, name), size)
def manrope(size, w=500):
    f = font("Manrope.ttf", size)
    try: f.set_variation_by_axes([w])
    except Exception: pass
    return f
def serif(size, it=False):
    return font("InstrumentSerif-Italic.ttf" if it else "InstrumentSerif-Regular.ttf", size)

# Instrument Serif has no arrow or subscript glyphs — those lines use Manrope.
ORB_CX, ORB_CY = W // 2, 408          # the orb sits in the same place every frame
WAVE_Y = 690                          # rhythm line lives between orb and copy

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
    if warm:                                        # release: faint clay heat
        add_radial(canv, cx, cy, g, CLAY_A, 0.10)
    body = radial_alpha(int(r), [(0, 0.85), (0.3, 0.5), (0.55, 0.2),
                                 (0.72, 0.04), (0.82, 0), (1, 0)])
    add_radial(canv, cx, cy, body, color, 0.85)
    c = radial_alpha(int(r * 0.7), [(0, 0.6), (0.3, 0.14), (0.5, 0), (1, 0)])
    add_radial(canv, cx, cy, c, WARMWHITE, core)

def drift(canv, cx, cy, gain, *, up=True, n=16, spread=520, reach=400, seed=5):
    """Streaked particles. Up = activation rising; down = the body settling."""
    rng = np.random.RandomState(seed)
    spr = radial_alpha(40, [(0, 0.9), (0.4, 0.4), (1, 0)])
    for _ in range(n):
        x = cx + (rng.random() - 0.5) * spread
        y = cy + (-1 if up else 1) * (40 + rng.random() * reach)
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

# --------------------------- rhythm + ring motifs ---------------------
def rings(img, cx, cy, base, specs):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for mult, op in specs:
        rr = base * mult
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                  outline=SAGE_T + (int(op * 255),), width=2)
    img.alpha_composite(ov)

def count_ticks(img, cx, cy, r, n=20, op=0.22):
    """n faint marks around the orb — the breaths that pass without notice."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for i in range(n):
        a = -math.pi / 2 + i * 2 * math.pi / n
        x0, y0 = cx + math.cos(a) * r, cy + math.sin(a) * r
        x1, y1 = cx + math.cos(a) * (r + 16), cy + math.sin(a) * (r + 16)
        fade = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(a * 3))   # uneven, not a dial
        d.line([x0, y0, x1, y1], fill=SAGE_T + (int(op * fade * 255),), width=2)
    img.alpha_composite(ov)

def circulation(img, cx, cy, r, op=0.38):
    """A ring whose brightness rotates — state feeding breath feeding state."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    steps = 240
    for i in range(steps):
        a0 = i * 2 * math.pi / steps
        a1 = (i + 1.6) * 2 * math.pi / steps
        lobe = abs(math.sin(a0 - math.pi / 4)) ** 1.6                # two bright lobes
        d.line([cx + math.cos(a0) * r, cy + math.sin(a0) * r,
                cx + math.cos(a1) * r, cy + math.sin(a1) * r],
               fill=SAGE_T + (int(op * lobe * 255),), width=3)
    img.alpha_composite(ov)

def breath_wave(img, cy, *, cycles, amp, span=760, inhale=0.5, op=0.42,
                width=3, cx=None, color=SAGE_T, fade_ends=True):
    """One rhythm line. `inhale` is the share of each cycle spent rising, so
    inhale=0.32 draws a short inhale and a long exhale."""
    cx = W / 2 if cx is None else cx
    x0, x1 = cx - span / 2, cx + span / 2
    pts, n = [], 460
    for i in range(n + 1):
        t = i / n
        p = (t * cycles) % 1.0
        if p < inhale: u = 0.5 * (1 - math.cos(math.pi * p / inhale))
        else:          u = 0.5 * (1 + math.cos(math.pi * (p - inhale) / (1 - inhale)))
        pts.append((x0 + t * (x1 - x0), cy - (u - 0.5) * 2 * amp))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for i in range(n):
        t = (i + 0.5) / n
        edge = min(1.0, t / 0.18, (1 - t) / 0.18) if fade_ends else 1.0
        d.line([pts[i], pts[i + 1]], fill=color + (int(op * edge * 255),), width=width)
    img.alpha_composite(ov)

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
        if it["kind"] == "seg":                      # mixed inline segments
            segs = it["segs"]
            tw = sum(d.textlength(s[0], font=s[1]) for s in segs)
            x = W / 2 - tw / 2
            for s in segs:
                t, f, fill = s[0], s[1], s[2]
                dy = s[3] if len(s) > 3 else 0       # baseline shift, e.g. subscripts
                d.text((x, y + dy), t, font=f, fill=fill); x += d.textlength(t, font=f)
        elif it["kind"] == "track":
            center_tracked(d, y, it["text"], it["font"], it["fill"], it["track"])
        else:
            d.text((W / 2, y), it["text"], font=it["font"], fill=it["fill"], anchor="ma")
        y += line_h(it)
    return y

# item builders -------------------------------------------------------
def L(text, font, fill, lh, gap=0):        return dict(kind="line", text=text, font=font, fill=fill, lh=lh, gap=gap)
def T(text, font, fill, track, lh, gap=0): return dict(kind="track", text=text, font=font, fill=fill, track=track, lh=lh, gap=gap)
def S(segs, lh, gap=0):                    return dict(kind="seg", segs=segs, lh=lh, gap=gap)

def para(d, text, font, fill, lh, max_w=880, gap=0):
    lines = wrap(d, text, font, max_w)
    return [L(ln, font, fill, lh, gap if i == len(lines) - 1 else 0) for i, ln in enumerate(lines)]

# fonts used a lot
def f_hook(it=False): return serif(78, it)
def f_mid(it=False):  return serif(58, it)
def f_body():         return manrope(34, 400)
def f_item():         return manrope(34, 500)   # sized so every list item fits one line
def f_head():         return manrope(28, 600)

TOTAL = 10

def build(idx, art_fn, region_y, items_fn, *, chrome=True):
    """art_fn paints the imagery (canvas pass then overlay pass); items_fn the copy."""
    canv = base_grad()
    overlay = art_fn(canv)                   # returns a callable for RGBA work
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

# 1 — 20,000 breaths, none of them noticed -----------------------------
def art1(canv):
    orb(canv, ORB_CX, ORB_CY, 296, 0.36, 0.42)
    return lambda img: count_ticks(img, ORB_CX, ORB_CY, 252)

frames.append(lambda: build(1, art1, 1000, lambda d: [
    L("What actually is", f_hook(), OFF, 88),
    S([("breathwork", f_hook(True), SAGE_T), ("?", f_hook(), OFF)], 88, gap=62),
    S([("We breathe around ", f_body(), MUTED), ("20,000", manrope(34, 600), OFF),
       (" times a day.", f_body(), MUTED)], 52),
] + para(d, "But most of us rarely think about how we breathe.", f_body(), MUTED, 52)))

# 2 — the same breath under stress and under calm ----------------------
LX, RX = 328, 752

def art2(canv):
    orb(canv, LX, ORB_CY, 186, 0.50, 0.62)       # stress: small, tight, brighter
    orb(canv, RX, ORB_CY, 288, 0.40, 0.46)       # calm: wide, soft
    def ov(img):
        breath_wave(img, 640, cycles=7, amp=13, span=330, cx=LX, op=0.40)
        breath_wave(img, 640, cycles=1.6, amp=30, span=360, cx=RX, op=0.34)
    return ov

frames.append(lambda: build(2, art2, 1010, lambda d: [
    L("Your breath changes", serif(74), OFF, 84),
    S([("with your ", serif(74), OFF), ("state.", serif(74, True), SAGE_T)], 84, gap=66),
    S([("Stress ", manrope(38, 600), OFF), ("→", manrope(38, 400), SAGE_T),
       ("  faster, shallower breathing", manrope(38, 400), MUTED)], 62),
    S([("Calm ", manrope(38, 600), OFF), ("→", manrope(38, 400), SAGE_T),
       ("  slower, easier breathing", manrope(38, 400), MUTED)], 62),
]))

# 3 — the loop runs in both directions ---------------------------------
def art3(canv):
    orb(canv, ORB_CX, ORB_CY, 264, 0.44, 0.52)
    return lambda img: circulation(img, ORB_CX, ORB_CY, 208)

frames.append(lambda: build(3, art3, 990, lambda d: [
    T("BUT HERE’S THE INTERESTING BIT", f_head(), CLAY, 3, 62, gap=52),
    S([("It works ", serif(76), OFF), ("both ways.", serif(76, True), SAGE_T)], 92, gap=58),
    L("Your state affects your breath.", manrope(36, 400), MUTED, 56),
    L("And your breath can influence your state.", manrope(36, 400), OFF, 56),
]))

# 4 — deliberate: one chosen rhythm ------------------------------------
def art4(canv):
    orb(canv, ORB_CX, ORB_CY, 320, 0.52, 0.76)
    def ov(img):
        rings(img, ORB_CX, ORB_CY, 160, [(1.30, 0.18)])
        breath_wave(img, WAVE_Y, cycles=1, amp=34, span=520, inhale=0.44, op=0.46, width=4)
    return ov

frames.append(lambda: build(4, art4, 1000, lambda d: [
    L("That’s what breathwork is:", serif(52), MUTED, 74, gap=44),
    L("Using your breath", serif(70), OFF, 84),
    S([("deliberately", serif(70, True), SAGE_T), (" to", serif(70), OFF)], 84),
    L("influence how you feel.", serif(70), OFF, 84),
]))

# 5 — many rhythms, none of them the answer ----------------------------
def art5(canv):
    specs = [(-372, 118, 0.30), (-188, 158, 0.38), (0, 132, 0.34),
             (196, 172, 0.36), (380, 126, 0.30)]
    for dx, r, g in specs:
        orb(canv, ORB_CX + dx, ORB_CY, r, g, g * 1.15)
    def ov(img):
        for dx, cyc, amp in [(-372, 5, 10), (-188, 2, 22), (0, 3.4, 14),
                             (196, 1.4, 26), (380, 6, 9)]:
            breath_wave(img, 632, cycles=cyc, amp=amp, span=152,
                        cx=ORB_CX + dx, op=0.30, width=2)
    return ov

frames.append(lambda: build(5, art5, 1000, lambda d: [
    L("And there isn’t one", serif(74), OFF, 88),
    S([("“right”", serif(74, True), SAGE_T), (" breath.", serif(74), OFF)], 88, gap=62),
] + para(d, "Different breathing patterns can be useful for different things.",
         f_body(), MUTED, 52, max_w=800)))

# 6 — relax: long exhale, everything settling downward ------------------
def art6(canv):
    orb(canv, ORB_CX, ORB_CY, 372, 0.50, 0.68)
    drift(canv, ORB_CX, ORB_CY, 0.14, up=False, n=9, spread=560, reach=210, seed=3)
    def ov(img):
        rings(img, ORB_CX, ORB_CY, 186, [(1.24, 0.13)])
        breath_wave(img, WAVE_Y + 58, cycles=2, amp=26, span=720, inhale=0.30, op=0.40)
    return ov

frames.append(lambda: build(6, art6, 1025, lambda d: [
    L("Sometimes you want to", serif(66), OFF, 80),
    L("slow things down.", serif(66, True), SAGE_T, 80, gap=56),
] + para(d, "Slower, more comfortable breathing can help you settle "
            "when you’re feeling stressed.", f_body(), MUTED, 52, max_w=820)))

# 7 — retrain: small, light, even --------------------------------------
def art7(canv):
    orb(canv, ORB_CX, ORB_CY, 230, 0.36, 0.64)
    def ov(img):
        # the wave runs straight through the orb — everyday breathing, always there
        breath_wave(img, ORB_CY + 148, cycles=6, amp=11, span=820, op=0.34, width=2)
    return ov

frames.append(lambda: build(7, art7, 930, lambda d: (
    [L("And then there’s how you", serif(56), OFF, 72),
     L("breathe throughout the day.", serif(56), OFF, 72, gap=40)] +
    para(d, "The aim is to make your everyday breathing more efficient.",
         f_body(), MUTED, 50, max_w=800, gap=52) + [
    # all three items share one size and weight — a list, not a list plus a caption
    L("Nasal breathing.", f_item(), OFF, 62),
    S([("CO", f_item(), OFF), ("2", manrope(22, 400), OFF, 15),
       (" tolerance.", f_item(), OFF)], 62),
    L("Breathing comfortably during movement and exercise.", f_item(), OFF, 62),
])))

# 8 — release: faster, connected, rising -------------------------------
def art8(canv):
    orb(canv, ORB_CX, ORB_CY, 344, 0.74, 0.86, warm=True)
    drift(canv, ORB_CX, ORB_CY, 0.34, up=True, n=16, spread=560, reach=240, seed=8)
    def ov(img):
        rings(img, ORB_CX, ORB_CY, 172, [(1.22, 0.16), (1.52, 0.09)])
        breath_wave(img, WAVE_Y, cycles=5, amp=30, span=760, inhale=0.5,
                    op=0.46, fade_ends=False)      # unbroken: no pause between breaths
    return ov

frames.append(lambda: build(8, art8, 985, lambda d: (
    [L("And sometimes you use the", serif(56), OFF, 72),
     L("breath to go a little deeper.", serif(56), OFF, 72, gap=44)] +
    para(d, "Some practices use faster, more connected breathing to create "
            "more activation in the body.", manrope(32, 400), MUTED, 48,
         max_w=800, gap=40) +
    para(d, "As you become more aware of what’s happening inside, you may notice "
            "emotion, sensation and whatever else starts to come up.",
         manrope(32, 400), SAGE_T, 48, max_w=800)
)))

# 9 — the three pathways, each with its own signature ------------------
PATH_Y = 340

def art9(canv):
    orb(canv, ORB_CX - 300, PATH_Y, 176, 0.40, 0.46)              # relax: wide, soft
    orb(canv, ORB_CX,       PATH_Y, 118, 0.30, 0.60)              # retrain: small, light
    orb(canv, ORB_CX + 300, PATH_Y, 196, 0.62, 0.80, warm=True)   # release: bright
    def ov(img):
        breath_wave(img, PATH_Y + 132, cycles=1.4, amp=17, span=210,
                    cx=ORB_CX - 300, inhale=0.30, op=0.32, width=2)
        breath_wave(img, PATH_Y + 132, cycles=5, amp=8, span=210,
                    cx=ORB_CX, op=0.30, width=2)
        breath_wave(img, PATH_Y + 132, cycles=4, amp=19, span=210,
                    cx=ORB_CX + 300, op=0.38, width=2, fade_ends=False)
    return ov

def pathway(name, lines, gap=0):
    return [T(name, manrope(30, 700), SAGE_T, 6, 50)] + \
           [L(ln, manrope(32, 400), MUTED, 44, gap if i == len(lines) - 1 else 0)
            for i, ln in enumerate(lines)]

frames.append(lambda: build(9, art9, 890, lambda d: (
    para(d, "That’s why I think about breathwork in three pathways:",
         manrope(34, 500), OFF, 48, max_w=760, gap=50) +
    pathway("RELAX", ["Slower, comfortable breathing",
                      "Help the body settle"], gap=38) +
    pathway("RETRAIN", ["Light, efficient everyday breathing",
                        "Improve how you breathe day to day"], gap=38) +
    pathway("RELEASE", ["Faster, more connected breathing",
                        "Explore emotion, sensation and what",
                        "comes up in the body"])
)))

# 10 — end card: type only, no logo mark -------------------------------
def art10(canv):
    orb(canv, ORB_CX, ORB_CY, 440, 0.62, 0.86)
    # no rhythm line here — the deck lands quiet
    return lambda img: rings(img, ORB_CX, ORB_CY, 220,
                             [(1.20, 0.15), (1.48, 0.09), (1.80, 0.05)])

frames.append(lambda: build(10, art10, 1000, lambda d: (
    para(d, "Over the next few weeks, I’ll show you practices from each pathway.",
         f_body(), MUTED, 52, max_w=780, gap=78) + [
    L("The Breath Reset", serif(96), OFF, 104, gap=14),
    L("Relax. Retrain. Release.", serif(46, True), SAGE_T, 64),
]), chrome=False))

if __name__ == "__main__":
    for fr in frames:
        fr()
    print(f"Done — {TOTAL} frames in", os.path.relpath(OUT, ROOT))
