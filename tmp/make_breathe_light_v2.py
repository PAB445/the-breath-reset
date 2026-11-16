#!/usr/bin/env python3
"""
Breathe Light with the v2 practice script -- edit, score and mix for all three cuts.

  ffmpeg -i assets/social/youtube/relax/breathe-light/source/breathe-light-v2.m4a \
         -ar 44100 -ac 1 tmp/bl2-source.wav
  BL_AUDIO=breathe-light-v2.m4a BL_WORDS=breathe-light-v2-words.json \
    HF_HOME=tmp/.hf tmp/.venv-asr/bin/python tmp/transcribe_breathe_light.py
  BL_TAG=bl2 tmp/.venv-dsp/bin/python tmp/clean_breathe_light_voice.py
  tmp/.venv-dsp/bin/python tmp/make_breathe_light_v2.py film|no-bolt|no-bolt-v2|reel|all

Two recordings:
  old  breathe-light.m4a     intro, both BOLT measurements, closing
  new  breathe-light-v2.m4a  the practice (notice / soften / breathe less / let go)

film     breathe-light/          old intro + BOLT 1, new practice, old BOLT 2 + closing
no-bolt  breathe-light-no-bolt/  old intro (no BOLT line), new practice, old closing
reel     instagram/practices/breathe-light/   90 s, selected lines

The new recording is gated to its words: every pause is true silence (mouse
scroll clicks and handling noise between phrases are gone), and short
transients in the pads around each word are de-clicked. Nothing is stretched;
pauses are lengthened at their quietest point.
"""
import json
import os
import sys

import numpy as np
import soundfile as sf
from scipy.ndimage import median_filter
from scipy.signal import butter, sosfilt

import make_breathe_light_audio as A
import make_breathe_light_variants as V

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
YT = os.path.join(ROOT, "assets", "social", "youtube", "relax")
SR = A.SR
CLOSE = "Soft, quiet, light."

NEW_CLEAN = os.path.join(HERE, "bl2-voice-clean.wav")
NEW_WORDS = os.path.join(HERE, "breathe-light-v2-words.json")

# (word ending the phrase, its source end time, target pause to the next word)
NEW_GAPS = [
    ("notice", 46.92, 14.0),        # "No need to change anything yet, just notice."
    ("leave", 69.12, 4.0),
    ("forcing", 74.14, 8.0),        # "No pushing, no forcing."
    ("softer", 88.40, 4.0),         # "...the inhale just a little smaller, a little softer."
    ("naturally", 92.28, 3.0),
    ("breathing", 117.56, 18.0),    # "Soft, quiet, imperceptible breathing."
    ("breath", 140.15, 3.0),
    ("more", 153.73, 12.0),         # "...soften the next inhale just a little more."
    ("sensation", 181.67, 16.0),    # "...just a mild comfortable sensation."
    ("would", 211.77, 10.0),
    ("air", 242.67, 16.0),          # "...a very slight desire for more air."
    ("notice", 257.55, 14.0),       # "...just stay curious about what you notice."
    ("anymore", 278.45, 22.0),      # Let Go: the long uninterrupted stretch
    ("okay", 301.13, 6.0),          # "Whatever you notice is okay."
]
NEW_SECTIONS = [("soften", ("now", 53.38)), ("lessair", ("now", 126.82)),
                ("letgo", ("and", 262.43))]

# no-bolt v2 only. Shorter practice pauses, and the Let Go pause after
# "anymore" is left at its natural length instead of being opened out.
SHORT_GAPS = [
    ("notice", 46.92, 8.0),         # "...just notice."
    ("leave", 69.12, 2.5),
    ("forcing", 74.14, 5.0),        # "No pushing, no forcing."
    ("softer", 88.40, 2.0),
    ("naturally", 92.28, 3.0),
    ("breathing", 117.56, 11.0),    # "Soft, quiet, imperceptible breathing."
    ("breath", 140.15, 3.0),
    ("more", 153.73, 7.0),
    ("sensation", 181.67, 10.0),
    ("notice", 257.55, 7.0),        # "...stay curious about what you notice."
    ("okay", 301.13, 4.0),
]
# "This is a bit of a dance ... desire for more air." is cut. The 6 s that
# follows "would." now leads straight into "And remember".
DANCE_GAP = 6.0

