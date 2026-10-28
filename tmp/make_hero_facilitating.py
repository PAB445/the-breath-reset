#!/usr/bin/env python3
"""
The Breath Reset — home hero photo: Suraj guiding a participant at The Inner Exhale.

Grades the photographer's frame towards the site's warm amber (out of the
red/magenta stage light), removes the blue lens flare across the chest,
lifts the face and adds a soft vignette around the portrait crop.

The output keeps the full landscape frame; the hero shows it as a 4:5 crop
on desktop and 5:4 on phones via object-position in styles.css.

    python3 tmp/make_hero_facilitating.py [path/to/full-res-original.jpg]
Output -> assets/photos/hero-suraj-facilitating.jpg
"""
import os
import sys
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, "assets", "events", "inner-exhale", "inner-exhale-guiding.jpg")
OUT = os.path.join(ROOT, "assets", "photos", "hero-suraj-facilitating.jpg")

# Positions are fractions of the frame so a full-res original lines up too.
FLARE = dict(x0=0.46, x1=0.90, y0=0.41, y1=0.51)   # band across chest + forearm
FACE = dict(cx=0.535, cy=0.30, r=0.15)
CROP_CX = 0.50                                     # centre of the 4:5 hero crop

def feather_box(H, W, x0, x1, y0, y1, soft):
    yy, xx = np.mgrid[0:H, 0:W]
    fx = np.clip(np.minimum(xx - x0 * W, x1 * W - xx) / (soft * W), 0, 1)
    fy = np.clip(np.minimum(yy - y0 * H, y1 * H - yy) / (soft * H), 0, 1)
    return (fx * fy)[..., None]

def radial(H, W, cx, cy, r):
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.hypot((xx - cx * W) / W, (yy - cy * H) / W) / r
    return np.clip(1 - d, 0, 1) ** 2

def main():
    img = Image.open(SRC).convert("RGB")
    a = np.asarray(img, float)
    H, W = a.shape[:2]
    R, G, B = a[..., 0], a[..., 1], a[..., 2]

    # 1. Lens flare: the flare only adds blue/violet, so cap blue against red.
    cap = 0.35 * R + 8
    deflared = a.copy()
    deflared[..., 2] = np.minimum(B, cap)
    m = feather_box(H, W, soft=0.03, **FLARE)
    a = a * (1 - m) + deflared * m

    # 2. Pull the magenta stage light towards amber.
    a[..., 0] *= 0.95
    a[..., 1] = a[..., 1] * 1.10 + 6
    a[..., 2] *= 0.92
    lum = (a @ np.array([0.299, 0.587, 0.114]))[..., None]
    a = lum + (a - lum) * 0.82

    # 3. Gentle filmic curve: lift shadows a touch, roll off highlights.
    x = np.clip(a / 255, 0, 1)
    x = 0.02 + 0.98 * x
    x = x + 0.55 * x * (1 - x) * (x - 0.42)
    a = x * 255

    # 4. Lift the face, then a soft vignette centred on the portrait crop.
    a *= 1 + 0.16 * radial(H, W, **FACE)[..., None]
    yy, xx = np.mgrid[0:H, 0:W]
    v = np.hypot((xx - CROP_CX * W) / (0.42 * W), (yy - 0.45 * H) / (0.75 * H))
    a *= (1 - 0.32 * np.clip(v - 0.55, 0, 1) ** 1.4)[..., None]

    out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    out = out.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=2))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.save(OUT, quality=88, optimize=True, progressive=True)
    print("saved", os.path.relpath(OUT, ROOT), out.size)

if __name__ == "__main__":
    main()
