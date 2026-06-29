#!/usr/bin/env python3
import json
import math
import os
import shutil
import subprocess
from fractions import Fraction
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(ROOT, "assets", "social", "youtube", "co2-tolerance")
INPUT_VIDEO = os.path.join(ASSET_DIR, "0629.mov")
OUTPUT_VIDEO = os.path.join(ASSET_DIR, "0629-timer.mp4")
OUTPUT_FINAL_VIDEO = os.path.join(ASSET_DIR, "0629-final.mp4")
COVER_IMAGE = os.path.join(ASSET_DIR, "cover.png")
END_IMAGE = os.path.join(ASSET_DIR, "end-screen.png")
FRAME_DIR = os.path.join(ROOT, "tmp", "co2-timer-frames")
FONTS = os.path.join(ROOT, "breathing-reel", "fonts")

TIMER_START_SECONDS = 3 * 60 + 5
TIMER_END_SECONDS = 4 * 60 + 15
TIMER_DURATION_SECONDS = TIMER_END_SECONDS - TIMER_START_SECONDS
COVER_SECONDS = 4
END_SECONDS = 5

OFFWHITE = (255, 250, 243, 255)
MUTED = (239, 231, 217, 230)
SAGE = (154, 180, 148, 255)
SAGE_TRACK = (239, 231, 217, 118)
CLAY = (224, 153, 119, 255)
SHADOW = (12, 8, 6, 210)


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), int(size))


