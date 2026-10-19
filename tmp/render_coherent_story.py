#!/usr/bin/env python3
"""
Coherent Breath Reset -- two-frame Instagram Story that supports the reel.

  Frame 1  story_intro.mp4 talking to camera, captions + RELAX tag
  Frame 2  20s of reel.mp4 (two full 5-in / 5-out cycles) with light copy

  python3 tmp/render_coherent_story.py            # render both
  STORY_STILLS=1 python3 tmp/render_coherent_story.py   # check stills only

Caption timings are word timestamps from faster-whisper (small.en and
medium.en agree on the wording). The clip is ad-libbed rather than the
written script, so the captions follow what is actually said. If the intro is
re-recorded, re-transcribe and rewrite CAPTIONS.

Face spans roughly y 480 (cap) to y 1300 (chin), so captions sit just under
the chin and the tag under them -- all above y 1650, clear of the reply bar.

Outputs -> assets/social/instagram/practices/coherent/story/
"""
import os
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

W, H = 1080, 1920
CX = W // 2
FPS = 30

SRC_DIR = os.path.join(ROOT, "assets", "social", "instagram", "practices",
                       "coherent")
INTRO_SRC = os.path.join(SRC_DIR, "story_intro.mp4")
REEL_SRC = os.path.join(SRC_DIR, "reel.mp4")
OUT_DIR = os.path.join(SRC_DIR, "story")
OVERLAY_DIR = os.path.join(OUT_DIR, "overlays")
OUT_1 = os.path.join(OUT_DIR, "story-1-intro.mp4")
OUT_2 = os.path.join(OUT_DIR, "story-2-reel.mp4")

INTRO_DUR = 15.40

# The reel has no intro card and starts on an inhale; cycles are 10s, so any
# multiple of 10 is the top of a breath. 30-50 is two whole cycles with the
# progress ring clearly part-drawn.
REEL_IN = 30.0
REEL_DUR = 20.0

BG_DEEP = (10, 8, 7)
SAGE = (143, 165, 138)
CLAY = (209, 144, 115)
CLAY_LT = (236, 190, 166)   # clay reads muddy over the red shirt
OFF = (239, 231, 217)
MUTED = (172, 164, 150)

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


def gradient_scrim(stops, color=BG_DEEP):
    """Full-width vertical ramp. stops: [(y_fraction, alpha)], smoothstepped."""
    small = Image.new("L", (1, 256))
    px = small.load()
    ys = [s[0] for s in stops]
    al = [s[1] for s in stops]
    for i in range(256):
        t = i / 255
        v = al[0] if t <= ys[0] else al[-1]
        for j in range(len(ys) - 1):
            if ys[j] <= t <= ys[j + 1]:
                u = (t - ys[j]) / (ys[j + 1] - ys[j])
                u = u * u * (3 - 2 * u)
                v = al[j] + (al[j + 1] - al[j]) * u
                break
        px[0, i] = int(round(v))
    pad = Image.new("RGBA", (W, H), color + (0,))
    pad.putalpha(small.resize((W, H), Image.BICUBIC))
    return pad


def with_halo(img, content, strength=0.6, blur=10):
    """Composite content over a dark blur of its own alpha."""
    halo = Image.new("RGBA", (W, H), BG_DEEP + (0,))
    halo.putalpha(content.split()[3].point(lambda v: int(v * strength)))
    img.alpha_composite(halo.filter(ImageFilter.GaussianBlur(blur)))
    img.alpha_composite(content)


def tracked_width(draw, text, fnt, tracking):
    return sum(draw.textlength(ch, font=fnt) + tracking for ch in text) - tracking


def draw_tracked_center(draw, cx, y, text, fnt, fill, tracking):
    x = cx - tracked_width(draw, text, fnt, tracking) / 2
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill, anchor="lm")
        x += draw.textlength(ch, font=fnt) + tracking


# ------------------------------------------------------------ frame 1: intro
CAP_SIZE = 50
CAP_LH = 66
CAP_CENTRE_Y = 1420
CAP_MAX_W = 860

