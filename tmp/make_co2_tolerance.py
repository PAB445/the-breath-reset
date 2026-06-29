#!/usr/bin/env python3
import math
import os
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "assets", "social", "youtube", "co2-tolerance")

S = 2
W, H = 1280 * S, 720 * S
CX = W // 2

CREAM = (248, 241, 232)
WARM_WHITE = (255, 250, 243)
CREAM_DEEP = (241, 231, 217)
CHARCOAL = (32, 39, 33)
INK = (21, 25, 22)
SAGE = (143, 165, 138)
SAGE_DARK = (95, 116, 94)
CLAY = (209, 144, 115)
OLIVE = (105, 120, 97)
MUTED = (125, 132, 118)
PILLAR_DIM = (129, 135, 122)

FONTS = os.path.join(ROOT, "breathing-reel", "fonts")


def font(path, size):
    return ImageFont.truetype(os.path.join(FONTS, path), int(size))


def manrope(size, weight=600):
    f = font("Manrope.ttf", size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def serif(size, italic=False):
    return font("InstrumentSerif-Italic.ttf" if italic else "InstrumentSerif-Regular.ttf", size)


def gradient_bg():
    small = Image.new("RGB", (64, 36))
    px = small.load()
    for y in range(36):
        for x in range(64):
            t = (x / 63 * 0.50 + y / 35 * 0.50)
            if t < 0.5:
                u = t / 0.5
                c = tuple(int(WARM_WHITE[i] + (CREAM[i] - WARM_WHITE[i]) * u) for i in range(3))
            else:
                u = (t - 0.5) / 0.5
                c = tuple(int(CREAM[i] + (CREAM_DEEP[i] - CREAM[i]) * u) for i in range(3))
            px[x, y] = c
    return small.resize((W, H), Image.BILINEAR).convert("RGBA")


def add_rings(img, mode="left"):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    def ring(cx, cy, r, color, alpha, width=2 * S):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color + (alpha,), width=width)

    if mode == "left":
        ring(int(125 * S), int(720 * S), int(380 * S), SAGE_DARK, 32)
        ring(int(125 * S), int(720 * S), int(260 * S), SAGE_DARK, 22)
        ring(int(1000 * S), int(-80 * S), int(300 * S), SAGE, 22)
        ring(int(1075 * S), int(364 * S), int(118 * S), SAGE_DARK, 36)
        ring(int(1075 * S), int(364 * S), int(80 * S), SAGE_DARK, 20)
    else:
        ring(CX, int(350 * S), int(480 * S), SAGE_DARK, 28)
        ring(CX, int(350 * S), int(360 * S), SAGE_DARK, 20)
        ring(int(-40 * S), int(720 * S), int(280 * S), SAGE_DARK, 22)
        ring(int(1330 * S), int(0), int(260 * S), SAGE, 20)
    return Image.alpha_composite(img, overlay)


def key_logo():
    logo = Image.open(os.path.join(ROOT, "assets", "brand", "logo.png")).convert("RGBA")
    px = logo.load()
    for y in range(logo.height):
        for x in range(logo.width):
            r, g, b, a = px[x, y]
            whiteness = min(r, g, b)
            if whiteness >= 250:
                na = 0
            elif whiteness <= 232:
                na = 255
            else:
                na = int(255 * (250 - whiteness) / 18)
            px[x, y] = (r, g, b, min(a, na))
    return logo


def draw_tracked(d, pos, text, fnt, fill, tracking):
    x, y = pos
    for ch in text:
        d.text((x, y), ch, font=fnt, fill=fill)
        x += d.textlength(ch, font=fnt) + tracking
    return x


def tracked_width(d, text, fnt, tracking):
    if not text:
        return 0
    return sum(d.textlength(ch, font=fnt) + tracking for ch in text) - tracking


def draw_tracked_center(d, cx, y, text, fnt, fill, tracking):
    x = cx - tracked_width(d, text, fnt, tracking) / 2
    draw_tracked(d, (x, y), text, fnt, fill, tracking)


def tracked_segments(d, x, y, segments, tracking):
    for text, fnt, fill in segments:
        for ch in text:
            d.text((x, y), ch, font=fnt, fill=fill)
            x += d.textlength(ch, font=fnt) + tracking
    return x


def tracked_segments_width(d, segments, tracking):
    width = -tracking
    for text, fnt, _ in segments:
        width += sum(d.textlength(ch, font=fnt) + tracking for ch in text)
    return width


