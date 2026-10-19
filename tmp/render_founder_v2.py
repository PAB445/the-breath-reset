#!/usr/bin/env python3
"""
Founder video v2 -- burns the lower third, two pull-quotes, and the end card
into founder-story-v2.mp4.

  python3 tmp/render_founder_v2.py          # full render
  FOUNDER_STILLS=1 python3 tmp/render_founder_v2.py   # timing check stills only

Timings come from the source's own speech pauses. The footage already carries
burned-in captions at rows 1153-1250 which vanish during pauses, so each
pull-quote fades in under the tail of a sentence, holds alone through the pause
that follows, and fades out as the next caption arrives. Quotes sit above head
height (head top is ~y 437) to stay clear of the caption band during that
overlap.

If the source is re-cut, every timing below has to be re-measured. Getting the
pause map is easy:

    ffmpeg -i <src> -af silencedetect=n=-20dB:d=0.30 -vn -f null -

Finding *which* pause is which is the harder part. The reliable trick is to
compare the burned-in caption bitmap (rows 1140-1270, thresholded above 235)
against the same rows of a previous render at a known time, and take the pause
with the highest IoU -- correct matches score ~0.98 against ~0.18 for everything
else, so it is unambiguous.

Outputs -> assets/social/youtube/founder-video/
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

W, H = 1080, 1920
CX = W // 2
FPS = 30

FOUNDER_DIR = os.path.join(ROOT, "assets", "social", "youtube", "founder-video")
SOURCE = os.path.join(FOUNDER_DIR, "founder-story-v2.mp4")
OUT_DIR = FOUNDER_DIR
OVERLAY_DIR = os.path.join(OUT_DIR, "overlays")
FINAL = os.path.join(OUT_DIR, "founder-story-v2-final.mp4")
END_CARD = os.path.join(OUT_DIR, "end.png")

# Web derivative. The master is ~84MB, which is far too heavy for the homepage;
# the film frame renders around 380px wide, so 720x1280 is still retina-sharp.
WEB_VIDEO = os.path.join(OUT_DIR, "founder-story-v2-web.mp4")
WEB_POSTER = os.path.join(OUT_DIR, "cover-web.jpg")
WEB_HEIGHT = 1280

# The source runs 66.62s and its black tail starts at 64.07s -- only 2.47s,
# which is not long enough to read a three-line card. Hold the last (black)
# frame a little longer and fade the music under it so the ending can breathe.
# Set TAIL_EXTEND = 0 to end exactly where the source does.
SRC_DUR = 66.618
BLACK_START = 64.067
TAIL_EXTEND = 1.60
TOTAL_DUR = SRC_DUR + TAIL_EXTEND
END_CARD_START = BLACK_START + 0.08       # let the cut to black land first
MUSIC_FADE_D = 1.25

# palette -- warm-black system
BG_DEEP = (10, 8, 7)
SAGE = (143, 165, 138)
SAGE_DARK = (95, 116, 94)
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
    """Full-width vertical darkening ramp. stops: [(y_fraction, alpha)].

    Full width rather than a localised pad -- an elliptical scrim falls off too
    fast at the ends of a long line and leaves the last words unsupported.
    """
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
            v = al[-1]
            for j in range(len(ys) - 1):
                if ys[j] <= t <= ys[j + 1]:
                    u = (t - ys[j]) / (ys[j + 1] - ys[j])
                    u = u * u * (3 - 2 * u)  # smoothstep
                    v = al[j] + (al[j + 1] - al[j]) * u
                    break
        px[0, i] = int(round(v))
    pad = Image.new("RGBA", (W, H), color + (0,))
    pad.putalpha(small.resize((W, H), Image.BICUBIC))
    return pad


def text_with_shadow(img, xy, text, fnt, fill, anchor=None, blur=12,
                     shadow_alpha=150):
    """Sharp type over a blurred dark copy -- holds up over dappled foliage."""
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text(xy, text, font=fnt,
                                fill=BG_DEEP + (shadow_alpha,), anchor=anchor)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(shadow)
    ImageDraw.Draw(img).text(xy, text, font=fnt, fill=fill, anchor=anchor)


def draw_tracked(draw, xy, text, fnt, fill, tracking, center=False):
    x, y = xy
    if center:
        w = sum(draw.textlength(ch, font=fnt) + tracking for ch in text) - tracking
        x -= w / 2
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking


# ------------------------------------------------------------------- overlays
QUOTE_SIZE = 72
QUOTE_Y = (288, 384)   # line centres; head top is ~y 437


def make_pull_quote(plain, accent, path):
    """Two-line quote: statement in off-white, turn in sage italic."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # clears by y~500, so his face stays untouched
    img.alpha_composite(gradient_scrim(
        [(0.0, 222), (0.125, 212), (0.20, 140), (0.26, 0), (1.0, 0)]))

    reg = serif(QUOTE_SIZE)
    ital = serif(QUOTE_SIZE, italic=True)
    text_with_shadow(img, (CX, QUOTE_Y[0]), plain, reg, OFF, anchor="mm")
    text_with_shadow(img, (CX, QUOTE_Y[1]), accent, ital, SAGE, anchor="mm")

    measure = ImageDraw.Draw(img)
    widest = max(measure.textlength(plain, font=reg),
                 measure.textlength(accent, font=ital))
    if widest > W - 150:
        print(f"  !! quote too wide ({widest:.0f}px): {plain} / {accent}")

    img.save(path, "PNG")
    return path


