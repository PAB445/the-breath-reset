#!/usr/bin/env python3
"""
Render every Breath Reset flow to a 1080x1920 MP4 with audio.
Mirrors breathing-reel/ exactly (orb, glow, mist, rings, progress arc OR box
path, cue, dots, brand, end card). Output is ready for Instagram / CapCut.

Run:   python3 tmp/render_reel.py              (renders all flows)
       REEL_FLOW=boxBreathing python3 ...      (single flow)
       REEL_TEST=1 REEL_FLOW=boxBreathing ...  (a few sample frames + PNGs)
Out:   assets/social/instagram/practices/<slug>/reel.mp4
"""
import os, sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flows import FLOWS, cycle_len, phase_at, orb_scale_at, ease_in_out

W, H = 1080, 1920
FPS  = 30
TEST = os.environ.get("REEL_TEST") == "1"
ONLY = os.environ.get("REEL_FLOW")           # render just one flow id if set

# palette
BG, BG_LIFT, BG_DEEP = (16, 13, 11), (26, 21, 18), (10, 8, 7)
SAGE    = np.array([143, 165, 138], float)
SAGE_T  = (143, 165, 138)
SAGE_LT = np.array([193, 205, 186], float)
OFF, MUTED, FAINT = (239, 231, 217), (172, 164, 150), (60, 57, 52)

# layout
ORB_CX, ORB_CY = 540, 880
ORB_BASE = 600
GLOW_BASE = 900
ARC_R = 315
BOX_Q = 330                  # box square half-size (px), sits outside the orb
CUE_FADE = 0.6

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONTS = os.path.join(ROOT, "breathing-reel", "fonts")
PRACTICES = os.path.join(ROOT, "assets", "social", "instagram", "practices")

def font(name, size): return ImageFont.truetype(os.path.join(FONTS, name), size)
def manrope(size, weight=600):
    f = font("Manrope.ttf", size)
    try: f.set_variation_by_axes([weight])
    except Exception: pass
    return f
def serif(size, italic=False):
    return font("InstrumentSerif-Italic.ttf" if italic else "InstrumentSerif-Regular.ttf", size)

def radial_alpha(size, stops):
    c = (size - 1) / 2
    yy, xx = np.mgrid[0:size, 0:size]
    r = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / (size / 2)
    xs = [s[0] for s in stops]; ys = [s[1] for s in stops]
    return np.clip(np.interp(r.ravel(), xs, ys).reshape(size, size), 0, 1)

def layer(): return Image.new("RGBA", (W, H), (0, 0, 0, 0))

# ----------------------------- static sprites (flow-independent) -----
def build_base():
    c = np.array([(W - 1) / 2, H * 0.42])
    yy, xx = np.mgrid[0:H, 0:W]
    maxd = math.hypot(max(c[0], W - c[0]), max(c[1], H - c[1]))
    r = np.sqrt((xx - c[0]) ** 2 + (yy - c[1]) ** 2) / maxd
    base = np.zeros((H, W, 3), float)
    for i in range(3):
        base[..., i] = np.interp(r.ravel(), [0, 0.46, 1],
            [BG_LIFT[i], BG[i], BG_DEEP[i]]).reshape(H, W)
    blob = Image.new("RGBA", (W, H), (0, 0, 0, 0)); bd = ImageDraw.Draw(blob)
    bd.ellipse([120 - 360, 760 - 360, 120 + 360, 760 + 360], fill=(143, 165, 138, 50))
    bd.ellipse([980 - 320, 1450 - 320, 980 + 320, 1450 + 320], fill=(95, 116, 94, 45))
    blob = blob.filter(ImageFilter.GaussianBlur(95)); bnp = np.asarray(blob, float)
    base += bnp[..., :3] * (bnp[..., 3:4] / 255.0) * 0.9
    vig = np.clip((r - 0.52) / (1 - 0.52), 0, 1) ** 1.4
    base *= (1 - 0.55 * vig[..., None])
    return np.clip(base, 0, 255)

