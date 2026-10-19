#!/usr/bin/env python3
"""
Founder video v2 cards (vertical 1080x1920).

Cover is a still frame lifted from the video and graded into the warm-black
palette, not a separate designed graphic. End card is type only -- no lung
mark, since assets/brand/logo.png is gone and the brief calls for no large
logos.

  python3 tmp/make_founder_cards_v2.py

Outputs -> assets/social/youtube/founder-video/cover.png and end.png
"""
import os
import subprocess

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

W, H = 1080, 1920
CX = W // 2

SOURCE = os.path.join(ROOT, "assets", "social", "youtube", "founder-video",
                      "founder-story-v2.mp4")
OUT_DIR = os.path.join(ROOT, "assets", "social", "youtube", "founder-video")

# Caption-free pause in the source; direct gaze, mouth closed.
COVER_TIME = 40.8

# Instagram crops Reels to 4:5 in the profile grid, so the safe vertical band
# is y 285..1635. Keep every cover element inside it.
GRID_TOP = 285
GRID_BOTTOM = 1635

# palette -- warm-black system, matches make_reel_cards.py / make_reels.py
BG = (16, 13, 11)
BG_DEEP = (10, 8, 7)
SAGE = (143, 165, 138)
SAGE_DARK = (95, 116, 94)
OFF = (239, 231, 217)
MUTED = (172, 164, 150)
CLAY = (209, 144, 115)

FONTS = os.path.join(ROOT, "breathing-reel", "fonts")


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), int(size))