# the score gets a fourth practice section between Soften and Let Go
A.PROG["lessair"] = (["vi", "IV", "I3", "V", "ii", "IV", "I", "V"], 10.0)
A.LEVELS["lessair"] = (0.95, 0.85, 0.62, 0.75, 0.40, 0.60, 0.75)
A.MELODY_NOTES["lessair"] = 2
A.MELODY_RANGE["lessair"] = (70, 82)


# ------------------------------------------------------------------ sources
def gate_new_voice(v, words):
    """Keep only the speech: word spans (plus their natural tails) pass,
    everything between phrases is silence. Clicks outside the words
    themselves are pulled down by 30 dB first, so they can neither hold the
    gate open nor sit on its edge."""
    hop = SR // 100
    n = len(v) // hop
    core = np.zeros(n, bool)
    for w in words:
        core[max(0, int((w["s"] - 0.03) * 100)):min(n, int((w["e"] + 0.03) * 100) + 1)] = True

    # de-click: 5 ms high-band frames that jump far above their neighbourhood
    h5 = SR // 200
    hb = sosfilt(butter(4, 2000, "high", fs=SR, output="sos"), v)
    m = len(hb) // h5
    he = 10 * np.log10((hb[:m * h5].reshape(m, h5) ** 2).mean(1) + 1e-14)
    jump = he - median_filter(he, 41)
    dip = np.ones(m)
    clicks = 0
    for i in np.flatnonzero(jump > 12):
        if i // 2 < n and not core[i // 2]:
            dip[max(0, i - 1):i + 3] = 10 ** (-30 / 20)
            clicks += 1
    dip = np.convolve(dip, np.hanning(5) / np.hanning(5).sum(), "same")
    d = np.repeat(dip, h5)
    v = v * np.pad(d, (0, len(v) - len(d)), constant_values=1.0)[:len(v)]

    # mouth clicks inside words: 2 ms impulses well above the 8 ms either side.
    # Only the band above 3 kHz is turned down, so the vowel underneath is untouched.
    h2 = SR // 500
    hf = sosfilt(butter(4, 3000, "high", fs=SR, output="sos"), v)
    m2 = len(hf) // h2
    e2 = 10 * np.log10((hf[:m2 * h2].reshape(m2, h2) ** 2).mean(1) + 1e-14)
    iso = e2 - np.maximum(np.roll(e2, 4), np.roll(e2, -4))
    hg = np.ones(m2)
    for i in np.flatnonzero((iso > 15) & (e2 > -75)):
        hg[max(0, i - 1):i + 2] = 0.1
        clicks += 1
    hg = np.convolve(hg, np.hanning(3) / np.hanning(3).sum(), "same")
    hg = np.pad(np.repeat(hg, h2), (0, len(v) - m2 * h2), constant_values=1.0)
    v = (v - hf) + hf * hg

    e = A.energy_db(v, hop)
    keep = np.zeros(n, bool)
    for w in words:
        s, t = int((w["s"] - 0.12) * 100), int((w["e"] + 0.12) * 100)
        keep[max(0, s):min(n, t)] = True
        # let the word's own decay ring out (up to 0.45 s) while it stays audible
        k = t
        while k < min(n, t + 45) and e[k] > -56:
            keep[k] = True
            k += 1
    # bridge very short holes so a phrase is never chopped mid-breath
    idx = np.flatnonzero(keep)
    for a, b in zip(idx, idx[1:]):
        if 1 < b - a <= 22:
            keep[a:b] = True

    # fades sit inside the kept region, so nothing outside it leaks through
    inner = np.convolve(keep.astype(float), np.ones(5), "same") >= 5 - 1e-6
    ramp = np.convolve(inner.astype(float), np.hanning(5) / np.hanning(5).sum(), "same") * keep
    g = np.repeat(ramp, hop)
    g = np.pad(g, (0, len(v) - len(g)), mode="edge")[:len(v)]
    print(f"new voice: kept {keep.mean() * 100:.0f}% of the recording, "
          f"{clicks} click frames repaired")
    return v * g


