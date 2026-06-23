#!/usr/bin/env bash
# Serve the breathing reel locally (required — do not open index.html via file://)
cd "$(dirname "$0")"
PORT="${1:-8080}"
echo "Breathing reel: http://localhost:${PORT}"
echo "Press Ctrl+C to stop."
python3 -m http.server "$PORT"