def draw_retrain_pillars(d, x, y, size, tracking, centered=False):
    on = manrope(size, 700)
    off = manrope(size, 500)
    segments = [
        ("RELAX", off, PILLAR_DIM),
        ("  ·  ", off, PILLAR_DIM),
        ("RETRAIN", on, CLAY),
        ("  ·  ", off, PILLAR_DIM),
        ("RELEASE", off, PILLAR_DIM),
    ]
    if centered:
        x = x - tracked_segments_width(d, segments, tracking) / 2
    tracked_segments(d, x, y, segments, tracking)


def wrap_words(d, text, fnt, max_w):
    words = text.split(" ")
    lines = []
    cur = ""
    for word in words:
        test = (cur + " " + word).strip()
        if cur and d.textlength(test, font=fnt) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def draw_mixed_title(d, x, y, raw, size, max_w, line_h):
    reg = serif(size)
    ital = serif(size, True)
    tokens = []
    italic = False
    for raw_word in raw.split(" "):
        starts = raw_word.startswith("|")
        ends = raw_word.endswith("|")
        word = raw_word.strip("|")
        use_italic = italic or starts
        tokens.append((word, ital if use_italic else reg, SAGE_DARK if use_italic else INK))
        if starts and not ends:
            italic = True
        if ends:
            italic = False

    space = d.textlength(" ", font=reg)
    lines, cur, cur_w = [], [], 0
    for token in tokens:
        tw = d.textlength(token[0], font=token[1])
        add = tw if not cur else space + tw
        if cur and cur_w + add > max_w:
            lines.append(cur)
            cur = [token]
            cur_w = tw
        else:
            cur.append(token)
            cur_w += add
    if cur:
        lines.append(cur)

    yy = y
    for line in lines:
        xx = x
        for i, (txt, fnt, fill) in enumerate(line):
            if i:
                xx += space
            d.text((xx, yy), txt, font=fnt, fill=fill)
            xx += d.textlength(txt, font=fnt)
        yy += line_h
    return yy


def add_founder_photo(img):
    panel_w = int(500 * S)
    co2_still = os.path.join(OUT_DIR, "cover-still.png")
    source = co2_still if os.path.exists(co2_still) else os.path.join(ROOT, "assets", "photos", "suraj.jpg")
    photo = Image.open(source).convert("RGB")
    target_ratio = panel_w / H
    photo_ratio = photo.width / photo.height
    if photo_ratio > target_ratio:
        new_h = H
        new_w = int(H * photo_ratio)
    else:
        new_w = panel_w
        new_h = int(panel_w / photo_ratio)
    photo = photo.resize((new_w, new_h), Image.LANCZOS)
    left = int((new_w - panel_w) * (0.50 if source == co2_still else 0.55))
    top = int((new_h - H) * (0.42 if source == co2_still else 0.14))
    photo = photo.crop((left, top, left + panel_w, top + H))
    gray = ImageOps.autocontrast(ImageOps.grayscale(photo), cutoff=1)
    duo = ImageOps.colorize(gray, black=(30, 34, 30), white=(238, 232, 222), mid=(116, 128, 112)).convert("RGBA")
    duo = duo.filter(ImageFilter.GaussianBlur(0.2 * S))

    mask = Image.new("L", (panel_w, H), 255)
    px = mask.load()
    fade = int(panel_w * 0.46)
    for x in range(panel_w):
        a = 255
        if x < fade:
            v = x / fade
            a = int(255 * (v * v))
        for y in range(H):
            px[x, y] = a
    duo.putalpha(mask)
    img.alpha_composite(duo, (W - panel_w, 0))
    return img