def match_tone(v):
    """The v2 session sits closer to the mic: ~3 dB more low end and top
    relative to the mids than the original. Shelve both back."""
    lo = sosfilt(butter(2, 220, "low", fs=SR, output="sos"), v)
    hi = sosfilt(butter(2, 3200, "high", fs=SR, output="sos"), v)
    return v + lo * (10 ** (-3.0 / 20) - 1) + hi * (10 ** (-2.8 / 20) - 1)


class Rec:
    def __init__(self, voice, words, gaps):
        self.v = voice
        self.words = words
        self.gaps = gaps
        self.ed = A.Editor(voice, words)

    def find(self, text, near, key="e"):
        return A.find_word(self.words, text, near, key=key)

    def end(self, text, near):
        return self.ed.true_end(self.words[self.find(text, near)]["e"])

    def start(self, text, near):
        return self.ed.true_start(self.words[self.find(text, near, "s")]["s"])


def load_recs():
    old_v, sr = sf.read(A.CLEAN)
    assert sr == SR
    new_v, sr = sf.read(NEW_CLEAN)
    assert sr == SR
    new_words = json.load(open(NEW_WORDS))["words"]
    new_v = match_tone(new_v)
    new_v = gate_new_voice(new_v, new_words)
    # match the new session to the old one before the shared voice chain
    gain = A.lufs(old_v) - A.lufs(new_v)
    new_v = new_v * 10 ** (gain / 20)
    print(f"new recording level matched {gain:+.1f} dB")
    return Rec(old_v, A.load_words(), A.GAPS), Rec(new_v, new_words, NEW_GAPS)


# ----------------------------------------------------------------- timeline
class Timeline:
    """Pieces of either recording laid end to end, with silence between."""

    def __init__(self, preroll):
        self.pieces = [np.zeros(int(round(preroll * SR)))]
        self.t = preroll
        self.clips = []          # (rec, src_a, src_b, out_t)
        self.words = []

    def gap(self, seconds):
        if seconds > 0:
            self.pieces.append(np.zeros(int(round(seconds * SR))))
            self.t += seconds

    def clip(self, rec, a, b, fade=0.04, first=None):
        """first: index of the clip's opening word, kept in the captions even
        when the transcript places its start before the cut."""
        i0, i1 = int(round(a * SR)), int(round(b * SR))
        seg = rec.v[i0:i1].copy()
        f = int(fade * SR)
        seg[:f] *= np.sin(np.linspace(0, np.pi / 2, f)) ** 2
        seg[-f:] *= np.cos(np.linspace(0, np.pi / 2, f)) ** 2
        a, b = i0 / SR, i1 / SR
        self.clips.append((rec, a, b, self.t))
        for k, w in enumerate(rec.words):
            if a <= (w["s"] + w["e"]) / 2 < b or k == first:
                self.words.append({"w": w["w"], "s": round(self.t + max(w["s"], a) - a, 3),
                                   "e": round(self.t + min(w["e"], b) - a, 3)})
        self.pieces.append(seg)
        self.t += len(seg) / SR

    def span(self, rec, a, b, extra=(), first=None):
        """rec[a:b] with its pauses lengthened to their targets.
        extra: more (pause_start, pause_end, target) pauses, e.g. BOLT windows."""
        cuts = []
        for text, near, target in rec.gaps:
            i = rec.find(text, near)
            if not (a < rec.words[i]["e"] and rec.words[i + 1]["s"] < b):
                continue
            p0 = rec.ed.true_end(rec.words[i]["e"])
            p1 = rec.ed.true_start(rec.words[i + 1]["s"])
            cuts.append((p0, p1, target))
        cuts += list(extra)
        pos = a
        for p0, p1, target in sorted(cuts):
            add = target - (p1 - p0)
            if add <= 0.05:
                continue
            c = rec.ed.cut_point(p0, p1)
            self.clip(rec, pos, c, first=first)
            self.gap(add)
            pos, first = c, None
        self.clip(rec, pos, b, first=first)

    def map(self, rec, src):
        for r, a, b, t0 in self.clips:
            if r is rec and a - 1e-6 <= src <= b + 1e-6:
                return t0 + src - a
        raise ValueError(f"source time {src:.2f} is not in the cut")

    def audio(self, outro, tail_fade=1.0):
        body = np.concatenate(self.pieces)
        n = int(tail_fade * SR)
        body[-n:] *= np.linspace(1, 0, n)
        return np.concatenate([body, np.zeros(int(round(outro * SR)))])