def build_orb():
    a = radial_alpha(ORB_BASE, [(0, 0.85), (0.30, 0.5), (0.55, 0.18), (0.72, 0.03), (0.82, 0), (1, 0)])
    core = radial_alpha(ORB_BASE, [(0, 0.45), (0.22, 0.12), (0.4, 0), (1, 0)])
    rgba = np.zeros((ORB_BASE, ORB_BASE, 4), np.uint8)
    for i in range(3):
        col = SAGE[i] * (1 - core) + np.array([232, 238, 226][i]) * core
        rgba[..., i] = np.clip(col, 0, 255).astype(np.uint8)
    rgba[..., 3] = (np.clip(a + core * 0.5, 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")

GLOW_L = Image.fromarray(
    (radial_alpha(GLOW_BASE, [(0, 0.55), (0.62, 0), (1, 0)]) * 255).astype(np.uint8), "L")

def build_mist():
    base_sprite = radial_alpha(64, [(0, 0.9), (0.4, 0.45), (1, 0)])
    rng = np.random.RandomState(7); parts = []
    for _ in range(46):
        ang = rng.random() * math.tau; dist = 120 + rng.random() * 460
        size = int(26 + rng.random() * 70)
        spr = np.asarray(Image.fromarray((base_sprite * 255).astype(np.uint8), "L")
                         .resize((size, size), Image.BILINEAR), float) / 255.0
        parts.append(dict(x=ORB_CX + math.cos(ang) * dist * 0.9,
                          y=ORB_CY + math.sin(ang) * dist, spr=spr, size=size,
                          baseAlpha=0.04 + rng.random() * 0.10,
                          wobAmp=6 + rng.random() * 12, wobSpeed=0.2 + rng.random() * 0.5,
                          phase=rng.random() * math.tau, drift=0.1 + rng.random() * 0.25))
    return parts

def add_sprite(canvas, alpha2d, cx, cy, color, gain):
    ah, aw = alpha2d.shape
    x0, y0 = int(round(cx - aw / 2)), int(round(cy - ah / 2))
    cx0, cy0 = max(x0, 0), max(y0, 0); cx1, cy1 = min(x0 + aw, W), min(y0 + ah, H)
    if cx1 <= cx0 or cy1 <= cy0: return
    sub = alpha2d[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
    canvas[cy0:cy1, cx0:cx1, :] += (sub[..., None] * gain) * color

print("Precomputing shared sprites...")
BASE = build_base()
ORB_IMG = build_orb()
MIST = build_mist()

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

def build_static_text(flow):
    img = layer(); d = ImageDraw.Draw(img)
    text_center(d, W // 2, 150, flow["reel"]["eyebrow"].upper(), manrope(26, 600), OFF, track=10)
    text_center(d, W // 2, 205, flow["reel"]["sub"], manrope(24, 400), MUTED)
    text_center(d, W // 2, 1690, "The Breath Reset", serif(46), OFF)
    text_center(d, W // 2, 1756, "RELAX. RETRAIN. RELEASE.", manrope(22, 400), MUTED, track=4)
    return img

def build_cue(text):
    img = layer(); d = ImageDraw.Draw(img)
    d.text((W // 2, 1360), text, font=manrope(60, 300), fill=OFF, anchor="ma")
    return img

def draw_dots(d, total, active):
    r, gap = 7, 36
    tot = (2 * r) * total + gap * (total - 1)
    x0 = W // 2 - tot / 2 + r; cy = 1470
    for i in range(total):
        cx = x0 + i * (2 * r + gap)
        if i < active:
            d.ellipse([cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1], fill=SAGE_T)
        else:
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=FAINT)

def build_endcard(flow):
    img = layer(); d = ImageDraw.Draw(img)
    yy = 712
    for line in flow["end"]["lines"]:
        d.text((W // 2, yy), line, font=serif(56), fill=OFF, anchor="mm"); yy += 78
    yy += 36
    d.line([(W // 2 - 60, yy), (W // 2 + 60, yy)], fill=(95, 116, 94), width=2); yy += 60
    d.text((W // 2, yy), "The Breath Reset", font=serif(80), fill=OFF, anchor="mm"); yy += 84
    d.text((W // 2, yy), flow["end"]["tagline"], font=serif(40, italic=True), fill=SAGE_T, anchor="mm")
    yy += 84
    f = manrope(28, 400); words = flow["end"]["cta"].split(" "); lines = []; cur = ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) > 720 and cur: lines.append(cur); cur = w
        else: cur = t
    lines.append(cur)
    for ln in lines:
        d.text((W // 2, yy), ln, font=f, fill=MUTED, anchor="mm"); yy += 44
    return img

# ----------------------------- box path ------------------------------
def box_point(u, q=BOX_Q):
    pts = [(ORB_CX - q, ORB_CY + q), (ORB_CX - q, ORB_CY - q),
           (ORB_CX + q, ORB_CY - q), (ORB_CX + q, ORB_CY + q)]   # BL,TL,TR,BR
    seg = min(int(u * 4), 3); f = u * 4 - seg
    a, b = pts[seg], pts[(seg + 1) % 4]
    return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f

# ----------------------------- render a flow -------------------------
def render_flow(fid, flow):
    slug = flow["slug"]
    total = flow["total"]; end_at = total - flow["endCard"]; end_fade = 1.3
    cyc = cycle_len(flow)
    nframes = int(total * FPS)
    omin, omax = flow["orbMin"], flow["orbMax"]
    is_box = flow.get("box", False)
    settle = flow.get("settleDown", False)

    text_static = build_static_text(flow)
    cues = {p["label"]: build_cue(p["label"]) for p in flow["phases"]}
    endcard = build_endcard(flow)
    bg_end = Image.fromarray(np.clip(BASE, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    bg_end.alpha_composite(endcard)
    bg_end_np = np.asarray(bg_end.convert("RGB"), float)

    out_dir = os.path.join(PRACTICES, slug)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "reel.mp4")
    if TEST:
        out = os.path.join(HERE, f"reel_test_{slug}.mp4")
        frame_iter = [0, int(cyc * FPS) - 2, nframes - 60, nframes - 20]
        writer = imageio_ffmpeg.write_frames(out, (W, H), fps=FPS, codec="libx264",
            macro_block_size=1, pix_fmt_in="rgb24", pix_fmt_out="yuv420p",
            output_params=["-crf", "20"], ffmpeg_log_level="error")
    else:
        master = os.path.join(HERE, f"master-{slug}.wav")
        writer = imageio_ffmpeg.write_frames(out, (W, H), fps=FPS, codec="libx264",
            macro_block_size=1, pix_fmt_in="rgb24", pix_fmt_out="yuv420p",
            audio_path=master, audio_codec="aac",
            output_params=["-crf", "18", "-preset", "medium", "-movflags", "+faststart"],
            ffmpeg_log_level="error")
        frame_iter = range(nframes)
    writer.send(None)

    print(f"  rendering {slug}: {nframes} frames ({total}s) -> {os.path.relpath(out, ROOT)}")
    for fi in frame_iter:
        t = fi / FPS
        phase, idx, el, p = phase_at(flow, t)
        is_hold = phase["name"] == "hold"

        # orb scale tied to phase progress; b normalised for glow/rings
        s = orb_scale_at(flow, t)
        b = (s - omin) / (omax - omin)
        if is_hold: b += 0.03 * math.sin(t * 1.6)
        b = max(0.0, min(1.0, b))

        # ---- additive canvas: base + glow + mist ----
        canv = BASE.copy()
        gd = int(GLOW_BASE * (0.82 + 0.26 * b))
        glow_a = np.asarray(GLOW_L.resize((gd, gd), Image.BILINEAR), float) / 255.0
        add_sprite(canv, glow_a, ORB_CX, ORB_CY, SAGE, 0.22 + 0.60 * b)
        for pt in MIST:
            wob = math.sin(t * pt["wobSpeed"] + pt["phase"]) * pt["wobAmp"]
            slow = ((t * pt["drift"] * 30) % 80) - 40
            y = pt["y"] - b * 70 + slow + ((1 - b) * 42 if settle else 0)
            add_sprite(canv, pt["spr"], pt["x"] + wob, y, SAGE_LT,
                       pt["baseAlpha"] * (0.35 + 0.65 * b))
        breath = Image.fromarray(np.clip(canv, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

        # ---- mid: rings + (arc OR box) + orb ----
        mid = layer(); d = ImageDraw.Draw(mid)
        for frac, base_op, sc0, sc1, addop in [(1.12, 0.10, 0.92, 0.16, 0.32),
                                               (1.34, 0.06, 0.90, 0.18, 0.22),
                                               (1.60, 0.03, 0.88, 0.20, 0.14)]:
            rr = (ORB_BASE / 2) * frac * (sc0 + sc1 * b)
            op = base_op + addop * b
            d.ellipse([ORB_CX - rr, ORB_CY - rr, ORB_CX + rr, ORB_CY + rr],
                      outline=(143, 165, 138, int(op * 255)), width=2)

        if is_box:
            # soft rounded-square track + travelling comet (one lap per cycle)
            d.rounded_rectangle([ORB_CX - BOX_Q, ORB_CY - BOX_Q, ORB_CX + BOX_Q, ORB_CY + BOX_Q],
                                radius=120, outline=(239, 231, 217, 26), width=2)
            u = (t % cyc) / cyc
            bx, by = box_point(u)
            d.ellipse([bx - 16, by - 16, bx + 16, by + 16], fill=(143, 165, 138, 60))
            d.ellipse([bx - 7, by - 7, bx + 7, by + 7], fill=(168, 188, 162, 255))
        else:
            prog = min(t / total, 1.0)
            d.ellipse([ORB_CX - ARC_R, ORB_CY - ARC_R, ORB_CX + ARC_R, ORB_CY + ARC_R],
                      outline=(239, 231, 217, 18), width=3)
            if prog > 0:
                d.arc([ORB_CX - ARC_R, ORB_CY - ARC_R, ORB_CX + ARC_R, ORB_CY + ARC_R],
                      start=-90, end=-90 + 360 * prog, fill=(143, 165, 138, 217), width=4)

        od = int(ORB_BASE * s)
        mid.alpha_composite(ORB_IMG.resize((od, od), Image.BILINEAR),
                            (ORB_CX - od // 2, ORB_CY - od // 2))
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
        draw_dots(ImageDraw.Draw(fg), phase["dots"], active)
        breath.alpha_composite(fg)

        breath_np = np.asarray(breath.convert("RGB"), float)
        cross = min((t - end_at) / end_fade, 1.0) if t >= end_at else 0.0
        frame = breath_np if cross <= 0 else breath_np * (1 - cross) + bg_end_np * cross

        out_u8 = np.clip(frame, 0, 255).astype(np.uint8)
        writer.send(out_u8.tobytes())
        if TEST:
            Image.fromarray(out_u8, "RGB").save(os.path.join(HERE, f"frame_{slug}_{fi:04d}.png"))
            print(f"    frame {fi} (t={t:.1f}s)")
        elif fi % 300 == 0:
            print(f"    {fi:4d}/{nframes} ({t:5.1f}s)")
    writer.close()
    print("  done ->", out)

# ----------------------------- main ----------------------------------
ids = [ONLY] if ONLY else list(FLOWS.keys())
for fid in ids:
    render_flow(fid, FLOWS[fid])
print("All done.")
