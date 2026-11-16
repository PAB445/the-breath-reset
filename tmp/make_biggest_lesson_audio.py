#!/usr/bin/env python3
"""
"Biggest breathwork lesson" reel -- voice cleanup, original score, final mix.
Run with the DSP venv (DeepFilterNet lives there):

  tmp/.venv-dsp/bin/python tmp/make_biggest_lesson_audio.py
  BL_REDENOISE=1 ...   # re-run the denoiser (otherwise cached)

Voice chain (gentle -- it should still sound like a man talking in a garden):
  1. DeepFilterNet 3 with an attenuation cap (edit.json audio.denoise_db), so
     the leaf hiss drops but breaths and word tails survive. Then a targeted
     declick for the odd hand/mic bump (one sits just before "keep busy").
  2. Lengthened pauses (edit.json holds) are filled with that pause's own room
     tone, crossfaded -- never digital silence.
  3. High-pass, a small low-mid dip, a touch of presence, de-ess, light 2:1
     compression, then a linear gain to the loudness target.

Score: original, synthesised here in numpy, so it is ours to publish. Soft felt
piano, warm pads, a low root and a breath-like air layer, arranged against the
story (see PLAN). Piano notes are placed in his natural pauses, never on top of
a word. To use a licensed track instead, set music.track in edit.json -- it
gets the same loudness, ducking and fades.

Outputs (tmp/):
  biggest-lesson-voice.wav   processed voice, finished-video timeline
  biggest-lesson-music.wav   music bed before ducking
  biggest-lesson-mix.wav     what the renderer muxes
"""
import json
import os
import subprocess

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.signal import butter, sosfilt

from biggest_lesson_edit import (EDIT, END_CARD_START, HOLDS, REEL_DIR, ROOT,
                                 SEGMENTS, SOURCE, SPEECH_OUT_END, SRC_DUR,
                                 TOTAL_DUR, WORDS_PATH, out_time)

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 48000
N = int(round(TOTAL_DUR * SR))

AUDIO = EDIT["audio"]
MUSIC_CFG = EDIT["music"]

RAW = os.path.join(HERE, "biggest-lesson-source.wav")
DENOISED = os.path.join(HERE, f"biggest-lesson-df{AUDIO['denoise_db']}.wav")
VOICE = os.path.join(HERE, "biggest-lesson-voice.wav")
MUSIC = os.path.join(HERE, "biggest-lesson-music.wav")
MIX = os.path.join(HERE, "biggest-lesson-mix.wav")
FINAL_LUFS = -15.0

meter = pyln.Meter(SR)


def lufs(x):
    return meter.integrated_loudness(x)


def db(x):
    return 10 ** (x / 20)


# ===================================================================== voice
def extract():
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", SOURCE, "-vn",
                    "-ac", "1", "-ar", str(SR), "-c:a", "pcm_f32le", RAW],
                   check=True)


def denoise():
    import torch
    from df.enhance import enhance, init_df
    x, _ = sf.read(RAW, dtype="float32")
    model, state, _ = init_df()
    torch.set_num_threads(8)
    y = enhance(model, state, torch.from_numpy(x[None, :]),
                atten_lim_db=float(AUDIO["denoise_db"]))[0].numpy()
    sf.write(DENOISED, y, SR, subtype="FLOAT")
    print("saved", os.path.relpath(DENOISED, ROOT))


def room_tone(chunk, length):
    """Fill `length` samples by looping `chunk` with 60 ms crossfades."""
    xf = int(0.06 * SR)
    out = np.zeros(length + len(chunk))
    pos, k = 0, 0
    fade = np.linspace(0, 1, xf)
    while pos < length:
        c = chunk if k % 2 == 0 else chunk[::-1]       # reversed: no audible loop
        seg = c.copy()
        seg[:xf] *= fade
        seg[-xf:] *= fade[::-1]
        out[pos:pos + len(seg)] += seg
        pos += len(seg) - xf
        k += 1
    return out[:length]


