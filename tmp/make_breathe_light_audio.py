#!/usr/bin/env python3
"""
Breathe Light (16:9 YouTube practice) -- voice edit, original score, final mix.

  tmp/.venv-dsp/bin/python tmp/clean_breathe_light_voice.py   # once: noise + echo
  tmp/.venv-dsp/bin/python tmp/make_breathe_light_audio.py    # edit + score + mix

Inputs
  tmp/bl-voice-clean.wav          cleaned voice, 48 kHz mono (source timeline)
  tmp/breathe-light-words.json    faster-whisper word stamps (source timeline)

Outputs -> assets/social/youtube/relax/breathe-light/
  breathe-light-voice.wav     edited, processed voice stem   (final timeline)
  breathe-light-music.wav     score stem, ducked as in the mix (final timeline)
  breathe-light-mix.wav       final master, -14 LUFS, true peak < -1 dBTP
  breathe-light.srt           subtitles
  breathe-light-edit.json     edit decision list + timeline that the renderer reads

The recording is the source of truth. Nothing is time-stretched: the edit only
lengthens existing pauses, always at the quietest point of the pause, with
short fades, so every word and breath keeps its own timing.

BOLT windows: the timer starts on the true acoustic end of "...begin." and the
voice resumes exactly BOLT_RESUME seconds later (60 s window + timer fade).
"""
import json
import os
import subprocess

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.signal import butter, oaconvolve, sosfilt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "assets", "social", "youtube", "relax", "breathe-light")
CLEAN = os.path.join(HERE, "bl-voice-clean.wav")
WORDS = os.path.join(HERE, "breathe-light-words.json")
EDIT_JSON = os.path.join(OUT_DIR, "breathe-light-edit.json")

SR = 48000
PREROLL = 13.0           # safety notice + title before the first word
OUTRO = 17.0             # landscape, closing title, musical resolution
BOLT_WINDOW = 60.0
BOLT_RESUME = 61.5       # voice returns 1.5 s after the window, once the timer has faded

TARGET_LUFS = -14.0
TRUE_PEAK = -1.2         # dBTP ceiling (spec: below -1)
VOICE_LUFS = -16.0       # voice stem before the final gain
MUSIC_LUFS = -23.0       # music stem measured *before* ducking
DUCK_DB = -9.0           # extra music dip while the voice is speaking

# --------------------------------------------------------------------- edit
# (word that ends the phrase, its approximate source end time, target pause in
# seconds from the end of that word to the start of the next one).
GAPS = [
    ("normal", 85.6, 3.0),          # after BOLT 1: settle before Notice
    # NOTICE
    ("abdomen", 116.3, 10.0),       # "...notice where you feel the movement"
    ("breathing", 120.1, 6.0),      # "Can you hear yourself breathing?"
    ("need", 130.4, 9.5),           # "...more effort than you need?"
    # SOFTEN
    ("nostrils", 181.1, 3.0),       # attention to the nostrils...
    ("out", 190.1, 18.0),           # ...cooler air in, warmer air out
    ("naturally", 205.9, 2.0),
    ("comfortable", 212.7, 18.0),   # "Allow the inhale to arrive gently..." "Quiet, soft and comfortable."
    ("more", 229.3, 5.0),
    ("breath", 236.5, 7.0),
    ("like", 259.0, 6.0),
    ("breathe", 271.0, 28.0),       # "Let your body breathe."
    # LET GO
    ("notice", 297.7, 21.0),        # "Just notice." -- the long uninterrupted stretch
    ("fine", 317.6, 8.0),           # "Whatever you notice is fine."
    # closing
    ("same", 364.2, 4.0),           # time to note the second score
]
BOLTS = [("begin", 48.4, "now", 78.7), ("begin", 353.2, "now", 358.0)]

# section starts, keyed by the first source word of each section
SECTION_STARTS = [
    ("intro", None),
    ("bolt1", ("take", 19.0)),
    ("notice", ("gently", 87.0)),
    ("soften", ("now", 137.9)),
    ("letgo", ("now", 283.4)),
    ("bolt2", ("now", 322.0)),
    ("closing", ("remember", 366.1)),
]


def norm(w):
    return w.lower().strip(".,?!;:'\"…")


def load_words():
    d = json.load(open(WORDS))
    words = [w for w in d["words"] if not (48.7 <= w["s"] < 49.0)]   # phantom "Ready?"
    return words