def manrope(size, weight=600):
    f = font("Manrope.ttf", size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def serif(size):
    return font("InstrumentSerif-Regular.ttf", size)


def probe(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,avg_frame_rate",
            "-show_entries", "format=duration",
            "-of", "json",
            path,
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    fps = float(Fraction(stream["avg_frame_rate"]))
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "fps": fps,
        "duration": float(data["format"]["duration"]),
    }


def draw_stroked_text(draw, xy, text, fnt, fill, anchor, stroke_width):
    draw.text(
        xy,
        text,
        font=fnt,
        fill=fill,
        anchor=anchor,
        stroke_width=stroke_width,
        stroke_fill=SHADOW,
    )


def fmt_time(seconds):
    whole = int(math.floor(seconds))
    return f"{whole // 60:02d}:{whole % 60:02d}"


def draw_timer_frame(width, height, fps, frame_index):
    elapsed = min(frame_index / fps, TIMER_DURATION_SECONDS)
    scale = max(0.74, width / 1150)

    ring_size = int(150 * scale)
    ring_width = max(4, int(6 * scale))
    ring_radius = ring_size / 2 - ring_width * 2.2
    margin_right = int(52 * scale)
    margin_top = int(40 * scale)
    gap = int(24 * scale)

    timer_font = manrope(66 * scale, 650)
    label_font = manrope(15 * scale, 800)
    note_font = manrope(14 * scale, 650)

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    rd = ImageDraw.Draw(img)

    ring_cx = width - margin_right - ring_size / 2
    ring_cy = margin_top + ring_size / 2
    bbox = [
        ring_cx - ring_radius,
        ring_cy - ring_radius,
        ring_cx + ring_radius,
        ring_cy + ring_radius,
    ]

    for off, alpha in ((2, 150), (4, 76)):
        shadow_bbox = [bbox[0] + off, bbox[1] + off, bbox[2] + off, bbox[3] + off]
        rd.ellipse(shadow_bbox, outline=(10, 8, 7, alpha), width=ring_width)

    rd.ellipse(bbox, outline=SAGE_TRACK, width=ring_width)
    minute_progress = (elapsed % 60) / 60
    rd.arc(bbox, start=-90, end=-90 + 360 * minute_progress, fill=SAGE, width=ring_width)

    d = ImageDraw.Draw(img)
    text_right = int(ring_cx - ring_size / 2 - gap)
    label_y = int(margin_top + 7 * scale)
    timer_y = int(label_y + 21 * scale)
    note_y = int(timer_y + 72 * scale)

    draw_stroked_text(d, (text_right, label_y), "HOLD TIME", label_font, CLAY, "ra", 1)
    draw_stroked_text(d, (text_right, timer_y), fmt_time(elapsed), timer_font, OFFWHITE, "ra", 1)
    draw_stroked_text(
        d,
        (text_right, note_y),
        "Stop at the first clear urge to breathe",
        note_font,
        MUTED,
        "ra",
        1,
    )
    return img


def make_frames(meta):
    if os.path.exists(FRAME_DIR):
        shutil.rmtree(FRAME_DIR)
    os.makedirs(FRAME_DIR, exist_ok=True)

    frame_count = int(round(TIMER_DURATION_SECONDS * meta["fps"])) + 1
    print(f"Rendering {frame_count} transparent timer frames...")
    for i in range(frame_count):
        frame = draw_timer_frame(meta["width"], meta["height"], meta["fps"], i)
        frame.save(os.path.join(FRAME_DIR, f"frame_{i:05d}.png"))
        if i and i % 300 == 0:
            print(f"  {i}/{frame_count}")


def composite(meta):
    cmd = [
        "ffmpeg",
        "-y",
        "-i", INPUT_VIDEO,
        "-framerate", str(meta["fps"]),
        "-i", os.path.join(FRAME_DIR, "frame_%05d.png"),
        "-filter_complex",
        f"[1:v]format=rgba,setpts=PTS+{TIMER_START_SECONDS}/TB[ov];"
        f"[0:v][ov]overlay=0:0:eof_action=pass:format=auto[v]",
        "-map", "[v]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        OUTPUT_VIDEO,
    ]
    print("Compositing timer overlay...")
    subprocess.run(cmd, check=True)


def assemble_final(meta):
    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-t", str(COVER_SECONDS),
        "-i", COVER_IMAGE,
        "-i", OUTPUT_VIDEO,
        "-loop", "1",
        "-t", str(END_SECONDS),
        "-i", END_IMAGE,
        "-filter_complex",
        f"[0:v]scale={meta['width']}:{meta['height']}:force_original_aspect_ratio=increase,"
        f"crop={meta['width']}:{meta['height']},setsar=1,fps={meta['fps']}[coverv];"
        f"[2:v]scale={meta['width']}:{meta['height']}:force_original_aspect_ratio=increase,"
        f"crop={meta['width']}:{meta['height']},setsar=1,fps={meta['fps']}[endv];"
        f"anullsrc=channel_layout=stereo:sample_rate=44100,atrim=0:{COVER_SECONDS}[covera];"
        f"anullsrc=channel_layout=stereo:sample_rate=44100,atrim=0:{END_SECONDS}[enda];"
        f"[1:v]setsar=1,fps={meta['fps']}[mainv];"
        "[1:a]aformat=sample_rates=44100:channel_layouts=stereo[maina];"
        "[coverv][covera][mainv][maina][endv][enda]concat=n=3:v=1:a=1[v][a]",
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        OUTPUT_FINAL_VIDEO,
    ]
    print("Assembling cover + timed video + end screen...")
    subprocess.run(cmd, check=True)


def main():
    meta = probe(INPUT_VIDEO)
    if TIMER_END_SECONDS > meta["duration"]:
        raise SystemExit(
            f"Timer end {TIMER_END_SECONDS}s is beyond video duration {meta['duration']:.2f}s"
        )
    print(
        f"Source: {meta['width']}x{meta['height']} @ {meta['fps']:.3f}fps, "
        f"{meta['duration']:.2f}s"
    )
    make_frames(meta)
    composite(meta)
    print("Saved", os.path.relpath(OUTPUT_VIDEO, ROOT))
    assemble_final(meta)
    print("Saved", os.path.relpath(OUTPUT_FINAL_VIDEO, ROOT))


if __name__ == "__main__":
    main()