def declick(x, ratio=4.0):
    """Pull down isolated spikes (hand/mic bumps). A click is louder than
    *both* sides within ~20 ms; a word onset is not, because the vowel after
    it is sustained."""
    blk = int(0.0025 * SR)
    n = len(x) // blk
    peaks = np.abs(x[:n * blk]).reshape(n, blk).max(1)
    gain = np.ones(n)
    for i in np.where(peaks > 0.05)[0]:
        left = peaks[max(0, i - 8):max(0, i - 1)]
        right = peaks[i + 3:i + 9]
        if not len(left) or not len(right):
            continue
        ref = max(left.max(), right.max())
        if peaks[i] > ratio * ref:
            gain[i] = min(gain[i], 1.5 * ref / peaks[i])
            print(f"  declick {i * blk / SR:7.3f}s  -{20 * np.log10(1 / gain[i]):.0f} dB")
    g = np.repeat(gain, blk)
    g = np.pad(g, (0, len(x) - len(g)), constant_values=1.0)
    k = int(0.004 * SR)                     # 4 ms smoothing, no new clicks
    g = np.convolve(g, np.ones(k) / k, mode="same")
    return x * np.minimum(g, 1.0)


def remap(x):
    """Source-timeline voice -> finished-video timeline (holds + tail)."""
    out = np.zeros(N)
    hold_from = {h["from"] for h in HOLDS}
    for s0, s1, o0, o1 in SEGMENTS:
        a, b = int(round(s0 * SR)), min(len(x), int(round(s1 * SR)))
        oa = int(round(o0 * SR))
        seg = x[a:b]
        if s0 in hold_from:
            # first half of the pause, room tone, second half
            half = len(seg) // 2
            fill = int(round((o1 - o0) * SR)) - len(seg)
            mid = seg[half // 2: half // 2 + max(half, int(0.25 * SR))]
            seg = np.concatenate([seg[:half], room_tone(mid, fill), seg[half:]])
        out[oa:oa + len(seg)] += seg[:N - oa]
    # the source stops right on "okay" -- ease out instead of a hard stop
    e = int(round(SPEECH_OUT_END * SR))
    f = int(0.12 * SR)
    out[e - f:e] *= np.linspace(1, 0, f) ** 2
    out[e:] = 0
    return out


# The source sits ~16 dB low, so it is lifted first to put the compressor
# thresholds where speech actually is. Two stages: a slow 2:1 for evenness and
# a fast one that only catches consonant peaks, so the final limiter barely
# works.
VOICE_CHAIN = ",".join([
    "highpass=f=80:p=2",
    "equalizer=f=240:t=q:w=1.0:g=-2.0",       # a little boxiness off
    "equalizer=f=3800:t=q:w=1.1:g=1.5",       # presence, not hype
    "deesser=i=0.30:m=0.5:f=0.5",
    "volume=15dB",
    "acompressor=threshold=-24dB:ratio=2:attack=12:release=220:knee=6",
    "acompressor=threshold=-12dB:ratio=5:attack=0.5:release=60:knee=4:detection=peak",
])


def process_voice():
    if not os.path.exists(RAW):
        extract()
    if not os.path.exists(DENOISED) or os.environ.get("BL_REDENOISE"):
        denoise()
    x, _ = sf.read(DENOISED, dtype="float64")
    y = remap(declick(x))
    tmp = VOICE.replace(".wav", "-pre.wav")
    sf.write(tmp, y.astype(np.float32), SR, subtype="FLOAT")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", tmp, "-af", VOICE_CHAIN,
                    "-ar", str(SR), "-c:a", "pcm_f32le", VOICE], check=True)
    os.remove(tmp)
    v, _ = sf.read(VOICE, dtype="float64")
    v = np.pad(v, (0, max(0, N - len(v))))[:N]
    v *= db(AUDIO["voice_lufs"] - lufs(v))
    sf.write(VOICE, v.astype(np.float32), SR, subtype="FLOAT")
    print("saved", os.path.relpath(VOICE, ROOT), f"({lufs(v):.1f} LUFS)")
    return v


# ===================================================================== score
NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7,
        "G#": 8, "A": 9, "A#": 10, "B": 11}


