#!/usr/bin/env python3
"""
Breathe Light variants. The original film in breathe-light/ is never written.

  tmp/.venv-dsp/bin/python tmp/make_breathe_light_variants.py no-bolt
  tmp/.venv-dsp/bin/python tmp/make_breathe_light_variants.py reel
  tmp/.venv-dsp/bin/python tmp/make_breathe_light_variants.py v2

no-bolt  assets/social/youtube/relax/breathe-light-no-bolt/
         Same practice, both BOLT measurements and the breath-hold notice removed.
         End card matches v2.

reel     assets/social/instagram/practices/breathe-light/
         90s, 9:16. Selected lines from the recording, short practice pauses.

v2       assets/social/youtube/relax/breathe-light-v2/
         The original film with the closing line replaced. Audio is the original
         (symlinked); only the picture tail is re-rendered.
"""
import json
import os
import shutil
import sys

import numpy as np
import soundfile as sf

import make_breathe_light_audio as A

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ORIG = os.path.join(ROOT, "assets", "social", "youtube", "relax", "breathe-light")
CLOSE = "Do a little less."
SR = A.SR


def span_of(ed, words, text, near, key="e"):
    i = A.find_word(words, text, near, key=key)
    if key == "s":
        return ed.true_start(words[i]["s"]), i
    return ed.true_end(words[i]["e"]), i


def in_cut(removes, t):
    return any(a <= t <= b for a, b in removes)


class CutEditor:
    """Like Editor, but also deletes source ranges (the BOLT passages)."""

    def __init__(self, voice, inserts, removes, preroll, outro):
        self.v = voice
        self.inserts = sorted(inserts)
        self.removes = sorted(removes)
        self.preroll = preroll
        self.outro = outro

    def removed_before(self, t):
        total = 0.0
        for a, b in self.removes:
            if b <= t:
                total += b - a
            elif a < t:
                total += t - a
        return total

    def map(self, t):
        added = sum(L for c, L in self.inserts if c <= t)
        return self.preroll + t - self.removed_before(t) + added

    def render(self, src_dur):
        fade = int(0.04 * SR)
        keeps = [(0.0, src_dur)]
        for a, b in self.removes:
            nxt = []
            for s, e in keeps:
                if b <= s or a >= e:
                    nxt.append((s, e))
                else:
                    if a - s > 0.02:
                        nxt.append((s, a))
                    if e - b > 0.02:
                        nxt.append((b, e))
            keeps = nxt
        chunks = []
        for s, e in keeps:
            points = [s] + [c for c, _ in self.inserts if s + 1e-3 < c < e - 1e-3] + [e]
            for p0, p1 in zip(points, points[1:]):
                i0, i1 = int(round(p0 * SR)), int(round(p1 * SR))
                seg = self.v[i0:i1].copy()
                if len(seg) < 8:
                    continue
                chunks.append(seg)
                for c, L in self.inserts:
                    if abs(c - p1) < 1e-3:
                        chunks.append(np.zeros(int(round(L * SR))))
        for i, seg in enumerate(chunks):
            if len(seg) < fade * 2 or np.all(seg == 0):
                continue
            if i:
                seg[:fade] *= np.sin(np.linspace(0, np.pi / 2, fade)) ** 2
            if i < len(chunks) - 1:
                seg[-fade:] *= np.cos(np.linspace(0, np.pi / 2, fade)) ** 2
        body = np.concatenate(chunks)
        n = min(len(body), int(0.8 * SR))
        body[-n:] *= np.linspace(1, 0, n)
        return np.concatenate([np.zeros(int(self.preroll * SR)), body,
                               np.zeros(int(self.outro * SR))])


