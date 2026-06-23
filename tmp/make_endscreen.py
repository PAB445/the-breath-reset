#!/usr/bin/env python3
import os
from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

S = 2  # supersample
W, H = 1280 * S, 720 * S
CX = W // 2

# ---- palette (from styles.css) ----
CREAM       = (248, 241, 232)
WARM_WHITE  = (255, 250, 243)
CREAM_DEEP  = (241, 231, 217)
CHARCOAL    = (32, 39, 33)
INK         = (21, 25, 22)
SAGE        = (143, 165, 138)
SAGE_DARK   = (95, 116, 94)
CLAY        = (209, 144, 115)
OLIVE       = (105, 120, 97)

def font(path, size):
    return ImageFont.truetype(os.path.join(ROOT, "breathing-reel", "fonts", path), int(size))

def manrope(size, weight=700):
    f = font("Manrope.ttf", size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f

def serif(size, italic=False):
    return font("InstrumentSerif-Italic.ttf" if italic else "InstrumentSerif-Regular.ttf", size)

# ---------------- background gradient ----------------
def gradient_bg():
    small = Image.new("RGB", (64, 36))
    px = small.load()
    for y in range(36):
        for x in range(64):
            t = (x / 63 * 0.5 + y / 35 * 0.5)
            if t < 0.5:
                u = t / 0.5
                c = tuple(int(WARM_WHITE[i] + (CREAM[i] - WARM_WHITE[i]) * u) for i in range(3))
            else:
                u = (t - 0.5) / 0.5
                c = tuple(int(CREAM[i] + (CREAM_DEEP[i] - CREAM[i]) * u) for i in range(3))
            px[x, y] = c
    return small.resize((W, H), Image.BILINEAR)

img = gradient_bg().convert("RGBA")

# ---------------- faint breathing rings ----------------
overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
od = ImageDraw.Draw(overlay)
def ring(cx, cy, r, color, alpha, width):
    od.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color + (alpha,), width=width)
# concentric rings centred on the page = a quiet breathing motif
ring(CX, int(360 * S), int(470 * S), SAGE_DARK, 30, 2 * S)
ring(CX, int(360 * S), int(360 * S), SAGE_DARK, 22, 2 * S)
ring(int(-60 * S), int(720 * S), int(300 * S), SAGE_DARK, 26, 2 * S)
ring(int(1320 * S), int(0 * S), int(260 * S), SAGE, 24, 2 * S)
img = Image.alpha_composite(img, overlay)

draw = ImageDraw.Draw(img)

# ---------------- helpers ----------------
def tracked_width(text, fnt, tracking):
    w = 0
    for ch in text:
        w += draw.textlength(ch, font=fnt) + tracking
    return w - tracking if text else 0

def draw_tracked_center(cx, y, text, fnt, fill, tracking):
    w = tracked_width(text, fnt, tracking)
    x = cx - w / 2
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking

# ---------------- text block (centred) ----------------
# eyebrow
eb_font = manrope(15 * S, 700)
eb_y = int(150 * S)
# small decorative lines either side of eyebrow
eb_text = "THE BREATH RESET"
ebw = tracked_width(eb_text, eb_font, int(4 * S))
line_len = int(46 * S)
gap = int(20 * S)
ly = eb_y + int(10 * S)
draw.line([(CX - ebw / 2 - gap - line_len, ly), (CX - ebw / 2 - gap, ly)], fill=CLAY, width=int(2 * S))
draw.line([(CX + ebw / 2 + gap, ly), (CX + ebw / 2 + gap + line_len, ly)], fill=CLAY, width=int(2 * S))
draw_tracked_center(CX, eb_y, eb_text, eb_font, CLAY, int(4 * S))

# title
title_font = serif(96 * S)
draw.text((CX, int(232 * S)), "The Breath Reset", font=title_font, fill=INK, anchor="mm")

# tagline (italic serif, sage)
tag_font = serif(46 * S, italic=True)
draw.text((CX, int(322 * S)), "Relax. Retrain. Release.", font=tag_font, fill=SAGE_DARK, anchor="mm")

# subtitle / CTA
sub_font = manrope(24 * S, 600)
draw.text((CX, int(388 * S)), "Follow for practical breathwork tools", font=sub_font, fill=OLIVE, anchor="mm")

# ---------------- logo (larger, under the text) ----------------
logo = Image.open(os.path.join(ROOT, "assets", "brand", "logo.png")).convert("RGBA")
lpx = logo.load()
for y in range(logo.height):
    for x in range(logo.width):
        r, g, b, a = lpx[x, y]
        whiteness = min(r, g, b)
        if whiteness >= 250:
            na = 0
        elif whiteness <= 232:
            na = 255
        else:
            na = int(255 * (250 - whiteness) / 18)
        lpx[x, y] = (r, g, b, min(a, na))

LOGO_SZ = int(210 * S)
logo = logo.resize((LOGO_SZ, LOGO_SZ), Image.LANCZOS)
logo_y = int(440 * S)
img.alpha_composite(logo, (CX - LOGO_SZ // 2, logo_y))

# ---------------- finish ----------------
out = img.convert("RGB").resize((1280, 720), Image.LANCZOS)
out_path = os.path.join(ROOT, "assets", "social", "youtube", "founder-video", "end-screen.png")
out.save(out_path, "PNG")
print("saved", out_path)