def hz(name):
    pitch, octave = name[:-1], int(name[-1])
    midi = 12 * (octave + 1) + NOTE[pitch]
    return 440.0 * 2 ** ((midi - 69) / 12)


O = out_time
# (finished-video time, voicing). D major, open voicings; the tonic is held
# back until "Sometimes I just need to let myself feel it".
PLAN = [
    (0.0,      ["B2", "F#3", "A3", "C#4", "D4"]),          # Bm9
    (O(11.9),  ["G2", "D3", "F#3", "A3", "B3"]),           # Gmaj9
    (O(20.9),  ["F#2", "C#3", "E3", "A3", "C#4"]),         # F#m7
    (O(28.3),  ["A2", "E3", "B3", "C#4", "E4"]),           # Aadd9
    (O(38.3),  ["B2", "F#3", "A3", "D4", "E4"]),           # Bm11
    (O(48.2),  ["G2", "D3", "A3", "B3", "F#4"]),           # Bali: Gmaj9, open
    (O(56.2),  ["E2", "B2", "G3", "D4", "F#4"]),           # Em9
    (O(62.0),  ["A2", "E3", "A3", "D4", "E4"]),            # Asus4
    (O(68.5),  ["D3", "A3", "E4", "F#4"]),                 # realisation: a glimpse of home
    (O(69.6),  ["B2", "F#3", "A3", "C#4", "D4"]),          # Bm9
    (O(79.2),  ["G2", "D3", "F#3", "B3"]),                 # people-pleasing: thin
    (O(88.6),  ["E2", "B2", "D3", "G3", "A3"]),            # Em7sus
    (O(97.4),  ["A2", "E3", "B3", "D4"]),                  # the line: suspended
    (O(101.4), ["G2", "D3", "A3", "B3", "D4"]),            # G6/9, warm
    (O(111.0), ["B2", "F#3", "A3", "D4"]),                 # Bm7
    (O(121.8), ["G2", "D3", "F#3", "A3", "B3"]),           # Gmaj9
    (O(131.2), ["E2", "B2", "F#3", "G3", "D4"]),           # Em9
    (O(134.9), ["A2", "E3", "G3", "C#4", "D4"]),           # A7sus
    (O(137.5), ["D2", "A2", "F#3", "A3", "C#4", "E4"]),    # Dmaj9 -- home
]

# Overall bed level over the story, 0..1 (pads). Piano and air have their own.
PAD_AUTO = [
    (0.0, 0.0), (5.0, 0.32), (16.0, 0.48), (O(47.6), 0.52),
    (O(49.5), 0.72), (O(68.3), 0.74), (O(68.9), 0.86), (O(69.7), 0.62),
    (O(79.0), 0.58), (O(81.5), 0.46), (O(97.0), 0.40), (O(98.0), 0.30),
    (O(101.0), 0.32), (O(101.6), 0.60), (O(104.0), 0.55),
    (O(131.0), 0.58), (O(137.4), 0.64), (O(138.6), 0.78),
    (END_CARD_START, 0.82), (TOTAL_DUR - 3.4, 0.80), (TOTAL_DUR, 0.0),
]
SHIMMER_AUTO = [(0, 0), (O(48.0), 0), (O(52.0), 0.55), (O(67.5), 0.6),
                (O(69.2), 0.7), (O(70.5), 0.0), (O(137.2), 0.0),
                (O(140.0), 0.42), (TOTAL_DUR - 3.0, 0.4), (TOTAL_DUR, 0)]
AIR_AUTO = [(0, 0), (O(48.0), 0), (O(53.0), 1.0), (O(68.0), 1.0),
            (O(71.0), 0.0), (O(136.0), 0.0), (O(141.0), 0.7),
            (TOTAL_DUR - 2.5, 0.6), (TOTAL_DUR, 0)]

t_all = np.arange(N) / SR
rng = np.random.RandomState(23)


def automation(pts, smooth_s=0.6):
    xs, ys = zip(*pts)
    v = np.interp(t_all, xs, ys)
    k = int(smooth_s * SR)
    c = np.cumsum(np.insert(v, 0, 0))
    sm = (c[k:] - c[:-k]) / k
    return np.concatenate([np.full(k - 1, sm[0]), sm])


