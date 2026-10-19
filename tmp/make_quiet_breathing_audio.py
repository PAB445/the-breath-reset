#!/usr/bin/env python3
"""
Quiet-breathing video -- music bed + final voice/music mix.

  python3 tmp/make_quiet_breathing_audio.py

Synthesises a low ambient bed (pad, a soft plucked pulse, minimal percussion)
in pure numpy, then mixes it far under the cleaned-up voice track.

  tmp/quiet-breathing-music.wav    music bed only, peak-normalised
  tmp/quiet-breathing-mix.wav      voice + music, what the renderer muxes

The bed is arranged against the speech: the pulse enters after the opening
demo breath, percussion after the first idea lands, and both drop out for the
guided breath (93-109s) so that moment feels open. No crescendo anywhere.

Loudness: voice -> -16 LUFS integrated, music bed -> ~-31 LUFS (15 dB under).
Both gains use measured loudness and a linear volume, never dynamic loudnorm,
which would lift the room tone in every pause.
"""
import os
import re
import subprocess
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = os.path.join(ROOT, "assets", "social", "youtube", "retrain",
                      "quiet-breathing", "quiet-breathing-source.mp4")
MUSIC = os.path.join(HERE, "quiet-breathing-music.wav")
MIX = os.path.join(HERE, "quiet-breathing-mix.wav")

SR = 44100
# Must match TOTAL_DUR in render_quiet_breathing.py.
DUR = 123.0

VOICE_LUFS = -16.0
MUSIC_LUFS = -31.0

BPM = 72.0
BEAT = 60.0 / BPM
CHORD_LEN = 8 * BEAT          # two bars of 4/4

# D major, open voicings. Starting offset puts Dmaj9 under the end card.
CHORDS = {
    "D":  [73.42, 110.00, 185.00, 277.18, 329.63],
    "Bm": [61.74, 92.50, 146.83, 220.00, 277.18],
    "G":  [98.00, 146.83, 220.00, 246.94, 369.99],
    "A":  [110.00, 164.81, 196.00, 246.94, 293.66],
}
ORDER = ["D", "Bm", "G", "A"]
ORDER_OFFSET = 2

rng = np.random.RandomState(7)
t_all = np.arange(int(DUR * SR)) / SR


def ramp(t, pts):
    """Piecewise-linear automation, smoothed. pts: [(time, value)]."""
    xs, ys = zip(*pts)
    v = np.interp(t, xs, ys)
    k = int(0.25 * SR)
    c = np.cumsum(np.insert(v, 0, 0))
    sm = (c[k:] - c[:-k]) / k
    return np.concatenate([np.full(k - 1, sm[0]), sm])[:len(v)]


def chord_at(i):
    return CHORDS[ORDER[(i + ORDER_OFFSET) % len(ORDER)]]


# ----------------------------------------------------------------------- pad
def pad():
    out = np.zeros((len(t_all), 2))
    n_chords = int(np.ceil(DUR / CHORD_LEN)) + 1
    for i in range(n_chords):
        start, end = i * CHORD_LEN, (i + 1) * CHORD_LEN
        a, b = max(0.0, start - 1.6), min(DUR, end + 2.4)
        i0, i1 = int(a * SR), int(b * SR)
        t = t_all[i0:i1]
        env = np.ones_like(t)
        fin = np.clip((t - (start - 1.6)) / 2.4, 0, 1)
        fout = np.clip(((end + 2.4) - t) / 2.6, 0, 1)
        env *= np.sin(fin * np.pi / 2) ** 2 * np.sin(fout * np.pi / 2) ** 2
        if i == 0:
            env = np.clip((t - 0.0) / 3.0, 0, 1) ** 2
            env *= np.sin(fout * np.pi / 2) ** 2
        for j, f in enumerate(chord_at(i)):
            gain = 0.30 if j == 0 else 0.20 / (1 + 0.25 * j)
            for ch, det in ((0, -0.0011), (1, 0.0013)):
                ph = rng.uniform(0, 2 * np.pi)
                sig = np.zeros_like(t)
                for k in range(1, 6):
                    sig += np.sin(2 * np.pi * f * k * (1 + det) * t + ph * k) / k ** 2.2
                out[i0:i1, ch] += gain * env * sig
    lfo = 1.0 + 0.08 * np.sin(2 * np.pi * 0.045 * t_all)
    return out * lfo[:, None]


# --------------------------------------------------------------------- pulse
def pluck(f, dur=1.4):
    t = np.arange(int(dur * SR)) / SR
    env = (1 - np.exp(-t / 0.005)) * np.exp(-t / 0.32)
    return env * (np.sin(2 * np.pi * f * t) + 0.22 * np.sin(4 * np.pi * f * t)
                  + 0.05 * np.sin(6 * np.pi * f * t))


