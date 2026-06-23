#!/usr/bin/env python3
"""
The Breath Reset — Instagram carousel (static, 12 frames, 1080x1350 / 4:5).
"Your mind knows you're safe. Your body hasn't got the memo."

Same dark warm-black + sage language as the breathing reels. The central orb is
the visual thread: it stays put but its STATE changes with the nervous-system
story — tense, fight/flight (brighter, rising particles), freeze (dim, cool,
still), coherent breathwork (soft, expanded, rings), then a calm end card.

Edit FRAMES / STATES below and re-run:  python3 tmp/make_post.py
Outputs -> assets/social/instagram/carousels/nervous-system/frame-01.png … frame-12.png
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350

# palette (matches the reels)
BG, BG_LIFT, BG_DEEP = (16, 13, 11), (26, 21, 18), (10, 8, 7)
SAGE      = np.array([143, 165, 138], float)
SAGE_T    = (143, 165, 138)
SAGE_DARK = (95, 116, 94)
OFF       = (239, 231, 217)
MUTED     = (172, 164, 150)
CLAY      = (209, 144, 115)
CLAY_A    = np.array([209, 144, 115], float)
COOL      = np.array([118, 140, 150], float)     # freeze: desaturated blue-grey
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

ORB_CX, ORB_CY = W // 2, 430          # orb sits in the same place every frame

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
    c = np.array([W / 2, H * 0.32])
    yy, xx = np.mgrid[0:H, 0:W]
    maxd = np.hypot(max(c[0], W - c[0]), max(c[1], H - c[1]))
    r = np.sqrt((xx - c[0]) ** 2 + (yy - c[1]) ** 2) / maxd
    canv = np.zeros((H, W, 3), float)
    for i in range(3):
        canv[..., i] = np.interp(r.ravel(), [0, 0.46, 1],
                                 [BG_LIFT[i], BG[i], BG_DEEP[i]]).reshape(H, W)
    return canv, r

# STATE PRESETS — r is the orb body diameter (px); glow/core are brightness.
STATES = {
    "tense":     dict(r=300, glow=0.42, core=0.50, color=SAGE),
    "tense2":    dict(r=276, glow=0.36, core=0.42, color=SAGE),
    "neutral":   dict(r=322, glow=0.46, core=0.52, color=SAGE),
    "flight":    dict(r=336, glow=0.74, core=0.85, color=SAGE, warm=True, particles=True),
    "freeze":    dict(r=246, glow=0.22, core=0.16, color=COOL,  cool=True),
    "brace":     dict(r=270, glow=0.30, core=0.30, color=COOL),
    "coherent":  dict(r=372, glow=0.58, core=0.82, color=SAGE, rings=True),
    "coherent2": dict(r=404, glow=0.64, core=0.90, color=SAGE, rings=True),
    "rise":      dict(r=344, glow=0.60, core=0.80, color=SAGE, warm=True, rings=True),  # gentle energy back
    "final":     dict(r=470, glow=0.70, core=0.92, color=SAGE, rings=True),
}

def draw_orb(canv, cx, cy, st):
    color = st["color"]
    g = radial_alpha(int(st["r"] * 3), [(0, 0.55), (0.6, 0), (1, 0)])
    add_radial(canv, cx, cy, g, color, st["glow"])
    if st.get("warm"):                              # flight: faint clay heat
        add_radial(canv, cx, cy, g, CLAY_A, 0.10)
    body = radial_alpha(st["r"], [(0, 0.85), (0.3, 0.5), (0.55, 0.2),
                                  (0.72, 0.04), (0.82, 0), (1, 0)])
    add_radial(canv, cx, cy, body, color, 0.85)
    core = radial_alpha(int(st["r"] * 0.7), [(0, 0.6), (0.3, 0.14), (0.5, 0), (1, 0)])
    add_radial(canv, cx, cy, core, WARMWHITE, st["core"])

def add_particles_up(canv, cx, cy, color, gain, n=16, seed=5):
    """Faint particles drifting upward — the felt 'lift' of fight/flight."""
    rng = np.random.RandomState(seed)
    spr = radial_alpha(40, [(0, 0.9), (0.4, 0.4), (1, 0)])
    for _ in range(n):
        x = cx + (rng.random() - 0.5) * 520
        y = cy - 40 - rng.random() * 430
        s = int(14 + rng.random() * 26)
        a = np.asarray(Image.fromarray((spr * 255).astype(np.uint8), "L")
                       .resize((s, int(s * 1.7)), Image.BILINEAR), float) / 255.0   # streaked
        add_radial(canv, x, y, a, color, gain * (0.4 + 0.6 * rng.random()))

def finish(canv):
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt((xx - W / 2) ** 2 + (yy - H / 2) ** 2) / np.hypot(W / 2, H / 2)
    vig = np.clip((r - 0.52) / 0.48, 0, 1) ** 1.5
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

# A "block" is a list of line-items stacked and vertically centred on cy.
#   line item: dict(kind, ...) — see draw below.
def line_h(it):
    return it["lh"] + it.get("gap", 0)

def draw_block(d, items, center_y):
    total = sum(line_h(it) for it in items)
    y = center_y - total / 2
    for it in items:
        if it["kind"] == "seg":                      # mixed inline segments
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

# item builders -------------------------------------------------------
def L(text, font, fill, lh, gap=0):   return dict(kind="line", text=text, font=font, fill=fill, lh=lh, gap=gap)
def T(text, font, fill, track, lh, gap=0): return dict(kind="track", text=text, font=font, fill=fill, track=track, lh=lh, gap=gap)
def S(segs, lh, gap=0):               return dict(kind="seg", segs=segs, lh=lh, gap=gap)

def para(d, text, font, fill, lh, max_w=900, gap=0):
    lines = wrap(d, text, font, max_w)
    return [L(ln, font, fill, lh, gap if i == len(lines) - 1 else 0) for i, ln in enumerate(lines)]

# ----------------------------- frames --------------------------------
def build(idx, state, region_y, items_fn, *, final=False):
    canv, _ = base_grad()
    st = STATES[state]
    draw_orb(canv, ORB_CX, ORB_CY, st)
    if st.get("particles"):
        add_particles_up(canv, ORB_CX, ORB_CY, SAGE * 1.3, st["glow"] * 0.5)
    img = finish(canv)
    if st.get("rings"):
        draw_rings(img, ORB_CX, ORB_CY, st["r"] / 2, [(1.22, 0.16), (1.5, 0.09), (1.82, 0.05)])

    d = ImageDraw.Draw(img)
    if final:
        logo = load_logo(132)
        img.alpha_composite(logo, (W // 2 - 66, ORB_CY - 66))
        d = ImageDraw.Draw(img)
    else:
        center_tracked(d, 74, "THE BREATH RESET", manrope(22, 600), SAGE_DARK, 6)
        center_tracked(d, 1258, f"{idx:02d}  /  12", manrope(20, 500), (110, 104, 95), 4)

    draw_block(d, items_fn(d), region_y)
    out = os.path.join(OUT, f"frame-{idx:02d}.png")
    img.convert("RGB").save(out); print("saved", os.path.relpath(out, ROOT))

# fonts used a lot
def f_hook(it=False): return serif(78, it)
def f_big():          return serif(94)
def f_quote():        return serif(60, it=True)
def f_body():         return manrope(38, 400)
def f_item():         return manrope(44, 400)
def f_head():         return manrope(28, 600)

def f_path():  return serif(56)   # pathway lines on frame 11

frames = []

# 1 — tense baseline ---------------------------------------------------
frames.append(lambda: build(1, "tense", 980, lambda d: [
    L("Your mind knows", f_hook(), OFF, 88),
    L("you’re safe.", f_hook(), OFF, 88, gap=34),
    S([("Your body hasn’t got ", f_hook(), OFF)], 88),
    S([("the ", f_hook(), OFF), ("memo.", f_hook(True), SAGE_T)], 88),
]))

# 2 — the felt question ------------------------------------------------
frames.append(lambda: build(2, "tense2", 980, lambda d: [
    S([("Ever felt ", f_hook(), OFF), ("anxious,", f_hook(True), SAGE_T)], 90),
    S([("numb,", f_hook(True), SAGE_T), (" or ", f_hook(), OFF), ("disconnected", f_hook(True), SAGE_T), ("…", f_hook(), OFF)], 90, gap=34),
    L("even when nothing", f_hook(), OFF, 86),
    L("is actually wrong?", f_hook(), OFF, 86),
]))

# 3 — reframe: not a thinking problem ----------------------------------
frames.append(lambda: build(3, "neutral", 980, lambda d: [
    L("That’s because anxiety isn’t", f_hook(), OFF, 84),
    L("always a thinking problem.", f_hook(), OFF, 84, gap=54),
    S([("Sometimes it’s a", f_hook(), OFF)], 86),
    S([("nervous system state.", f_hook(True), SAGE_T)], 86),
]))

# 4 — fight / flight / freeze (activation) -----------------------------
frames.append(lambda: build(4, "flight", 940, lambda d: (
    para(d, "When your system senses threat, it can move into protection.",
         f_body(), MUTED, 54, max_w=820, gap=56) + [
    L("Fight.", f_big(), OFF, 96),
    L("Flight.", f_big(), OFF, 96),
    L("Freeze.", f_big(), SAGE_T, 96),
])))

# 5 — fight/flight symptoms --------------------------------------------
frames.append(lambda: build(5, "flight", 930, lambda d: [
    T("FIGHT OR FLIGHT CAN FEEL LIKE", f_head(), CLAY, 3, 60, gap=58),
    L("racing thoughts", f_item(), OFF, 78),
    L("tight chest", f_item(), OFF, 78),
    L("restlessness", f_item(), OFF, 78),
    L("urgency", f_item(), OFF, 78),
    L("always being “on”", manrope(38, 400), MUTED, 72),
]))

# 6 — freeze / shutdown symptoms ---------------------------------------
frames.append(lambda: build(6, "freeze", 930, lambda d: [
    T("FREEZE OR SHUTDOWN CAN FEEL LIKE", f_head(), MUTED, 3, 60, gap=58),
    L("numbness", f_item(), OFF, 78),
    L("dissociation", f_item(), OFF, 78),
    L("flatness", f_item(), OFF, 78),
    L("brain fog", f_item(), OFF, 78),
    L("feeling far away from yourself", manrope(38, 400), MUTED, 72),
]))

# 7 — the pivot --------------------------------------------------------
frames.append(lambda: build(7, "neutral", 970, lambda d: [
    L("And these states often need", f_hook(), OFF, 88),
    S([("different types ", f_hook(True), SAGE_T)], 88),
    S([("of ", f_hook(), OFF), ("breath", f_hook(True), SAGE_T), (".", f_hook(), OFF)], 88),
]))

# 8 — too activated -> calm down ---------------------------------------
frames.append(lambda: build(8, "coherent", 945, lambda d: [
    L("If your system is too activated,", serif(58), OFF, 74),
    L("slow breathing can help", serif(58), OFF, 74),
    L("you come down.", serif(58), OFF, 74, gap=56),
    L("Longer exhales.", manrope(40, 500), OFF, 58),
    L("Steady rhythm.", manrope(40, 500), OFF, 58),
    L("Less force.", manrope(40, 500), SAGE_T, 58),
]))

# 9 — shut down -> gentle energy (warm "rise" orb) ---------------------
frames.append(lambda: build(9, "rise", 950, lambda d: [
    L("If your system is shut down,", serif(58), OFF, 74),
    L("you may not need more calm.", serif(58), OFF, 74, gap=52),
    L("You may need gentle energy.", manrope(40, 500), OFF, 58),
    L("More breath.", manrope(40, 500), OFF, 58),
    L("More rhythm.", manrope(40, 500), OFF, 58),
    L("A safe way back into the body.", manrope(38, 400), SAGE_T, 58),
]))

# 10 — what breathwork really is ---------------------------------------
frames.append(lambda: build(10, "coherent", 955, lambda d: (
    [L("That’s why breathwork isn’t just", serif(60), OFF, 78),
     S([("“take a deep breath.”", serif(60, it=True), SAGE_T)], 78, gap=58)] +
    para(d, "It’s learning how to use the breath to meet your state.",
         f_body(), MUTED, 54, max_w=820)
)))

# 11 — the three pathways ----------------------------------------------
frames.append(lambda: build(11, "coherent2", 940, lambda d: (
    para(d, "At The Breath Reset, we work with three pathways:",
         manrope(34, 500), MUTED, 50, max_w=820, gap=60) + [
    S([("Relax", f_path(), SAGE_T), (" — calm the body", f_path(), OFF)], 84),
    S([("Retrain", f_path(), SAGE_T), (" — improve everyday breathing", f_path(), OFF)], 84),
    S([("Release", f_path(), SAGE_T), (" — move what’s been held", f_path(), OFF)], 84),
])))

# 12 — end card --------------------------------------------------------
frames.append(lambda: build(12, "final", 945, lambda d: (
    para(d, "For people who look like they’re coping, but inside feel anxious, "
            "numb, overwhelmed, or switched on.", f_body(), MUTED, 54, max_w=820, gap=70) + [
    dict(kind="line", text="The Breath Reset", font=serif(96), fill=OFF, lh=104, gap=12),
    L("Relax. Retrain. Release.", serif(46, it=True), SAGE_T, 64),
]), final=True))

if __name__ == "__main__":
    for fr in frames:
        fr()
    print("Done — 12 frames in", os.path.relpath(OUT, ROOT))