def lowpass(x, f, order=2):
    return sosfilt(butter(order, f, "low", fs=SR, output="sos"), x, axis=0)


def chord_spans():
    spans = []
    for i, (start, notes) in enumerate(PLAN):
        end = PLAN[i + 1][0] if i + 1 < len(PLAN) else TOTAL_DUR
        spans.append((start, end, notes))
    return spans


def pad_layer(octave_up=False):
    """Detuned additive voices per chord, long crossfades between chords."""
    out = np.zeros((N, 2))
    for start, end, notes in chord_spans():
        a = max(0.0, start - 2.0)
        b = min(TOTAL_DUR, end + 3.0)
        i0, i1 = int(a * SR), int(b * SR)
        t = t_all[i0:i1]
        fin = np.clip((t - a) / 3.2, 0, 1)
        fout = np.clip((b - t) / 3.4, 0, 1)
        env = np.sin(fin * np.pi / 2) ** 2 * np.sin(fout * np.pi / 2) ** 2
        if start == 0.0:
            env = np.clip(t / 4.0, 0, 1) ** 2 * np.sin(fout * np.pi / 2) ** 2
        voices = notes[-2:] if octave_up else notes
        for j, name in enumerate(voices):
            f = hz(name) * (2 if octave_up else 1)
            gain = (0.30 if j == 0 else 0.22 / (1 + 0.3 * j)) * (0.5 if octave_up else 1)
            for ch, cents in ((0, -5.0), (1, 4.0)):
                det = 2 ** (cents / 1200)
                ph = rng.uniform(0, 2 * np.pi)
                sig = np.zeros_like(t)
                for k in range(1, 5):
                    sig += np.sin(2 * np.pi * f * det * k * t + ph * k) / k ** 2.4
                # each voice breathes on its own slow cycle
                lfo = 1 + 0.12 * np.sin(2 * np.pi * (0.05 + 0.013 * j) * t + ph)
                out[i0:i1, ch] += gain * env * sig * lfo
    return lowpass(out, 2400 if not octave_up else 4200)


def root_layer():
    """Very low sine on the chord root -- warmth, felt more than heard."""
    out = np.zeros(N)
    for start, end, notes in chord_spans():
        a, b = max(0.0, start - 1.5), min(TOTAL_DUR, end + 2.0)
        i0, i1 = int(a * SR), int(b * SR)
        t = t_all[i0:i1]
        env = (np.sin(np.clip((t - a) / 2.5, 0, 1) * np.pi / 2) ** 2 *
               np.sin(np.clip((b - t) / 2.5, 0, 1) * np.pi / 2) ** 2)
        f = hz(notes[0])
        while f > 70:
            f /= 2
        out[i0:i1] += 0.5 * env * np.sin(2 * np.pi * f * t)
    return np.stack([out, out], axis=1)


def felt_piano(f, vel, dur=7.0):
    """Soft felt-piano tone: slightly inharmonic partials, faster decay up
    the series, two detuned strings, a muted hammer."""
    t = np.arange(int(dur * SR)) / SR
    B = 0.00035
    x = np.zeros_like(t)
    for k in range(1, 11):
        fk = k * f * np.sqrt(1 + B * k * k)
        if fk > 7000:
            break
        amp = k ** -1.7 * np.exp(-(k - 1) * (1.15 - vel))
        tau = 3.4 * (220 / f) ** 0.3 / (1 + 0.55 * (k - 1))
        env = 0.72 * np.exp(-t / tau) + 0.28 * np.exp(-t / (tau * 3.5))
        for cents in (-0.9, 0.9):
            x += amp * env * np.sin(2 * np.pi * fk * 2 ** (cents / 1200) * t
                                    + rng.uniform(0, 2 * np.pi))
    x *= 1 - np.exp(-t / 0.007)
    hammer = lowpass(rng.randn(len(t)), 900) * np.exp(-t / 0.018) * 0.06
    x = lowpass(x + hammer, 2600)
    x[-int(0.6 * SR):] *= np.linspace(1, 0, int(0.6 * SR))
    return x * vel


