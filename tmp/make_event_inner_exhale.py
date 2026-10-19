#!/usr/bin/env python3
"""
The Breath Reset — event announcement: "The Inner Exhale" workshop.

Same dark warm-black + sage orb language as the carousels / reels, so it sits
in the grid. Renders a 4:5 feed post and a 9:16 story from one layout.

Edit EVENT below and re-run:  python3 tmp/make_event_inner_exhale.py
Outputs -> assets/social/instagram/events/inner-exhale/post.png, story.png
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

EVENT = dict(
    title_a="The Inner", title_b="Exhale",
    kicker="BREAKTHROUGH BREATHWORK",
    hosts="Hosted by Suraj & Bianca",
    blurb="A 3-hour immersive breathwork workshop to regulate your nervous system, "
          "release what’s held, and reconnect with more clarity and ease.",
    pillars=[("Learn", ["PRACTICAL BREATHING", "EDUCATION"]),
             ("Breathe", ["75-MINUTE GUIDED", "BREATHWORK FLOW"]),
             ("Take home", ["SIMPLE TOOLS", "TO KEEP"])],
    day="SUNDAY", date="11 October 2026", time="2:30 – 5:30pm",
    venue="Mothership Studios", suburb="Marrickville",
    cta="TICKETS VIA EVENTBRITE", cta_sub="Link in bio",
)

BG, BG_LIFT, BG_DEEP = (16, 13, 11), (26, 21, 18), (10, 8, 7)
SAGE      = np.array([143, 165, 138], float)
SAGE_T    = (143, 165, 138)
SAGE_DARK = (95, 116, 94)
OFF       = (239, 231, 217)
MUTED     = (172, 164, 150)
FAINT     = (110, 104, 95)
INK       = (21, 25, 22)
WARMWHITE = np.array([232, 238, 226], float)

HERE  = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.dirname(HERE)
FONTS = os.path.join(ROOT, "breathing-reel", "fonts")
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

# --------------------------- background + orb ------------------------
def radial_alpha(size, stops):
    c = (size - 1) / 2
    yy, xx = np.mgrid[0:size, 0:size]
    r = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / (size / 2)
    xs = [s[0] for s in stops]; ys = [s[1] for s in stops]
    return np.clip(np.interp(r.ravel(), xs, ys).reshape(size, size), 0, 1)

def add_radial(canv, cx, cy, a2d, color, gain):
    H, W = canv.shape[:2]
    ah, aw = a2d.shape
    x0, y0 = int(round(cx - aw / 2)), int(round(cy - ah / 2))
    cx0, cy0 = max(x0, 0), max(y0, 0); cx1, cy1 = min(x0 + aw, W), min(y0 + ah, H)
    if cx1 <= cx0 or cy1 <= cy0: return
    sub = a2d[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
    canv[cy0:cy1, cx0:cx1, :] += (sub[..., None] * gain) * color

def background(W, H, orb_cy, orb_r):
    c = np.array([W / 2, orb_cy])
    yy, xx = np.mgrid[0:H, 0:W]
    maxd = np.hypot(max(c[0], W - c[0]), max(c[1], H - c[1]))
    r = np.sqrt((xx - c[0]) ** 2 + (yy - c[1]) ** 2) / maxd
    canv = np.zeros((H, W, 3), float)
    for i in range(3):
        canv[..., i] = np.interp(r.ravel(), [0, 0.46, 1],
                                 [BG_LIFT[i], BG[i], BG_DEEP[i]]).reshape(H, W)
    cx = W / 2
    add_radial(canv, cx, orb_cy, radial_alpha(int(orb_r * 3), [(0, 0.55), (0.6, 0), (1, 0)]), SAGE, 0.52)
    add_radial(canv, cx, orb_cy, radial_alpha(orb_r, [(0, 0.85), (0.3, 0.5), (0.55, 0.2),
                                                     (0.72, 0.04), (0.82, 0), (1, 0)]), SAGE, 0.85)
    add_radial(canv, cx, orb_cy, radial_alpha(int(orb_r * 0.7), [(0, 0.6), (0.3, 0.14), (0.5, 0), (1, 0)]),
               WARMWHITE, 0.82)

    r2 = np.sqrt((xx - W / 2) ** 2 + (yy - H / 2) ** 2) / np.hypot(W / 2, H / 2)
    vig = np.clip((r2 - 0.52) / 0.48, 0, 1) ** 1.5
    canv *= (1 - 0.5 * vig[..., None])
    canv += np.random.RandomState(11).randn(H, W)[..., None] * 6
    img = Image.fromarray(np.clip(canv, 0, 255).astype(np.uint8)).convert("RGBA")

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for mult, op in [(1.22, 0.16), (1.5, 0.09), (1.82, 0.05)]:
        rr = orb_r / 2 * mult
        d.ellipse([cx - rr, orb_cy - rr, cx + rr, orb_cy + rr],
                  outline=(143, 165, 138, int(op * 255)), width=2)
    img.alpha_composite(ov)
    return img

# ----------------------------- text ----------------------------------
def tracked_w(d, text, fnt, track):
    return sum(d.textlength(c, font=fnt) + track for c in text) - track

def tracked(d, x_center, y, text, fnt, fill, track):
    x = x_center - tracked_w(d, text, fnt, track) / 2
    for c in text:
        d.text((x, y), c, font=fnt, fill=fill); x += d.textlength(c, font=fnt) + track

def wrap(d, text, fnt, max_w):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=fnt) > max_w and cur: lines.append(cur); cur = w
        else: cur = t
    if cur: lines.append(cur)
    return lines

def segs(d, x_center, y, parts):
    x = x_center - sum(d.textlength(t, font=f) for t, f, _ in parts) / 2
    for t, f, fill in parts:
        d.text((x, y), t, font=f, fill=fill); x += d.textlength(t, font=f)

# ----------------------------- layout --------------------------------
def draw_layers(W, H, L, cta_label=None, cta_pill=True):
    """Each block on its own transparent layer, in reveal order, so the
    video ad can bring them in one at a time."""
    e = EVENT
    cx = W / 2
    layers = []
    def layer(key):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        layers.append((key, im))
        return im, ImageDraw.Draw(im)

    _, d = layer("brand")
    tracked(d, cx, L["brand_y"], "WORKSHOP", manrope(22, 600), SAGE_DARK, 6)

    _, d = layer("title")
    t = serif(L["title"]); ti = serif(L["title"], it=True)
    segs(d, cx, L["title_y"], [(e["title_a"] + " ", t, OFF), (e["title_b"], ti, SAGE_T)])

    _, d = layer("kicker")
    tracked(d, cx, L["kicker_y"], e["kicker"], manrope(24, 600), MUTED, 7)
    d.text((cx, L["kicker_y"] + 44), e["hosts"], font=serif(36, it=True), fill=OFF, anchor="ma")

    _, d = layer("blurb")
    ly = L["kicker_y"] + 116
    d.line([(cx - 38, ly), (cx + 38, ly)], fill=SAGE_DARK, width=2)
    body = manrope(L["body"], 400)
    y = ly + 36
    for ln in wrap(d, e["blurb"], body, L["body_w"]):
        d.text((cx, y), ln, font=body, fill=MUTED, anchor="ma"); y += L["body_lh"]

    _, d = layer("pillars")
    py = L["pillars_y"]
    col_w = (W - 2 * L["pad"]) / 3
    lab = manrope(19, 600)
    for i, (word, lines) in enumerate(e["pillars"]):
        ccx = L["pad"] + col_w * (i + 0.5)
        d.text((ccx, py), word, font=serif(52, it=True), fill=SAGE_T, anchor="ma")
        for j, ln in enumerate(lines):
            tracked(d, ccx, py + 80 + j * 30, ln, lab, OFF, 2.5)
        if i:
            x = L["pad"] + col_w * i
            d.line([(x, py + 8), (x, py + 128)], fill=(60, 58, 52), width=1)

    _, d = layer("panel")
    px0, px1 = L["pad"], W - L["pad"]
    py0, py1 = L["panel_y"], L["panel_y"] + L["panel_h"]
    d.rounded_rectangle([px0, py0, px1, py1], radius=28,
                        fill=(239, 231, 217, 12), outline=(143, 165, 138, 70), width=2)
    mid = (px0 + px1) / 2
    d.line([(mid, py0 + 30), (mid, py1 - 30)], fill=SAGE_T, width=1)
    cy_ = (py0 + py1) / 2
    lx = (px0 + mid) / 2
    tracked(d, lx, cy_ - 68, e["day"], manrope(20, 600), SAGE_T, 6)
    d.text((lx, cy_ - 36), e["date"], font=serif(54), fill=OFF, anchor="ma")
    d.text((lx, cy_ + 32), e["time"], font=manrope(26, 500), fill=MUTED, anchor="ma")
    rx = (mid + px1) / 2
    tracked(d, rx, cy_ - 68, "WHERE", manrope(20, 600), SAGE_T, 6)
    d.text((rx, cy_ - 36), e["venue"], font=serif(48), fill=OFF, anchor="ma")
    d.text((rx, cy_ + 32), e["suburb"], font=manrope(26, 500), fill=MUTED, anchor="ma")

    _, d = layer("cta")
    label = cta_label or f"{e['cta']}  ·  {e['cta_sub'].upper()}   →"
    by0 = L["cta_y"]; bh = 84
    if cta_pill:
        d.rounded_rectangle([px0, by0, px1, by0 + bh], radius=bh // 2, fill=SAGE_T)
        tracked(d, cx, by0 + bh / 2 - 14, label, manrope(22, 700), INK, 4)
    else:
        tracked(d, cx, by0 + bh / 2 - 14, label, manrope(22, 700), SAGE_T, 5)
    return layers

def render(name, W, H, L):
    img = background(W, H, L["orb_cy"], L["orb_r"])
    for _, im in draw_layers(W, H, L):
        img.alpha_composite(im)

    out = os.path.join(OUT, f"{name}.png")
    img.convert("RGB").save(out); print("saved", os.path.relpath(out, ROOT))

POST = dict(pad=80, brand_y=60, orb_cy=215, orb_r=220, title=128, title_y=330,
            kicker_y=505, body=30, body_w=860, body_lh=45,
            pillars_y=832, panel_y=1004, panel_h=180, cta_y=1212)
# The story keeps the top ~200px and bottom ~200px clear of Instagram's UI.
STORY = dict(pad=80, brand_y=200, orb_cy=470, orb_r=320, title=140, title_y=690,
             kicker_y=870, body=33, body_w=860, body_lh=50,
             pillars_y=1225, panel_y=1425, panel_h=200, cta_y=1655)

if __name__ == "__main__":
    render("post", 1080, 1350, POST)
    render("story", 1080, 1920, STORY)