def midpoint(tl, rec, text, near):
    """Section boundary: halfway through the pause before this word."""
    k = rec.find(text, near, "s")
    prev = rec.words[k - 1]["e"]
    try:
        before = tl.map(rec, prev)
    except ValueError:
        before = None
    on = tl.map(rec, rec.words[k]["s"])
    if before is None or before > on:
        return on - 1.5
    return (before + on) / 2


def finish_sections(starts, total):
    sections = [{"name": n, "start": round(s, 3)} for n, s in starts]
    for s, nxt in zip(sections, sections[1:] + [{"start": total}]):
        s["end"] = round(nxt["start"], 3)
    for s in sections:
        print(f"  {s['name']:8s} {s['start']:7.2f} - {s['end']:7.2f} ({s['end'] - s['start']:6.1f}s)")
    return sections


def new_practice(tl, new, gaps=None, cut_dance=False, dance_gap=DANCE_GAP):
    """The whole v2 recording, pauses lengthened. Returns section starts.
    cut_dance drops "This is a bit of a dance ... more air." and leaves
    dance_gap seconds between "would." and "And remember"."""
    saved = new.gaps
    if gaps is not None:
        new.gaps = gaps
    a = new.start("gently", 0.84) - 0.12
    b = new.end("room", 311.51) + 0.3
    notice = tl.t
    if cut_dance:
        mid = new.end("would", 211.77) + 0.18
        resume = new.start("and", 249.53) - 0.10
        tl.span(new, a, mid, first=new.find("gently", 0.84, "s"))
        tl.gap(dance_gap)
        tl.span(new, resume, b, first=new.find("and", 249.53, "s"))
    else:
        tl.span(new, a, b, first=new.find("gently", 0.84, "s"))
    new.gaps = saved
    out = [("notice", notice - 1.0)]
    for name, (text, near) in NEW_SECTIONS:
        out.append((name, midpoint(tl, new, text, near)))
    return out


