#!/usr/bin/env python3
import os
import subprocess
import wave

import imageio_ffmpeg
import numpy as np

SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "tmp", "audio-prototypes")
os.makedirs(OUT_DIR, exist_ok=True)
FF = imageio_ffmpeg.get_ffmpeg_exe()


def fade(sig, fin, fout):
    a = sig.copy()
    fi, fo = int(fin * SR), int(fout * SR)
    if fi:
        a[:fi] *= np.linspace(0, 1, fi)
    if fo:
        a[-fo:] *= np.linspace(1, 0, fo)
    return a


def lowpass_box(x, k):
    c = np.cumsum(np.insert(x, 0, 0))
    y = (c[k:] - c[:-k]) / k
    return np.concatenate([np.full(k - 1, y[0]), y])[: len(x)]


def band_noise(seed, dur, low_k, high_k):
    rng = np.random.RandomState(seed)
    n = rng.randn(int(dur * SR))
    low = lowpass_box(n, low_k)
    lower = lowpass_box(n, high_k)
    return low - lower


def ambient(dur):
    t = np.arange(int(dur * SR)) / SR
    breath = 0.5 + 0.5 * np.sin(2 * np.pi * t / 10 - np.pi / 2)
    sig = np.zeros_like(t)
    for f, amp, det in [(110.0, 0.42, 0.0), (164.81, 0.20, 0.2), (220.0, 0.10, -0.16)]:
        sig += amp * np.sin(2 * np.pi * (f + det) * t)
    sig *= 0.65 + 0.18 * breath
    sig += 0.045 * lowpass_box(np.random.RandomState(7).randn(len(t)), 90)
    sig = fade(sig, 2.0, 2.0)
    return (0.18 * sig / np.max(np.abs(sig))).astype(np.float32)


def air_cue(kind):
    if kind == "inhale":
        dur = 1.35
        t = np.arange(int(dur * SR)) / SR
        x = np.linspace(0, 1, len(t))
        air = band_noise(11, dur, 34, 950)
        tone = np.sin(2 * np.pi * (185 + 38 * x) * t) * 0.10
        env = np.sin(np.pi * x) ** 1.4
        tilt = 0.58 + 0.42 * x
        sig = (air * 0.72 * tilt + tone) * env
        gain = 0.115
    elif kind == "exhale":
        dur = 1.85
        t = np.arange(int(dur * SR)) / SR
        x = np.linspace(0, 1, len(t))
        air = band_noise(17, dur, 52, 1300)
        tone = np.sin(2 * np.pi * (150 - 30 * x) * t) * 0.09
        env = np.where(x < 0.18, 0.5 - 0.5 * np.cos(np.pi * x / 0.18), np.exp(-(x - 0.18) / 0.55))
        tilt = 1.0 - 0.45 * x
        sig = (air * 0.78 * tilt + tone) * env
        gain = 0.105
    else:
        dur = 0.9
        t = np.arange(int(dur * SR)) / SR
        x = np.linspace(0, 1, len(t))
        air = band_noise(23, dur, 120, 1800)
        pulse = np.sin(2 * np.pi * 146.83 * t) * np.exp(-t / 0.28)
        env = np.exp(-x / 0.42)
        sig = (0.08 * air + 0.18 * pulse) * env
        gain = 0.075
    sig = fade(sig, 0.02, 0.12)
    return (gain * sig / np.max(np.abs(sig))).astype(np.float32)


def bell(dur=2.6):
    t = np.arange(int(dur * SR)) / SR
    sig = np.zeros_like(t)
    for ratio, amp, decay in [(0.56, 1.0, 3.5), (0.92, 0.45, 2.4), (1.19, 0.3, 1.8)]:
        sig += amp * np.sin(2 * np.pi * 440 * ratio * t) * np.exp(-t / decay)
    return (0.16 * fade(sig / np.max(np.abs(sig)), 0.006, 0.6)).astype(np.float32)


def mix_at(track, snd, at):
    i = int(at * SR)
    j = min(i + len(snd), len(track))
    track[i:j] += snd[: j - i]


def write_wav(path, sig):
    sig = np.clip(sig, -0.98, 0.98)
    data = (sig * 32767).astype(np.int16)
    data = np.column_stack([data, data])
    with wave.open(path, "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


dur = 28.0
master = ambient(dur).astype(np.float64)
mix_at(master, bell(), 0.0)

events = [
    (3.0, "inhale"),
    (7.0, "exhale"),
    (12.0, "inhale"),
    (16.0, "hold"),
    (20.0, "exhale"),
    (24.0, "hold"),
]
for at, kind in events:
    mix_at(master, air_cue(kind), at)

master *= 0.82 / np.max(np.abs(master))
wav = os.path.join(OUT_DIR, "soft-air-cues-example.wav")
mp3 = os.path.join(OUT_DIR, "soft-air-cues-example.mp3")
write_wav(wav, master)
subprocess.run([FF, "-y", "-loglevel", "error", "-i", wav, "-codec:a", "libmp3lame", "-q:a", "3", mp3], check=True)
print(mp3)
