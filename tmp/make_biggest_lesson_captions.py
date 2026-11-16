#!/usr/bin/env python3
"""
Builds captions.srt for the "Biggest breathwork lesson" reel from the word
timestamps (tmp/biggest-lesson-words.json) and the phrase list below.

  python3 tmp/make_biggest_lesson_captions.py           # refuses to overwrite
  python3 tmp/make_biggest_lesson_captions.py --force   # rebuild from scratch

The SRT is on the *finished-video* timeline (holds included), so it can be
uploaded alongside the MP4 as-is. After it exists, edit captions.srt directly
-- the renderer reads it. Only rebuild after a re-cut or a change to the holds
in edit.json (rebuilding discards hand edits).

Phrases follow what is actually said (Australian spelling). A cue containing
<i>...</i> renders as a highlighted moment: larger Instrument Serif, the <i>
words in sage italic. A newline inside a phrase is an explicit line break.
"""
import json
import os
import re
import sys

from biggest_lesson_edit import (CAPTIONS_PATH, HOLD_END, ROOT, TAIL,
                                 WORDS_PATH, out_time)

PHRASES = [
    "One of the biggest things breathwork has taught me",
    "is how often I go into my head",
    "to avoid <i>feeling</i>\nwhat’s happening in my body.",
    "For years I struggled with anxiety",
    "and I spent so much time trying to understand it.",
    "Reading books, going to therapy,",
    "doing all sorts of self-development work.",
    "One of my biggest breakthroughs was realising",
    "I didn’t actually need to get rid of the anxiety.",
    "I could feel anxious\n<i>and still get on with my life.</i>",
    "But strangely, I never really applied that lesson to other emotions.",
    "Whenever something uncomfortable came up,",
    "I’d immediately start analysing it.",
    "Why am I feeling this? Is it something from my childhood?",
    "Is there something I need to work through?",
    "And while understanding our emotions can be really useful,",
    "I’ve started to realise that sometimes all this thinking",
    "is actually a way of avoiding\n<i>the feeling itself.</i>",
    "I remember having a really powerful breathwork experience in Bali",
    "where some pretty uncomfortable feelings started coming up.",
    "Immediately, my mind wanted to understand what was happening.",
    "Why am I feeling this? Where is it coming from?",
    "I kept catching myself doing this.",
    "Every time, I’d remind myself to come back into my body.",
    "And it made me realise how often we do this in everyday life.",
    "We overthink, distract ourselves, keep busy,",
    "sometimes even lash out at someone.",
    "Take people-pleasing, for example.",
    "You send someone a message",
    "and afterwards you start worrying about how they’ve interpreted it.",
    "Maybe they think you’re rude.",
    "So you send another message",
    "to explain yourself or make sure everything’s okay.",
    "But sometimes you’re not really sending that second message",
    "because anything needs fixing.",
    "You’re sending it because you want\nthat uncomfortable feeling <i>to go away.</i>",
    "And I’ve started noticing this in myself in much smaller moments too.",
    "Like when I’m having my morning coffee",
    "and start thinking about everything I need to do that day.",
    "I can feel the familiar tension building.",
    "And rather than trying to immediately calm myself down",
    "or think my way out of it,",
    "practising just noticing it.",
    "Where do I actually feel this in my body,",
    "and can I let it be there without needing to do anything about it?",
    "Can I get on with my day even if it doesn’t disappear?",
    "Because I’m starting to realise that sometimes",
    "I don’t need to understand, fix or get rid of what I’m feeling.",
    "Sometimes I just need to\n<i>let myself feel it.</i>",
    "And I don’t need to feel good all the time\n<i>to be okay.</i>",
]

LEAD = 0.05          # caption appears just before the first word
TAIL_PLAIN = 0.30    # and lingers a beat after the last
TAIL_HERO = 0.90     # highlighted lines linger longer, so they land
GAP = 0.06           # never two cues on screen at once


def letters(s):
    return re.sub(r"[^a-z]", "", re.sub(r"<[^>]+>", "", s.lower()))


def align(words):
    """Consume whisper words for each phrase by matching letter counts --
    robust to punctuation, hyphenation and z/s spelling."""
    cues, i = [], 0
    for text in PHRASES:
        need = len(letters(text))
        got, first = 0, i
        while got < need:
            got += len(letters(words[i]["w"]))
            i += 1
        if got != need:
            sys.exit(f"alignment drift at: {text!r} ({got} vs {need} letters)")
        a, b = words[first], words[i - 1]
        s = a["s"] if a["e"] - a["s"] <= 0.7 else a["e"] - 0.35
        e = b["e"] if b["e"] - b["s"] <= 0.7 else b["s"] + 0.5
        cues.append([s, e, text])
    if i != len(words):
        sys.exit(f"{len(words) - i} words left over -- phrase list incomplete")
    return cues


def to_output(cues):
    out = []
    for k, (s, e, text) in enumerate(cues):
        hero = "<i>" in text
        start = out_time(s) - LEAD
        end = out_time(e) + (TAIL_HERO if hero else TAIL_PLAIN)
        if k + 1 < len(cues):
            end = min(end, out_time(cues[k + 1][0]) - LEAD - GAP)
        else:
            # the last line stays up through the settle hold
            end = HOLD_END - TAIL["fade_to_dark"] * 0.4
        out.append((max(0.0, start), end, text))
    return out


def stamp(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(cues, path):
    with open(path, "w") as f:
        for n, (s, e, text) in enumerate(cues, 1):
            f.write(f"{n}\n{stamp(s)} --> {stamp(e)}\n{text}\n\n")
    print("saved", os.path.relpath(path, ROOT), f"({len(cues)} cues)")


if __name__ == "__main__":
    if os.path.exists(CAPTIONS_PATH) and "--force" not in sys.argv:
        sys.exit("captions.srt exists -- edit it directly, or pass --force "
                 "to rebuild (discards hand edits)")
    with open(WORDS_PATH) as f:
        words = json.load(f)["words"]
    write_srt(to_output(align(words)), CAPTIONS_PATH)