# --------------------------------------------------------------------- film
def build_film(old, new):
    out = os.path.join(YT, "breathe-light")
    preroll, outro = A.PREROLL, A.OUTRO
    tl = Timeline(preroll)

    # old: intro + BOLT 1, up to "...return completely to normal."
    bolt_spans = []
    for w0, t0, w1, t1 in A.BOLTS:
        end = old.ed.true_end(old.words[old.find(w0, t0 + 0.4)]["e"])
        on = old.ed.true_start(old.words[old.find(w1, t1, "s")]["s"])
        bolt_spans.append((end, on))
    normal = old.end("normal", 85.6)
    tl.span(old, 0.0, normal + 0.15, extra=[(*bolt_spans[0], A.BOLT_RESUME)])
    tl.gap(3.0 - 0.15 - 0.12)
    starts = [("intro", 0.0), ("bolt1", midpoint(tl, old, "take", 19.0))]
    starts += new_practice(tl, new, gaps=SHORT_GAPS, cut_dance=True)

    # old: BOLT 2 + closing
    tl.gap(5.0 - 0.3 - 0.1)
    bolt2_at = tl.t - 2.5
    now = old.start("now", 322.16) - 0.1
    tl.span(old, now, len(old.v) / SR, extra=[(*bolt_spans[1], A.BOLT_RESUME)],
            first=old.find("now", 322.16, "s"))
    starts += [("bolt2", bolt2_at), ("closing", midpoint(tl, old, "remember", 366.1))]

    voice = tl.audio(outro)
    total = round(len(voice) / SR, 3)
    print(f"film duration {total:.1f}s ({int(total // 60)}:{total % 60:04.1f})")
    sections = finish_sections(starts, total)

    bolts = []
    for (end, on), cue in zip(bolt_spans, (("ready", 42.6), ("take", 347.2))):
        ts = tl.map(old, end)
        b = {"src_end": round(end, 3), "src_resume": round(on, 3),
             "timer_start": round(ts, 3), "timer_end": round(ts + A.BOLT_WINDOW, 3),
             "voice_resume": round(tl.map(old, on), 3),
             "card_in": round(tl.map(old, old.words[old.find(*cue, key="s")]["s"]) - 0.4, 3)}
        bolts.append(b)
        print(f"  BOLT timer {b['timer_start']:.2f} -> {b['timer_end']:.2f}, "
              f"voice resumes +{b['voice_resume'] - b['timer_start']:.2f}s")
    # handling noise during the demonstrated hold: nothing of the voice inside a window
    t = np.arange(len(voice)) / SR
    for b in bolts:
        lo, hi = b["timer_start"] + 0.35, b["voice_resume"] - 0.5
        voice *= 1 - np.clip((t - lo) / 0.25, 0, 1) * np.clip((hi - t) / 0.25, 0, 1)

    edit = {
        "total": total, "preroll": preroll, "fps_hint": 24,
        "voice_start": preroll, "last_word_end": tl.words[-1]["e"],
        "bolts": bolts, "sections": sections, "words": tl.words,
        "script": "breathe-light-v2.m4a (practice) + breathe-light.m4a (intro, BOLT, closing)",
    }
    V.write_mix(out, voice, edit, NAMES)


NAMES = ("breathe-light-mix.wav", "breathe-light-voice.wav", "breathe-light-music.wav",
         "breathe-light.srt", "breathe-light-edit.json")


# ------------------------------------------------------------------ no-bolt
def build_no_bolt(old, new):
    out = os.path.join(YT, "breathe-light-no-bolt")
    preroll, outro = 8.0, 16.0
    tl = Timeline(preroll)
    tl.clip(old, 0.0, old.end("comfortably", 9.6) + 0.15)
    tl.gap(1.0 - 0.15 - 0.08)                    # "We'll measure our BOLT score..." is cut
    tl.clip(old, old.start("let's", 16.7) - 0.08, old.end("begin", 17.2) + 0.25,
            first=old.find("let's", 16.7, "s"))
    tl.gap(4.2 - 0.25 - 0.12)
    starts = [("intro", 0.0)] + new_practice(tl, new)
    # closing without "Remember, the goal isn't to achieve a particular number"
    tl.gap(6.0 - 0.3 - 0.08)
    closing_at = tl.t - 3.0
    tl.span(old, old.start("as", 375.88) - 0.08, len(old.v) / SR,
            first=old.find("as", 375.88, "s"))
    starts.append(("closing", closing_at))

    voice = tl.audio(outro, tail_fade=0.8)
    total = round(len(voice) / SR, 3)
    print(f"no-bolt duration {total:.1f}s ({int(total // 60)}:{total % 60:04.1f})")
    sections = finish_sections(starts, total)
    spoken = " ".join(w["w"] for w in tl.words).lower()
    for banned in ("bolt", "pinch", "timer", "score", "number"):
        if banned in spoken:
            raise SystemExit(f"no-bolt cut still contains {banned!r}")
    edit = {
        "total": total, "preroll": preroll, "fps_hint": 24,
        "voice_start": preroll, "last_word_end": tl.words[-1]["e"],
        "bolts": [], "sections": sections, "words": tl.words,
        "close_line": CLOSE, "close_size": 104, "safety": False,
        "script": "breathe-light-v2.m4a (practice) + breathe-light.m4a (intro, closing)",
    }
    V.write_mix(out, voice, edit, NAMES)


