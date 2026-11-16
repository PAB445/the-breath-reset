#!/usr/bin/env python3
"""
Breathe Light -- 90s Instagram reel, 1080x1920.

  tmp/.venv-dsp/bin/python tmp/make_breathe_light_variants.py reel   # audio first
  tmp/.venv-dsp/bin/python tmp/render_breathe_light_reel.py
  BL_STILLS=1 tmp/.venv-dsp/bin/python tmp/render_breathe_light_reel.py

The picture is the same lake, centre-cropped to 9:16 and scaled up. The score
and the voice come from breathe-light-edit.json in the reel folder.
"""
import json
import os
import subprocess
import sys
import time
from multiprocessing import Pool

import numpy as np
from PIL import Image

import render_breathe_light as R

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "assets", "social", "instagram", "practices", "breathe-light")
EDIT = json.load(open(os.path.join(OUT, "breathe-light-edit.json")))
MIX = os.path.join(OUT, "reel-mix.wav")
# the variant script names the mix with the long-film stem; accept either
if not os.path.exists(MIX):
    MIX = os.path.join(OUT, "breathe-light-mix.wav")
FINAL = os.path.join(OUT, "reel.mp4")
COVER = os.path.join(OUT, "cover.png")

PW, PH = 1080, 1920
FPS = 24
TOTAL = EDIT["total"]
N = int(round(TOTAL * FPS))
# Work larger than the delivery frame, then crop 9:16 and scale down, so the
# portrait picture is a downsample of the 5K plates rather than an upscale.
R.W, R.H = 3600, 2024
CROP_W = int(round(R.H * 9 / 16))

# A 90-second dawn: the mist thins and the light warms, same shape as the long film.
R.WARMTH = [(0, 0.02), (18, 0.08), (40, 0.28), (62, 0.55), (TOTAL, 0.78)]
R.MIST = [(0, 1.0), (24, 0.92), (50, 0.62), (TOTAL, 0.42)]
R.ZOOM = [(0, 1.02), (TOTAL, 1.075)]
R.PAN_X = [(0, 0.50), (TOTAL, 0.53)]
R.PAN_Y = [(0, 0.50), (TOTAL, 0.47)]


def blit(canvas, sprite, cx, cy, alpha):
    if alpha <= 0.004:
        return
    s = sprite
    if alpha < 0.996:
        s = s.copy()
        s.putalpha(s.getchannel("A").point(lambda v: int(v * alpha)))
    x, y = int(round(cx - s.width / 2)), int(round(cy - s.height / 2))
    canvas.alpha_composite(s, (max(0, x), max(0, y)), (max(0, -x), max(0, -y)))


