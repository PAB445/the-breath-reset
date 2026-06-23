#!/usr/bin/env python3
import os
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

S = 2  # supersample
W, H = 1280 * S, 720 * S

# ---- palette ----
CREAM       = (248, 241, 232)
WARM_WHITE  = (255, 250, 243)
CREAM_DEEP  = (241, 231, 217)
CHARCOAL    = (32, 39, 33)
INK         = (21, 25, 22)
SAGE        = (143, 165, 138)
SAGE_DARK   = (95, 116, 94)
CLAY        = (209, 144, 115)
OLIVE       = (105, 120, 97)

FONTS = os.path.join(ROOT, "breathing-reel", "fonts")
def font(path, size):
    return ImageFont.truetype(os.path.join(FONTS, path), int(size))

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
            # diagonal blend warm-white (top-left) -> cream -> deeper cream (bottom-right)
            t = (x / 63 * 0.55 + y / 35 * 0.45)
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
ring(int(-120 * S), int(720 * S), int(380 * S), SAGE_DARK, 42, 2 * S)
ring(int(-40 * S),  int(700 * S), int(260 * S), SAGE_DARK, 28, 2 * S)
ring(int(560 * S),  int(-120 * S), int(240 * S), SAGE, 26, 2 * S)
img = Image.alpha_composite(img, overlay)

# ---------------- photo (duotone) on the right ----------------
PANEL_W = int(540 * S)
photo = Image.open(os.path.join(ROOT, "assets", "photos", "suraj.jpg")).convert("RGB")
# cover-fit the panel
target_ratio = PANEL_W / H
pr = photo.width / photo.height
if pr > target_ratio:
    new_h = H
    new_w = int(H * pr)
else:
    new_w = PANEL_W
    new_h = int(PANEL_W / pr)
photo = photo.resize((new_w, new_h), Image.LANCZOS)
# crop: horizontal 52%, vertical 18% (top-weighted)
left = int((new_w - PANEL_W) * 0.52)
top = int((new_h - H) * 0.18)
photo = photo.crop((left, top, left + PANEL_W, top + H))

# duotone: near-neutral warm grey
gray = ImageOps.autocontrast(ImageOps.grayscale(photo), cutoff=1)
duo = ImageOps.colorize(gray, black=(26, 30, 26), white=(238, 232, 222),
                        mid=(120, 130, 116)).convert("RGBA")

# left-edge fade mask so the photo melts into the cream
mask = Image.new("L", (PANEL_W, H), 255)
mpx = mask.load()
fade = int(PANEL_W * 0.42)
for x in range(PANEL_W):
    if x < fade:
        v = x / fade
        a = int(255 * (v * v))  # ease-in
    else:
        a = 255
    for y in range(H):
        mpx[x, y] = a
duo.putalpha(mask)

img.alpha_composite(duo, (W - PANEL_W, 0))

# ---------------- logo (key out white) ----------------
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
LOGO_SZ = int(74 * S)
logo = logo.resize((LOGO_SZ, LOGO_SZ), Image.LANCZOS)

draw = ImageDraw.Draw(img)

PAD_X = int(72 * S)
PAD_TOP = int(60 * S)

img.alpha_composite(logo, (PAD_X - int(6 * S), PAD_TOP - int(6 * S)))

# wordmark
name_font = serif(34 * S)
tag_font = manrope(13 * S, 700)
name_x = PAD_X + LOGO_SZ + int(12 * S)
draw.text((name_x, PAD_TOP + int(2 * S)), "The Breath Reset", font=name_font, fill=CHARCOAL)

# letterspaced tagline
def draw_tracked(d, pos, text, fnt, fill, tracking):
    x, y = pos
    for ch in text:
        d.text((x, y), ch, font=fnt, fill=fill)
        x += d.textlength(ch, font=fnt) + tracking
    return x
draw_tracked(draw, (name_x + int(2 * S), PAD_TOP + int(44 * S)),
             "BREATHE  ·  RESET  ·  RESTORE", tag_font, SAGE_DARK, int(3 * S))

# ---------------- eyebrow ----------------
eb_y = int(372 * S)
eb_font = manrope(15 * S, 700)
line_w = int(40 * S)
draw.line([(PAD_X, eb_y + int(9 * S)), (PAD_X + line_w, eb_y + int(9 * S))], fill=CLAY, width=int(2 * S))
draw_tracked(draw, (PAD_X + line_w + int(14 * S), eb_y), "A FOUNDER STORY", eb_font, CLAY, int(3.5 * S))

# ---------------- title (mixed serif, word wrap) ----------------
title_reg = serif(66 * S)
title_ital = serif(66 * S, italic=True)
title_words = "For years, I woke up with the feeling of |anxiety| in the pit of my stomach.".split(" ")

# build tokens with style
tokens = []
for w in title_words:
    if w.startswith("|") and w.endswith("|"):
        tokens.append((w.strip("|"), title_ital, SAGE_DARK))
    else:
        tokens.append((w, title_reg, INK))

MAX_W = int(620 * S)
space_w = draw.textlength(" ", font=title_reg)

# wrap into lines
lines = []
cur = []
cur_w = 0
for tok in tokens:
    tw = draw.textlength(tok[0], font=tok[1])
    add = tw if not cur else space_w + tw
    if cur and cur_w + add > MAX_W:
        lines.append(cur)
        cur = [tok]
        cur_w = tw
    else:
        cur.append(tok)
        cur_w += add
if cur:
    lines.append(cur)

ty = int(404 * S)
line_h = int(70 * S)
for line in lines:
    x = PAD_X
    for i, (txt, fnt, fill) in enumerate(line):
        if i > 0:
            x += space_w
        draw.text((x, ty), txt, font=fnt, fill=fill)
        x += draw.textlength(txt, font=fnt)
    ty += line_h

# ---------------- subtitle ----------------
sub_font = manrope(23 * S, 600)
draw.text((PAD_X, ty + int(16 * S)), "Why I started The Breath Reset", font=sub_font, fill=OLIVE)

# ---------------- finish ----------------
out = img.convert("RGB").resize((1280, 720), Image.LANCZOS)
out_path = os.path.join(ROOT, "assets", "social", "the_breath_reset_founder_video_cover.png")
out.save(out_path, "PNG")
print("saved", out_path)