def make_lower_third(path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # sits below the caption band (rows 1153-1250), above Instagram's chrome,
    # and the ramp doubles as a backing for the captions themselves
    img.alpha_composite(gradient_scrim(
        [(0.0, 0), (0.52, 0), (0.63, 125), (0.71, 200), (1.0, 212)]))

    content = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(content)
    cd.line([(92, 1326), (92, 1414)], fill=SAGE_DARK, width=3)
    cd.text((124, 1318), "Suraj", font=serif(64), fill=OFF)
    draw_tracked(cd, (126, 1388), "THE BREATH RESET", manrope(23, 700),
                 MUTED, 4.5)

    # dark halo lifted from the content's own alpha, so the small tracked
    # caps get the same support as the name
    halo = Image.new("RGBA", (W, H), BG_DEEP + (0,))
    halo.putalpha(content.split()[3].point(lambda v: int(v * 0.62)))
    img.alpha_composite(halo.filter(ImageFilter.GaussianBlur(10)))
    img.alpha_composite(content)

    img.save(path, "PNG")
    return path


# ------------------------------------------------------------------ the cues
# (png path, start, fade_in, fade_out_start, end) -- seconds
def build_cues():
    os.makedirs(OVERLAY_DIR, exist_ok=True)

    lower = make_lower_third(os.path.join(OVERLAY_DIR, "lower-third.png"))
    # "My body didn't" rather than "My body was still on edge" -- the caption
    # underneath reads "my body still felt like it was constantly on edge", and
    # the longer version put the same words on screen twice.
    q1 = make_pull_quote("My mind understood.", "My body didn't.",
                         os.path.join(OVERLAY_DIR, "quote-1.png"))
    q2 = make_pull_quote("Not just understanding it.", "Actually feeling it.",
                         os.path.join(OVERLAY_DIR, "quote-2.png"))

    # Measured caption-free windows: 40.25-41.45 and 48.25-49.25. Each quote
    # reaches full opacity as its caption clears and fades out as the next one
    # returns, so two blocks of text are never readable at once.
    return [
        # fades out into the 3.26-3.84s pause, off his opening line
        dict(png=lower, start=0.80, fin=0.70, fout_at=2.95, end=3.60),
        dict(png=q1, start=39.80, fin=0.50, fout_at=41.35, end=41.80),
        dict(png=q2, start=47.60, fin=0.60, fout_at=49.20, end=49.65),
        dict(png=END_CARD, start=END_CARD_START, fin=0.85, fout_at=None,
             end=TOTAL_DUR),
    ]


# -------------------------------------------------------------------- render
def filtergraph(cues):
    parts = []
    label = "0:v"
    if TAIL_EXTEND > 0:
        parts.append(f"[0:v]tpad=stop_mode=clone:"
                     f"stop_duration={TAIL_EXTEND:.3f}[base]")
        label = "base"
    for i, cue in enumerate(cues, start=1):
        dur = cue["end"] - cue["start"]
        chain = [f"[{i}:v]format=rgba",
                 f"fade=t=in:st=0:d={cue['fin']:.3f}:alpha=1"]
        if cue["fout_at"] is not None:
            fout_d = cue["end"] - cue["fout_at"]
            chain.append(
                f"fade=t=out:st={cue['fout_at'] - cue['start']:.3f}"
                f":d={fout_d:.3f}:alpha=1")
        chain.append(f"setpts=PTS+{cue['start']:.3f}/TB")
        parts.append(",".join(chain) + f"[ov{i}]")

        out = f"v{i}"
        parts.append(
            f"[{label}][ov{i}]overlay=0:0:eof_action=pass:format=auto"
            f":enable='between(t,{cue['start']:.3f},{cue['end']:.3f})'[{out}]")
        label = out
        cue["_dur"] = dur
    return ";".join(parts), label


def inputs_for(cues):
    args = []
    for cue in cues:
        args += ["-loop", "1", "-framerate", str(FPS),
                 "-t", f"{cue['end'] - cue['start']:.3f}", "-i", cue["png"]]
    return args


def render(cues):
    graph, last = filtergraph(cues)
    audio_map = "0:a"
    if TAIL_EXTEND > 0:
        graph += (f";[0:a]afade=t=out:st={SRC_DUR - MUSIC_FADE_D:.3f}"
                  f":d={MUSIC_FADE_D:.3f},"
                  f"apad=pad_dur={TAIL_EXTEND + 0.1:.3f}[aout]")
        audio_map = "[aout]"

    cmd = (["ffmpeg", "-y", "-i", SOURCE] + inputs_for(cues) +
           ["-filter_complex", graph,
            "-map", f"[{last}]", "-map", audio_map,
            "-t", f"{TOTAL_DUR:.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", FINAL])
    subprocess.run(cmd, check=True)
    print("saved", os.path.relpath(FINAL, ROOT))


def render_web():
    """Smaller derivative plus a light poster, for the website embed."""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", FINAL,
         "-vf", f"scale=-2:{WEB_HEIGHT}",
         "-c:v", "libx264", "-preset", "slow", "-crf", "27",
         "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.0",
         "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart", WEB_VIDEO],
        check=True)

    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-i", os.path.join(OUT_DIR, "cover.png"),
         "-vf", f"scale=-2:{WEB_HEIGHT}", "-q:v", "4", WEB_POSTER],
        check=True)

    for path in (WEB_VIDEO, WEB_POSTER):
        mb = os.path.getsize(path) / 1e6
        print(f"saved {os.path.relpath(path, ROOT)}  ({mb:.1f} MB)")


def stills(cues):
    """Sample each cue at its hold point so timings can be eyeballed fast."""
    graph, last = filtergraph(cues)
    check_dir = os.path.join(ROOT, "tmp", "founder-v2-frames")
    os.makedirs(check_dir, exist_ok=True)
    for cue in cues:
        hold = (cue["fout_at"] if cue["fout_at"] else cue["end"] - 1.0) - 0.35
        out = os.path.join(check_dir, f"check-{hold:.2f}.png")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", SOURCE] + inputs_for(cues) +
            ["-filter_complex", graph, "-map", f"[{last}]",
             "-ss", f"{hold:.3f}", "-frames:v", "1", "-s", "432x768", out],
            check=True)
        print("saved", os.path.relpath(out, ROOT))


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    if not os.path.exists(END_CARD):
        sys.exit("Run tmp/make_founder_cards_v2.py first (end.png missing)")
    cues = build_cues()
    if os.environ.get("FOUNDER_STILLS"):
        stills(cues)
    elif os.environ.get("FOUNDER_WEB_ONLY"):
        render_web()
    else:
        render(cues)
        render_web()
