#!/usr/bin/env python3
"""
Breathe Light -- automated QC against the brief.

  tmp/.venv-dsp/bin/python tmp/qc_breathe_light.py
"""
import json
import os
import re
import subprocess

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(os.path.dirname(HERE), "assets", "social", "youtube", "relax", "breathe-light")
E = json.load(open(os.path.join(D, "breathe-light-edit.json")))
voice, sr = sf.read(os.path.join(D, "breathe-light-voice.wav"))
music, _ = sf.read(os.path.join(D, "breathe-light-music.wav"))
music = music.mean(1)


def db(x):
    return 10 * np.log10(np.mean(x ** 2) + 1e-12)


def window(x, a, b):
    return x[int(a * sr):int(b * sr)]


ok = True


def check(name, cond, detail):
    global ok
    ok &= bool(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}: {detail}")


words = E["words"]
for i, b in enumerate(E["bolts"], 1):
    dur = b["timer_end"] - b["timer_start"]
    check(f"BOLT {i} window", abs(dur - 60) < 1e-6, f"{dur:.3f}s")
    begin = max((w for w in words if w["w"].lower().startswith("begin")
                 and w["e"] <= b["timer_start"] + 0.5), key=lambda w: w["e"])
    check(f"BOLT {i} starts after 'begin'", 0 <= b["timer_start"] - begin["e"] + 0.5 < 1.0,
          f"word ends ~{begin['e']:.2f}s (whisper), timer starts {b['timer_start']:.2f}s")
    inside = [w for w in words if b["timer_start"] < w["s"] < b["timer_end"]]
    peak = 20 * np.log10(np.abs(window(voice, b["timer_start"] + 0.3, b["timer_end"])).max() + 1e-9)
    check(f"BOLT {i} no voice in window", not inside and peak < -45,
          f"{len(inside)} words, voice-stem peak {peak:.1f} dBFS")
    check(f"BOLT {i} voice resumes after window", b["voice_resume"] >= b["timer_end"],
          f"resumes {b['voice_resume'] - b['timer_end']:.2f}s after the window")

S = {s["name"]: (s["start"], s["end"]) for s in E["sections"]}
bl = S["letgo"][1] - S["notice"][0]
# the v2 script runs 5:14 before any pause is lengthened
check("Breathe Light ~6-7 min", 330 <= bl <= 460,
      f"{bl:.0f}s  (" + ", ".join(f"{n} {S[n][1] - S[n][0]:.0f}s" for n in
                                  ("notice", "soften", "lessair", "letgo") if n in S) + ")")

lg = [(a["e"], b["s"]) for a, b in zip(words, words[1:])
      if S["letgo"][0] <= a["e"] < S["letgo"][1]]
longest = max(b - a for a, b in lg)
check("Let Go has 20-30s uninterrupted", longest >= 20, f"longest pause {longest:.1f}s")

hop = sr // 2
m = music[: len(music) // hop * hop].reshape(-1, hop)
mdb = 10 * np.log10((m ** 2).mean(1) + 1e-12)
inner = mdb[int(4 / 0.5):-int(8 / 0.5)]
check("music continuous", inner.min() > -60, f"quietest 0.5s block {inner.min():.1f} dBFS")

v = voice[: len(voice) // hop * hop].reshape(-1, hop)
vdb = 10 * np.log10((v ** 2).mean(1) + 1e-12)
speech = vdb > -35
margin = np.median(vdb[speech] - mdb[:len(vdb)][speech])
check("voice clearly above music", margin > 10, f"median {margin:.1f} dB voice-over-music in speech")

mp4 = os.path.join(D, "breathe-light-youtube.mp4")
if os.path.exists(mp4):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", mp4, "-af",
                        "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
    i_l = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1])
    tp = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)[-1])
    check("integrated loudness", abs(i_l + 14) <= 0.5, f"{i_l:.1f} LUFS")
    check("true peak", tp < -1.0, f"{tp:.1f} dBTP")
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,width,height,r_frame_rate,duration",
                        "-of", "compact", mp4], capture_output=True, text=True).stdout
    print(p.strip())
print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
