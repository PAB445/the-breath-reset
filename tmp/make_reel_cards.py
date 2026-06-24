#!/usr/bin/env python3
"""
COVER + END cards for every Breath Reset flow (vertical 1080x1920).
Dark warm-black + sage scheme to match the breathing visualisation, in the
same design language as the earlier YouTube cover/end screen.

Copy comes from tmp/flows.py (single source of truth). Re-run after edits:
  python3 tmp/make_reel_cards.py

Outputs -> assets/social/instagram/practices/<slug>/cover.png and end.png
"""
import os, sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flows import FLOWS

W, H = 1080, 1920

# palette (matches the reel)
BG        = (16, 13, 11)
BG_LIFT   = (26, 21, 18)
BG_DEEP   = (10, 8, 7)
SAGE      = np.array([143, 165, 138], float)
SAGE_T    = (143, 165, 138)
SAGE_DARK = (95, 116, 94)
OFF       = (239, 231, 217)
MUTED     = (172, 164, 150)
CLAY      = (209, 144, 115)

HERE  = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.dirname(HERE)
FONTS = os.path.join(ROOT, "breathing-reel", "fonts")
PRACTICES = os.path.join(ROOT, "assets", "social", "instagram", "practices")

def font(name, size): return ImageFont.truetype(os.path.join(FONTS, name), size)
def manrope(size, w=600):
    f = font("Manrope.ttf", size)
    try: f.set_variation_by_axes([w])
    except Exception: pass
    return f
def serif(size, it=False):
    return font("InstrumentSerif-Italic.ttf" if it else "InstrumentSerif-Regular.ttf", size)

# ----------------------------- shared bg -----------------------------
def radial_alpha(size, stops):
    c = (size - 1) / 2
    yy, xx = np.mgrid[0:size, 0:size]
    r = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / (size / 2)
    xs = [s[0] for s in stops]; ys = [s[1] for s in stops]
    return np.clip(np.interp(r.ravel(), xs, ys).reshape(size, size), 0, 1)