def manrope(size, weight=600):
    f = font("Manrope.ttf", size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def serif(size, italic=False):
    return font("InstrumentSerif-Italic.ttf" if italic else
                "InstrumentSerif-Regular.ttf", size)


# ---------------------------------------------------------------- text helpers
def tracked_width(draw, text, fnt, tracking):
    if not text:
        return 0
    w = sum(draw.textlength(ch, font=fnt) + tracking for ch in text)
    return w - tracking


def draw_tracked(draw, xy, text, fnt, fill, tracking, center=False):
    x, y = xy
    if center:
        x -= tracked_width(draw, text, fnt, tracking) / 2
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking


def wrap_mixed(draw, text, reg, ital, max_w, plain_fill, accent_fill):
    """Wrap `text` where |pipes| mark an italic accent run. -> list of lines,
    each a list of (word, font, fill)."""
    tokens = []
    accent = False
    for word in text.split(" "):
        opens, closes = word.startswith("|"), word.endswith("|")
        bare = word.strip("|")
        in_accent = accent or opens
        tokens.append((bare, ital, accent_fill) if in_accent
                      else (bare, reg, plain_fill))
        if opens and closes and len(word) >= 2:
            accent = False          # single-word accent
        elif opens:
            accent = True           # run opens and continues
        elif closes:
            accent = False          # run ends here

    space = draw.textlength(" ", font=reg)
    lines, cur, cur_w = [], [], 0.0
    for tok in tokens:
        tw = draw.textlength(tok[0], font=tok[1])
        add = tw if not cur else space + tw
        if cur and cur_w + add > max_w:
            lines.append(cur)
            cur, cur_w = [tok], tw
        else:
            cur.append(tok)
            cur_w += add
    if cur:
        lines.append(cur)
    return lines


def line_width(draw, line, space):
    w = 0.0
    for i, (txt, fnt, _) in enumerate(line):
        if i:
            w += space
        w += draw.textlength(txt, font=fnt)
    return w


def draw_mixed_lines(draw, lines, x, y, line_h, space, center=False):
    for line in lines:
        lx = x - line_width(draw, line, space) / 2 if center else x
        for i, (txt, fnt, fill) in enumerate(line):
            if i:
                lx += space
            draw.text((lx, y), txt, font=fnt, fill=fill)
            lx += draw.textlength(txt, font=fnt)
        y += line_h
    return y


# ------------------------------------------------------------------ gradients
def vertical_ramp(stops, width=W, height=H):
    """stops: [(y_fraction, alpha 0-255)] -> L-mode mask, smooth."""
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
                    u = (t - ys[j]) / (ys[j + 1] - ys[j])
                    u = u * u * (3 - 2 * u)  # smoothstep
                    v = al[j] + (al[j + 1] - al[j]) * u
                    break
        px[0, i] = int(round(v))
    return small.resize((width, height), Image.BICUBIC)


def radial_glow(size, color, peak_alpha):
    """Soft circular glow as an RGBA image of side `size`."""
    layer = Image.new("L", (64, 64), 0)
    px = layer.load()
    c = 31.5
    for y in range(64):
        for x in range(64):
            r = (((x - c) ** 2 + (y - c) ** 2) ** 0.5) / c
            v = max(0.0, 1.0 - r)
            px[x, y] = int(peak_alpha * (v ** 2.2))
    mask = layer.resize((size, size), Image.BICUBIC)
    glow = Image.new("RGBA", (size, size), color + (0,))
    glow.putalpha(mask)
    return glow


# ---------------------------------------------------------------------- cover
def grab_still(t):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(t), "-i", SOURCE,
         "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        check=True, capture_output=True).stdout
    import io
    return Image.open(io.BytesIO(raw)).convert("RGB")


def grade(img):
    """Pull the sunny garden footage toward the warm-black brand palette."""
    img = ImageEnhance.Color(img).enhance(0.62)
    img = ImageEnhance.Brightness(img).enhance(0.80)
    img = ImageEnhance.Contrast(img).enhance(1.06)

    # warm wash so the greens sit closer to the clay/sage end of the palette
    wash = Image.new("RGB", img.size, (54, 40, 30))
    img = Image.blend(img, wash, 0.14)

    # corner vignette
    vig = Image.new("RGBA", img.size, BG_DEEP + (0,))
    edge = vertical_ramp([(0.0, 130), (0.18, 0), (0.82, 0), (1.0, 150)],
                         img.size[0], img.size[1])
    vig.putalpha(edge)
    return Image.alpha_composite(img.convert("RGBA"), vig)


def build_cover():
    still = grab_still(COVER_TIME)
    if still.size != (W, H):
        still = still.resize((W, H), Image.LANCZOS)

    img = grade(still)

    # bottom scrim so the headline has somewhere quiet to sit
    scrim = Image.new("RGBA", (W, H), BG_DEEP + (0,))
    scrim.putalpha(vertical_ramp([(0.50, 0), (0.66, 110), (0.78, 218), (1.0, 246)]))
    img = Image.alpha_composite(img, scrim)

    # gentle top scrim to seat the wordmark
    top = Image.new("RGBA", (W, H), BG_DEEP + (0,))
    top.putalpha(vertical_ramp([(0.0, 150), (0.13, 96), (0.30, 0), (1.0, 0)]))
    img = Image.alpha_composite(img, top)

    draw = ImageDraw.Draw(img)

    # very small wordmark, inside the 4:5 grid crop
    draw_tracked(draw, (CX, GRID_TOP + 58), "THE BREATH RESET",
                 manrope(26, 700), OFF, 7.5, center=True)

    # headline, left-aligned and bottom-weighted -- editorial, not centred ad
    reg, ital = serif(96), serif(96, italic=True)
    lines = wrap_mixed(draw, "I tried to |think my way out| of anxiety.",
                       reg, ital, W - 180, OFF, SAGE)
    line_h = 112
    block_h = line_h * len(lines)
    top_y = 1440 - block_h
    space = draw.textlength(" ", font=reg)

    rule_y = top_y - 46
    draw.line([(90, rule_y), (90 + 66, rule_y)], fill=CLAY, width=3)

    draw_mixed_lines(draw, lines, 90, top_y, line_h, space)

    out = os.path.join(OUT_DIR, "cover.png")
    img.convert("RGB").save(out, "PNG")
    print("saved", os.path.relpath(out, ROOT))


# -------------------------------------------------------------------- end card
def build_end():
    img = Image.new("RGBA", (W, H), BG + (255,))

    cy = 930

    # faint lift behind the type, same quiet glow as the Instagram posts
    img.alpha_composite(radial_glow(1600, (92, 112, 88), 66),
                        (CX - 800, cy - 800))

    draw = ImageDraw.Draw(img)
    draw.text((CX, cy), "The Breath Reset", font=serif(104), fill=OFF, anchor="mm")
    draw.text((CX, cy + 104), "Relax. Retrain. Release.",
              font=serif(58, italic=True), fill=SAGE, anchor="mm")

    rule_y = cy + 186
    draw.line([(CX - 46, rule_y), (CX + 46, rule_y)], fill=SAGE_DARK, width=2)

    sub = manrope(27, 600)
    for i, line in enumerate(["Follow for simple breathwork practices",
                              "and nervous system education."]):
        draw.text((CX, rule_y + 62 + i * 40), line, font=sub, fill=MUTED,
                  anchor="mm")

    out = os.path.join(OUT_DIR, "end.png")
    img.convert("RGB").save(out, "PNG")
    print("saved", os.path.relpath(out, ROOT))


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    build_cover()
    build_end()
