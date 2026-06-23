#!/usr/bin/env python3
"""
Generate calming, premium audio for every Breath Reset flow.

For each flow (coherent, extendedExhale, boxBreathing):
  breathing-reel/audio/ambient-<slug>.mp3   breath-synced drone/pad (web, looped)
  tmp/master-<slug>.wav                      full mix (ambient + bells) for the MP4

Shared:
  breathing-reel/audio/bell.mp3              soft bell (start / end)
  breathing-reel/audio/tone-inhale.mp3       gentle rising swell (optional)
  breathing-reel/audio/tone-exhale.mp3       gentle falling swell (optional)

Pure synthesis (numpy) — no samples, no paid libs. Re-run after changing flows.
"""
import os, sys, wave, subprocess
import numpy as np
import imageio_ffmpeg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flows import FLOWS, cycle_len, orb_scale_at

FF = imageio_ffmpeg.get_ffmpeg_exe()
SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AUD  = os.path.join(ROOT, "breathing-reel", "audio")
os.makedirs(AUD, exist_ok=True)

# --------------------------------------------------------------------------
def breath_env(flow, t):
    """0..1 breath amplitude over time, following this flow's orb scale."""
    omin, omax = flow["orbMin"], flow["orbMax"]
    vals = np.array([orb_scale_at(flow, float(x)) for x in t])
    return (vals - omin) / (omax - omin)

def fade(sig, fin, fout):
    a = sig.copy()
    fi, fo = int(fin * SR), int(fout * SR)
    if fi: a[:fi]  *= np.linspace(0, 1, fi)
    if fo: a[-fo:] *= np.linspace(1, 0, fo)
    return a

def lowpass_box(x, k):
    c = np.cumsum(np.insert(x, 0, 0))
    y = (c[k:] - c[:-k]) / k
    return np.concatenate([np.full(k - 1, y[0]), y])[:len(x)]

def ambient(flow, dur=None):
    if dur is None:
        dur = flow["total"]
    t = np.arange(int(dur * SR)) / SR
    # sample the breath envelope coarsely then upsample (orb_scale per-sample is slow)
    tc = np.linspace(0, dur, int(dur * 50))
    bc = breath_env(flow, tc)
    b = np.interp(t, tc, bc)
    sig = np.zeros_like(t)
    for f, a, det in [(110.0, 0.50, 0.0), (110.0, 0.42, 0.55),
                      (164.81, 0.26, 0.0), (220.0, 0.11, 0.30)]:
        vib = 0.0018 * np.sin(2 * np.pi * 0.07 * t)
        sig += a * np.sin(2 * np.pi * (f + det) * t * (1 + vib))
    sig *= (0.80 + 0.20 * b)
    air = lowpass_box(np.random.RandomState(3).randn(len(t)), 60)
    sig += 0.12 * air * (0.6 + 0.4 * b)
    sig = fade(sig, 4.0, 4.0)
    sig *= 0.30 / np.max(np.abs(sig))
    return sig.astype(np.float32)

def bell(dur=4.5, base=440.0, gain=0.6):
    t = np.arange(int(dur * SR)) / SR
    ratios = [0.56, 0.92, 1.19, 1.71, 2.00, 2.74]
    amps   = [1.00, 0.60, 0.50, 0.34, 0.24, 0.14]
    decays = [4.4, 3.4, 2.8, 2.2, 1.7, 1.2]
    s = np.zeros_like(t)
    for r, a, d in zip(ratios, amps, decays):
        s += a * np.sin(2 * np.pi * base * r * t) * np.exp(-t / d)
    atk = int(0.006 * SR); s[:atk] *= np.linspace(0, 1, atk)
    s *= gain / np.max(np.abs(s))
    return s.astype(np.float32)

def tone(rising=True, dur=1.8, gain=0.18):
    t = np.arange(int(dur * SR)) / SR
    f0, f1 = (174.6, 220.0) if rising else (220.0, 174.6)
    f = np.linspace(f0, f1, len(t))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)
    s *= np.sin(np.pi * np.linspace(0, 1, len(t))) ** 1.5
    s *= gain / np.max(np.abs(s))
    return s.astype(np.float32)

# --------------------------------------------------------------------------
def write_wav(path, sig, stereo=True):
    sig = np.clip(sig, -1, 1)
    data = (sig * 32767).astype(np.int16)
    if stereo: data = np.column_stack([data, data])
    with wave.open(path, "w") as w:
        w.setnchannels(2 if stereo else 1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(data.tobytes())

def to_mp3(wav_path, mp3_path):
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", wav_path,
                    "-codec:a", "libmp3lame", "-q:a", "4", mp3_path], check=True)
    os.remove(wav_path)

def export_mp3(name, sig):
    wav = os.path.join(AUD, name + ".wav"); mp3 = os.path.join(AUD, name + ".mp3")
    write_wav(wav, sig); to_mp3(wav, mp3)
    print("  ->", os.path.relpath(mp3, ROOT))

def mix_at(track, snd, at):
    i = int(at * SR); j = min(i + len(snd), len(track)); track[i:j] += snd[:j - i]

# durations for the long-form YouTube master — keep in sync with
# FORMATS["youtube"] in tmp/render_reel.py
LONG_DUR     = 300
LONG_ENDCARD = 4

def make_master(flow, dur, endCard, suffix=""):
    """ambient pad + opening/closing bell, written to tmp/master-<slug><suffix>.wav."""
    master = ambient(flow, dur).astype(np.float64)
    mix_at(master, bell(gain=0.5), 0.0)
    mix_at(master, bell(gain=0.5), dur - endCard)
    master *= 0.92 / np.max(np.abs(master))
    path = os.path.join(HERE, f"master-{flow['slug']}{suffix}.wav")
    write_wav(path, master)
    print("  ->", os.path.relpath(path, ROOT))

# --------------------------------------------------------------------------
print("Shared bell + tones...")
export_mp3("bell", bell())
export_mp3("tone-inhale", tone(True))
export_mp3("tone-exhale", tone(False))

for fid, flow in FLOWS.items():
    slug = flow["slug"]
    print(f"Flow {fid} ({slug}, {flow['total']}s)...")
    # web ambient loop (unchanged)
    export_mp3(f"ambient-{slug}", ambient(flow))
    # masters for the MP4 renders
    make_master(flow, flow["total"], flow["endCard"], "")       # Instagram reel / YouTube short
    make_master(flow, LONG_DUR, LONG_ENDCARD, "-long")          # long-form 16:9 YouTube

print("Done.")