def add_radial(canvas, cx, cy, alpha2d, color, gain):
    ah, aw = alpha2d.shape
    x0, y0 = int(round(cx - aw / 2)), int(round(cy - ah / 2))
    cx0, cy0 = max(x0, 0), max(y0, 0)
    cx1, cy1 = min(x0 + aw, W), min(y0 + ah, H)
    if cx1 <= cx0 or cy1 <= cy0: return
    sub = alpha2d[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
    canvas[cy0:cy1, cx0:cx1, :] += (sub[..., None] * gain) * color

def base_canvas(glow_cy):
    """Warm-black gradient + a soft sage halo (the breathing motif) at glow_cy."""
    c = np.array([(W - 1) / 2, H * 0.42])
    yy, xx = np.mgrid[0:H, 0:W]
    maxd = math.hypot(max(c[0], W - c[0]), max(c[1], H - c[1]))
    r = np.sqrt((xx - c[0]) ** 2 + (yy - c[1]) ** 2) / maxd
    canv = np.zeros((H, W, 3), float)
    for i in range(3):
        canv[..., i] = np.interp(r.ravel(), [0, 0.46, 1],
                                 [BG_LIFT[i], BG[i], BG_DEEP[i]]).reshape(H, W)
    # central sage glow halo
    glow = radial_alpha(900, [(0, 0.55), (0.62, 0), (1, 0)])
    add_radial(canv, W // 2, glow_cy, glow, SAGE, 0.42)
    return canv, r

def finish(canv, r):
    vig = np.clip((r - 0.5) / 0.5, 0, 1) ** 1.4
    canv *= (1 - 0.5 * vig[..., None])
    img = Image.fromarray(np.clip(canv, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    return img

def add_grain(img):
    noise = (np.random.RandomState(11).randn(H, W) * 7)
    arr = np.asarray(img.convert("RGB"), float) + noise[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

def draw_rings(img, cy, radii_op):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for rr, op in radii_op:
        d.ellipse([W // 2 - rr, cy - rr, W // 2 + rr, cy + rr],
                  outline=(143, 165, 138, int(op * 255)), width=2)
    img.alpha_composite(layer)

# ----------------------------- logo ----------------------------------
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

# --------------------------- text helpers ----------------------------
def tracked_w(d, text, fnt, track):
    return sum(d.textlength(c, font=fnt) + track for c in text) - track if text else 0

def center_tracked(d, cy, text, fnt, fill, track):
    w = tracked_w(d, text, fnt, track)
    x = W / 2 - w / 2
    for c in text:
        d.text((x, cy), c, font=fnt, fill=fill); x += d.textlength(c, font=fnt) + track

def divider(d, cy, half=70, color=SAGE_DARK):
    d.line([(W / 2 - half, cy), (W / 2 + half, cy)], fill=color, width=2)

# which brand pillar a video belongs to -> highlighted on the cover
PILLARS = ["RELAX", "RETRAIN", "RELEASE"]
CATEGORY_INDEX = {"relax": 0, "retrain": 1, "release": 2}
PILLAR_DIM = (96, 90, 82)        # the two inactive pillars (faint warm grey)

def tracked_segments(d, cy, segments, track):
    """Render coloured segments [(text, font, fill), ...] as one centered, tracked line."""
    total = -track
    for text, fnt, _ in segments:
        total += sum(d.textlength(c, font=fnt) + track for c in text)
    x = W / 2 - total / 2
    for text, fnt, fill in segments:
        for c in text:
            d.text((x, cy), c, font=fnt, fill=fill); x += d.textlength(c, font=fnt) + track

def category_pillars(d, cy, category, size=21, track=5):
    """RELAX · RETRAIN · RELEASE with this video's pillar lit (clay) and the rest dimmed."""
    active = CATEGORY_INDEX.get(category, 0)
    on, off = manrope(size, 800), manrope(size, 600)
    segs = []
    for i, word in enumerate(PILLARS):
        if i:
            segs.append((" · ", off, PILLAR_DIM))
        segs.append((word, on, CLAY) if i == active else (word, off, PILLAR_DIM))
    tracked_segments(d, cy, segs, track)

def eyebrow_with_lines(d, cy, text, fnt, fill, track, line=46, gap=22):
    w = tracked_w(d, text, fnt, track)
    ly = cy + fnt.size * 0.42
    d.line([(W/2 - w/2 - gap - line, ly), (W/2 - w/2 - gap, ly)], fill=fill, width=2)
    d.line([(W/2 + w/2 + gap, ly), (W/2 + w/2 + gap + line, ly)], fill=fill, width=2)
    center_tracked(d, cy, text, fnt, fill, track)

def wrap_mixed_title(d, cy, raw, size, max_w, line_h):
    """Centered serif title; |...| spans (one or more words) are italic + sage."""
    reg, ital = serif(size), serif(size, it=True)
    toks = []
    italic = False
    for w in raw.split(" "):
        starts, ends = w.startswith("|"), w.endswith("|")
        clean = w.strip("|")
        cur = italic or starts
        toks.append((clean, ital if cur else reg, SAGE_T if cur else OFF))
        if starts and not ends:
            italic = True
        if ends:
            italic = False
    space = d.textlength(" ", font=reg)
    lines, cur, cw = [], [], 0
    for tk in toks:
        tw = d.textlength(tk[0], font=tk[1])
        add = tw if not cur else space + tw
        if cur and cw + add > max_w:
            lines.append(cur); cur = [tk]; cw = tw
        else:
            cur.append(tk); cw += add
    if cur: lines.append(cur)
    y = cy
    for line in lines:
        tw = sum(d.textlength(t[0], font=t[1]) for t in line) + space * (len(line) - 1)
        x = W / 2 - tw / 2
        for i, (txt, fnt, fill) in enumerate(line):
            if i: x += space
            d.text((x, y), txt, font=fnt, fill=fill); x += d.textlength(txt, font=fnt)
        y += line_h
    return y

def wrap_plain(d, cy, text, fnt, fill, max_w, line_h):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=fnt) > max_w and cur:
            lines.append(cur); cur = w
        else: cur = t
    lines.append(cur)
    y = cy
    for ln in lines:
        d.text((W / 2, y), ln, font=fnt, fill=fill, anchor="ma"); y += line_h
    return y

# ============================== COVER ================================
# Instagram cover = the scroll-stopper. The emotional hook leads; the
# practice promise and the simple "how" sit underneath; brand grounds it.
def render_cover(flow):
    cov = flow["cover"]
    canv, r = base_canvas(glow_cy=360)
    img = finish(canv, r)
    draw_rings(img, 360, [(250, 0.14), (320, 0.07)])

    logo = load_logo(132)
    img.alpha_composite(logo, (W // 2 - 66, 360 - 66))
    img = add_grain(img)
    d = ImageDraw.Draw(img)

    # brand lockup (top)
    d.text((W // 2, 470), "The Breath Reset", font=serif(46), fill=OFF, anchor="ma")
    center_tracked(d, 540, "BREATHE · RESET · RESTORE", manrope(20, 600), SAGE_DARK, 6)

    # eyebrow + emotional hook (hero)
    eyebrow_with_lines(d, 812, cov["eyebrow"], manrope(25, 700), CLAY, 5)
    y = wrap_mixed_title(d, 892, cov["hook"], size=98, max_w=900, line_h=104)

    # the gentle "how" — short, reassuring, nervous-system language
    divider(d, y + 54)
    sy = y + 110
    n = len(cov["steps"])
    for i, step in enumerate(cov["steps"]):
        fill = OFF if i < n - 1 else MUTED
        d.text((W // 2, sy), step, font=manrope(34, 500 if i < n - 1 else 400),
               fill=fill, anchor="ma")
        sy += 60

    category_pillars(d, 1822, flow.get("category", "relax"))

    out_dir = os.path.join(PRACTICES, flow["slug"])
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "cover.png")
    img.convert("RGB").save(out); print("saved", os.path.relpath(out, ROOT))

# =============================== END =================================
# Soft landing: a felt-sense close, the brand promise, then the save cue.
def render_end(flow):
    end = flow["end"]
    canv, r = base_canvas(glow_cy=1410)
    img = finish(canv, r)
    draw_rings(img, 1410, [(270, 0.14), (350, 0.07)])
    img = add_grain(img)
    d = ImageDraw.Draw(img)

    # gentle close (Instrument Serif for soft emotional emphasis)
    yy = 470
    for line in end["lines"]:
        d.text((W // 2, yy), line, font=serif(66), fill=OFF, anchor="ma"); yy += 92

    divider(d, yy + 36)

    d.text((W // 2, yy + 86), "The Breath Reset", font=serif(104), fill=OFF, anchor="ma")
    d.text((W // 2, yy + 232), end["tagline"], font=serif(48, it=True),
           fill=SAGE_T, anchor="ma")
    wrap_plain(d, yy + 326, end["cta"], manrope(30, 400), MUTED, 740, 46)

    # logo larger, under the text (sits inside the lower glow halo)
    logo = load_logo(220)
    img.alpha_composite(logo, (W // 2 - 110, 1410 - 110))

    out_dir = os.path.join(PRACTICES, flow["slug"])
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "end.png")
    img.convert("RGB").save(out); print("saved", os.path.relpath(out, ROOT))

if __name__ == "__main__":
    for fid, flow in FLOWS.items():
        print(f"Flow {fid}:")
        render_cover(flow)
        render_end(flow)