def write_mix(out_dir, voice, tl, names):
    """names: (mix, voice, music, srt, edit) filenames."""
    os.makedirs(out_dir, exist_ok=True)
    total = tl["total"]
    n = int(round(total * SR))
    v = np.pad(voice, (0, max(0, n - len(voice))))[:n]
    v = A.process_voice(v)
    v *= 10 ** ((A.VOICE_LUFS - A.lufs(v)) / 20)
    v = A.true_peak_limit(np.stack([v, v], axis=1), -5.0)[0][:, 0]
    vact = A.voice_activity(v)
    music, sched = A.build_music(tl["sections"], total, vact)
    n = min(len(music), len(vact))          # int() vs round() can disagree by a sample
    music, vact, v = music[:n], vact[:n], v[:n]
    music *= 10 ** ((A.MUSIC_LUFS - A.lufs(music)) / 20)
    music *= (10 ** (A.DUCK_DB * vact / 20))[:, None]
    vs = np.stack([v, v], axis=1).astype(np.float32)
    mix = vs + music
    g = 10 ** ((A.TARGET_LUFS - A.lufs(mix)) / 20)
    mix *= g
    vs *= g
    music *= g
    pre = mix.copy()
    mix, limited = A.true_peak_limit(mix, A.TRUE_PEAK)
    gr = 20 * np.log10(np.maximum(np.abs(mix).max(1), 1e-9)
                       / np.maximum(np.abs(pre).max(1), 1e-9))
    print(f"mix gain {20 * np.log10(g):+.1f} dB, limiter {limited * 100:.2f}%, "
          f"max reduction {-gr.min():.1f} dB")
    sf.write(os.path.join(out_dir, names[0]), mix, SR, subtype="PCM_24")
    sf.write(os.path.join(out_dir, names[1]), vs[:, 0], SR, subtype="PCM_24")
    sf.write(os.path.join(out_dir, names[2]), music, SR, subtype="PCM_24")
    cues = A.subtitle_cues(tl["words"])
    A.write_srt(cues, os.path.join(out_dir, names[3]))
    tl["subtitles"] = [[round(s, 3), round(e, 3), t] for s, e, t in cues]
    tl["chords"] = [[round(a, 2), round(d, 2), c, s] for a, d, c, s in sched]
    with open(os.path.join(out_dir, names[4]), "w") as f:
        json.dump(tl, f, indent=1)
    print("saved", os.path.relpath(out_dir, ROOT))


def build_no_bolt():
    preroll, outro = 8.0, 16.0
    out = os.path.join(ROOT, "assets", "social", "youtube", "relax", "breathe-light-no-bolt")
    voice, sr = sf.read(A.CLEAN)
    assert sr == SR
    words = A.load_words()
    probe = A.Editor(voice, words)

    well, _ = span_of(probe, words, "we'll", 11.1, key="s")
    lets, _ = span_of(probe, words, "let's", 16.7, key="s")
    begin, _ = span_of(probe, words, "begin", 17.2)
    gently, _ = span_of(probe, words, "gently", 87.0, key="s")
    fine, _ = span_of(probe, words, "fine", 317.0)
    remember, _ = span_of(probe, words, "remember", 366.1, key="s")

    removes = [
        (well - 0.06, lets - 0.08),          # "We'll measure our BOLT score..."
        (begin + 0.25, gently - 0.06),       # first measurement, timer and score
        (fine + 0.30, remember - 0.08),      # second measurement and score
    ]
    base = A.Editor(voice, words)
    for text, near, target in A.GAPS:
        i = A.find_word(words, text, near)
        if in_cut(removes, words[i]["e"]) or in_cut(removes, words[i + 1]["s"]):
            continue
        a = base.true_end(words[i]["e"])
        b = base.true_start(words[i + 1]["s"])
        base.extend(a, b, target)
    # Room to settle between "Let's begin." and the practice, and between
    # "Whatever you notice is fine." and the closing.
    base.inserts.append((begin + 0.12, 4.0))
    base.inserts.append((fine + 0.15, 6.0))

    ed = CutEditor(voice, base.inserts, removes, preroll, outro)
    src_dur = len(voice) / SR
    kept = [w for w in words if not in_cut(removes, (w["s"] + w["e"]) / 2)]
    mapped = [{"w": w["w"], "s": round(ed.map(w["s"]), 3), "e": round(ed.map(w["e"]), 3)}
              for w in kept]
    total = ed.map(src_dur) + outro
    starts = [
        ("intro", None),
        ("notice", ("gently", 87.0)),
        ("soften", ("now", 137.9)),
        ("letgo", ("now", 283.4)),
        ("closing", ("remember", 366.1)),
    ]
    sections = []
    for name, ref in starts:
        if ref is None:
            start = 0.0
        else:
            k = A.find_word(kept, ref[0], ref[1], key="s")
            prev = ed.map(kept[k - 1]["e"])
            start = (prev + ed.map(kept[k]["s"])) / 2
        sections.append({"name": name, "start": round(start, 3)})
    for s, nxt in zip(sections, sections[1:] + [{"start": total}]):
        s["end"] = round(nxt["start"], 3)

    print(f"no-bolt duration {total:.1f}s")
    for s in sections:
        print(f"  {s['name']:8s} {s['start']:7.2f} - {s['end']:7.2f} ({s['end'] - s['start']:6.1f}s)")
    spoken = " ".join(w["w"] for w in mapped)
    for banned in ("BOLT", "pinch", "timer", "second score"):
        if banned.lower() in spoken.lower():
            raise SystemExit(f"no-bolt cut still contains {banned!r}")

    src = os.path.join(out, "source")
    os.makedirs(out, exist_ok=True)
    if not os.path.lexists(src):
        os.symlink(os.path.join("..", "breathe-light", "source"), src)
    tl = {
        "total": round(total, 3), "preroll": preroll, "fps_hint": 24,
        "voice_start": preroll, "last_word_end": mapped[-1]["e"],
        "bolts": [], "sections": sections, "words": mapped,
        "close_line": CLOSE, "close_size": 104, "safety": False,
        "inserts": [{"src_time": round(c, 3), "added": round(L, 3)}
                    for c, L in sorted(base.inserts)],
        "removes": [[round(a, 3), round(b, 3)] for a, b in removes],
    }
    write_mix(out, ed.render(src_dur), tl,
              ("breathe-light-mix.wav", "breathe-light-voice.wav",
               "breathe-light-music.wav", "breathe-light.srt", "breathe-light-edit.json"))