def cover():
    img = add_rings(gradient_bg(), "left")
    img = add_founder_photo(img)
    d = ImageDraw.Draw(img)

    pad_x = int(72 * S)
    pad_top = int(58 * S)
    logo_sz = int(72 * S)
    logo = key_logo().resize((logo_sz, logo_sz), Image.LANCZOS)
    img.alpha_composite(logo, (pad_x - int(6 * S), pad_top - int(6 * S)))

    name_x = pad_x + logo_sz + int(12 * S)
    d.text((name_x, pad_top + int(2 * S)), "The Breath Reset", font=serif(34 * S), fill=CHARCOAL)
    draw_retrain_pillars(d, name_x + int(2 * S), pad_top + int(44 * S), 13 * S, int(3 * S))

    eb_y = int(202 * S)
    eb_font = manrope(15 * S, 700)
    d.line([(pad_x, eb_y + int(9 * S)), (pad_x + int(40 * S), eb_y + int(9 * S))],
           fill=CLAY, width=int(2 * S))
    draw_tracked(d, (pad_x + int(54 * S), eb_y), "CO₂ TOLERANCE", eb_font, CLAY, int(3.5 * S))

    ty = int(244 * S)
    ty = draw_mixed_title(d, pad_x, ty, "Breath |Hold| Test", 86 * S, int(650 * S), int(88 * S))

    sub_font = manrope(25 * S, 600)
    d.text((pad_x, ty + int(8 * S)), "A simple way to explore your CO₂ tolerance", font=sub_font, fill=OLIVE)

    ins_font = manrope(25 * S, 500)
    small_font = manrope(20 * S, 500)
    iy = ty + int(70 * S)
    for line in ["Breathe normally.", "Exhale gently. Then hold."]:
        d.text((pad_x, iy), line, font=ins_font, fill=INK)
        iy += int(39 * S)
    d.text((pad_x, iy + int(10 * S)), "Stop when you feel the first clear urge to breathe.",
           font=small_font, fill=MUTED)

    footer_y = int(642 * S)
    d.text((pad_x, footer_y), "The Breath Reset", font=serif(28 * S), fill=CHARCOAL)
    draw_retrain_pillars(d, pad_x, footer_y + int(42 * S), 12 * S, int(2.8 * S))

    out = img.convert("RGB").resize((1280, 720), Image.LANCZOS)
    out.save(os.path.join(OUT_DIR, "cover.png"), "PNG")


def end_screen():
    img = add_rings(gradient_bg(), "center")
    d = ImageDraw.Draw(img)

    eb_font = manrope(15 * S, 700)
    eb_text = "BREATH HOLD TEST"
    eb_y = int(108 * S)
    ebw = tracked_width(d, eb_text, eb_font, int(4 * S))
    ly = eb_y + int(10 * S)
    d.line([(CX - ebw / 2 - int(68 * S), ly), (CX - ebw / 2 - int(22 * S), ly)],
           fill=CLAY, width=int(2 * S))
    d.line([(CX + ebw / 2 + int(22 * S), ly), (CX + ebw / 2 + int(68 * S), ly)],
           fill=CLAY, width=int(2 * S))
    draw_tracked_center(d, CX, eb_y, eb_text, eb_font, CLAY, int(4 * S))

    d.text((CX, int(190 * S)), "Take a normal breath.", font=serif(72 * S), fill=INK, anchor="mm")
    d.text((CX, int(268 * S)), "Notice how your body feels.", font=serif(46 * S, True),
           fill=SAGE_DARK, anchor="mm")

    d.line([(CX - int(70 * S), int(334 * S)), (CX + int(70 * S), int(334 * S))],
           fill=SAGE_DARK, width=int(2 * S))

    prompt_font = manrope(25 * S, 500)
    for y, line in [(390, "Your hold time is just information."),
                    (428, "Not a score. Not a test to force.")]:
        d.text((CX, int(y * S)), line, font=prompt_font, fill=CHARCOAL, anchor="mm")

    instruction_font = manrope(23 * S, 500)
    d.text((CX, int(498 * S)), "Retest another day and notice what changes.",
           font=instruction_font, fill=OLIVE, anchor="mm")

    cta_font = manrope(20 * S, 700)
    d.rounded_rectangle([CX - int(175 * S), int(548 * S), CX + int(175 * S), int(592 * S)],
                        radius=int(22 * S), outline=SAGE_DARK + (82,), width=int(2 * S))
    d.text((CX, int(571 * S)), "Save this and try again in 7 days.",
           font=cta_font, fill=SAGE_DARK, anchor="mm")

    d.text((CX, int(642 * S)), "The Breath Reset", font=serif(31 * S), fill=CHARCOAL, anchor="mm")
    draw_retrain_pillars(d, CX, int(672 * S), 12 * S, int(2.8 * S), centered=True)

    out = img.convert("RGB").resize((1280, 720), Image.LANCZOS)
    out.save(os.path.join(OUT_DIR, "end-screen.png"), "PNG")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    cover()
    end_screen()
    print("saved", os.path.relpath(os.path.join(OUT_DIR, "cover.png"), ROOT))
    print("saved", os.path.relpath(os.path.join(OUT_DIR, "end-screen.png"), ROOT))


if __name__ == "__main__":
    main()
