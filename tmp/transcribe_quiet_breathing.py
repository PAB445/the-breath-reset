#!/usr/bin/env python3
"""
Word-level transcript for the quiet-breathing video. Run with the ASR venv:

  HF_HOME=tmp/.hf tmp/.venv-asr/bin/python tmp/transcribe_quiet_breathing.py

Writes tmp/quiet-breathing-words.json -- [{"w", "s", "e"}] -- which
render_quiet_breathing.py reads to time subtitles and overlays.
"""
import json
import os

from faster_whisper import WhisperModel

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = os.path.join(ROOT, "assets", "social", "youtube", "retrain",
                      "quiet-breathing", "quiet-breathing-source.mp4")
OUT = os.path.join(HERE, "quiet-breathing-words.json")

PROMPT = ("Take a deep breath for me. Oxygen saturation, carbon dioxide, CO2. "
          "Smaller. Slower. Quieter. Quiet breathing.")

model = WhisperModel("medium.en", device="cpu", compute_type="int8")
segments, _ = model.transcribe(SOURCE, word_timestamps=True, beam_size=5,
                               initial_prompt=PROMPT, vad_filter=False)
words = []
for seg in segments:
    print(f"[{seg.start:6.2f} - {seg.end:6.2f}] {seg.text}")
    for w in seg.words:
        words.append({"w": w.word.strip(), "s": round(w.start, 3),
                      "e": round(w.end, 3)})

with open(OUT, "w") as f:
    json.dump(words, f, indent=0)
print("saved", os.path.relpath(OUT, ROOT), len(words), "words")