def find_word(words, text, near, key="e", tol=2.5):
    best = None
    for i, w in enumerate(words):
        if norm(w["w"]) == text and abs(w[key] - near) < tol:
            if best is None or abs(w[key] - near) < abs(words[best][key] - near):
                best = i
    if best is None:
        raise ValueError(f"word {text!r} near {near}s not found")
    return best


def energy_db(x, hop):
    n = len(x) // hop
    return 10 * np.log10((x[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)


class Editor:
    """Source -> final timeline mapping built from silence insertions."""

    def __init__(self, voice, words):
        self.v = voice
        self.words = words
        self.e = energy_db(voice, SR // 100)          # 10 ms frames
        self.inserts = []                             # (src_time, seconds)

    def true_end(self, t, thr=-58.0, quiet=0.30):
        i = max(0, int((t - 0.5) * 100))
        k = int(quiet * 100)
        while i < len(self.e) - k:
            if (self.e[i:i + k] < thr).all():
                return i / 100
            i += 1
        return t

    def true_start(self, t, thr=-58.0):
        i = int((t - 0.8) * 100)
        while i < int((t + 0.5) * 100):
            if self.e[i] >= thr and self.e[i + 1] >= thr:
                return i / 100
            i += 1
        return t

    def cut_point(self, a, b):
        """Quietest 200 ms inside the pause, clear of both words."""
        lo, hi = a + 0.35, b - 0.6
        if hi - lo < 0.2:
            return (a + b) / 2
        e = self.e[int(lo * 100):int(hi * 100)]
        sm = np.convolve(e, np.ones(20) / 20, mode="same")
        return lo + int(np.argmin(sm)) / 100

    def extend(self, a, b, target):
        add = target - (b - a)
        if add > 0.05:
            self.inserts.append((self.cut_point(a, b), add))
        return add

    def map(self, t):
        return PREROLL + t + sum(L for c, L in self.inserts if c <= t)

    def render(self, src_dur):
        fade = int(0.2 * SR)
        out, pos = [], 0
        for c, L in sorted(self.inserts):
            ci = int(c * SR)
            seg = self.v[pos:ci].copy()
            seg[-fade:] *= np.cos(np.linspace(0, np.pi / 2, fade)) ** 2
            if pos > 0:
                seg[:fade] *= np.sin(np.linspace(0, np.pi / 2, fade)) ** 2
            out += [seg, np.zeros(int(round(L * SR)))]
            pos = ci
        tail = self.v[pos:int(src_dur * SR)].copy()
        tail[:fade] *= np.sin(np.linspace(0, np.pi / 2, fade)) ** 2
        tail[-int(1.0 * SR):] *= np.linspace(1, 0, int(1.0 * SR))
        out.append(tail)
        body = np.concatenate(out)
        return np.concatenate([np.zeros(int(PREROLL * SR)), body,
                               np.zeros(int(OUTRO * SR))])


def build_edit(voice, words):
    ed = Editor(voice, words)
    bolts = []
    for w0, t0, w1, t1 in BOLTS:
        i = find_word(words, w0, t0 + 0.4)
        j = find_word(words, w1, t1, key="s")
        end = ed.true_end(words[i]["e"])
        on = ed.true_start(words[j]["s"])
        ed.extend(end, on, BOLT_RESUME)
        bolts.append({"src_end": end, "src_resume": on})
    for text, near, target in GAPS:
        i = find_word(words, text, near)
        a = ed.true_end(words[i]["e"])
        b = ed.true_start(words[i + 1]["s"])
        ed.extend(a, b, target)

    for b, (w0, t0, _, _) in zip(bolts, BOLTS):
        b["timer_start"] = round(ed.map(b["src_end"]), 3)
        b["timer_end"] = round(b["timer_start"] + BOLT_WINDOW, 3)
        b["voice_resume"] = round(ed.map(b["src_resume"]), 3)
        # timer card fades in on "Ready?" (bolt 1) / "Take a nice big inhale" (bolt 2)
        cue = ("ready", 42.6) if t0 < 100 else ("take", 347.2)
        b["card_in"] = round(ed.map(words[find_word(words, *cue, key="s")]["s"]) - 0.4, 3)

    src_dur = len(voice) / SR
    total = ed.map(src_dur) + OUTRO
    sections = []
    for name, ref in SECTION_STARTS:
        if ref is None:
            start = 0.0
        else:
            k = find_word(words, ref[0], ref[1], key="s")
            prev_end = ed.map(words[k - 1]["e"])
            start = (prev_end + ed.map(words[k]["s"])) / 2
        sections.append({"name": name, "start": round(start, 3)})
    for s, n in zip(sections, sections[1:] + [{"start": total}]):
        s["end"] = round(n["start"], 3)

    mapped = [{"w": w["w"], "s": round(ed.map(w["s"]), 3), "e": round(ed.map(w["e"]), 3)}
              for w in words]
    last_word_end = mapped[-1]["e"]
    return ed, {
        "total": round(total, 3), "preroll": PREROLL, "fps_hint": 24,
        "voice_start": PREROLL, "last_word_end": last_word_end,
        "bolts": bolts, "sections": sections,
        "inserts": [{"src_time": round(c, 3), "out_time": round(ed.map(c), 3),
                     "added": round(L, 3)} for c, L in sorted(ed.inserts)],
        "words": mapped,
    }


# ---------------------------------------------------------------- subtitles
def fmt_ts(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


FIXES = {"bolt": "BOLT"}


def _text(ws):
    return " ".join(FIXES.get(w["w"].lower(), w["w"]) for w in ws)


def _split(ws, max_chars):
    """Split a sentence into readable cues, preferring commas, then the
    most balanced word boundary."""
    if len(_text(ws)) <= max_chars:
        return [ws]
    best = None
    for i in range(1, len(ws)):
        a, b = _text(ws[:i]), _text(ws[i:])
        score = abs(len(a) - len(b)) - (25 if ws[i - 1]["w"][-1:] == "," else 0)
        if best is None or score < best[0]:
            best = (score, i)
    i = best[1]
    return _split(ws[:i], max_chars) + _split(ws[i:], max_chars)


def subtitle_cues(words, max_chars=74):
    sentences, cur = [], []
    for w in words:
        if cur and w["s"] - cur[-1]["e"] > 1.5:
            sentences.append(cur)
            cur = []
        cur.append(w)
        if w["w"][-1:] in ".?!":
            sentences.append(cur)
            cur = []
    if cur:
        sentences.append(cur)
    # merge very short sentences ("Ready?", "Inhale.") with their neighbours
    merged = []
    for s in sentences:
        if (merged and len(_text(merged[-1]) + _text(s)) < 44
                and s[0]["s"] - merged[-1][-1]["e"] < 2.5):
            merged[-1] = merged[-1] + s
        else:
            merged.append(s)
    cues = []
    for s in merged:
        for part in _split(s, max_chars):
            cues.append([part[0]["s"], part[-1]["e"], _text(part)])
    for i, c in enumerate(cues):
        nxt = cues[i + 1][0] if i + 1 < len(cues) else c[1] + 3
        c[1] = min(max(c[1] + 0.6, c[0] + 1.2), nxt - 0.05)
    return cues


def two_lines(text, width=42):
    if len(text) <= width:
        return text
    words = text.split()
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        score = abs(len(a) - len(b)) + (0 if len(a) <= len(b) else 3)
        if best is None or score < best[0]:
            best = (score, a + "\n" + b)
    return best[1]


def write_srt(cues, path):
    with open(path, "w") as f:
        for i, (s, e, text) in enumerate(cues, 1):
            f.write(f"{i}\n{fmt_ts(s)} --> {fmt_ts(e)}\n{two_lines(text)}\n\n")


# ------------------------------------------------------------------- voice
VOICE_CHAIN = (
    "highpass=f=75:p=2,"
    "equalizer=f=170:t=q:w=0.9:g=1.5,"         # warmth DeepFilterNet thins slightly
    "equalizer=f=420:t=q:w=1.2:g=-1.5,"        # boxiness of the room
    "equalizer=f=3200:t=q:w=1.0:g=1.2,"        # presence / intelligibility
    "deesser=i=0.35:m=0.5:f=0.5,"
    "acompressor=threshold=-28dB:ratio=2.6:attack=10:release=220:knee=5:makeup=2.5"
)


def process_voice(x):
    tmp_in = os.path.join(HERE, "bl-voice-edit-raw.wav")
    tmp_out = os.path.join(HERE, "bl-voice-edit-proc.wav")
    sf.write(tmp_in, x.astype(np.float32), SR, subtype="FLOAT")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", tmp_in, "-af", VOICE_CHAIN,
                    "-c:a", "pcm_f32le", tmp_out], check=True)
    y, _ = sf.read(tmp_out)
    return y[:len(x)]


def voice_activity(v):
    """0..1 smoothed 'someone is speaking' curve at audio rate."""
    hop = SR // 100
    e = energy_db(v, hop)
    act = (e > -48).astype(float)
    # hold 0.6 s, attack 0.35 s, release 2.2 s
    held = np.convolve(act, np.ones(60), mode="full")[:len(act)] > 0
    env = np.zeros(len(e))
    a_up, a_dn = 1 - np.exp(-1 / 35), 1 - np.exp(-1 / 220)
    s = 0.0
    for i, h in enumerate(held):
        s += (h - s) * (a_up if h > s else a_dn)
        env[i] = s
    env = np.repeat(env, hop)
    return np.pad(env, (0, len(v) - len(env)), mode="edge")


# ------------------------------------------------------------------- music
# An original score, synthesised here so the soundtrack is fully owned and
# YouTube-safe. Key of D-flat major; felt piano, warm pads, a low cello-like
# line, air. Harmony moves slowly (one chord every 9-11 s) and the arrangement
# follows the practice: grounded -> flowing -> open -> resolved.
def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# name: (bass, voicing)
CH = {
    "I":    (37, [44, 53, 60, 63, 68]),        # Dbmaj9
    "I3":   (41, [49, 56, 60, 63, 68]),        # Db/F
    "IV":   (42, [49, 53, 58, 61, 68]),        # Gbmaj9
    "vi":   (34, [49, 53, 56, 60, 65]),        # Bbm9
    "V":    (32, [51, 56, 58, 61, 63]),        # Absus
    "ii":   (39, [54, 58, 61, 65, 70]),        # Ebm9
    "iii":  (41, [48, 56, 60, 63, 67]),        # Fm7
    "iv":   (42, [45, 49, 54, 57, 61]),        # Gbm6 (borrowed -- the warm ache)
    "Ipad": (37, [49, 53, 56, 60, 65, 68]),    # final open Db add9
}
PENTA = {1, 3, 5, 8, 10}                        # Db Eb F Ab Bb

PROG = {
    "intro":   (["I", "IV", "I", "IV"], 10.5),
    "bolt1":   (["I", "IV", "vi", "IV"], 10.5),
    "notice":  (["I", "IV", "vi", "IV", "I", "iii", "IV", "V"], 10.0),
    "soften":  (["I", "vi", "IV", "V", "I3", "ii", "IV", "V",
                 "vi", "iii", "IV", "I", "ii", "vi", "IV", "V"], 9.0),
    "letgo":   (["IV", "I3", "vi", "iii", "IV", "iv", "I", "I"], 10.0),
    "bolt2":   (["I", "IV", "I", "IV"], 10.5),
    "closing": (["IV", "vi", "IV", "iv", "Ipad"], 9.0),
}

# 0..1 layer levels per section (crossfaded across boundaries)
LEVELS = {
    #           pad  low  chord melody arp  shimmer air
    "intro":   (0.80, 0.0, 0.35, 0.35, 0.0, 0.0, 0.5),
    "bolt1":   (0.85, 0.3, 0.30, 0.30, 0.0, 0.0, 0.6),
    "notice":  (0.90, 0.6, 0.55, 0.55, 0.0, 0.15, 0.6),
    "soften":  (0.95, 0.8, 0.65, 0.80, 0.55, 0.45, 0.7),
    "letgo":   (1.00, 0.9, 0.70, 0.90, 0.35, 0.75, 0.8),
    "bolt2":   (0.85, 0.5, 0.35, 0.35, 0.0, 0.25, 0.6),
    "closing": (0.95, 0.7, 0.65, 0.70, 0.0, 0.55, 0.6),
}
LAYERS = ["pad", "low", "chord", "melody", "arp", "shimmer", "air"]
MELODY_NOTES = {"intro": 1, "bolt1": 1, "notice": 2, "soften": 3, "letgo": 3,
                "bolt2": 1, "closing": 3}
MELODY_RANGE = {"intro": (68, 77), "bolt1": (68, 77), "notice": (68, 79),
                "soften": (70, 82), "letgo": (72, 85), "bolt2": (68, 77),
                "closing": (68, 80)}

rng = np.random.RandomState(20261102)


def section_at(sections, t):
    for s in sections:
        if s["start"] <= t < s["end"]:
            return s["name"]
    return sections[-1]["name"]


def layer_curve(sections, n, idx, xfade=8.0):
    pts = []
    for s in sections:
        lv = LEVELS[s["name"]][idx]
        pts += [(s["start"] + xfade / 2, lv), (s["end"] - xfade / 2, lv)]
    xs, ys = zip(*pts)
    t = np.arange(n) / SR
    return np.interp(t, xs, ys).astype(np.float32)


def chord_schedule(sections, total):
    sched, t, pos = [], 0.0, {k: 0 for k in PROG}
    end_music = total - 2.0
    while t < end_music:
        sec = section_at(sections, t + 0.01)
        names, dur = PROG[sec]
        name = names[pos[sec] % len(names)]
        pos[sec] += 1
        if sec == "closing" and name == "Ipad":
            dur = end_music - t + 2.0                       # ring out to the end
        dur = min(dur, total - t)
        sched.append((t, dur, name, sec))
        t += dur
    return sched


_piano_cache = {}


def piano(m, vel, length=8.0):
    """Felt-piano tone: inharmonic partials, two detuned strings per note,
    steep high-partial rolloff (felt hammer), two-stage decay."""
    key = (m, round(vel, 2))
    if key in _piano_cache:
        return _piano_cache[key]
    f0 = hz(m)
    n = int(length * SR)
    t = np.arange(n, dtype=np.float32) / SR
    out = np.zeros(n, np.float32)
    B = 0.00032
    tau = 1.0 + 3.2 * (261.6 / f0) ** 0.55
    for k in range(1, int(min(12, 7000 / f0)) + 1):
        fk = k * f0 * np.sqrt(1 + B * k * k)
        amp = k ** -1.3 * np.exp(-(k - 1) * (0.62 - 0.3 * vel))
        tk = tau / (1 + 0.45 * (k - 1))
        env = 0.55 * np.exp(-t / (0.22 * tk)) + 0.45 * np.exp(-t / tk)
        ph = rng.uniform(0, 2 * np.pi, 2)
        s = (np.sin(2 * np.pi * fk * t + ph[0]) +
             np.sin(2 * np.pi * fk * (1 + 0.0006) * t + ph[1]))
        out += (amp * 0.5) * env * s
    att = 1 - np.exp(-t / 0.006)
    thump = np.exp(-t / 0.03) * np.sin(2 * np.pi * f0 * 0.5 * t) * 0.15
    rel = np.clip((length - t) / 0.6, 0, 1)
    y = (out + thump) * att * rel * vel
    _piano_cache[key] = y
    return y


def add(buf, sig, t0, gain=1.0, pan=0.0):
    i0 = int(t0 * SR)
    if i0 >= len(buf):
        return
    s = sig[:len(buf) - i0]
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[i0:i0 + len(s), 0] += s * gain * l
    buf[i0:i0 + len(s), 1] += s * gain * r


def pad_tone(m, dur, att=3.5, rel=4.5, bright=1.0):
    f0 = hz(m)
    n = int((dur + rel) * SR)
    t = np.arange(n, dtype=np.float32) / SR
    out = np.zeros((n, 2), np.float32)
    for v, (det, pan) in enumerate(((-0.0026, -0.6), (0.0, 0.0), (0.0029, 0.6))):
        s = np.zeros(n, np.float32)
        for k in range(1, 9):
            if k * f0 > 5000:
                break
            amp = (1 / k) * np.exp(-k * f0 / (850 * bright))
            s += amp * np.sin(2 * np.pi * f0 * k * (1 + det) * t + rng.uniform(0, 6.28))
        l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        out[:, 0] += s * l
        out[:, 1] += s * r
    a = np.clip(t / att, 0, 1)
    env = np.sin(a * np.pi / 2) ** 2 * np.clip((dur + rel - t) / rel, 0, 1) ** 1.6
    lfo = 1 + 0.07 * np.sin(2 * np.pi * rng.uniform(0.05, 0.11) * t + rng.uniform(0, 6))
    return out * (env * lfo)[:, None]


def low_tone(m, dur, att=4.0, rel=5.0):
    """Cello-ish sustained bass: few partials, slow bow, gentle vibrato."""
    f0 = hz(m + 12) if m < 36 else hz(m)
    n = int((dur + rel) * SR)
    t = np.arange(n, dtype=np.float32) / SR
    vib = 1 + 0.0022 * np.sin(2 * np.pi * 4.6 * t) * np.clip((t - 1.5) / 3, 0, 1)
    ph = 2 * np.pi * f0 * np.cumsum(vib) / SR
    s = (np.sin(ph) + 0.45 * np.sin(2 * ph + 0.3) + 0.2 * np.sin(3 * ph + 1.1)
         + 0.08 * np.sin(4 * ph))
    a = np.clip(t / att, 0, 1)
    env = np.sin(a * np.pi / 2) ** 2 * np.clip((dur + rel - t) / rel, 0, 1) ** 1.5
    return (s * env).astype(np.float32)


def air_layer(n):
    """Soft breathy noise band that swells very slowly -- wind over water."""
    noise = rng.randn(n, 2).astype(np.float32)
    sos = butter(2, [1800, 6500], btype="band", fs=SR, output="sos")
    x = sosfilt(sos, noise, axis=0).astype(np.float32)
    t = np.arange(n) / SR
    sw = 0.55 + 0.45 * np.sin(2 * np.pi * t / 23.0) * np.sin(2 * np.pi * t / 61.0 + 1.0)
    return x * sw[:, None].astype(np.float32)


def reverb_ir(seconds, damp_hz, seed):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    r = np.random.RandomState(seed)
    ir = np.zeros((n, 2), np.float32)
    for ch in range(2):
        x = r.randn(n) * np.exp(-6.9 * t / seconds)
        # progressively darker tail: blend a lowpassed copy in over time
        sos = butter(1, damp_hz, fs=SR, output="sos")
        lp = sosfilt(sos, x)
        w = np.clip(t / (seconds * 0.4), 0, 1)
        y = (1 - w) * x + w * lp * 2.0
        y[: int(0.022 * SR)] = 0
        ir[:, ch] = y / np.sqrt((y ** 2).sum())
    return ir


def convolve(x, ir):
    return np.stack([oaconvolve(x[:, c], ir[:, c])[:len(x)] for c in range(2)],
                    axis=1).astype(np.float32)


def build_music(sections, total, vact):
    n = int(total * SR)
    lv = {name: layer_curve(sections, n, i) for i, name in enumerate(LAYERS)}
    sched = chord_schedule(sections, total)
    pad = np.zeros((n, 2), np.float32)
    low = np.zeros((n, 2), np.float32)
    keys = np.zeros((n, 2), np.float32)          # chords + melody + arp (piano)
    shim = np.zeros((n, 2), np.float32)

    def act(t):
        i = min(int(t * SR), len(vact) - 1)
        return vact[i]

    prev = 75
    for ci, (t0, dur, name, sec) in enumerate(sched):
        bass, voicing = CH[name]
        last = ci == len(sched) - 1
        # pad
        for m in voicing:
            add_sig = pad_tone(m, dur + 1.2, att=3.5 if ci else 6.0,
                               rel=7.0 if last else 4.5)
            i0 = max(0, int((t0 - 1.0) * SR))
            seg = add_sig[:n - i0]
            pad[i0:i0 + len(seg)] += seg * 0.10
        # low line
        lo = low_tone(bass, dur + 0.8, rel=6.0 if last else 5.0)
        add(low, lo, max(0, t0 - 0.6), 0.16, -0.1)
        # shimmer: top two voicing notes an octave up, very bright, mostly reverb
        for m in voicing[-2:]:
            sh = pad_tone(m + 12, dur + 1.0, att=5.0, rel=6.0, bright=1.8)
            i0 = max(0, int((t0 - 0.5) * SR))
            seg = sh[:n - i0]
            shim[i0:i0 + len(seg)] += seg * 0.05
        # rolled piano chord on the change
        lvl = lv["chord"][min(int(t0 * SR), n - 1)]
        if lvl > 0.05 and not (sec in ("intro", "bolt1", "bolt2") and ci % 2):
            for k, m in enumerate([x for x in voicing if x >= 49]):
                add(keys, piano(m, 0.20 + 0.05 * (k == 0)), t0 + 0.05 + 0.085 * k,
                    lvl * 0.9, -0.3 + 0.15 * k)
        # melody -- answers the voice rather than talking over it
        mel_lvl = lv["melody"][min(int(t0 * SR), n - 1)]
        k_notes = MELODY_NOTES[sec]
        if sec == "soften":
            k_notes = 2 + (ci % 3 == 1) + (ci % 4 == 2)
        lo_m, hi_m = MELODY_RANGE[sec]
        grid = np.arange(0.9, dur * 0.78, 0.95)
        if mel_lvl > 0.05 and len(grid):
            picks = sorted(rng.choice(len(grid), size=min(k_notes, len(grid)),
                                      replace=False))
            scale = [m for m in range(lo_m, hi_m + 1) if m % 12 in PENTA]
            chord_pcs = {m % 12 for m in voicing}
            for j, g in enumerate(picks):
                tn = t0 + grid[g] + rng.uniform(-0.06, 0.06)
                if act(tn) > 0.55:
                    continue
                si = int(np.argmin([abs(s - prev) for s in scale]))
                si = int(np.clip(si + rng.choice([-2, -1, -1, 1, 1, 2]), 0, len(scale) - 1))
                m = scale[si]
                if j == len(picks) - 1:              # land phrases on a chord tone
                    cands = [s for s in scale if s % 12 in chord_pcs] or scale
                    m = min(cands, key=lambda s: abs(s - m))
                vel = rng.uniform(0.30, 0.42)
                add(keys, piano(m, vel), tn, mel_lvl * 1.0, 0.15)
                prev = m
        # arpeggio -- slow broken chord, only where it has room
        arp_lvl = lv["arp"][min(int(t0 * SR), n - 1)]
        if arp_lvl > 0.05:
            notes = [x for x in voicing if x >= 53] + [voicing[-1] + 12 - 12 * (voicing[-1] > 72)]
            pattern = notes + notes[-2:0:-1]
            step = 0.82
            for k, tt in enumerate(np.arange(t0 + 0.4, t0 + dur - 0.3, step)):
                if act(tt) > 0.7:
                    continue
                m = pattern[k % len(pattern)]
                add(keys, piano(m, 0.16 + 0.04 * (k % 4 == 0)), tt,
                    arp_lvl * 0.55, 0.35 * np.sin(k * 0.9))

    pad *= lv["pad"][:, None]
    low *= lv["low"][:, None]
    shim *= lv["shimmer"][:, None]
    air = air_layer(n) * (lv["air"] * 0.022)[:, None]

    long_ir = reverb_ir(6.5, 1800, 3)
    mid_ir = reverb_ir(3.2, 3200, 5)
    wet = convolve(keys * 0.55 + pad * 0.35 + shim * 0.9 + low * 0.15, long_ir)
    wet2 = convolve(keys * 0.35, mid_ir)
    dry = keys * 0.55 + pad * 0.75 + low * 0.85 + shim * 0.15 + air
    mix = dry + wet * 0.85 + wet2 * 0.4

    # gentle master tone: tame low rumble, soften the very top
    mix = sosfilt(butter(2, 45, btype="high", fs=SR, output="sos"), mix, axis=0)
    mix = sosfilt(butter(1, 11000, fs=SR, output="sos"), mix, axis=0)
    # clear the voice's warmth band (-3 dB at 150-450 Hz) and open up the top
    mix -= 0.3 * sosfilt(butter(2, [150, 450], btype="band", fs=SR, output="sos"), mix, axis=0)
    mix += 1.2 * sosfilt(butter(2, 2600, btype="high", fs=SR, output="sos"), mix, axis=0)
    mix = mix.astype(np.float32)

    t = np.arange(n) / SR
    fade_in = np.clip(t / 5.0, 0, 1) ** 2
    fade_out = np.clip((total - t) / 9.0, 0, 1) ** 1.5
    mix *= (fade_in * fade_out)[:, None]
    return mix, sched


# --------------------------------------------------------------------- mix
def lufs(x):
    return pyln.Meter(SR).integrated_loudness(x)


def true_peak_limit(x, ceiling_db):
    """Look-ahead limiter on a 4x oversampled detector, so inter-sample peaks
    are caught (ffmpeg's alimiter alone is sample-peak only)."""
    from scipy.ndimage import minimum_filter1d, uniform_filter1d
    from scipy.signal import resample_poly
    ceil = 10 ** (ceiling_db / 20)
    up = np.abs(resample_poly(x, 4, 1, axis=0)).max(axis=1)
    peak = up.reshape(-1, 4).max(axis=1)[:len(x)]
    need = np.minimum(1.0, ceil / np.maximum(peak, 1e-9))
    # Hold the minimum over +-20 ms, then average over 20 ms: the averaged gain
    # can never exceed what any sample in reach needs, and it ramps smoothly.
    w = int(0.020 * SR)
    g = uniform_filter1d(minimum_filter1d(need, size=2 * w + 1), size=w)
    g = np.minimum(g, need)
    return x * g[:, None], float((g < 0.999).mean())


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    voice, sr = sf.read(CLEAN)
    assert sr == SR
    words = load_words()
    ed, tl = build_edit(voice, words)
    total = tl["total"]
    print(f"final duration {total:.1f}s ({int(total // 60)}:{total % 60:04.1f})")
    for b in tl["bolts"]:
        print(f"  BOLT timer {b['timer_start']:.2f} -> {b['timer_end']:.2f}, "
              f"voice resumes {b['voice_resume']:.2f} "
              f"(+{b['voice_resume'] - b['timer_start']:.2f}s)")
    for s in tl["sections"]:
        print(f"  {s['name']:8s} {s['start']:7.2f} - {s['end']:7.2f}  ({s['end'] - s['start']:6.1f}s)")

    v = ed.render(len(voice) / SR)
    n = int(round(total * SR))
    v = np.pad(v, (0, max(0, n - len(v))))[:n]
    # The recording carries handling noise while the breath hold is being
    # demonstrated (nose pinch, ~54.6 s in the source). Nothing of the voice
    # track should be heard inside a BOLT window, so it is muted there.
    t = np.arange(n) / SR
    for b in tl["bolts"]:
        a, z = b["timer_start"] + 0.35, b["voice_resume"] - 0.5
        g = 1 - np.clip((t - a) / 0.25, 0, 1) * np.clip((z - t) / 0.25, 0, 1)
        v *= g
    v = process_voice(v)
    v *= 10 ** ((VOICE_LUFS - lufs(v)) / 20)
    v = true_peak_limit(np.stack([v, v], axis=1), -5.0)[0][:, 0]
    vact = voice_activity(v)

    music, sched = build_music(tl["sections"], total, vact)
    music *= 10 ** ((MUSIC_LUFS - lufs(music)) / 20)
    duck = 10 ** (DUCK_DB * vact / 20)
    music *= duck[:, None]

    vs = np.stack([v, v], axis=1).astype(np.float32)
    mix = vs + music
    g = 10 ** ((TARGET_LUFS - lufs(mix)) / 20)
    mix *= g
    vs *= g
    music *= g
    pre = mix.copy()
    mix, limited = true_peak_limit(mix, TRUE_PEAK)
    gr = 20 * np.log10(np.maximum(np.abs(mix).max(1), 1e-9) / np.maximum(np.abs(pre).max(1), 1e-9))
    print(f"mix gain {20 * np.log10(g):+.1f} dB, limiter active {limited * 100:.2f}% "
          f"of samples, max reduction {-gr.min():.1f} dB, "
          f"99.9th pct {-np.percentile(gr, 0.1):.2f} dB")

    sf.write(os.path.join(OUT_DIR, "breathe-light-mix.wav"), mix, SR, subtype="PCM_24")
    sf.write(os.path.join(OUT_DIR, "breathe-light-voice.wav"), vs[:, 0], SR, subtype="PCM_24")
    sf.write(os.path.join(OUT_DIR, "breathe-light-music.wav"), music, SR, subtype="PCM_24")

    cues = subtitle_cues(tl["words"])
    write_srt(cues, os.path.join(OUT_DIR, "breathe-light.srt"))
    tl["subtitles"] = [[round(s, 3), round(e, 3), t] for s, e, t in cues]
    tl["chords"] = [[round(a, 2), round(d, 2), c, s] for a, d, c, s in sched]
    with open(EDIT_JSON, "w") as f:
        json.dump(tl, f, indent=1)
    print("saved stems, srt and", os.path.relpath(EDIT_JSON, ROOT))


if __name__ == "__main__":
    main()
