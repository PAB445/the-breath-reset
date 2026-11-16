#!/usr/bin/env python3
"""
Breathe Light -- voice cleanup (noise + room echo). Run with the DSP venv:

  tmp/.venv-dsp/bin/python tmp/clean_breathe_light_voice.py            # full file
  BL_EXCERPT=60,100 tmp/.venv-dsp/bin/python tmp/clean_breathe_light_voice.py

  (venv: uv venv --python 3.10 tmp/.venv-dsp; uv pip install torch==2.0.1
   torchaudio==2.0.2 "numpy<2" deepfilternet nara_wpe soundfile scipy pyloudnorm)

Chain:
  1. WPE (weighted prediction error) dereverberation -- a linear-prediction
     method that removes the late reverb tail of the room without the
     "underwater" artefacts of spectral gating. Taps/delay tuned for a small
     reflective room (iPad on a desk).
  2. DeepFilterNet 3 -- neural speech denoiser; also suppresses the residual
     diffuse reverb WPE leaves. atten_lim keeps it from gating the room dead,
     so breaths and the natural tail of each word survive.
  3. Gentle tonal shaping happens later in the mix script (EQ / compression),
     not here, so this file is the "clean but uncoloured" voice.

Writes tmp/bl-voice-clean.wav (48 kHz mono float).
"""
import os

import numpy as np
import soundfile as sf
import torch
from df.enhance import enhance, init_df
from nara_wpe.utils import istft, stft
from nara_wpe.wpe import wpe
from scipy.signal import resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))
TAG = os.environ.get("BL_TAG", "bl")                 # "bl2" for the v2 script
SRC = os.path.join(HERE, f"{TAG}-source.wav")         # 44.1k mono from the m4a
OUT = os.path.join(HERE, f"{TAG}-voice-clean.wav")

WPE_TAPS = int(os.environ.get("BL_WPE_TAPS", 10))
WPE_DELAY = 3
WPE_ITER = 3
DF_ATTEN_DB = float(os.environ.get("BL_DF_ATTEN", 35))
WPE_MIX = float(os.environ.get("BL_WPE_MIX", 1.0))


def dereverb(x, sr):
    size, shift = 1024, 256
    Y = stft(x[None, :], size=size, shift=shift)          # (1, T, F)
    Y = Y.transpose(2, 0, 1)                              # (F, 1, T)
    Z = wpe(Y, taps=WPE_TAPS, delay=WPE_DELAY, iterations=WPE_ITER,
            statistics_mode="full")
    z = istft(Z.transpose(1, 2, 0), size=size, shift=shift)[0]
    z = z[:len(x)]
    if len(z) < len(x):
        z = np.pad(z, (0, len(x) - len(z)))
    return WPE_MIX * z + (1 - WPE_MIX) * x


def denoise(x48):
    model, state, _ = init_df()
    torch.set_num_threads(8)
    y = enhance(model, state, torch.from_numpy(x48[None, :].astype(np.float32)),
                atten_lim_db=DF_ATTEN_DB)
    return y[0].numpy()


def main():
    x, sr = sf.read(SRC, dtype="float64")
    out = OUT
    ex = os.environ.get("BL_EXCERPT")
    if ex:
        a, b = (float(v) for v in ex.split(","))
        x = x[int(a * sr):int(b * sr)]
        out = OUT.replace(".wav", f"-x{int(a)}.wav")
        sf.write(out.replace("clean", "orig"), x, sr)
    x48 = resample_poly(x, 160, 147)                      # 44.1k -> 48k
    sr48 = 48000
    y = dereverb(x48, sr48)
    if os.environ.get("BL_NO_DF") != "1":
        y = denoise(y)
    sf.write(out, y.astype(np.float32), sr48, subtype="FLOAT")
    print("saved", out)


if __name__ == "__main__":
    main()