def clip(voice, ed, words, a_word, a_near, b_word, b_near):
    i = A.find_word(words, a_word, a_near, key="s")
    j = A.find_word(words, b_word, b_near)
    origin = words[i]["s"] - 0.08
    end = ed.true_end(words[j]["e"]) + 0.1
    seg = voice[int(round(origin * SR)):int(round(end * SR))].copy()
    n = int(0.02 * SR)
    seg[:n] *= np.sin(np.linspace(0, np.pi / 2, n)) ** 2
    seg[-n:] *= np.cos(np.linspace(0, np.pi / 2, n)) ** 2
    return seg, words[i:j + 1], origin


def build_reel():
    """90 seconds. Speech lengths are fixed; the four practice pauses share
    whatever time is left so the film lands on exactly 90s."""
    out = os.path.join(ROOT, "assets", "social", "instagram", "practices", "breathe-light")
    preroll, outro = 5.5, 8.0
    voice, _ = sf.read(A.CLEAN)
    words = A.load_words()
    ed = A.Editor(voice, words)
    # (start word, near, end word, near, label shown at the start of the following pause)
    specs = [
        ("today", 2.9, "comfortably", 9.6, None),
        ("gently", 87.0, "you", 95.3, None),
        ("don't", 105.0, "movement", 110.2, "NOTICE"),
        ("now", 137.9, "quieter", 145.2, "SOFTEN"),
        ("allow", 198.0, "naturally", 205.1, None),
        ("now", 283.4, "breathing", 286.6, "LET GO"),
        ("sometimes", 383.3, "less", 387.2, None),
    ]
    # pauses after each clip; the four long ones are scaled to hit 90s
    base_gaps = [1.4, 1.0, 7.0, 8.0, 7.0, 6.0, 0.0]
    segs, groups, origins = [], [], []
    for spec in specs:
        seg, chosen, origin = clip(voice, ed, words, *spec[:4])
        segs.append(seg)
        groups.append(chosen)
        origins.append(origin)
    speech = sum(len(s) for s in segs) / SR
    joins = sum(base_gaps)
    scale_idx = [2, 3, 4, 5]
    fixed = preroll + outro + speech + sum(base_gaps[i] for i in range(len(base_gaps)) if i not in scale_idx)
    room = 90.0 - fixed
    share = sum(base_gaps[i] for i in scale_idx)
    gaps = [g * (room / share) if i in scale_idx else g for i, g in enumerate(base_gaps)]
    print(f"reel speech {speech:.1f}s, practice pauses "
          + " ".join(f"{gaps[i]:.1f}" for i in scale_idx))

    mapped, labels = [], []
    t = preroll
    pieces = [np.zeros(int(preroll * SR))]
    for seg, chosen, origin, gap, spec in zip(segs, groups, origins, gaps, specs):
        for w in chosen:
            mapped.append({"w": w["w"],
                           "s": round(t + (w["s"] - origin), 3),
                           "e": round(t + (w["e"] - origin), 3)})
        t += len(seg) / SR
        pieces.append(seg)
        if spec[4]:
            labels.append({"name": spec[4], "start": round(t + 0.3, 3),
                           "end": round(t + 0.3 + 5.5, 3)})
        t += gap
        pieces.append(np.zeros(int(round(gap * SR))))
    body = np.concatenate(pieces)
    total = 90.0
    body = np.pad(body, (0, max(0, int(total * SR) - len(body))))[:int(total * SR)]
    # section spans follow the clips, so the score still has a shape
    def at(label, which="start"):
        return next(x[which] for x in labels if x["name"] == label)
    last = mapped[-1]["e"]
    sections = [
        {"name": "intro", "start": 0.0, "end": round(labels[0]["start"], 3)},
        {"name": "notice", "start": round(labels[0]["start"], 3), "end": round(at("SOFTEN"), 3)},
        {"name": "soften", "start": round(at("SOFTEN"), 3), "end": round(at("LET GO"), 3)},
        {"name": "letgo", "start": round(at("LET GO"), 3), "end": round(last + 1.0, 3)},
        {"name": "closing", "start": round(last + 1.0, 3), "end": total},
    ]
    tl = {
        "total": total, "preroll": preroll, "fps_hint": 24, "portrait": True,
        "voice_start": preroll, "last_word_end": last,
        "bolts": [], "sections": sections, "words": mapped, "labels": labels,
        "title": [round(preroll - 0.8, 3), round(preroll + 6.5, 3)],
        "close": [round(last + 1.4, 3), total - 0.3],
        "close_line": CLOSE, "safety": False,
    }
    print(f"reel close {tl['close'][0]:.1f}s, last word {last:.1f}s")
    write_mix(out, body, tl,
              ("breathe-light-mix.wav", "breathe-light-voice.wav",
               "breathe-light-music.wav", "breathe-light.srt", "breathe-light-edit.json"))


