#!/usr/bin/env python3
"""Crop + grade the Inner Exhale guiding photo for the site hero."""
import os
import numpy as np
from PIL import Image, ImageEnhance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "events", "inner-exhale", "inner-exhale-guiding.jpg")
OUT = os.path.join(ROOT, "assets", "photos", "hero-suraj-facilitating.jpg")
PREVIEW = os.path.join(ROOT, "tmp", "hero-preview.jpg")

src = Image.open(SRC).convert("RGB")
W, H = src.size

crop_w = int(H * 4 / 5)
cx = 620
x0 = max(0, min(cx - crop_w // 2, W - crop_w))
portrait = src.crop((x0, 0, x0 + crop_w, H))

out_w, out_h = 900, 1125
img = portrait.resize((out_w, out_h), Image.LANCZOS)
a = np.array(img, dtype=np.float32)

# Warm amber grade: ease magenta/blue cast
a[..., 0] = a[..., 0] * 1.05 + 5
a[..., 1] = a[..., 1] * 1.02 + 2
a[..., 2] = a[..., 2] * 0.90

y = np.linspace(0, 1, out_h, dtype=np.float32)[:, None]
x = np.linspace(0, 1, out_w, dtype=np.float32)[None, :]

# Soften the purple/blue lens-flare streak across the mid torso / arm.
# Magenta flare: blue high vs green, in a thin horizontal band.
purple = np.clip((a[..., 2] - a[..., 1]) / 28.0, 0, 1)
blueish = np.clip((a[..., 2] - a[..., 0] * 0.7) / 40.0, 0, 1)
band = np.exp(-0.5 * ((y - 0.49) / 0.07) ** 2)
horiz = np.exp(-0.5 * ((x - 0.45) / 0.42) ** 2)
flare = np.clip(np.maximum(purple, blueish) * band * horiz * 2.2, 0, 1)
# Paint the streak with neighbouring warm amber instead of blue
amber = a[..., 0] * 0.50 + a[..., 1] * 0.40 + 12
a[..., 2] = a[..., 2] * (1 - flare) + amber * flare
a[..., 0] = np.minimum(255, a[..., 0] + flare * 8)
a[..., 1] = np.minimum(255, a[..., 1] + flare * 4)

# Gentle face lift
face = np.exp(-(((x - 0.58) / 0.22) ** 2 + ((y - 0.22) / 0.18) ** 2))
a += face[..., None] * 14

# Soft vignette
r2 = np.sqrt(((x - 0.5) / 0.5) ** 2 + ((y - 0.5) / 0.5) ** 2)
vig = np.clip((r2 - 0.55) / 0.7, 0, 1) ** 1.4
a *= (1 - 0.20 * vig[..., None])

img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
img = ImageEnhance.Contrast(img).enhance(1.05)
img = ImageEnhance.Color(img).enhance(0.94)
img = ImageEnhance.Sharpness(img).enhance(1.08)

img.save(OUT, quality=90, optimize=True)
img.resize((360, 450)).save(PREVIEW, quality=85)
print("saved", OUT, img.size)
