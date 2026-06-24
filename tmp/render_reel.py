#!/usr/bin/env python3
"""
Render every Breath Reset flow in multiple formats.

Formats (see FORMATS below):
  reel     1080x1920 9:16  -> assets/social/instagram/practices/<slug>/reel.mp4
  youtube  1920x1080 16:9  -> assets/social/youtube/long/<slug>/youtube.mp4
                              (~5 min, looped, with a baked-in intro title card)

YouTube Shorts reuse the 9:16 reel verbatim: after the reels render, each
reel.mp4 + cover.png is copied to assets/social/youtube/shorts/<slug>/.

All geometry lives in make_layout(fmt); the portrait numbers are identical to
the original renderer, so reels look exactly as before.

Run:   python3 tmp/render_reel.py                 (all formats, all flows)
       REEL_FORMAT=youtube python3 ...            (one format)
       REEL_FLOW=boxBreathing python3 ...         (one flow)
       REEL_TEST=1 REEL_FLOW=boxBreathing ...     (a few sample frames + PNGs)
"""
import os, sys, math, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flows import FLOWS, cycle_len, phase_at, orb_scale_at, ease_in_out

FPS  = 30
TEST = os.environ.get("REEL_TEST") == "1"
ONLY = os.environ.get("REEL_FLOW")            # render just one flow id if set
FMT_ONLY = os.environ.get("REEL_FORMAT")      # render just one format if set
CUE_FADE = 0.6

# palette
BG, BG_LIFT, BG_DEEP = (16, 13, 11), (26, 21, 18), (10, 8, 7)
SAGE      = np.array([143, 165, 138], float)
SAGE_T    = (143, 165, 138)
SAGE_LT   = np.array([193, 205, 186], float)
SAGE_DARK = (95, 116, 94)
CLAY      = (209, 144, 115)
OFF, MUTED, FAINT = (239, 231, 217), (172, 164, 150), (60, 57, 52)

HERE  = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.dirname(HERE)
FONTS = os.path.join(ROOT, "breathing-reel", "fonts")

# ===================================================================== formats
FORMATS = {
    "reel": dict(
        W=1080, H=1920, dur=None, endCard=None, intro=0,
        out=("instagram", "practices"), name="reel.mp4",
        master="master-{slug}.wav"),
    "youtube": dict(
        W=1920, H=1080, dur=300, endCard=4, intro=6,
        out=("youtube", "long"), name="youtube.mp4",
        master="master-{slug}-long.wav"),
}

def make_layout(fmt):
    """All geometry + text positions for one format (portrait or landscape)."""
    W, H = fmt["W"], fmt["H"]
    if H >= W:        # ---- portrait (Instagram reel / YouTube short) ----
        return dict(
            W=W, H=H, orb_cx=540, orb_cy=880, orb_base=600, glow_base=900,
            arc_r=315, box_q=330,
            eyebrow_y=150, eyebrow_size=26, eyebrow_track=10,
            sub_y=205, sub_size=24,
            brand_y=1690, brand_size=46,
            brand_sub_y=1756, brand_sub_size=22, brand_sub_track=4,
            cue_y=1360, cue_size=60,
            dots_cy=1470, dots_r=7, dots_gap=36,
            end_scale=1.0, end_y=712, end_cta_w=720,
            intro_eyebrow_y=812, intro_eyebrow_size=25,
            intro_hook_y=892, intro_hook_size=98, intro_hook_w=900, intro_hook_lh=104,
            intro_steps_size=34)
    # ---- landscape (long-form 16:9 YouTube) ----
    return dict(
        W=W, H=H, orb_cx=960, orb_cy=496, orb_base=470, glow_base=720,
        arc_r=250, box_q=250,
        eyebrow_y=64, eyebrow_size=24, eyebrow_track=10,
        sub_y=112, sub_size=22,
        brand_y=966, brand_size=44,
        brand_sub_y=1024, brand_sub_size=20, brand_sub_track=4,
        cue_y=790, cue_size=46,
        dots_cy=872, dots_r=6, dots_gap=30,
        end_scale=0.95, end_y=300, end_cta_w=1000,
        intro_eyebrow_y=300, intro_eyebrow_size=24,
        intro_hook_y=360, intro_hook_size=82, intro_hook_w=1350, intro_hook_lh=92,
        intro_steps_size=32)

# ===================================================================== fonts
def font(name, size): return ImageFont.truetype(os.path.join(FONTS, name), size)
def manrope(size, weight=600):
    f = font("Manrope.ttf", size)
    try: f.set_variation_by_axes([weight])
    except Exception: pass
    return f