def build_v2():
    """Folder for the new end card. Picture is rendered separately; the audio
    is the original film, linked rather than copied."""
    out = os.path.join(ROOT, "assets", "social", "youtube", "relax", "breathe-light-v2")
    os.makedirs(out, exist_ok=True)
    for name in ("breathe-light-mix.wav", "breathe-light-voice.wav",
                 "breathe-light-music.wav", "source"):
        dest = os.path.join(out, name)
        if not os.path.lexists(dest):
            os.symlink(os.path.join("..", "breathe-light", name), dest)
    tl = json.load(open(os.path.join(ORIG, "breathe-light-edit.json")))
    tl["close_line"] = CLOSE
    tl["close_size"] = 104
    with open(os.path.join(out, "breathe-light-edit.json"), "w") as f:
        json.dump(tl, f, indent=1)
    shutil.copy(os.path.join(ORIG, "breathe-light.srt"), os.path.join(out, "breathe-light.srt"))
    thumb = os.path.join(ORIG, "breathe-light-thumbnail.jpg")
    if os.path.exists(thumb):
        shutil.copy(thumb, os.path.join(out, "breathe-light-thumbnail.jpg"))
    print("prepared", os.path.relpath(out, ROOT),
          f"close card from {tl['last_word_end'] + 2.6:.1f}s")


if __name__ == "__main__":
    {"no-bolt": build_no_bolt, "reel": build_reel, "v2": build_v2}[sys.argv[1]]()
