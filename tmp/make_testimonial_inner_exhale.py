#!/usr/bin/env python3
"""
The Breath Reset — Inner Exhale testimonial post.

A softened session photo with the participant's words laid over it. No cards,
boxes or graphics — just the photograph, the quote and a quiet sign-off.

Edit QUOTE below and re-run:  python3 tmp/make_testimonial_inner_exhale.py
Output -> assets/social/instagram/events/inner-exhale/testimonial-<name>.png
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

QUOTE = dict(
    name="bakari",
    # Line breaks are set by hand ("|") so each line ends on a natural pause.
    paragraphs=["This workshop gave me|so much peace through presence.",
                "It’s emotional, powerful,|and uplifting.",
                "If you’re reading this,|look for me at the next one."],
    attribution="— Bakari, Inner Exhale participant",
    photo="session-floor.jpg",
    focus_x=0.49,   # horizontal centre of the 4:5 crop, as a fraction of photo width
    blur=7,
)

W, H = 1080, 1350
OFF   = (239, 231, 217)
MUTED = (214, 204, 188)

HERE  = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.dirname(HERE)
FONTS = os.path.join(ROOT, "breathing-reel", "fonts")
PHOTO = os.path.join(ROOT, "assets", "events", "inner-exhale", QUOTE["photo"])
OUT   = os.path.join(ROOT, "assets", "social", "instagram", "events", "inner-exhale")
os.makedirs(OUT, exist_ok=True)

def font(name, size): return ImageFont.truetype(os.path.join(FONTS, name), size)
def manrope(size, w=500):
    f = font("Manrope.ttf", size)
    try: f.set_variation_by_axes([w])
    except Exception: pass
    return f
def serif(size, it=False):
    return font("InstrumentSerif-Italic.ttf" if it else "InstrumentSerif-Regular.ttf", size)

def tracked(d, x_center, y, text, fnt, fill, track):
    w = sum(d.textlength(c, font=fnt) + track for c in text) - track
    x = x_center - w / 2
    for c in text:
        d.text((x, y), c, font=fnt, fill=fill); x += d.textlength(c, font=fnt) + track

def photo_background():
    src = Image.open(PHOTO).convert("RGB")
    sw, sh = src.size
    cw = sh * W / H
    x0 = min(max(QUOTE["focus_x"] * sw - cw / 2, 0), sw - cw)
    img = src.crop((round(x0), 0, round(x0 + cw), sh)).resize((W, H), Image.LANCZOS)
    img = img.filter(ImageFilter.GaussianBlur(QUOTE["blur"]))

    a = np.asarray(img, float)
    lum = a.mean(axis=2, keepdims=True)
    a = lum + (a - lum) * 0.85              # ease the saturation a touch
    a *= 0.52                               # dim the room so the words carry
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2)) / np.sqrt(2)
    a *= (1 - 0.35 * np.clip((r - 0.35) / 0.65, 0, 1) ** 1.6)[..., None]
    a += np.random.RandomState(7).randn(H, W)[..., None] * 3.5
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")

def render():
    img = photo_background()
    txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    cx = W / 2

    q = serif(64)
    lh, gap = 74, 52
    blocks = [p.split("|") for p in QUOTE["paragraphs"]]
    blocks[0][0] = "“" + blocks[0][0]
    blocks[-1][-1] = blocks[-1][-1] + "”"
    attr_gap, attr_size = 62, 27
    block_h = sum(len(b) * lh for b in blocks) + gap * (len(blocks) - 1) + attr_gap + attr_size

    y = H * 0.465 - block_h / 2
    for b in blocks:
        for ln in b:
            d.text((cx, y), ln, font=q, fill=OFF, anchor="ma"); y += lh
        y += gap
    y += attr_gap - gap
    d.text((cx, y), QUOTE["attribution"], font=manrope(attr_size, 500), fill=MUTED, anchor="ma")

    tracked(d, cx, H - 112, "THE INNER EXHALE", manrope(19, 600), OFF + (130,), 7)

    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow.putalpha(txt.getchannel("A").point(lambda v: v * 0.55).filter(ImageFilter.GaussianBlur(14)))
    img.alpha_composite(shadow)
    img.alpha_composite(txt)

    out = os.path.join(OUT, f"testimonial-{QUOTE['name']}.png")
    img.convert("RGB").save(out); print("saved", os.path.relpath(out, ROOT))

if __name__ == "__main__":
    render()