def build_no_bolt_v2(old, new):
    """Shorter cut of the no-BOLT film. Writes breathe-light-no-bolt-v2/ and
    leaves the original no-BOLT film untouched."""
    out = os.path.join(YT, "breathe-light-no-bolt-v2")
    preroll, outro = 8.0, 12.0
    tl = Timeline(preroll)
    tl.clip(old, 0.0, old.end("comfortably", 9.6) + 0.15)
    tl.gap(1.0 - 0.15 - 0.08)
    tl.clip(old, old.start("let's", 16.7) - 0.08, old.end("begin", 17.2) + 0.25,
            first=old.find("let's", 16.7, "s"))
    tl.gap(4.2 - 0.25 - 0.12)
    starts = [("intro", 0.0)] + new_practice(tl, new, gaps=SHORT_GAPS, cut_dance=True)
    tl.gap(4.0 - 0.3 - 0.08)
    closing_at = tl.t - 2.0
    tl.span(old, old.start("as", 375.88) - 0.08, len(old.v) / SR,
            first=old.find("as", 375.88, "s"))
    starts.append(("closing", closing_at))

    voice = tl.audio(outro, tail_fade=0.8)
    total = round(len(voice) / SR, 3)
    print(f"no-bolt v2 duration {total:.1f}s ({int(total // 60)}:{total % 60:04.1f})")
    sections = finish_sections(starts, total)
    spoken = " ".join(w["w"] for w in tl.words).lower()
    for banned in ("bolt", "pinch", "timer", "score", "number", "dance", "uncomfortable"):
        if banned in spoken:
            raise SystemExit(f"no-bolt v2 cut still contains {banned!r}")
    edit = {
        "total": total, "preroll": preroll, "fps_hint": 24,
        "voice_start": preroll, "last_word_end": tl.words[-1]["e"],
        "bolts": [], "sections": sections, "words": tl.words,
        "close_line": CLOSE, "close_size": 104, "safety": False,
        "script": "breathe-light-v2.m4a, dance passage and Let Go pause removed",
    }
    V.write_mix(out, voice, edit, NAMES)


