#!/usr/bin/env bash
# Renders every takeaway-card deliverable from src/cards.html into output/.
# Needs Google Chrome (or set CHROME=/path/to/chrome).
set -euo pipefail

cd "$(dirname "$0")"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
SRC="file://$(pwd)/src/cards.html"
OUT="output"
mkdir -p "$OUT"

chrome() {
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --no-first-run \
    --no-default-browser-check --user-data-dir="$(mktemp -d)" \
    --run-all-compositor-stages-before-draw --virtual-time-budget=8000 "$@" 2>/dev/null
}

pdf() { chrome --no-pdf-header-footer --print-to-pdf="$OUT/$1" "$SRC?$2"; }

# width/height in CSS px, scale = device pixels per CSS px (3.125 = 300 DPI)
png() { chrome --window-size="$3,$4" --force-device-scale-factor="$5" --screenshot="$OUT/$1" "$SRC?$2"; }

echo "Layout check (spareMm must be >= 0; numbers are wrapped line counts):"
chrome --dump-dom "$SRC?view=check" | sed -n '/<pre id="check">/,/<\/pre>/p' | sed 's/<[^>]*>//g'
[[ "${1:-}" == "--check" ]] && exit 0

pdf "the-breath-reset-cards-A4-home-print.pdf"        "view=sheet"
pdf "the-breath-reset-cards-A4-ivory-stock.pdf"       "view=sheet&tint=0"
pdf "the-breath-reset-card-A6-trade-print-bleed.pdf"  "view=a6"

png "card-front-A6-300dpi.png"      "view=card-front"    397  562  3.125
png "card-back-A6-300dpi.png"       "view=card-back"     397  562  3.125
png "sheet-front-A4-300dpi.png"     "view=sheet-front"   794  1123 3.125
png "sheet-back-A4-300dpi.png"      "view=sheet-back"    794  1123 3.125
png "mockup-front-and-back.png"     "view=mockup"        1600 1100 2
png "mockup-A4-sheets.png"          "view=sheet-preview" 1600 1100 2

# Tag print images as 300 DPI so they open at true physical size, and add JPEG copies.
for f in card-front-A6 card-back-A6 sheet-front-A4 sheet-back-A4; do
  sips -s dpiWidth 300 -s dpiHeight 300 "$OUT/$f-300dpi.png" >/dev/null
done
for f in "$OUT"/*.png; do
  sips -s format jpeg -s formatOptions 95 "$f" --out "${f%.png}.jpg" >/dev/null
done

ls -lh "$OUT"