def chord_at(t):
    cur = PLAN[0][1]
    for start, notes in PLAN:
        if start <= t:
            cur = notes
    return cur


def pauses():
    """(start, end) of every natural pause >= 0.45 s, finished-video time."""
    with open(WORDS_PATH) as f:
        words = json.load(f)["words"]
    out = []
    for a, b in zip(words, words[1:]):
        if b["s"] - a["e"] >= 0.45:
            out.append((O(a["e"]), O(b["s"])))
    out.append((SPEECH_OUT_END, TOTAL_DUR))
    return out


def piano_events():
    """Notes go in the pauses. Density follows the story: almost nothing at
    the start, a little more in Bali, held back for the people-pleasing
    example, and a resolved arpeggio at the end."""
    ev = []
    bali0, bali1 = O(48.2), O(69.6)
    pp0, pp1 = O(79.2), O(101.0)
    for k, (s, e) in enumerate(pauses()):
        if s < 15.0:                         # opening: atmosphere only
            continue
        span = e - s
        top = chord_at(s + 0.3)
        hi = [hz(n) * 2 for n in top[-3:]]
        if bali0 <= s < bali1:
            ev.append((s + 0.12, hi[k % 3], 0.42))
            if span > 0.9:
                ev.append((s + 0.62, hi[(k + 1) % 3], 0.34))
        elif pp0 <= s < pp1:
            continue                          # let the example speak
        elif s < bali0:
            if k % 2 == 0:
                ev.append((s + 0.1, hi[k % 3], 0.36))
        elif s >= O(137.0):
            continue                          # ending handled below
        elif k % 2 == 0 or span > 1.2:
            ev.append((s + 0.1, hi[k % 3], 0.38))
    # the realisation: a slow rising figure in the lengthened pause
    r = O(68.5)
    for i, n in enumerate(["D5", "F#5", "A5"]):
        ev.append((r + 0.15 + i * 0.55, hz(n), 0.36 - i * 0.03))
    # after "to go away": one low, warm dyad
    g = O(101.1)
    ev += [(g + 0.2, hz("D4"), 0.40), (g + 0.24, hz("B4"), 0.30)]
    # home: arpeggio under "let myself feel it", then into the end card
    h = O(139.5)
    ev += [(h, hz("D4"), 0.34), (h + 0.06, hz("A4"), 0.28)]
    ev += [(SPEECH_OUT_END + 0.35, hz("F#5"), 0.36),
           (SPEECH_OUT_END + 1.25, hz("A5"), 0.30),
           (END_CARD_START + 1.1, hz("E5"), 0.30),
           (END_CARD_START + 2.6, hz("D5"), 0.32)]
    return sorted(ev)


def piano_layer():
    out = np.zeros((N + 8 * SR, 2))
    for i, (t0, f, vel) in enumerate(piano_events()):
        x = felt_piano(f, vel)
        pan = 0.5 + 0.14 * np.sin(i * 1.7)
        i0 = int(t0 * SR)
        out[i0:i0 + len(x), 0] += x * (1 - pan) * 2
        out[i0:i0 + len(x), 1] += x * pan * 2
    return out[:N]


def air_layer():
    """Band-limited noise swelling on a slow breath cycle -- organic, not
    a sound effect."""
    n = rng.randn(N, 2)
    n = sosfilt(butter(2, [350, 2400], "band", fs=SR, output="sos"), n, axis=0)
    cycle = 0.5 - 0.5 * np.cos(2 * np.pi * t_all / 9.5)
    return n * (0.15 + 0.85 * cycle)[:, None] * 0.05


def reverb(x, seconds=4.2, wet=0.38, seed=11):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = np.empty_like(x)
    size = 1 << int(np.ceil(np.log2(len(x) + n)))
    for ch in range(x.shape[1]):
        ir = np.random.RandomState(seed + ch).randn(n) * np.exp(-t / (seconds / 6.9))
        ir = lowpass(ir, 5000)
        ir[: int(0.02 * SR)] = 0
        ir /= np.sqrt((ir ** 2).sum())
        y = np.fft.irfft(np.fft.rfft(x[:, ch], size) * np.fft.rfft(ir, size), size)
        out[:, ch] = x[:, ch] + wet * y[: len(x)]
    return out


