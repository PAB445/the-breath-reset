#!/usr/bin/env python3
"""
Word-level transcript for the Breathe Light YouTube practice. Run with the ASR venv:

  HF_HOME=tmp/.hf tmp/.venv-asr/bin/python tmp/transcribe_breathe_light.py
  BL_AUDIO=breathe-light-v2.m4a BL_WORDS=breathe-light-v2-words.json ...   # v2 script

Writes tmp/breathe-light-words.json -- [{"w", "s", "e"}] -- which
make_breathe_light_audio.py uses to find section boundaries and pauses.
"""
import json
import os

from faster_whisper import WhisperModel

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = os.path.join(ROOT, "assets", "social", "youtube", "relax", "breathe-light",
                      "source", os.environ.get("BL_AUDIO", "breathe-light.m4a"))
OUT = os.path.join(HERE, os.environ.get("BL_WORDS", "breathe-light-words.json"))

PROMPT = ("The Breath Reset. Breathe Light. BOLT score, control pause. "
          "Ready? Begin. Notice. Soften. Let go. Nostrils.")

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
