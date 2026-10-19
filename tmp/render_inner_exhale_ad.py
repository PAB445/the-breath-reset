#!/usr/bin/env python3
"""
The Inner Exhale — 15s silent 9:16 video, in two cuts that differ only in
the end-card CTA:

  story  "Tickets on Eventbrite ↓" above an empty band for a link sticker
  reel   the sage "Tickets via Eventbrite · Link in bio" pill, sat a little
         lower to give it room under the details panel

  0–0.8s   orb fades up in the middle of the frame
  0.8–4s   inhale: orb swells, "Breathe in…"
  4.4–7.6s exhale: orb softens and drifts up into its poster position,
           "…and let it go", rings ripple out
  7–10.6s  title, then each block of the poster rises in
  to 15s   end card holds while the orb keeps breathing gently

In the story cut the bottom of the frame (STICKER_ZONE) is left empty for an
Instagram link sticker pointing at Eventbrite; nothing is ever drawn there.

Layout and copy come from make_event_inner_exhale.py (EVENT, draw_layers).

  python3 tmp/render_inner_exhale_ad.py              # render both cuts
  python3 tmp/render_inner_exhale_ad.py reel         # just one
  AD_STILLS=1 python3 tmp/render_inner_exhale_ad.py  # check frames only

Outputs -> assets/social/instagram/events/inner-exhale/
  story.mp4, ad-sticker-guide.png, reel.mp4
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

from make_event_inner_exhale import (BG, BG_DEEP, BG_LIFT, OFF, OUT, ROOT, SAGE,
                                     WARMWHITE, add_radial, draw_layers,
                                     radial_alpha, serif)

W, H, FPS, DUR = 1080, 1920, 30, 15.0
CX = W / 2

# Final poster layout: tighter than the static story so the link sticker fits
# between the CTA prompt and the reply bar.
AD = dict(pad=80, brand_y=200, title=140, title_y=640,
          kicker_y=818, body=33, body_w=860, body_lh=50,
          pillars_y=1170, panel_y=1345, panel_h=180, cta_y=1537)
STICKER_ZONE = (180, 1610, 900, 1745)

ORB_START_CY, ORB_END_CY = 880, 450
R_START, R_FULL, R_END = 300, 470, 290
T_IN0, T_IN1, T_OUT0, T_OUT1 = 0.8, 4.0, 4.4, 7.6

PROMPTS = [("Breathe in…", 0.9, 3.9), ("…and let it go", 4.6, 7.0)]
PROMPT_Y = 1390

REVEAL = {"title": 7.0, "brand": 7.4, "kicker": 7.9, "blurb": 8.4,
          "pillars": 8.9, "panel": 9.4, "cta": 9.9}
REVEAL_DUR, REVEAL_RISE = 0.7, 22


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def ramp(t, t0, dur):
    return ease((t - t0) / dur)


# ---------------------------------------------------------------- orb state
def orb_state(t):
    """(centre y, body diameter, breath fullness 0..1)."""
    if t < T_IN0:
        return ORB_START_CY, R_START, 0.0
    if t < T_IN1:
        b = ramp(t, T_IN0, T_IN1 - T_IN0)
        return ORB_START_CY, R_START + (R_FULL - R_START) * b, b
    if t < T_OUT0:
        return ORB_START_CY, R_FULL, 1.0
    if t < T_OUT1:
        u = ramp(t, T_OUT0, T_OUT1 - T_OUT0)
        cy = ORB_START_CY + (ORB_END_CY - ORB_START_CY) * u
        return cy, R_FULL + (R_END - R_FULL) * u, 1.0 - u
    idle = (1 - math.cos(2 * math.pi * (t - T_OUT1) / 6.0)) / 2
    return ORB_END_CY, R_END * (1 + 0.06 * idle), 0.25 * idle


# ------------------------------------------------------------ static pieces
def base_canvas():
    c = np.array([W / 2, H * 0.36])
    yy, xx = np.mgrid[0:H, 0:W]
    maxd = np.hypot(max(c[0], W - c[0]), max(c[1], H - c[1]))
    r = np.sqrt((xx - c[0]) ** 2 + (yy - c[1]) ** 2) / maxd
    canv = np.zeros((H, W, 3), np.float32)
    for i in range(3):
        canv[..., i] = np.interp(r.ravel(), [0, 0.46, 1],
                                 [BG_LIFT[i], BG[i], BG_DEEP[i]]).reshape(H, W)
    r2 = np.sqrt((xx - W / 2) ** 2 + (yy - H / 2) ** 2) / np.hypot(W / 2, H / 2)
    vig = (1 - 0.5 * np.clip((r2 - 0.52) / 0.48, 0, 1) ** 1.5)[..., None]
    return canv, vig.astype(np.float32)


GLOW = radial_alpha(int(R_FULL * 3), [(0, 0.55), (0.6, 0), (1, 0)])
BODY = radial_alpha(R_FULL, [(0, 0.85), (0.3, 0.5), (0.55, 0.2),
                             (0.72, 0.04), (0.82, 0), (1, 0)])
CORE = radial_alpha(int(R_FULL * 0.7), [(0, 0.6), (0.3, 0.14), (0.5, 0), (1, 0)])


def scaled(a2d, s):
    n = max(int(a2d.shape[0] * s), 2)
    return np.asarray(Image.fromarray(a2d.astype(np.float32))
                      .resize((n, n), Image.BILINEAR))


def cropped(im):
    box = im.getbbox()
    return im.crop(box), box[:2]


def fade_alpha(im, a):
    if a >= 0.999:
        return im
    out = im.copy()
    out.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    return out


def prompt_layer(text):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((CX, PROMPT_Y), text, font=serif(76, it=True),
                            fill=OFF, anchor="mm")
    return cropped(im)


# --------------------------------------------------------------- one frame
def frame(t, ctx):
    cy, r, b = orb_state(t)
    canv = ctx["base"].copy()
    s = r / R_FULL
    add_radial(canv, CX, cy, scaled(GLOW, s), SAGE, 0.46 + 0.18 * b)
    add_radial(canv, CX, cy, scaled(BODY, s), SAGE, 0.85)
    add_radial(canv, CX, cy, scaled(CORE, s), WARMWHITE, 0.74 + 0.2 * b)
    canv *= ctx["vig"]
    canv += ctx["grain"]
    canv *= ramp(t, 0.0, 0.6)
    img = Image.fromarray(np.clip(canv, 0, 255).astype(np.uint8)).convert("RGBA")

    rings = ramp(t, 6.8, 1.2)
    ripple = (t - 7.2) / 2.2
    if rings > 0 or 0 < ripple < 1:
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        for mult, op in [(1.22, 0.16), (1.5, 0.09), (1.82, 0.05)]:
            rr = r / 2 * mult
            d.ellipse([CX - rr, cy - rr, CX + rr, cy + rr],
                      outline=(143, 165, 138, int(op * 255 * rings)), width=2)
        if 0 < ripple < 1:
            rr = r / 2 * (1.0 + 2.4 * ease(ripple))
            d.ellipse([CX - rr, cy - rr, CX + rr, cy + rr],
                      outline=(143, 165, 138, int(70 * (1 - ripple))), width=2)
        img.alpha_composite(ov)

    for (im, (x, y)), (_, t0, t1) in zip(ctx["prompts"], PROMPTS):
        a = min(ramp(t, t0, 0.5), 1 - ramp(t, t1 - 0.5, 0.5))
        if a > 0:
            img.alpha_composite(fade_alpha(im, a), (x, y + int(10 * (1 - a))))

    for key, (im, (x, y)) in ctx["layers"]:
        a = ramp(t, REVEAL[key], REVEAL_DUR)
        if a > 0:
            img.alpha_composite(fade_alpha(im, a),
                                (x, y + int(REVEAL_RISE * (1 - a))))
    return img.convert("RGB")


CUTS = {
    "story": dict(layout=AD, cta_label="TICKETS ON EVENTBRITE   ↓", cta_pill=False),
    "reel":  dict(layout=dict(AD, cta_y=1580),
                  cta_label="TICKETS VIA EVENTBRITE  ·  LINK IN BIO", cta_pill=True),
}


def context(cut):
    base, vig = base_canvas()
    # Static grain: animated grain made the 15s file ~100MB.
    grain = (np.random.RandomState(11).randn(H, W, 1) * 6).astype(np.float32)
    c = CUTS[cut]
    layers = [(k, cropped(im)) for k, im in
              draw_layers(W, H, c["layout"], cta_label=c["cta_label"], cta_pill=c["cta_pill"])]
    return dict(base=base, vig=vig, grain=grain, layers=layers,
                prompts=[prompt_layer(p[0]) for p in PROMPTS])


def sticker_guide(ctx):
    img = frame(DUR - 1 / FPS, ctx).convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    x0, y0, x1, y1 = STICKER_ZONE
    for x in range(x0, x1, 24):
        d.line([(x, y0), (min(x + 12, x1), y0)], fill=(209, 144, 115, 230), width=3)
        d.line([(x, y1), (min(x + 12, x1), y1)], fill=(209, 144, 115, 230), width=3)
    for y in range(y0, y1, 24):
        d.line([(x0, y), (x0, min(y + 12, y1))], fill=(209, 144, 115, 230), width=3)
        d.line([(x1, y), (x1, min(y + 12, y1))], fill=(209, 144, 115, 230), width=3)
    d.text((CX, (y0 + y1) / 2), "link sticker here", font=serif(40, it=True),
           fill=(209, 144, 115, 230), anchor="mm")
    img.alpha_composite(ov)
    out = os.path.join(OUT, "ad-sticker-guide.png")
    img.convert("RGB").save(out)
    print("saved", os.path.relpath(out, ROOT))


def render(ctx, cut):
    out = os.path.join(OUT, f"{cut}.mp4")
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-profile:v", "high", "-pix_fmt", "yuv420p",
         "-color_primaries", "bt709", "-color_trc", "bt709",
         "-colorspace", "bt709", "-movflags", "+faststart", out],
        stdin=subprocess.PIPE)
    n = int(DUR * FPS)
    for i in range(n):
        proc.stdin.write(frame(i / FPS, ctx).tobytes())
        if i % 90 == 0:
            print(f"  frame {i}/{n}")
    proc.stdin.close()
    if proc.wait():
        raise SystemExit("ffmpeg failed")
    print("saved", os.path.relpath(out, ROOT))


if __name__ == "__main__":
    for cut in sys.argv[1:] or list(CUTS):
        ctx = context(cut)
        if os.environ.get("AD_STILLS"):
            d = os.path.join(ROOT, "tmp", "event-ad-frames")
            os.makedirs(d, exist_ok=True)
            for t in (0.5, 2.5, 4.2, 6.0, 7.6, 8.6, 10.6, 14.9):
                frame(t, ctx).save(os.path.join(d, f"{cut}-t{t:04.1f}.png"))
            print("stills in", os.path.relpath(d, ROOT))
        else:
            render(ctx, cut)
        if cut == "story":
            sticker_guide(ctx)
