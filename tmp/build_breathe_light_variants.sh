#!/bin/bash
# Breathe Light with the v2 practice script: audio for all three cuts, then picture.
#   film     assets/social/youtube/relax/breathe-light/          (with BOLT)
#   no-bolt  assets/social/youtube/relax/breathe-light-no-bolt/
#   reel     assets/social/instagram/practices/breathe-light/
set -euo pipefail
cd "$(dirname "$0")/.."
PY=tmp/.venv-dsp/bin/python
YT="$PWD/assets/social/youtube/relax"

echo "=== audio ==="
"$PY" tmp/make_breathe_light_v2.py all

echo "=== film ==="
BL_SRC="$YT/breathe-light" "$PY" tmp/render_breathe_light.py
BL_SRC="$YT/breathe-light" BL_THUMB=1 "$PY" tmp/render_breathe_light.py

echo "=== no-bolt ==="
BL_SRC="$YT/breathe-light-no-bolt" "$PY" tmp/render_breathe_light.py
BL_SRC="$YT/breathe-light-no-bolt" BL_THUMB=1 "$PY" tmp/render_breathe_light.py

echo "=== reel ==="
"$PY" tmp/render_breathe_light_reel.py
echo "=== done ==="
