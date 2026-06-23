#!/usr/bin/env python3
"""
The Breath Reset — vertical (1080x1920) text-reel decks + single posts.
Same dark warm-black + sage language as the breathing reels and the carousel.
The central orb is the thread; its STATE shifts with the nervous-system story.

Builds:
  assets/social/instagram/carousels/nervous-system/frame-01..12.png
  assets/social/instagram/reel-frames/breathwork-not-deep-breathing/frame-01..10.png
  assets/social/instagram/reel-frames/session-what-happens/frame-01..11.png
  assets/social/instagram/posts/*.png

Edit the DECKS / SINGLES data near the bottom and re-run:
  python3 tmp/make_reels.py
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920

# palette (matches the reels / carousel)
BG, BG_LIFT, BG_DEEP = (16, 13, 11), (26, 21, 18), (10, 8, 7)
SAGE      = np.array([143, 165, 138], float)
SAGE_T    = (143, 165, 138)
SAGE_DARK = (95, 116, 94)
OFF       = (239, 231, 217)
MUTED     = (172, 164, 150)
CLAY      = (209, 144, 115)
CLAY_A    = np.array([209, 144, 115], float)
COOL      = np.array([118, 140, 150], float)
WARMWHITE = np.array([232, 238, 226], float)

HERE  = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.dirname(HERE)
FONTS = os.path.join(ROOT, "breathing-reel", "fonts")
SOCIAL = os.path.join(ROOT, "assets", "social", "instagram")

def font(name, size): return ImageFont.truetype(os.path.join(FONTS, name), size)
def manrope(size, w=500):
    f = font("Manrope.ttf", size)
    try: f.set_variation_by_axes([w])
    except Exception: pass
    return f
def serif(size, it=False):
    return font("InstrumentSerif-Italic.ttf" if it else "InstrumentSerif-Regular.ttf", size)

ORB_CX, ORB_CY = W // 2, 620          # orb sits in the upper third every frame

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

# orb body diameter (r), glow/core brightness, tint, behaviour flags
STATES = {
    "neutral":   dict(r=330, glow=0.46, core=0.52, color=SAGE),
    "tense":     dict(r=300, glow=0.40, core=0.48, color=SAGE),
    "wired":     dict(r=292, glow=0.64, core=0.78, color=SAGE),               # switched on: tight + bright
    "flight":    dict(r=340, glow=0.74, core=0.85, color=SAGE, warm=True, particles="up"),
    "freeze":    dict(r=250, glow=0.22, core=0.16, color=COOL, cool=True),
    "coherent":  dict(r=372, glow=0.58, core=0.82, color=SAGE, rings=True),
    "coherent2": dict(r=404, glow=0.64, core=0.90, color=SAGE, rings=True),
    "rise":      dict(r=344, glow=0.60, core=0.80, color=SAGE, warm=True, rings=True),  # gentle energy back
    "release":   dict(r=430, glow=0.66, core=0.86, color=SAGE, rings=True, particles="flow"),
    "final":     dict(r=470, glow=0.70, core=0.92, color=SAGE, rings=True),
}

def draw_orb(canv, cx, cy, st):
    color = st["color"]
    g = radial_alpha(int(st["r"] * 3), [(0, 0.55), (0.6, 0), (1, 0)])
    add_radial(canv, cx, cy, g, color, st["glow"])
    if st.get("warm"):
        add_radial(canv, cx, cy, g, CLAY_A, 0.10)
    body = radial_alpha(st["r"], [(0, 0.85), (0.3, 0.5), (0.55, 0.2),
                                  (0.72, 0.04), (0.82, 0), (1, 0)])
    add_radial(canv, cx, cy, body, color, 0.85)
    core = radial_alpha(int(st["r"] * 0.7), [(0, 0.6), (0.3, 0.14), (0.5, 0), (1, 0)])
    add_radial(canv, cx, cy, core, WARMWHITE, st["core"])

def add_particles(canv, cx, cy, color, gain, mode, seed=5):
    rng = np.random.RandomState(seed)
    spr = radial_alpha(40, [(0, 0.9), (0.4, 0.4), (1, 0)])
    if mode == "up":                                   # fight/flight: rising streaks
        for _ in range(16):
            x = cx + (rng.random() - 0.5) * 540
            y = cy - 40 - rng.random() * 460
            s = int(14 + rng.random() * 26)
            a = np.asarray(Image.fromarray((spr * 255).astype(np.uint8), "L")
                           .resize((s, int(s * 1.7)), Image.BILINEAR), float) / 255.0
            add_radial(canv, x, y, a, color, gain * (0.4 + 0.6 * rng.random()))
    else:                                              # release: gentle flowing orbs
        for _ in range(20):
            ang = rng.random() * np.pi * 2
            dist = 150 + rng.random() * 320
            x = cx + np.cos(ang) * dist
            y = cy + np.sin(ang) * dist * 0.95
            s = int(16 + rng.random() * 30)
            a = np.asarray(Image.fromarray((spr * 255).astype(np.uint8), "L")
                           .resize((s, s), Image.BILINEAR), float) / 255.0
            add_radial(canv, x, y, a, color, gain * (0.3 + 0.5 * rng.random()))

def finish(canv):
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt((xx - W / 2) ** 2 + (yy - H / 2) ** 2) / np.hypot(W / 2, H / 2)
    vig = np.clip((r - 0.55) / 0.45, 0, 1) ** 1.5
    canv *= (1 - 0.5 * vig[..., None])
    img = Image.fromarray(np.clip(canv, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    noise = np.random.RandomState(11).randn(H, W) * 6
    arr = np.asarray(img.convert("RGB"), float) + noise[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

def draw_rings(img, cx, cy, base, specs):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for mult, op in specs:
        rr = base * mult
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                  outline=(143, 165, 138, int(op * 255)), width=2)
    img.alpha_composite(ov)

def load_logo(size):
    logo = Image.open(os.path.join(ROOT, "assets", "brand", "logo.png")).convert("RGBA")
    px = logo.load()
    for y in range(logo.height):
        for x in range(logo.width):
            r, g, b, a = px[x, y]
            wn = min(r, g, b)
            na = 0 if wn >= 250 else (255 if wn <= 232 else int(255 * (250 - wn) / 18))
            px[x, y] = (r, g, b, min(a, na))
    return logo.resize((size, size), Image.LANCZOS)

# ----------------------------- text ----------------------------------
def center_tracked(d, cy, text, fnt, fill, track):
    w = sum(d.textlength(c, font=fnt) + track for c in text) - track
    x = W / 2 - w / 2
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
        if it["kind"] == "seg":
            segs = it["segs"]
            tw = sum(d.textlength(t, font=f) for t, f, _ in segs)
            x = W / 2 - tw / 2
            for t, f, fill in segs:
                d.text((x, y), t, font=f, fill=fill); x += d.textlength(t, font=f)
        elif it["kind"] == "track":
            center_tracked(d, y, it["text"], it["font"], it["fill"], it["track"])
        else:
            d.text((W / 2, y), it["text"], font=it["font"], fill=it["fill"], anchor="ma")
        y += line_h(it)
    return y

def L(text, font, fill, lh, gap=0): return dict(kind="line", text=text, font=font, fill=fill, lh=lh, gap=gap)
def T(text, font, fill, track, lh, gap=0): return dict(kind="track", text=text, font=font, fill=fill, track=track, lh=lh, gap=gap)
def S(segs, lh, gap=0): return dict(kind="seg", segs=segs, lh=lh, gap=gap)

def para(d, text, font, fill, lh, max_w=900, gap=0):
    lines = wrap(d, text, font, max_w)
    return [L(ln, font, fill, lh, gap if i == len(lines) - 1 else 0) for i, ln in enumerate(lines)]

# fonts
def f_hook(it=False): return serif(84, it)
def f_big():          return serif(104)
def f_quote():        return serif(64, it=True)
def f_body():         return manrope(40, 400)
def f_item():         return manrope(46, 400)
def f_head():         return manrope(28, 600)
def f_path():         return serif(60)

# ----------------------------- frame builder -------------------------
def build(out_dir, fname, state, region_y, items_fn, *, idx=None, total=None, final=False):
    os.makedirs(out_dir, exist_ok=True)
    canv = base_grad()
    st = STATES[state]
    draw_orb(canv, ORB_CX, ORB_CY, st)
    if st.get("particles"):
        add_particles(canv, ORB_CX, ORB_CY, SAGE * 1.3, st["glow"] * 0.5, st["particles"])
    img = finish(canv)
    if st.get("rings"):
        draw_rings(img, ORB_CX, ORB_CY, st["r"] / 2, [(1.22, 0.16), (1.5, 0.09), (1.82, 0.05)])

    d = ImageDraw.Draw(img)
    if final:
        logo = load_logo(140)
        img.alpha_composite(logo, (W // 2 - 70, ORB_CY - 70))
        d = ImageDraw.Draw(img)
    else:
        center_tracked(d, 120, "THE BREATH RESET", manrope(24, 600), SAGE_DARK, 6)
        if idx and total:
            center_tracked(d, 1820, f"{idx:02d}  /  {total:02d}", manrope(22, 500), (110, 104, 95), 4)

    draw_block(d, items_fn(d), region_y)
    out = os.path.join(out_dir, fname)
    img.convert("RGB").save(out); print("saved", os.path.relpath(out, ROOT))

# ===================================================================
# DECK 1 — "Breathwork isn't just deep breathing" (10 frames)
# ===================================================================
def deck_breathwork():
    out = os.path.join(SOCIAL, "reel-frames", "breathwork-not-deep-breathing")
    N = 10
    F = []

    F.append(("neutral", 1300, lambda d: [
        L("Breathwork isn’t just", f_hook(), OFF, 96),
        S([("deep breathing.", f_hook(True), SAGE_T)], 96),
    ]))

    F.append(("tense", 1300, lambda d: [
        T("IT’S NOT ALWAYS", f_head(), MUTED, 4, 60, gap=64),
        L("“Take a big breath”", f_quote(), OFF, 92),
        L("or", manrope(34, 400), MUTED, 70),
        L("“Calm down.”", f_quote(), OFF, 92),
    ]))

    F.append(("neutral", 1300, lambda d: [
        L("Different nervous", f_hook(), OFF, 96),
        L("system states", f_hook(), OFF, 96, gap=30),
        S([("need ", f_hook(), OFF), ("different kinds", f_hook(True), SAGE_T)], 96),
        L("of breath.", f_hook(), OFF, 96),
    ]))

    F.append(("flight", 1250, lambda d: [
        S([("If you’re in ", f_hook(), OFF), ("fight or flight", f_hook(True), SAGE_T), ("…", f_hook(), OFF)], 100, gap=56),
        L("racing thoughts", f_item(), OFF, 78),
        L("tight chest", f_item(), OFF, 78),
        L("restlessness", f_item(), OFF, 78),
        L("always “on”", f_item(), OFF, 78, gap=54),
        L("you may need a slower rhythm.", manrope(38, 400), MUTED, 60),
    ]))

    F.append(("coherent", 1280, lambda d: [
        L("Longer exhales.", serif(72), OFF, 88),
        L("Steady breathing.", serif(72), OFF, 88),
        L("Less force.", serif(72), OFF, 88, gap=66),
        L("A way to tell the body:", manrope(38, 400), MUTED, 64),
        L("“You don’t have to run.”", f_quote(), SAGE_T, 86),
    ]))

    F.append(("freeze", 1250, lambda d: [
        S([("If you’re in ", f_hook(), OFF), ("freeze", f_hook(True), SAGE_T)], 100),
        S([("or ", f_hook(), OFF), ("shutdown", f_hook(True), SAGE_T), ("…", f_hook(), OFF)], 100, gap=56),
        L("numb", f_item(), OFF, 76),
        L("flat", f_item(), OFF, 76),
        L("dissociated", f_item(), OFF, 76),
        L("disconnected", f_item(), OFF, 76, gap=52),
        L("you may not need more calm.", manrope(38, 400), MUTED, 60),
    ]))

    F.append(("rise", 1290, lambda d: [
        L("You may need", f_hook(), OFF, 92),
        S([("gentle activation.", f_hook(True), SAGE_T)], 92, gap=66),
        L("More breath.", manrope(42, 500), OFF, 62),
        L("More rhythm.", manrope(42, 500), OFF, 62),
        L("A safe way back into the body.", manrope(38, 400), SAGE_T, 62),
    ]))

    F.append(("coherent", 1300, lambda d: (
        [L("That’s why breathwork", f_hook(), OFF, 92),
         L("is not one technique.", f_hook(), OFF, 92, gap=64)] +
        para(d, "It’s learning how to match the breath to the state you’re in.",
             f_body(), MUTED, 56, max_w=860)
    )))

    F.append(("coherent2", 1300, lambda d: [
        T("WE WORK WITH THREE PATHWAYS", f_head(), CLAY, 3, 70, gap=78),
        L("Relax", serif(78), OFF, 96),
        L("Retrain", serif(78), OFF, 96),
        L("Release", serif(78), SAGE_T, 96),
    ]))

    F.append(("final", 1290, lambda d: [
        L("Relax the body.", serif(64), OFF, 80),
        L("Retrain everyday breathing.", serif(64), OFF, 80),
        L("Release what’s been held.", serif(64), SAGE_T, 80, gap=80),
        dict(kind="line", text="The Breath Reset", font=serif(86), fill=OFF, lh=96, gap=10),
        L("Relax. Retrain. Release.", serif(44, it=True), SAGE_T, 60),
    ], dict(final=True)))

    for i, item in enumerate(F, 1):
        state, ry, fn = item[0], item[1], item[2]
        kw = item[3] if len(item) > 3 else {}
        build(out, f"frame-{i:02d}.png", state, ry, fn, idx=i, total=N, **kw)

# ===================================================================
# DECK 2 — "What happens in a Breath Reset session?" (11 frames)
# ===================================================================
def deck_session():
    out = os.path.join(SOCIAL, "reel-frames", "session-what-happens")
    N = 11
    F = []

    F.append(("neutral", 1300, lambda d: [
        L("What happens in a", f_hook(), OFF, 96),
        S([("Breath Reset", f_hook(True), SAGE_T)], 96),
        L("session?", f_hook(), OFF, 96),
    ]))

    F.append(("neutral", 1290, lambda d: [
        L("You don’t need to be", f_hook(), OFF, 88),
        L("good at breathing.", f_hook(), OFF, 88, gap=46),
        L("You don’t need to", serif(60), MUTED, 76),
        L("know what to do.", serif(60), MUTED, 76, gap=46),
        S([("Just arrive ", f_hook(), OFF), ("as you are.", f_hook(True), SAGE_T)], 88),
    ]))

    F.append(("neutral", 1300, lambda d: [
        T("FIRST, WE CHECK IN", f_head(), CLAY, 3, 64, gap=72),
        L("How are you feeling?", f_quote(), OFF, 88),
        L("What’s been showing up?", f_quote(), OFF, 88),
        L("What does your body", f_quote(), OFF, 80),
        L("need today?", f_quote(), SAGE_T, 88),
    ]))

    F.append(("neutral", 1310, lambda d: [
        L("Then we choose", f_hook(), OFF, 96),
        S([("the right kind ", f_hook(True), SAGE_T), ("of breath.", f_hook(), OFF)], 96, gap=66),
        L("Not every session is the same.", manrope(38, 400), MUTED, 60),
    ]))

    F.append(("wired", 1270, lambda d: [
        S([("If your system feels ", f_hook(), OFF)], 92),
        S([("switched on", f_hook(True), SAGE_T), ("…", f_hook(), OFF)], 92, gap=64),
        L("we may use slower breathing,", manrope(40, 400), OFF, 62),
        L("longer exhales,", manrope(40, 400), OFF, 62),
        L("and grounding practices.", manrope(40, 400), SAGE_T, 62),
    ]))

    F.append(("freeze", 1270, lambda d: [
        S([("If you feel ", f_hook(), OFF), ("numb", f_hook(True), SAGE_T)], 92),
        S([("or ", f_hook(), OFF), ("disconnected", f_hook(True), SAGE_T), ("…", f_hook(), OFF)], 92, gap=64),
        L("we may use gentle activation,", manrope(40, 400), OFF, 62),
        L("rhythm,", manrope(40, 400), OFF, 62),
        L("and body connection.", manrope(40, 400), SAGE_T, 62),
    ]))

    F.append(("release", 1290, lambda d: (
        [S([("If there’s ", f_hook(), OFF), ("emotion", f_hook(True), SAGE_T)], 90),
         S([("or tension being held…", f_hook(), OFF)], 90, gap=60)] +
        para(d, "we may use a deeper release-based breath, but only at a pace that feels safe.",
             f_body(), MUTED, 56, max_w=860)
    )))

    F.append(("coherent", 1280, lambda d: [
        L("The session is guided", f_hook(), OFF, 88),
        L("the whole way.", f_hook(), OFF, 88, gap=64),
        L("Voice.", manrope(42, 500), OFF, 60),
        L("Music.", manrope(42, 500), OFF, 60),
        L("Breathing rhythm.", manrope(42, 500), OFF, 60),
        L("Space to feel.", manrope(42, 500), OFF, 60),
        L("Space to pause.", manrope(42, 500), SAGE_T, 60),
    ]))

    F.append(("coherent", 1300, lambda d: [
        T("AFTER THE BREATHING, WE INTEGRATE", f_head(), CLAY, 2, 64, gap=72),
        L("What did you notice?", f_quote(), OFF, 88),
        L("What shifted?", f_quote(), OFF, 88),
        L("What does your system", f_quote(), OFF, 80),
        L("need next?", f_quote(), SAGE_T, 88),
    ]))

    F.append(("coherent", 1300, lambda d: (
        [L("Then you leave with", f_hook(), OFF, 88),
         S([("a simple practice.", f_hook(True), SAGE_T)], 88, gap=62)] +
        para(d, "Something you can use during the week when your body feels anxious, "
                "tense, or switched on.", f_body(), MUTED, 56, max_w=860)
    )))

    F.append(("final", 1280, lambda d: (
        [T("THE BREATH RESET IS BUILT AROUND", f_head(), MUTED, 2, 58, gap=42),
         L("Relax · Retrain · Release", serif(60), SAGE_T, 78, gap=66)] +
        para(d, "A grounded way to use your breath to come back to yourself.",
             f_body(), MUTED, 56, max_w=820, gap=70) +
        [dict(kind="line", text="The Breath Reset", font=serif(80), fill=OFF, lh=92, gap=8),
         L("Relax. Retrain. Release.", serif(44, it=True), SAGE_T, 60)]
    ), dict(final=True)))

    for i, item in enumerate(F, 1):
        state, ry, fn = item[0], item[1], item[2]
        kw = item[3] if len(item) > 3 else {}
        build(out, f"frame-{i:02d}.png", state, ry, fn, idx=i, total=N, **kw)

# ===================================================================
# SINGLE POSTS (one frame each, lockup at the bottom)
# ===================================================================
def single(fname, state, hook_items, lock_lines):
    out = os.path.join(SOCIAL, "posts")
    os.makedirs(out, exist_ok=True)
    canv = base_grad()
    st = STATES[state]
    draw_orb(canv, ORB_CX, ORB_CY, st)
    if st.get("particles"):
        add_particles(canv, ORB_CX, ORB_CY, SAGE * 1.3, st["glow"] * 0.5, st["particles"])
    img = finish(canv)
    if st.get("rings"):
        draw_rings(img, ORB_CX, ORB_CY, st["r"] / 2, [(1.22, 0.16), (1.5, 0.09), (1.82, 0.05)])
    d = ImageDraw.Draw(img)
    center_tracked(d, 120, "THE BREATH RESET", manrope(24, 600), SAGE_DARK, 6)
    draw_block(d, hook_items(d), 1180)
    # bottom lockup
    d.line([(W / 2 - 70, 1560), (W / 2 + 70, 1560)], fill=SAGE_DARK, width=2)
    y = 1610
    for text, fnt, fill in lock_lines:
        d.text((W / 2, y), text, font=fnt, fill=fill, anchor="ma"); y += fnt.size + 22
    p = os.path.join(out, fname)
    img.convert("RGB").save(p); print("saved", os.path.relpath(p, ROOT))

def singles():
    single("anxiety-and-body.png", "tense", lambda d: [
        L("You can understand", f_hook(), OFF, 100),
        L("your anxiety", f_hook(), OFF, 100, gap=30),
        S([("and still feel it", f_hook(True), SAGE_T)], 100),
        L("in your body.", f_hook(), OFF, 100),
    ], [
        ("The Breath Reset", serif(64), OFF),
        ("Relax. Retrain. Release.", serif(40, it=True), SAGE_T),
    ])

    single("high-functioning.png", "wired", lambda d: [
        S([("High-functioning", f_hook(True), SAGE_T)], 104, gap=24),
        L("doesn’t always", f_hook(), OFF, 100),
        L("mean regulated.", f_hook(), OFF, 100),
    ], [
        ("The Breath Reset", serif(58), OFF),
        ("For people who look like they’re coping,", manrope(28, 400), MUTED),
        ("but don’t always feel it inside.", manrope(28, 400), MUTED),
    ])

    single("forcing-calm.png", "coherent", lambda d: [
        L("Breathwork isn’t about", f_hook(), OFF, 96),
        S([("forcing calm.", f_hook(True), SAGE_T)], 96, gap=54),
        L("It’s about meeting", f_hook(), OFF, 96),
        L("your body where it is.", serif(70), OFF, 90),
    ], [
        ("The Breath Reset", serif(64), OFF),
        ("Relax. Retrain. Release.", serif(40, it=True), SAGE_T),
    ])

if __name__ == "__main__":
    deck_breathwork()
    deck_session()
    singles()
    print("Done.")