def frame(A, t, index):
    img = R.landscape(A, t)
    title_a = R.env(t, *EDIT["title"], 1.4, 1.6)
    close_a = R.env(t, *EDIT["close"], 1.8, 0.4)
    label_a = max((R.env(t, lb["start"], lb["end"], 1.2, 1.4) for lb in EDIT["labels"]),
                  default=0.0)
    scrim = max(title_a, close_a)
    if scrim:
        img = img * (1 - 0.30 * scrim * A.card_scrim * A.sun_protect)
    if label_a:
        img = img * (1 - 0.32 * label_a * A.lower_scrim)
    img = img * A.vignette
    fade = R.smooth(t / 1.8) * R.smooth((TOTAL - t) / 2.2)
    img = img * fade
    wide = R.camera(img, t, R.W, R.H).convert("RGBA")
    x0 = (R.W - CROP_W) // 2
    pic = wide.crop((x0, 0, x0 + CROP_W, R.H)).resize((PW, PH), Image.LANCZOS)

    if title_a:
        blit(pic, R.caps("THE BREATH RESET", 26, 650, R.OFF, 0.42, 0.75),
             PW / 2, 760, title_a)
        blit(pic, R.rule(64), PW / 2, 820, title_a)
        blit(pic, R.line("Breathe Light", ("serif", 116, True), R.SAGE_BRIGHT, 0.45, 18),
             PW / 2, 930 + R.lift(t, EDIT["title"][0], 14, 1.8) * (PH / R.H), title_a)
    for lb in EDIT["labels"]:
        a = R.env(t, lb["start"], lb["end"], 1.2, 1.4)
        if a:
            blit(pic, R.rule(44), PW / 2, 1460, a * 0.9)
            blit(pic, R.caps(lb["name"], 40, 650, R.OFF, 0.5, 0.7),
                 PW / 2, 1530, a)
    if close_a:
        blit(pic, R.caps("THE BREATH RESET", 26, 650, R.OFF, 0.42, 0.75),
             PW / 2, 760, close_a)
        blit(pic, R.rule(64), PW / 2, 820, close_a)
        a2 = close_a * R.smooth((t - EDIT["close"][0] - 0.5) / 1.6)
        blit(pic, R.line(EDIT["close_line"], ("serif", 84, True), R.SAGE_BRIGHT, 0.45, 16),
             PW / 2, 940, a2)

    arr = np.asarray(pic.convert("RGB"), np.float32)
    g = np.asarray(Image.fromarray(A.grain[index % len(A.grain)]).resize((PW, PH), Image.BILINEAR))
    arr += g[..., None] * (1.6 * fade)
    return np.clip(arr + 0.5, 0, 255).astype(np.uint8)


_A = None


def _init():
    global _A
    _A = R.Assets()


def _chunk(args):
    ci, f0, f1, path = args
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{PW}x{PH}", "-r", str(FPS), "-i", "-",
         "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
         "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-tune", "grain",
         "-g", str(FPS * 4), "-bf", "2",
         "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         path], stdin=subprocess.PIPE)
    for i in range(f0, f1):
        enc.stdin.write(frame(_A, i / FPS, i).tobytes())
        if ci == 0 and (i - f0) % 120 == 0:
            print(f"  reel {i / N * 100:4.0f}%", flush=True)
    enc.stdin.close()
    enc.wait()
    return path


def render():
    tmp = os.path.join(HERE, "bl-chunks-reel")
    os.makedirs(tmp, exist_ok=True)
    workers = 7
    bounds = np.linspace(0, N, workers * 2 + 1).astype(int)
    jobs = [(i, bounds[i], bounds[i + 1], os.path.join(tmp, f"c{i:03d}.mp4"))
            for i in range(len(bounds) - 1)]
    t0 = time.time()
    with Pool(workers, initializer=_init) as pool:
        paths = pool.map(_chunk, jobs, chunksize=1)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{p}'\n" for p in paths)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-i", MIX, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                    "-t", f"{TOTAL:.3f}", "-movflags", "+faststart", FINAL], check=True)
    for p in paths:
        os.remove(p)
    print(f"saved {os.path.relpath(FINAL, ROOT)} ({os.path.getsize(FINAL) / 1e6:.0f} MB, "
          f"{time.time() - t0:.0f}s)")


def stills():
    A = R.Assets()
    times = [EDIT["title"][0] + 2.5, EDIT["labels"][0]["start"] + 2,
             EDIT["labels"][1]["start"] + 2, EDIT["close"][0] + 3]
    dest = os.path.join(HERE, "breathe-light-frames")
    os.makedirs(dest, exist_ok=True)
    for t in times:
        p = os.path.join(dest, f"reel-{t:05.1f}.jpg")
        Image.fromarray(frame(A, t, int(t * FPS))).save(p, quality=90)
        print("saved", os.path.relpath(p, ROOT))
    Image.fromarray(frame(A, EDIT["title"][0] + 2.5, 0)).save(COVER)
    print("saved", os.path.relpath(COVER, ROOT))


if __name__ == "__main__":
    if os.environ.get("BL_STILLS"):
        stills()
    else:
        render()
        stills()
