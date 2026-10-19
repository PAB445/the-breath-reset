#!/usr/bin/env python3
"""
Extended Exhale Breath Reset -- final reel + the animated Story frame.

  reel_final.mp4   5s cover, the 90s reel, 5s end card, matching
                   coherent/reel_final.mp4. The end card is silent; the pad
                   fades in under the last second of the cover.
  story/story-2-reel.mp4
                   20s of reel.mp4 (two full 4-in / 6-out cycles) with the
                   same light copy overlay as the coherent story

The talking-to-camera intro (story-1) is recorded separately; once it exists,
add it the way render_coherent_story.py does.

  python3 tmp/render_extended_exhale_story.py
  STORY_STILLS=1 python3 tmp/render_extended_exhale_story.py

Run after render_reel.py, which writes reel.mp4.
"""
import os
import subprocess
import wave

from PIL import Image, ImageDraw

import render_coherent_story as cs
from render_coherent_story import CX, FPS, H, MUTED, OFF, W, manrope, serif

SRC_DIR = os.path.join(cs.ROOT, "assets", "social", "instagram", "practices",
                       "extended-exhale")
REEL_SRC = os.path.join(SRC_DIR, "reel.mp4")
COVER = os.path.join(SRC_DIR, "cover.png")
END = os.path.join(SRC_DIR, "end.png")
FINAL = os.path.join(SRC_DIR, "reel_final.mp4")
OUT_DIR = os.path.join(SRC_DIR, "story")
OVERLAY_DIR = os.path.join(OUT_DIR, "overlays")
OUT_2 = os.path.join(OUT_DIR, "story-2-reel.mp4")

# pad pre-roll from make_audio.py, played under the end of the cover
LEAD = os.path.join(cs.ROOT, "tmp", "master-extended-exhale-lead.wav")

COVER_HOLD = 5.0
END_HOLD = 5.0

# cycles are 10s (4 + 6), so 30-50 is two whole cycles from the top of an inhale
REEL_IN = 30.0
REEL_DUR = cs.REEL_DUR


def make_reel_overlay(path):
    """Same scrims as the coherent story: covers the reel's own eyebrow and
    brand footer so the words never sit on screen twice."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.alpha_composite(cs.gradient_scrim(
        [(0.0, 255), (0.125, 255), (0.27, 0), (0.80, 0), (0.855, 255),
         (1.0, 255)]))
    d = ImageDraw.Draw(img)
    d.text((CX, 300), "90-second Breath Reset", font=serif(82), fill=OFF,
           anchor="mm")
    d.text((CX, 376), "For when you need to come down.",
           font=manrope(34, 500), fill=MUTED, anchor="mm")
    img.save(path, "PNG")
    return path


def wave_seconds(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def render_final():
    lead_s = wave_seconds(LEAD)
    graph = (
        f"[0:v]format=yuv420p,setsar=1[c];"
        f"[1:v]format=yuv420p,setsar=1[r];"
        f"[2:v]format=yuv420p,setsar=1[e];"
        f"[3:a][5:a][1:a][4:a]concat=n=4:v=0:a=1[a];"
        f"[c][r][e]concat=n=3:v=1:a=0[v]")
    silence = ["-f", "lavfi", "-t", "{:.3f}", "-i",
               "anullsrc=r=44100:cl=stereo"]
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-loop", "1", "-framerate", str(FPS), "-t", f"{COVER_HOLD:.3f}",
         "-i", COVER,
         "-i", REEL_SRC,
         "-loop", "1", "-framerate", str(FPS), "-t", f"{END_HOLD:.3f}",
         "-i", END]
        + [s.format(COVER_HOLD - lead_s) for s in silence]
        + [s.format(END_HOLD) for s in silence]
        + ["-i", LEAD]
        + ["-filter_complex", graph, "-map", "[v]", "-map", "[a]"]
        + cs.ENCODE + [FINAL], check=True)
    print("saved", os.path.relpath(FINAL, cs.ROOT))


def render_story(cues):
    graph, last = cs.reel_graph(cues)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{REEL_IN:.3f}",
         "-t", f"{REEL_DUR:.3f}", "-i", REEL_SRC] + cs.inputs_for(cues) +
        ["-filter_complex", graph, "-map", f"[{last}]", "-map", "[aout]",
         "-t", f"{REEL_DUR:.3f}"] + cs.ENCODE + [OUT_2], check=True)
    print("saved", os.path.relpath(OUT_2, cs.ROOT))


def stills(cues):
    check_dir = os.path.join(cs.ROOT, "tmp", "story-frames")
    os.makedirs(check_dir, exist_ok=True)
    for t in (3.9, 9.9):
        graph, last = cs.reel_graph(cues, audio=False)
        out = os.path.join(check_dir, f"check-ee-reel-{t:.1f}.png")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{REEL_IN}",
             "-t", f"{REEL_DUR}", "-i", REEL_SRC] + cs.inputs_for(cues) +
            ["-filter_complex", graph, "-map", f"[{last}]",
             "-ss", f"{t:.3f}", "-frames:v", "1", out], check=True)
        print("saved", os.path.relpath(out, cs.ROOT))


if __name__ == "__main__":
    os.makedirs(OVERLAY_DIR, exist_ok=True)
    cues = [dict(png=make_reel_overlay(os.path.join(OVERLAY_DIR, "reel-copy.png")),
                 start=0.0, end=REEL_DUR, fin=0.0, fout=0.0)]
    if os.environ.get("STORY_STILLS"):
        stills(cues)
    else:
        render_final()
        render_story(cues)