# --------------------------------------------------------------------- reel
def build_reel(old, new):
    """90 seconds, a complete short practice rather than isolated lines.

    Each block is consecutive speech, so nothing starts or ends mid-thought:
    what this is, settle, soften, breathe a little less, one cue, let go, close.
    The practice pauses share whatever time the speech leaves. Breathe Less is
    split in two, with "Soften the inhale, relax the exhale." between the halves.
    """
    out = os.path.join(ROOT, "assets", "social", "instagram", "practices", "breathe-light")
    preroll, outro, total = 4.2, 6.4, 90.0
    # (recording, first word, near, last word, near, gap after, label on that gap)
    # gap None means "one of the practice pauses", scaled to land on 90s.
    # HOLD is the second half of the Breathe Less pause: timed, but not shown.
    steps = [
        (old, "today", 2.9, "light", 5.28, 0.85, None),
        (new, "let", 18.84, "jaw", 22.50, None, "NOTICE"),
        (new, "now", 53.38, "breathing", 57.62, None, "SOFTEN"),
        (new, "now", 126.82, "breath", 140.15, None, "BREATHE LESS"),
        (new, "soften", 142.09, "exhale", 146.11, None, "HOLD"),
        (new, "and", 262.43, "breathing", 268.05, None, "LET GO"),
        (new, "whatever", 299.11, "okay", 301.13, 0.0, None),
    ]
    weights = {"NOTICE": 1.0, "SOFTEN": 1.0, "BREATHE LESS": 1.6, "HOLD": 1.6, "LET GO": 1.1}
    label_hold = {"BREATHE LESS": 8.0}
    segs = []
    for rec, w0, n0, w1, n1, gap, label in steps:
        i = rec.find(w0, n0, "s")
        # true_start walks back into the previous phrase when the gap is short,
        # which pulls the tail of "Reset." in ahead of "Today".
        a = rec.ed.true_start(rec.words[i]["s"]) - 0.08
        if i > 0:
            a = max(a, rec.words[i - 1]["e"] + 0.20)
        b = rec.end(w1, n1) + 0.12
        segs.append((rec, a, b, gap, label, i))
    speech = sum(b - a for _, a, b, _, _, _ in segs)
    fixed_gaps = sum(s[3] for s in segs if s[3] is not None)
    room = total - preroll - outro - speech - fixed_gaps
    unit = room / sum(weights[s[4]] for s in segs if s[3] is None)
    if unit < 3.0:
        raise SystemExit(f"reel practice pause would be only {unit:.1f}s; the cut is too full")
    gaps = [unit * weights[s[4]] if s[3] is None else s[3] for s in segs]
    print(f"reel speech {speech:.1f}s, practice pauses "
          + ", ".join(f"{s[4]} {g:.1f}s" for s, g in zip(segs, gaps) if s[3] is None))

    tl = Timeline(preroll)
    labels = []
    for (rec, a, b, _, label, first), g in zip(segs, gaps):
        tl.clip(rec, a, b, fade=0.02, first=first)
        if label and label != "HOLD":
            labels.append({"name": label, "start": round(tl.t + 0.25, 3),
                           "end": round(tl.t + 0.25 + min(label_hold.get(label, 4.6), g - 0.4), 3)})
        tl.gap(g)
    voice = np.concatenate(tl.pieces)
    voice = np.pad(voice, (0, max(0, int(total * SR) - len(voice))))[:int(total * SR)]
    last = tl.words[-1]["e"]
    at = {lb["name"]: lb["start"] for lb in labels}
    sections = [
        {"name": "intro", "start": 0.0, "end": at["NOTICE"]},
        {"name": "notice", "start": at["NOTICE"], "end": at["SOFTEN"]},
        {"name": "soften", "start": at["SOFTEN"], "end": at["BREATHE LESS"]},
        {"name": "lessair", "start": at["BREATHE LESS"], "end": at["LET GO"]},
        {"name": "letgo", "start": at["LET GO"], "end": round(last + 1.0, 3)},
        {"name": "closing", "start": round(last + 1.0, 3), "end": total},
    ]
    edit = {
        "total": total, "preroll": preroll, "fps_hint": 24, "portrait": True,
        "voice_start": preroll, "last_word_end": last,
        "bolts": [], "sections": sections, "words": tl.words, "labels": labels,
        "title": [round(preroll - 0.8, 3), round(preroll + 7.4, 3)],
        "close": [round(last + 1.4, 3), total - 0.3],
        "close_line": CLOSE, "safety": False,
    }
    print(f"reel close {edit['close'][0]:.1f}s, last word {last:.1f}s")
    V.write_mix(out, voice, edit, NAMES)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    old, new = load_recs()
    for name, fn in (("film", build_film), ("no-bolt", build_no_bolt),
                     ("no-bolt-v2", build_no_bolt_v2), ("reel", build_reel)):
        if which in (name, "all"):
            print(f"=== {name} ===")
            fn(old, new)