def serif(size, italic=False):
    return font("InstrumentSerif-Italic.ttf" if italic else "InstrumentSerif-Regular.ttf", size)

def layer(L): return Image.new("RGBA", (L["W"], L["H"]), (0, 0, 0, 0))

def radial_alpha(size, stops):
    c = (size - 1) / 2
    yy, xx = np.mgrid[0:size, 0:size]
    r = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / (size / 2)
    xs = [s[0] for s in stops]; ys = [s[1] for s in stops]
    return np.clip(np.interp(r.ravel(), xs, ys).reshape(size, size), 0, 1)

# ----------------------------- static sprites (format-dependent) -----
def build_base(L):
    W, H = L["W"], L["H"]
    c = np.array([(W - 1) / 2, H * 0.42])
    yy, xx = np.mgrid[0:H, 0:W]
    maxd = math.hypot(max(c[0], W - c[0]), max(c[1], H - c[1]))
    r = np.sqrt((xx - c[0]) ** 2 + (yy - c[1]) ** 2) / maxd
    base = np.zeros((H, W, 3), float)
    for i in range(3):
        base[..., i] = np.interp(r.ravel(), [0, 0.46, 1],
            [BG_LIFT[i], BG[i], BG_DEEP[i]]).reshape(H, W)
    blob = Image.new("RGBA", (W, H), (0, 0, 0, 0)); bd = ImageDraw.Draw(blob)
    r1, r2 = 0.1875 * H, 0.1667 * H            # blob radii (fractions of height)
    bd.ellipse([0.111 * W - r1, 0.396 * H - r1, 0.111 * W + r1, 0.396 * H + r1],
               fill=(143, 165, 138, 50))
    bd.ellipse([0.907 * W - r2, 0.755 * H - r2, 0.907 * W + r2, 0.755 * H + r2],
               fill=(95, 116, 94, 45))
    blob = blob.filter(ImageFilter.GaussianBlur(int(95 * H / 1920)))
    bnp = np.asarray(blob, float)
    base += bnp[..., :3] * (bnp[..., 3:4] / 255.0) * 0.9
    vig = np.clip((r - 0.52) / (1 - 0.52), 0, 1) ** 1.4
    base *= (1 - 0.55 * vig[..., None])
    return np.clip(base, 0, 255)