# (text, start, end). Line breaks are explicit so phrases break where the
# voice does, not where the width runs out.
CAPTIONS = [
    ("I've just posted a short\nbreathing practice", 0.45, 2.62),
    ("as part of the Relax phase", 2.62, 4.36),
    ("of The Breath Reset.", 4.36, 6.20),
    ("It's a video I use", 6.40, 7.74),
    ("when I'm feeling wired\nor overwhelmed", 7.74, 9.32),
    ("to quickly bring me\nback to my body.", 9.32, 12.05),
    ("Find the longer version", 12.80, 13.90),
    ("on my Instagram Reel.", 13.90, INTRO_DUR),
]
TAG_START = 11.95


def make_caption(text, path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    content = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(content)
    fnt = manrope(CAP_SIZE, 600)
    lines = text.split("\n")
    y0 = CAP_CENTRE_Y - (len(lines) - 1) * CAP_LH / 2
    for i, line in enumerate(lines):
        if d.textlength(line, font=fnt) > CAP_MAX_W:
            print(f"  !! caption too wide: {line}")
        d.text((CX, y0 + i * CAP_LH), line, font=fnt, fill=OFF, anchor="mm")
    with_halo(img, content, strength=0.75, blur=9)
    img.save(path, "PNG")
    return path


def make_intro_scrim(path):
    """Soft floor under the caption band; stays off the chin (y ~1300)."""
    img = gradient_scrim([(0.0, 0), (0.69, 0), (0.78, 95), (0.90, 120),
                          (1.0, 120)])
    img.save(path, "PNG")
    return path


def make_tag(path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    content = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(content)
    draw_tracked_center(d, CX, 1546, "RELAX", manrope(29, 700), CLAY_LT, 8)
    d.text((CX, 1604), "Coherent Breath Reset", font=serif(46, italic=True),
           fill=OFF, anchor="mm")
    with_halo(img, content, strength=0.9, blur=11)
    img.save(path, "PNG")
    return path


def intro_cues():
    os.makedirs(OVERLAY_DIR, exist_ok=True)
    cues = [dict(png=make_intro_scrim(os.path.join(OVERLAY_DIR, "intro-scrim.png")),
                 start=0.0, end=INTRO_DUR, fin=0.0, fout=0.0)]
    for i, (text, s, e) in enumerate(CAPTIONS, start=1):
        png = make_caption(text, os.path.join(OVERLAY_DIR, f"cap-{i:02d}.png"))
        cues.append(dict(png=png, start=s, end=e, fin=0.08, fout=0.08))
    cues.append(dict(png=make_tag(os.path.join(OVERLAY_DIR, "tag.png")),
                     start=TAG_START, end=INTRO_DUR, fin=0.45, fout=0.0))
    return cues


# ------------------------------------------------------------- frame 2: reel
def make_reel_overlay(path):
    """Replaces the reel's own eyebrow (y ~169-221) and brand footer
    (y ~1690-1772) so the same words never sit on screen twice."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.alpha_composite(gradient_scrim(
        [(0.0, 255), (0.125, 255), (0.27, 0), (0.80, 0), (0.855, 255),
         (1.0, 255)]))

    content = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(content)
    d.text((CX, 300), "90-second Breath Reset", font=serif(82), fill=OFF,
           anchor="mm")
    d.text((CX, 376), "For when your body feels switched on.",
           font=manrope(34, 500), fill=MUTED, anchor="mm")

    img.alpha_composite(content)
    img.save(path, "PNG")
    return path


# -------------------------------------------------------------------- render
def filtergraph(cues, base):
    parts, label = [], base
    for i, cue in enumerate(cues, start=1):
        dur = cue["end"] - cue["start"]
        chain = [f"[{i}:v]format=rgba"]
        if cue["fin"]:
            chain.append(f"fade=t=in:st=0:d={cue['fin']:.3f}:alpha=1")
        if cue["fout"]:
            chain.append(f"fade=t=out:st={dur - cue['fout']:.3f}"
                         f":d={cue['fout']:.3f}:alpha=1")
        chain.append(f"setpts=PTS+{cue['start']:.3f}/TB")
        parts.append(",".join(chain) + f"[ov{i}]")
        parts.append(
            f"[{label}][ov{i}]overlay=0:0:eof_action=pass:format=auto"
            f":enable='between(t,{cue['start']:.3f},{cue['end']:.3f})'[v{i}]")
        label = f"v{i}"
    return parts, label


def inputs_for(cues):
    args = []
    for cue in cues:
        args += ["-loop", "1", "-framerate", str(FPS),
                 "-t", f"{cue['end'] - cue['start']:.3f}", "-i", cue["png"]]
    return args


ENCODE = ["-c:v", "libx264", "-preset", "medium", "-crf", "18",
          "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(FPS),
          "-color_primaries", "bt709", "-color_trc", "bt709",
          "-colorspace", "bt709",
          "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]


def intro_graph(cues, audio=True):
    # a touch warmer and less saturated -- pulls the harbour blue back
    # towards the brand's warm palette without looking graded
    parts = ["[0:v]eq=saturation=0.88:gamma=1.01,"
             "colorbalance=rm=0.03:bm=-0.035:rh=0.02:bh=-0.02[base]"]
    more, last = filtergraph(cues, "base")
    parts += more
    if audio:
        parts.append(f"[0:a]afade=t=in:st=0:d=0.15,"
                     f"afade=t=out:st={INTRO_DUR - 0.30:.3f}:d=0.30[aout]")
    return ";".join(parts), last


def reel_graph(cues, audio=True):
    parts = [f"[0:v]fade=t=in:st=0:d=0.35,"
             f"fade=t=out:st={REEL_DUR - 0.6:.3f}:d=0.6[base]"]
    more, last = filtergraph(cues, "base")
    parts += more
    if audio:
        parts.append(f"[0:a]afade=t=in:st=0:d=0.6,"
                     f"afade=t=out:st={REEL_DUR - 1.2:.3f}:d=1.2[aout]")
    return ";".join(parts), last


def render_intro(cues):
    graph, last = intro_graph(cues)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", INTRO_SRC] + inputs_for(cues) +
        ["-filter_complex", graph, "-map", f"[{last}]", "-map", "[aout]",
         "-t", f"{INTRO_DUR:.3f}"] + ENCODE + [OUT_1], check=True)
    print("saved", os.path.relpath(OUT_1, ROOT))


def render_reel(cues):
    graph, last = reel_graph(cues)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{REEL_IN:.3f}",
         "-t", f"{REEL_DUR:.3f}", "-i", REEL_SRC] + inputs_for(cues) +
        ["-filter_complex", graph, "-map", f"[{last}]", "-map", "[aout]",
         "-t", f"{REEL_DUR:.3f}"] + ENCODE + [OUT_2], check=True)
    print("saved", os.path.relpath(OUT_2, ROOT))


def stills(intro, reel):
    check_dir = os.path.join(ROOT, "tmp", "story-frames")
    os.makedirs(check_dir, exist_ok=True)
    jobs = [(INTRO_SRC, [], intro, intro_graph, t)
            for t in (1.5, 8.5, 12.4, 14.5)]
    jobs += [(REEL_SRC, ["-ss", f"{REEL_IN}", "-t", f"{REEL_DUR}"], reel,
              reel_graph, t) for t in (4.9, 9.9)]
    for src, pre, cues, gfn, t in jobs:
        graph, last = gfn(cues, audio=False)
        name = "intro" if src == INTRO_SRC else "reel"
        out = os.path.join(check_dir, f"check-{name}-{t:.1f}.png")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error"] + pre + ["-i", src] +
            inputs_for(cues) +
            ["-filter_complex", graph, "-map", f"[{last}]",
             "-ss", f"{t:.3f}", "-frames:v", "1", out], check=True)
        print("saved", os.path.relpath(out, ROOT))


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    intro = intro_cues()
    reel = [dict(png=make_reel_overlay(os.path.join(OVERLAY_DIR, "reel-copy.png")),
                 start=0.0, end=REEL_DUR, fin=0.0, fout=0.0)]
    if os.environ.get("STORY_STILLS"):
        stills(intro, reel)
    else:
        render_intro(intro)
        render_reel(reel)