def build_score():
    pad = pad_layer() * automation(PAD_AUTO)[:, None]
    shimmer = pad_layer(octave_up=True) * automation(SHIMMER_AUTO)[:, None]
    root = root_layer() * 0.16 * automation(PAD_AUTO)[:, None]
    air = air_layer() * automation(AIR_AUTO)[:, None]
    piano = piano_layer() * 0.55
    dry = pad + root + piano * 0.75
    wet_more = reverb(shimmer + air + piano * 0.6, seconds=6.0, wet=0.75, seed=31)
    mix = reverb(dry, wet=0.36) + wet_more * 0.8
    tail = np.clip((TOTAL_DUR - t_all) / 3.2, 0, 1) ** 1.6
    mix *= tail[:, None]
    return mix * (0.5 / np.max(np.abs(mix)))


def load_track(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "2",
                          "-ar", str(SR), "-f", "f32le", "-"],
                         check=True, capture_output=True).stdout
    x = np.frombuffer(raw, dtype="<f4").reshape(-1, 2).astype(np.float64)
    x = np.pad(x, ((0, max(0, N - len(x))), (0, 0)))[:N]
    fin = np.clip(t_all / 2.0, 0, 1)
    fout = np.clip((TOTAL_DUR - t_all) / 3.5, 0, 1) ** 1.5
    return x * (fin * fout)[:, None]


# ======================================================================= mix
def duck_curve(voice, duck_db):
    """Gain curve that dips the music while he is speaking. Slow release so
    the music swells back in each pause rather than pumping."""
    hop = int(0.02 * SR)
    frames = len(voice) // hop
    rms = np.sqrt((voice[:frames * hop].reshape(frames, hop) ** 2).mean(1) + 1e-12)
    active = (20 * np.log10(rms) > -42).astype(float)
    g = np.zeros(frames)
    a_att, a_rel = np.exp(-1 / (0.08 / 0.02)), np.exp(-1 / (0.55 / 0.02))
    level = 0.0
    for i, v in enumerate(active):
        coef = a_att if v > level else a_rel
        level = coef * level + (1 - coef) * v
        g[i] = level
    g = np.repeat(g, hop)
    g = np.pad(g, (0, N - len(g)), mode="edge")[:N]
    return db(-duck_db * g)


def main():
    voice = process_voice()

    track = MUSIC_CFG.get("track")
    if track:
        music = load_track(os.path.join(REEL_DIR, track))
        print("music: using", track)
    else:
        music = build_score()
        print("music: original generated score")
    music *= db(AUDIO["music_lufs"] - lufs(music) + MUSIC_CFG.get("gain_db", 0))
    sf.write(MUSIC, music.astype(np.float32), SR, subtype="FLOAT")
    print("saved", os.path.relpath(MUSIC, ROOT), f"({lufs(music):.1f} LUFS)")

    music *= duck_curve(voice, MUSIC_CFG.get("duck_db", 5.0))[:, None]
    mix = voice[:, None] + music
    mix *= db(FINAL_LUFS - lufs(mix))
    tmp = MIX.replace(".wav", "-pre.wav")
    sf.write(tmp, mix.astype(np.float32), SR, subtype="FLOAT")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", tmp,
                    "-af", "alimiter=limit=0.891:attack=3:release=60:level=false",
                    "-ar", str(SR), "-c:a", "pcm_s24le", MIX], check=True)
    os.remove(tmp)
    out, _ = sf.read(MIX)
    peak = 20 * np.log10(np.max(np.abs(out)))
    print("saved", os.path.relpath(MIX, ROOT),
          f"({lufs(out):.1f} LUFS, peak {peak:.1f} dBFS, {TOTAL_DUR:.2f}s)")


if __name__ == "__main__":
    main()