def build_orb(L):
    ob = L["orb_base"]
    a = radial_alpha(ob, [(0, 0.85), (0.30, 0.5), (0.55, 0.18), (0.72, 0.03), (0.82, 0), (1, 0)])
    core = radial_alpha(ob, [(0, 0.45), (0.22, 0.12), (0.4, 0), (1, 0)])
    rgba = np.zeros((ob, ob, 4), np.uint8)
    for i in range(3):
        col = SAGE[i] * (1 - core) + np.array([232, 238, 226][i]) * core
        rgba[..., i] = np.clip(col, 0, 255).astype(np.uint8)
    rgba[..., 3] = (np.clip(a + core * 0.5, 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")

def build_glow(L):
    gb = L["glow_base"]
    return Image.fromarray(
        (radial_alpha(gb, [(0, 0.55), (0.62, 0), (1, 0)]) * 255).astype(np.uint8), "L")

def build_mist(L):
    cx, cy, sc = L["orb_cx"], L["orb_cy"], L["orb_base"] / 600.0
    base_sprite = radial_alpha(64, [(0, 0.9), (0.4, 0.45), (1, 0)])
    rng = np.random.RandomState(7); parts = []
    for _ in range(46):
        ang = rng.random() * math.tau; dist = (120 + rng.random() * 460) * sc
        size = max(8, int((26 + rng.random() * 70) * sc))
        spr = np.asarray(Image.fromarray((base_sprite * 255).astype(np.uint8), "L")
                         .resize((size, size), Image.BILINEAR), float) / 255.0
        parts.append(dict(x=cx + math.cos(ang) * dist * 0.9,
                          y=cy + math.sin(ang) * dist, spr=spr, size=size,
                          baseAlpha=0.04 + rng.random() * 0.10,
                          wobAmp=(6 + rng.random() * 12) * sc, wobSpeed=0.2 + rng.random() * 0.5,
                          phase=rng.random() * math.tau, drift=0.1 + rng.random() * 0.25))
    return parts

def add_sprite(canvas, alpha2d, cx, cy, color, gain, W, H):
    ah, aw = alpha2d.shape
    x0, y0 = int(round(cx - aw / 2)), int(round(cy - ah / 2))
    cx0, cy0 = max(x0, 0), max(y0, 0); cx1, cy1 = min(x0 + aw, W), min(y0 + ah, H)
    if cx1 <= cx0 or cy1 <= cy0: return
    sub = alpha2d[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
    canvas[cy0:cy1, cx0:cx1, :] += (sub[..., None] * gain) * color

def build_assets(L):
    return dict(BASE=build_base(L), ORB_IMG=build_orb(L),
                GLOW_L=build_glow(L), MIST=build_mist(L))

# ----------------------------- text helpers --------------------------
def text_center(d, cx, y, text, fnt, fill, track=0, top=True):
    if track:
        w = sum(d.textlength(c, font=fnt) + track for c in text) - track
        x = cx - w / 2
        for c in text:
            d.text((x, y), c, font=fnt, fill=fill); x += d.textlength(c, font=fnt) + track
    else:
        d.text((cx, y), text, font=fnt, fill=fill, anchor="ma" if top else "mm")

def paste_alpha(dst, src, a):
    if a <= 0: return
    if a >= 1: dst.alpha_composite(src); return
    r, g, b, al = src.split(); al = al.point(lambda v: int(v * a))
    dst.alpha_composite(Image.merge("RGBA", (r, g, b, al)))

def wrap_mixed(d, cx, y, raw, size, max_w, line_h):
    """Centered serif title; |...| spans (one or more words) are italic + sage."""
    reg, ital = serif(size), serif(size, True)
    toks, italic = [], False
    for w in raw.split(" "):
        starts, ends = w.startswith("|"), w.endswith("|")
        clean = w.strip("|"); cur = italic or starts
        toks.append((clean, ital if cur else reg, SAGE_T if cur else OFF))
        if starts and not ends: italic = True
        if ends: italic = False
    space = d.textlength(" ", font=reg)
    lines, curl, cw = [], [], 0
    for tk in toks:
        tw = d.textlength(tk[0], font=tk[1]); add = tw if not curl else space + tw
        if curl and cw + add > max_w:
            lines.append(curl); curl = [tk]; cw = tw
        else:
            curl.append(tk); cw += add
    if curl: lines.append(curl)
    yy = y
    for line in lines:
        tw = sum(d.textlength(t[0], font=t[1]) for t in line) + space * (len(line) - 1)
        x = cx - tw / 2
        for i, (txt, fnt, fill) in enumerate(line):
            if i: x += space
            d.text((x, yy), txt, font=fnt, fill=fill); x += d.textlength(txt, font=fnt)
        yy += line_h
    return yy

# which brand pillar a video belongs to -> highlighted in the brand line
PILLARS = ["RELAX", "RETRAIN", "RELEASE"]
CATEGORY_INDEX = {"relax": 0, "retrain": 1, "release": 2}
PILLAR_DIM = (120, 114, 104)        # the two inactive pillars

def tracked_segments(d, cx, cy, segments, track):
    """Render coloured segments [(text, font, fill), ...] as one centered, tracked line."""
    total = -track
    for text, fnt, _ in segments:
        total += sum(d.textlength(c, font=fnt) + track for c in text)
    x = cx - total / 2
    for text, fnt, fill in segments:
        for c in text:
            d.text((x, cy), c, font=fnt, fill=fill); x += d.textlength(c, font=fnt) + track

def brand_pillars(d, cx, cy, category, size, track):
    """RELAX. RETRAIN. RELEASE. with this video's pillar lit (clay) and the rest dimmed."""
    active = CATEGORY_INDEX.get(category, 0)
    on, off = manrope(size, 700), manrope(size, 400)
    segs = []
    for i, word in enumerate(PILLARS):
        if i:
            segs.append((". ", off, PILLAR_DIM))
        segs.append((word, on, CLAY) if i == active else (word, off, PILLAR_DIM))
    segs.append((".", off, PILLAR_DIM))
    tracked_segments(d, cx, cy, segs, track)

def build_static_text(flow, L):
    img = layer(L); d = ImageDraw.Draw(img); W = L["W"]
    text_center(d, W // 2, L["eyebrow_y"], flow["reel"]["eyebrow"].upper(),
                manrope(L["eyebrow_size"], 600), OFF, track=L["eyebrow_track"])
    text_center(d, W // 2, L["sub_y"], flow["reel"]["sub"], manrope(L["sub_size"], 400), MUTED)
    text_center(d, W // 2, L["brand_y"], "The Breath Reset", serif(L["brand_size"]), OFF)
    brand_pillars(d, W // 2, L["brand_sub_y"], flow.get("category", "relax"),
                  L["brand_sub_size"], L["brand_sub_track"])
    return img

def build_cue(text, L):
    img = layer(L); d = ImageDraw.Draw(img)
    d.text((L["W"] // 2, L["cue_y"]), text, font=manrope(L["cue_size"], 300),
           fill=OFF, anchor="ma")
    return img

def draw_dots(d, total, active, L):
    r, gap, cy = L["dots_r"], L["dots_gap"], L["dots_cy"]
    tot = (2 * r) * total + gap * (total - 1)
    x0 = L["W"] // 2 - tot / 2 + r
    for i in range(total):
        cx = x0 + i * (2 * r + gap)
        if i < active:
            d.ellipse([cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1], fill=SAGE_T)
        else:
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=FAINT)

def build_endcard(flow, L):
    img = layer(L); d = ImageDraw.Draw(img); W = L["W"]
    s = L["end_scale"]; yy = L["end_y"]
    for line in flow["end"]["lines"]:
        d.text((W // 2, yy), line, font=serif(int(56 * s)), fill=OFF, anchor="mm")
        yy += int(78 * s)
    yy += int(36 * s)
    d.line([(W // 2 - 60, yy), (W // 2 + 60, yy)], fill=SAGE_DARK, width=2)
    yy += int(60 * s)
    d.text((W // 2, yy), "The Breath Reset", font=serif(int(80 * s)), fill=OFF, anchor="mm")
    yy += int(84 * s)
    d.text((W // 2, yy), flow["end"]["tagline"], font=serif(int(40 * s), italic=True),
           fill=SAGE_T, anchor="mm")
    yy += int(84 * s)
    f = manrope(int(28 * s), 400); words = flow["end"]["cta"].split(" "); lines = []; cur = ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) > L["end_cta_w"] and cur: lines.append(cur); cur = w
        else: cur = t
    lines.append(cur)
    for ln in lines:
        d.text((W // 2, yy), ln, font=f, fill=MUTED, anchor="mm"); yy += int(44 * s)
    return img

def build_intro(flow, L):
    """Title card for the long-form video: hook + simple how, brand-grounded."""
    img = layer(L); d = ImageDraw.Draw(img); W = L["W"]; cov = flow["cover"]
    text_center(d, W // 2, L["intro_eyebrow_y"], cov["eyebrow"].upper(),
                manrope(L["intro_eyebrow_size"], 700), CLAY, track=5)
    y = wrap_mixed(d, W // 2, L["intro_hook_y"], cov["hook"],
                   L["intro_hook_size"], L["intro_hook_w"], L["intro_hook_lh"])
    d.line([(W // 2 - 70, y + 34), (W // 2 + 70, y + 34)], fill=SAGE_DARK, width=2)
    sy = y + 92; n = len(cov["steps"])
    for i, step in enumerate(cov["steps"]):
        fill = OFF if i < n - 1 else MUTED
        d.text((W // 2, sy), step, font=manrope(L["intro_steps_size"], 500 if i < n - 1 else 400),
               fill=fill, anchor="ma")
        sy += L["intro_steps_size"] + 24
    brand_pillars(d, W // 2, L["brand_sub_y"], flow.get("category", "relax"),
                  L["brand_sub_size"], L["brand_sub_track"])
    return img

# ----------------------------- box path ------------------------------
def box_point(u, L):
    cx, cy, q = L["orb_cx"], L["orb_cy"], L["box_q"]
    pts = [(cx - q, cy + q), (cx - q, cy - q), (cx + q, cy - q), (cx + q, cy + q)]  # BL,TL,TR,BR
    seg = min(int(u * 4), 3); f = u * 4 - seg
    a, b = pts[seg], pts[(seg + 1) % 4]
    return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f

# ----------------------------- render a flow -------------------------
def render_flow(fid, flow, fmt_name, fmt, L, assets):
    W, H = L["W"], L["H"]
    slug = flow["slug"]
    total = fmt["dur"] or flow["total"]
    endCard = fmt["endCard"] if fmt["endCard"] is not None else flow["endCard"]
    intro_sec = fmt.get("intro", 0); intro_fade = 1.5
    end_at = total - endCard; end_fade = 1.3
    cyc = cycle_len(flow)
    nframes = int(total * FPS)
    omin, omax = flow["orbMin"], flow["orbMax"]
    is_box = flow.get("box", False)
    settle = flow.get("settleDown", False)
    cx, cy = L["orb_cx"], L["orb_cy"]
    orb_base, glow_base = L["orb_base"], L["glow_base"]
    arc_r, box_q = L["arc_r"], L["box_q"]
    box_scl = box_q / 330.0

    BASE = assets["BASE"]; ORB_IMG = assets["ORB_IMG"]
    GLOW_L = assets["GLOW_L"]; MIST = assets["MIST"]

    text_static = build_static_text(flow, L)
    cues = {p["label"]: build_cue(p["label"], L) for p in flow["phases"]}
    bg_end = Image.fromarray(np.clip(BASE, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    bg_end.alpha_composite(build_endcard(flow, L))
    bg_end_np = np.asarray(bg_end.convert("RGB"), float)

    bg_intro_np = None
    if intro_sec:
        bg_intro = Image.fromarray(np.clip(BASE, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
        bg_intro.alpha_composite(build_intro(flow, L))
        bg_intro_np = np.asarray(bg_intro.convert("RGB"), float)

    sub1, sub2 = fmt["out"]
    out_dir = os.path.join(ROOT, "assets", "social", sub1, sub2, slug)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, fmt["name"])
    if TEST:
        out = os.path.join(HERE, f"test_{fmt_name}_{slug}.mp4")
        cand = [0, (int(intro_sec * FPS) + 12) if intro_sec else int(cyc * FPS) - 2,
                nframes // 2, nframes - 60, nframes - 20]
        frame_iter = sorted({f for f in cand if 0 <= f < nframes})
        writer = imageio_ffmpeg.write_frames(out, (W, H), fps=FPS, codec="libx264",
            macro_block_size=1, pix_fmt_in="rgb24", pix_fmt_out="yuv420p",
            output_params=["-crf", "20"], ffmpeg_log_level="error")
    else:
        master = os.path.join(HERE, fmt["master"].format(slug=slug))
        writer = imageio_ffmpeg.write_frames(out, (W, H), fps=FPS, codec="libx264",
            macro_block_size=1, pix_fmt_in="rgb24", pix_fmt_out="yuv420p",
            audio_path=master, audio_codec="aac",
            output_params=["-crf", "18", "-preset", "medium", "-movflags", "+faststart"],
            ffmpeg_log_level="error")
        frame_iter = range(nframes)
    writer.send(None)

    print(f"  [{fmt_name}] {slug}: {nframes} frames ({total}s) {W}x{H} -> {os.path.relpath(out, ROOT)}")
    for fi in frame_iter:
        t = fi / FPS
        phase, idx, el, p = phase_at(flow, t)
        is_hold = phase["name"] == "hold"

        s = orb_scale_at(flow, t)
        b = (s - omin) / (omax - omin)
        if is_hold: b += 0.03 * math.sin(t * 1.6)
        b = max(0.0, min(1.0, b))

        # ---- additive canvas: base + glow + mist ----
        canv = BASE.copy()
        gd = int(glow_base * (0.82 + 0.26 * b))
        glow_a = np.asarray(GLOW_L.resize((gd, gd), Image.BILINEAR), float) / 255.0
        add_sprite(canv, glow_a, cx, cy, SAGE, 0.22 + 0.60 * b, W, H)
        for pt in MIST:
            wob = math.sin(t * pt["wobSpeed"] + pt["phase"]) * pt["wobAmp"]
            slow = ((t * pt["drift"] * 30) % 80) - 40
            y = pt["y"] - b * 70 + slow + ((1 - b) * 42 if settle else 0)
            add_sprite(canv, pt["spr"], pt["x"] + wob, y, SAGE_LT,
                       pt["baseAlpha"] * (0.35 + 0.65 * b), W, H)
        breath = Image.fromarray(np.clip(canv, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

        # ---- mid: rings + (arc OR box) + orb ----
        mid = layer(L); d = ImageDraw.Draw(mid)
        for frac, base_op, sc0, sc1, addop in [(1.12, 0.10, 0.92, 0.16, 0.32),
                                               (1.34, 0.06, 0.90, 0.18, 0.22),
                                               (1.60, 0.03, 0.88, 0.20, 0.14)]:
            rr = (orb_base / 2) * frac * (sc0 + sc1 * b)
            op = base_op + addop * b
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                      outline=(143, 165, 138, int(op * 255)), width=2)

        if is_box:
            d.rounded_rectangle([cx - box_q, cy - box_q, cx + box_q, cy + box_q],
                                radius=int(120 * box_scl), outline=(239, 231, 217, 26), width=2)
            u = (t % cyc) / cyc
            bx, by = box_point(u, L)
            cr = max(8, int(16 * box_scl)); ir = max(4, int(7 * box_scl))
            d.ellipse([bx - cr, by - cr, bx + cr, by + cr], fill=(143, 165, 138, 60))
            d.ellipse([bx - ir, by - ir, bx + ir, by + ir], fill=(168, 188, 162, 255))
        else:
            prog = min(t / total, 1.0)
            d.ellipse([cx - arc_r, cy - arc_r, cx + arc_r, cy + arc_r],
                      outline=(239, 231, 217, 18), width=3)
            if prog > 0:
                d.arc([cx - arc_r, cy - arc_r, cx + arc_r, cy + arc_r],
                      start=-90, end=-90 + 360 * prog, fill=(143, 165, 138, 217), width=4)

        od = int(orb_base * s)
        mid.alpha_composite(ORB_IMG.resize((od, od), Image.BILINEAR),
                            (cx - od // 2, cy - od // 2))
        breath.alpha_composite(mid)

        # ---- foreground: text + cue (crossfade) + dots ----
        fg = text_static.copy()
        new_a = min(1.0, el / CUE_FADE)
        is_first = t < flow["phases"][0]["dur"]
        prev_label = flow["phases"][idx - 1]["label"]
        cur_label = phase["label"]
        paste_alpha(fg, cues[cur_label], new_a)
        if not is_first and prev_label != cur_label:
            paste_alpha(fg, cues[prev_label], max(0.0, 1 - el / CUE_FADE))
        active = min(int(el) + 1, phase["dots"])
        draw_dots(ImageDraw.Draw(fg), phase["dots"], active, L)
        breath.alpha_composite(fg)

        frame = np.asarray(breath.convert("RGB"), float)
        # intro title card holds, then crossfades out to reveal the breathing
        if intro_sec and t < intro_sec + intro_fade:
            a = 1.0 if t < intro_sec else 1 - (t - intro_sec) / intro_fade
            frame = bg_intro_np * a + frame * (1 - a)
        # end card crossfades in over the final endCard seconds
        if t >= end_at:
            cross = min((t - end_at) / end_fade, 1.0)
            frame = frame * (1 - cross) + bg_end_np * cross

        out_u8 = np.clip(frame, 0, 255).astype(np.uint8)
        writer.send(out_u8.tobytes())
        if TEST:
            Image.fromarray(out_u8, "RGB").save(
                os.path.join(HERE, f"frame_{fmt_name}_{slug}_{fi:05d}.png"))
            print(f"    frame {fi} (t={t:.1f}s)")
        elif fi % 300 == 0:
            print(f"    {fi:5d}/{nframes} ({t:6.1f}s)")
    writer.close()
    print("  done ->", out)

# ----------------------------- shorts (copy of the reel) -------------
def copy_shorts(ids):
    src_root = os.path.join(ROOT, "assets", "social", "instagram", "practices")
    dst_root = os.path.join(ROOT, "assets", "social", "youtube", "shorts")
    print("Copying YouTube Shorts from the reels...")
    for fid in ids:
        slug = FLOWS[fid]["slug"]
        sd, dd = os.path.join(src_root, slug), os.path.join(dst_root, slug)
        os.makedirs(dd, exist_ok=True)
        for fn in ("reel.mp4", "cover.png"):
            sp = os.path.join(sd, fn)
            if os.path.exists(sp):
                shutil.copy2(sp, os.path.join(dd, fn))
                print("  ->", os.path.relpath(os.path.join(dd, fn), ROOT))
            else:
                print(f"  (skip, missing {os.path.relpath(sp, ROOT)})")

# ----------------------------- main ----------------------------------
def main():
    fmt_names = [FMT_ONLY] if FMT_ONLY else list(FORMATS.keys())
    ids = [ONLY] if ONLY else list(FLOWS.keys())
    for fmt_name in fmt_names:
        fmt = FORMATS[fmt_name]
        print(f"Format {fmt_name} ({fmt['W']}x{fmt['H']}) — precomputing sprites...")
        L = make_layout(fmt); assets = build_assets(L)
        for fid in ids:
            render_flow(fid, FLOWS[fid], fmt_name, fmt, L, assets)
    # Shorts reuse the 9:16 reels verbatim
    if not TEST and (not FMT_ONLY or FMT_ONLY == "reel"):
        copy_shorts(ids)
    print("All done.")

if __name__ == "__main__":
    main()
