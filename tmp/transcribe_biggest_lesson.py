#!/usr/bin/env python3
"""
Word-level transcript for the "Biggest breathwork lesson" reel. Run with the
ASR venv:

  HF_HOME=tmp/.hf tmp/.venv-asr/bin/python tmp/transcribe_biggest_lesson.py

Writes tmp/biggest-lesson-words.json -- {"segments": [...], "words": [{"w",
"s", "e"}]} -- which the caption/edit timings in
assets/social/instagram/reflections/biggest-breathwork-lesson/ are built from.
Only needs re-running if the source is re-cut.
"""
import json
import os

from faster_whisper import WhisperModel

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = os.path.join(ROOT, "assets", "social", "instagram", "reflections",
                      "biggest-breathwork-lesson", "source.mp4")
OUT = os.path.join(HERE, "biggest-lesson-words.json")

PROMPT = ("The Breath Reset. Breathwork. Bali. Anxiety, overthinking, "
          "people-pleasing. I don't need to feel good all the time to be okay.")

model = WhisperModel("medium.en", device="cpu", compute_type="int8")
segments, _ = model.transcribe(SOURCE, word_timestamps=True, beam_size=5,
                               initial_prompt=PROMPT, vad_filter=False)
words, segs = [], []
for seg in segments:
    print(f"[{seg.start:6.2f} - {seg.end:6.2f}] {seg.text}", flush=True)
    segs.append({"s": round(seg.start, 3), "e": round(seg.end, 3),
                 "text": seg.text.strip()})
    for w in seg.words:
        words.append({"w": w.word.strip(), "s": round(w.start, 3),
                      "e": round(w.end, 3)})

with open(OUT, "w") as f:
    json.dump({"segments": segs, "words": words}, f, indent=0)
print("saved", os.path.relpath(OUT, ROOT), len(words), "words")
