#!/usr/bin/env python3
"""
Quiet-breathing Instagram cover (vertical 1080x1920).

Same treatment as the founder cover: a graded still from the footage, not a
designed graphic. Headline sits in the 4:5 grid crop Instagram uses on the
profile, so the type survives the feed and the grid.

  python3 tmp/make_quiet_breathing_cover.py

Output -> assets/social/youtube/retrain/quiet-breathing/cover.png
"""
import os
import subprocess

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

W, H = 1080, 1920
CX = W // 2

OUT_DIR = os.path.join(ROOT, "assets", "social", "youtube", "retrain",
                       "quiet-breathing")
SOURCE = os.path.join(OUT_DIR, "quiet-breathing-source.mp4")

# Same 9:16 crop as render_quiet_breathing.py (full-height, face-centred).
CROP_W, CROP_X = 608, 456

# Settled moment in the guided breath: mouth closed, quieter than the
# talking portrait used before (65.4s).
COVER_TIME = float(os.environ.get("QB_COVER_TIME", "100.15"))

# Instagram Reels profile grid is 4:5, so the safe band is y 285..1635.
GRID_TOP = 285
GRID_BOTTOM = 1635

BG_DEEP = (10, 8, 7)
SAGE = (143, 165, 138)
OFF = (239, 231, 217)
CLAY = (209, 144, 115)

FONTS = os.path.join(ROOT, "breathing-reel", "fonts")

HEADLINE = (
    "You might not need a |deeper breath.|\n"
    "You might need a |quieter one.|"
)


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
    paragraphs = text.split("\n")
    lines = []
    for para in paragraphs:
        tokens = []
        accent = False
        for word in para.split(" "):
            if not word:
                continue
            opens, closes = word.startswith("|"), word.endswith("|")
            bare = word.strip("|")
            in_accent = accent or opens
            tokens.append((bare, ital, accent_fill) if in_accent
                          else (bare, reg, plain_fill))
            if opens and closes and len(word) >= 2:
                accent = False
            elif opens:
                accent = True
            elif closes:
                accent = False

        space = draw.textlength(" ", font=reg)
        cur, cur_w = [], 0.0
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


def vertical_ramp(stops, width=W, height=H):
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
                    u = u * u * (3 - 2 * u)
                    v = al[j] + (al[j + 1] - al[j]) * u
                    break
        px[0, i] = int(round(v))
    return small.resize((width, height), Image.BICUBIC)


def grab_still(t):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(t), "-i", SOURCE,
         "-vf", f"crop={CROP_W}:1080:{CROP_X}:0,scale={W}:{H}:flags=lanczos",
         "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        check=True, capture_output=True).stdout
    import io
    return Image.open(io.BytesIO(raw)).convert("RGB")


def grade(img):
    """Pull the bright bamboo footage toward the warm-black brand palette."""
    img = ImageEnhance.Color(img).enhance(0.62)
    img = ImageEnhance.Brightness(img).enhance(0.78)
    img = ImageEnhance.Contrast(img).enhance(1.08)

    wash = Image.new("RGB", img.size, (54, 40, 30))
    img = Image.blend(img, wash, 0.16)

    vig = Image.new("RGBA", img.size, BG_DEEP + (0,))
    edge = vertical_ramp([(0.0, 130), (0.18, 0), (0.82, 0), (1.0, 160)],
                         img.size[0], img.size[1])
    vig.putalpha(edge)
    return Image.alpha_composite(img.convert("RGBA"), vig)


def build_cover():
    img = grade(grab_still(COVER_TIME))

    # Bottom scrim is a little heavier than the founder cover -- the olive
    # shirt is brighter than the brown jacket, and the type needs a quiet seat.
    scrim = Image.new("RGBA", (W, H), BG_DEEP + (0,))
    scrim.putalpha(vertical_ramp([(0.48, 0), (0.64, 120), (0.76, 226), (1.0, 248)]))
    img = Image.alpha_composite(img, scrim)

    top = Image.new("RGBA", (W, H), BG_DEEP + (0,))
    top.putalpha(vertical_ramp([(0.0, 150), (0.13, 96), (0.30, 0), (1.0, 0)]))
    img = Image.alpha_composite(img, top)

    draw = ImageDraw.Draw(img)

    draw_tracked(draw, (CX, GRID_TOP + 58), "THE BREATH RESET",
                 manrope(26, 700), OFF, 7.5, center=True)

    # Sized so each sentence stays one line. The italic sage words are the turn.
    reg, ital = serif(72), serif(72, italic=True)
    lines = wrap_mixed(draw, HEADLINE, reg, ital, W - 160, OFF, SAGE)
    line_h = 92
    block_h = line_h * len(lines)
    # Keep the last line above the 4:5 grid crop, with a little air.
    top_y = 1480 - block_h
    space = draw.textlength(" ", font=reg)

    rule_y = top_y - 46
    draw.line([(90, rule_y), (90 + 66, rule_y)], fill=CLAY, width=3)

    draw_mixed_lines(draw, lines, 90, top_y, line_h, space)

    out = os.path.join(OUT_DIR, "cover.png")
    img.convert("RGB").save(out, "PNG")
    print("saved", os.path.relpath(out, ROOT),
          f"({len(lines)} lines, last y ~{top_y + block_h:.0f})")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    build_cover()