def pulse():
    out = np.zeros((len(t_all) + SR * 2, 2))
    step = BEAT / 2
    n = int(DUR / step)
    for s in range(n):
        t0 = s * step
        tones = sorted(chord_at(int(t0 // CHORD_LEN))[2:])
        pattern = [0, 2, 1, 2, 0, 2, 1, 2]
        f = tones[pattern[s % 8] % len(tones)] * 2
        vel = 1.0 if s % 8 == 0 else (0.72 if s % 2 == 0 else 0.5)
        vel *= rng.uniform(0.9, 1.0)
        p = pluck(f) * vel
        i0 = int(t0 * SR)
        pan = 0.5 + (0.18 if s % 2 else -0.18)
        out[i0:i0 + len(p), 0] += p * (1 - pan)
        out[i0:i0 + len(p), 1] += p * pan
    out = out[:len(t_all)]
    # dotted-eighth echo, ping-ponged
    d = int(BEAT * 0.75 * SR)
    echo = np.zeros_like(out)
    echo[d:, 1] += 0.28 * out[:-d, 0]
    echo[d:, 0] += 0.28 * out[:-d, 1]
    echo[2 * d:] += 0.12 * out[:-2 * d]
    return out + echo


# ---------------------------------------------------------------- percussion
def percussion():
    out = np.zeros(len(t_all) + SR)
    kt = np.arange(int(0.6 * SR)) / SR
    freq = 46 + 64 * np.exp(-kt / 0.035)
    kick = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-kt / 0.16)
    kick *= 1 - np.exp(-kt / 0.002)

    ht = np.arange(int(0.12 * SR)) / SR
    for s in range(int(DUR / (BEAT / 2))):
        t0 = s * BEAT / 2
        i0 = int(t0 * SR)
        if s % 4 == 0:
            out[i0:i0 + len(kick)] += 0.9 * kick
        if s % 2 == 1:
            noise = rng.randn(len(ht))
            noise = np.diff(noise, prepend=0)           # crude high-pass
            noise = np.diff(noise, prepend=0)
            hat = noise * np.exp(-ht / 0.022) * rng.uniform(0.6, 1.0)
            out[i0:i0 + len(hat)] += 0.05 * hat
    out = out[:len(t_all)]
    return np.stack([out, out], axis=1)


# ------------------------------------------------------------------- reverb
def reverb(x, seconds=2.6, wet=0.25):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = np.empty_like(x)
    for ch in range(x.shape[1]):
        ir = np.random.RandomState(11 + ch).randn(n) * np.exp(-t / (seconds / 6.9))
        ir[: int(0.012 * SR)] = 0
        ir /= np.sqrt((ir ** 2).sum())
        size = 1 << int(np.ceil(np.log2(len(x) + n)))
        y = np.fft.irfft(np.fft.rfft(x[:, ch], size) * np.fft.rfft(ir, size), size)
        out[:, ch] = x[:, ch] + wet * y[: len(x)]
    return out


def build_music():
    t = t_all
    pad_auto = ramp(t, [(0, 1.0), (92.5, 1.0), (95.0, 0.72), (108.5, 0.72),
                        (111.0, 0.95), (120.5, 0.95), (123.0, 0.0)])
    pulse_auto = ramp(t, [(0, 0), (6.2, 0), (9.0, 0.85), (92.0, 0.85),
                          (94.2, 0.0), (109.6, 0.0), (111.5, 0.55),
                          (117.5, 0.55), (120.0, 0.0), (123, 0)])
    perc_auto = ramp(t, [(0, 0), (12.0, 0), (16.0, 0.8), (91.5, 0.8),
                         (93.5, 0.0), (110.0, 0.0), (112.0, 0.4),
                         (117.0, 0.4), (118.8, 0.0), (123, 0)])

    mix = (pad() * 1.0 * pad_auto[:, None]
           + pulse() * 0.16 * pulse_auto[:, None]
           + percussion() * 0.20 * perc_auto[:, None])
    mix = reverb(mix, wet=0.32)
    end_fade = np.clip((DUR - t) / 2.5, 0, 1) ** 1.5
    mix *= end_fade[:, None]
    mix *= 10 ** (-3 / 20) / np.max(np.abs(mix))
    return mix


def write_wav(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("saved", os.path.relpath(path, ROOT))


# --------------------------------------------------------------------- mix
VOICE_CHAIN = ("highpass=f=75,afftdn=nr=8:nf=-50,"
               "acompressor=threshold=-26dB:ratio=2.2:attack=10:release=220")


def integrated_lufs(args, chain):
    res = subprocess.run(["ffmpeg", "-hide_banner", "-nostats"] + args +
                         ["-af", chain + ",ebur128", "-f", "null", "-"],
                         capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", res.stderr)
    return float(m[-1])


def mix():
    v_lufs = integrated_lufs(["-i", SOURCE, "-vn"], VOICE_CHAIN)
    m_lufs = integrated_lufs(["-i", MUSIC], "anull")
    gv = VOICE_LUFS - v_lufs
    gm = MUSIC_LUFS - m_lufs
    print(f"voice {v_lufs:.1f} LUFS -> {gv:+.1f} dB; "
          f"music {m_lufs:.1f} LUFS -> {gm:+.1f} dB")
    graph = (f"[0:a]{VOICE_CHAIN},volume={gv:.2f}dB,aresample={SR},"
             f"aformat=channel_layouts=stereo,apad[v];"
             f"[1:a]volume={gm:.2f}dB[m];"
             f"[v][m]amix=inputs=2:normalize=0:duration=longest,"
             f"alimiter=limit=0.85:level=false,atrim=0:{DUR}[out]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", SOURCE, "-i", MUSIC,
                    "-filter_complex", graph, "-map", "[out]",
                    "-ar", str(SR), "-c:a", "pcm_s16le", MIX], check=True)
    print("saved", os.path.relpath(MIX, ROOT))
    print(f"mix {integrated_lufs(['-i', MIX], 'anull'):.1f} LUFS")


if __name__ == "__main__":
    write_wav(MUSIC, build_music())
    mix()
