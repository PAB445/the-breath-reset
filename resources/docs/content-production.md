# The Breath Reset — Content Production Guide

How guided breath videos, reels, YouTube formats, and static social assets are built in this repo. Use this when adding a new practice, re-rendering after copy/timing changes, or producing more Instagram/YouTube content.

---

## Overview

This is **not** a Remotion or npm-based video app. Content is produced with:

| Layer | Tech |
|-------|------|
| **Website** | Plain HTML/CSS/JS, hosted on GitHub Pages |
| **Interactive breath player** | `breathing-reel/` — Canvas/SVG animation in the browser |
| **Video rendering** | Python 3 + Pillow + numpy + **imageio-ffmpeg** (bundled ffmpeg) |
| **Audio** | Pure numpy synthesis in `tmp/make_audio.py` — no paid samples |

There are **two implementations** of the breathing visual that must stay in sync:

1. **Python offline renderer** — `tmp/render_reel.py` (frame-by-frame → MP4)
2. **Web player** — `breathing-reel/script.js` (live preview / optional screen recording)

Both read timing and copy from the same **`tmp/flows.py`** config (the web player mirrors it manually in `script.js`).

---

## Prerequisites

**Python 3** with:

```bash
pip install numpy Pillow imageio-ffmpeg
```

No `requirements.txt` in the repo — install the three packages above.

**Fonts** (already in repo): `breathing-reel/fonts/` — Instrument Serif, Manrope.

**ffmpeg** comes via `imageio-ffmpeg`; scripts call it automatically for MP3 export and MP4 muxing.

---

## Directory structure (content-related)

```
the-breath-reset/
├── tmp/                          # All build scripts live here
│   ├── flows.py                  # ★ Single source of truth for breath flows
│   ├── make_audio.py             # Synthesise audio + master WAVs for MP4s
│   ├── make_reel_cards.py        # Cover + end card PNGs (9:16)
│   ├── render_reel.py            # ★ Main MP4 renderer (all video formats)
│   ├── make_reels.py             # Text-reel frame decks + single posts
│   ├── make_post.py              # Carousel PNGs (4:5)
│   ├── make_cover.py             # YouTube founder cover (16:9, light palette)
│   ├── make_endscreen.py         # YouTube founder end screen (16:9)
│   └── master-<slug>.wav         # Generated audio masters (gitignored-ish temp)
│
├── breathing-reel/                 # Web player + audio assets
│   ├── index.html, script.js, styles.css
│   ├── serve.sh                  # Local HTTP server
│   ├── audio/                    # bell, tones, ambient loops (MP3)
│   └── fonts/
│
├── assets/social/
│   ├── instagram/
│   │   ├── practices/<slug>/     # ★ Guided practice outputs
│   │   │   ├── reel.mp4          # 9:16 video
│   │   │   ├── cover.png         # Thumbnail / scroll-stopper
│   │   │   └── end.png           # Static end card (reference)
│   │   ├── carousels/            # 4:5 carousel frame sequences
│   │   ├── reel-frames/          # 9:16 text-reel PNG decks
│   │   └── posts/                # Single 9:16 posts
│   └── youtube/
│       ├── shorts/<slug>/        # Copy of reel.mp4 + cover.png
│       ├── long/<slug>/          # 16:9 ~5 min videos
│       │   └── youtube.mp4
│       └── founder-video/        # Static 16:9 cover + end-screen PNGs
│
├── videos.html                   # Website page embedding the 9:16 reels
└── resources/docs/               # This guide + design guide PDF
```

---

## Single source of truth: `tmp/flows.py`

Every guided breath **flow** is defined here. Used by audio, cards, and video render.

### Flow fields

| Field | Purpose |
|-------|---------|
| `slug` | URL-safe folder name (`coherent`, `extended-exhale`, `box-breathing`) |
| `category` | Brand pillar: `"relax"`, `"retrain"`, or `"release"` — highlights on cover + in-video brand line |
| `total` | Session length in seconds (reel/short duration) |
| `endCard` | Seconds at end for end-card crossfade |
| `orbMin` / `orbMax` | Normalise orb glow/ring brightness (0–1) |
| `phases` | List of breath phases (see below) |
| `box` | Optional: draw rounded-square progress path (box breathing) |
| `settleDown` | Optional: mist drifts down on exhale |
| `reel` | On-screen eyebrow + subtitle during breathing |
| `cover` | Intro card / thumbnail copy (`hook` uses `\|italic sage\|` syntax) |
| `end` | End card lines, tagline, CTA |

### Phase model

Each phase:

```python
{"name": "inhale", "label": "Breathe in", "dur": 5, "dots": 5, "orb": [0.70, 1.00]}
```

- `name`: `"inhale"` | `"exhale"` | `"hold"` — drives audio cues
- `label`: On-screen cue text
- `dur`: Exact seconds
- `dots`: Timing dots shown during this phase
- `orb`: `[startScale, endScale]` — orb diameter; holds keep scale steady

**Cycle** = sum of phase durations. Breathing loops: `t % cycle`.

### Current flows

| ID | Slug | Duration | Cycle | Category |
|----|------|----------|-------|----------|
| `coherent` | `coherent` | 90s | 10s (5+5 inhale/exhale) | relax |
| `extendedExhale` | `extended-exhale` | 90s | 10s (4+6) | relax |
| `boxBreathing` | `box-breathing` | 120s | 16s (4+4+4+4) | relax |

### ⚠️ Keep in sync

When you change timing or copy in `flows.py`, also update the matching object in **`breathing-reel/script.js`** (`FLOWS`).

---

## Guided practice videos — full pipeline

This is the main workflow for Instagram Reels, YouTube Shorts, and long YouTube.

### Step 1 — Edit the flow (if needed)

Edit `tmp/flows.py` (+ mirror in `breathing-reel/script.js`).

### Step 2 — Generate audio

```bash
python3 tmp/make_audio.py
```

**Outputs:**

| File | Purpose |
|------|---------|
| `breathing-reel/audio/bell.mp3` | Soft bell — session start/end |
| `breathing-reel/audio/tone-inhale.mp3` | Phase cue (web player) |
| `breathing-reel/audio/tone-exhale.mp3` | Phase cue (web player) |
| `breathing-reel/audio/tone-hold.mp3` | Phase cue for box holds (web player) |
| `breathing-reel/audio/ambient-<slug>.mp3` | Breath-synced pad loop (web player) |
| `tmp/master-<slug>.wav` | Full mix for reel/short MP4 |
| `tmp/master-<slug>-long.wav` | Full mix for 5-min YouTube MP4 |

**Master mix contents:**

1. Breath-synced ambient drone (follows orb scale over time)
2. Opening bell at `t = 0`
3. Closing bell at `t = total - endCard`
4. **Phase-start cues** at every inhale/exhale/hold boundary (except first inhale — opening bell marks it; none in last ~1s before closing bell)

**Phase cue design** (in `CUE_SPEC` in `make_audio.py`):

- **Inhale** - soft upward air swell with a subtle rising body
- **Exhale** - longer warm air release with a subtle falling body
- **Hold** - very quiet low pulse / shimmer

To adjust or remove cues: edit `CUE_SPEC`, `cue()`, and/or the scheduling loop in `make_master()`. Re-run `make_audio.py` then re-render videos.

**Long-form constants** (keep in sync):

- `LONG_DUR = 300` and `LONG_ENDCARD = 4` in `make_audio.py`
- `FORMATS["youtube"]` in `render_reel.py` (`dur=300`, `endCard=4`)

### Step 3 — Generate cover + end cards

```bash
python3 tmp/make_reel_cards.py
```

**Outputs:** `assets/social/instagram/practices/<slug>/cover.png` and `end.png`

- **Cover** — scroll-stopper: logo, hook, steps, pillar line at bottom
- **End** — static reference card (also rendered into video crossfade)
- **Pillar line** — `RELAX · RETRAIN · RELEASE` with active category in clay, others dimmed (from `flow["category"]`)

### Step 4 — Render videos

```bash
python3 tmp/render_reel.py
```

**Outputs per flow:**

| Format | Resolution | Duration | Output path |
|--------|------------|----------|-------------|
| **Instagram Reel** | 1080×1920 (9:16) | `flow["total"]` | `assets/social/instagram/practices/<slug>/reel.mp4` |
| **YouTube Short** | Same file as reel | Same | `assets/social/youtube/shorts/<slug>/reel.mp4` (+ `cover.png` copied) |
| **Long YouTube** | 1920×1080 (16:9) | 300s (5 min) | `assets/social/youtube/long/<slug>/youtube.mp4` |

After reels render, `copy_shorts()` automatically copies `reel.mp4` + `cover.png` to the Shorts folder.

**Video specs:** 30 fps, H.264 (libx264), yuv420p, CRF 18, AAC audio from master WAV, `-movflags +faststart`.

**Long YouTube extras:**

- Breathing animation **loops** for 5 minutes (phase math uses `t % cycle`)
- **Intro title card** (~6s hold + ~1.5s crossfade out) — copy from `flow["cover"]`
- **End card** crossfade in over last `endCard` seconds — copy from `flow["end"]`
- Landscape layout: orb centred, text repositioned via `make_layout()` in `render_reel.py`

### Environment variables (render)

| Variable | Effect |
|----------|--------|
| `REEL_FLOW=coherent` | Render one flow only (`coherent`, `extendedExhale`, `boxBreathing`) |
| `REEL_FORMAT=reel` | Render one format only (`reel` or `youtube`) |
| `REEL_TEST=1` | Output a few sample frames + PNGs to `tmp/` (fast layout check) |

Examples:

```bash
REEL_TEST=1 REEL_FORMAT=youtube REEL_FLOW=coherent python3 tmp/render_reel.py
REEL_FORMAT=youtube python3 tmp/render_reel.py          # long videos only
REEL_FLOW=boxBreathing python3 tmp/render_reel.py        # one flow, all formats
```

### Typical full rebuild (after flow/copy/audio changes)

```bash
python3 tmp/make_audio.py
python3 tmp/make_reel_cards.py    # if cover/end copy or category changed
python3 tmp/render_reel.py
```

**Render time (approximate, offline on a laptop):**

- 3 reels (90s + 90s + 120s): ~5–8 min
- 3 long YouTube (300s each, 9000 frames): ~25–30 min each batch
- Full pipeline (6 videos): ~35–45 min

---

## Web player preview

Preview before or instead of Python render:

```bash
cd breathing-reel && ./serve.sh 8080
```

Open:

- `http://localhost:8080/index.html?flow=coherent`
- `http://localhost:8080/index.html?flow=extendedExhale`
- `http://localhost:8080/index.html?flow=boxBreathing`
- `http://localhost:8080/index.html?preview=12.5` — static frame at t=12.5s

**Do not** open `index.html` via `file://` — audio and fonts need HTTP.

**Audio in browser** (`AudioBus` in `script.js`):

- Ambient loop fades in on start
- Bell on start and near end
- `toneInhale` / `toneExhale` / `toneHold` on each phase change
- Same MP3 files as generated by `make_audio.py`

---

## Visual system (guided videos)

**Palette** (dark warm-black + sage — matches design guide):

| Name | RGB |
|------|-----|
| BG | 16, 13, 11 |
| Sage | 143, 165, 138 |
| Off-white | 239, 231, 217 |
| Clay (accent) | 209, 144, 115 |
| Muted | 172, 164, 150 |

**On-screen elements:**

- Radial gradient background + soft sage blobs + vignette
- Central **orb** (scales with breath phase, eased)
- **Glow** + **mist particles** (breath-amplitude driven)
- Concentric **rings**
- **Progress arc** (coherent/extended) or **box path + comet** (box breathing)
- Eyebrow + subtitle (top), cue text + dots (mid), brand + pillar line (bottom)
- End card crossfade (last few seconds)

Portrait layout constants live in `make_layout()` for `reel`; landscape constants for `youtube`.

---

## Brand pillars (Relax · Retrain · Release)

Each flow has `"category": "relax" | "retrain" | "release"`.

**Where it appears:**

1. **Cover PNG** — bottom line: active pillar in clay/bold, others dimmed (`make_reel_cards.py`)
2. **In-video brand line** — `RELAX. RETRAIN. RELEASE.` with same highlighting (`render_reel.py` → `brand_pillars()`)
3. **Long video intro card** — same pillar line at bottom during intro

All three current practices are **Relax**. For a Retrain or Release video, set `category` and regenerate cards + re-render.

---

## Static social content (PNG only)

These scripts produce **images**, not MP4s. Assemble into reels/carousels manually in CapCut, Instagram, etc.

### Text-reel decks + single posts — `tmp/make_reels.py`

```bash
python3 tmp/make_reels.py
```

**Outputs (1080×1920, 9:16):**

| Output | Description |
|--------|-------------|
| `assets/social/instagram/reel-frames/breathwork-not-deep-breathing/frame-01..10.png` | Educational text reel |
| `assets/social/instagram/reel-frames/session-what-happens/frame-01..11.png` | Session explainer reel |
| `assets/social/instagram/posts/anxiety-and-body.png` | Single post |
| `assets/social/instagram/posts/high-functioning.png` | Single post |
| `assets/social/instagram/posts/forcing-calm.png` | Single post |

Edit frame copy in the `DECKS` / `singles()` sections at the bottom of `make_reels.py`.

### Carousel — `tmp/make_post.py`

```bash
python3 tmp/make_post.py
```

**Output:** `assets/social/instagram/carousels/nervous-system/frame-01..12.png` (1080×1350, **4:5**)

Orb **state** changes per frame (tense → wired → freeze → coherent → final). Edit `FRAMES` in the script.

### YouTube founder video assets (light palette, 16:9)

Separate design language from breath videos (cream/charcoal, not dark sage):

```bash
python3 tmp/make_cover.py       # → assets/social/youtube/founder-video/cover.png
python3 tmp/make_endscreen.py   # → assets/social/youtube/founder-video/end-screen.png
```

1280×720 supersampled at 2×. No MP4 render script for founder video in repo.

---

## Website integration

**`videos.html`** embeds the 9:16 practice reels:

- Posters: `assets/social/instagram/practices/<slug>/cover.png`
- Sources: `assets/social/instagram/practices/<slug>/reel.mp4`

Long 16:9 YouTube files are **not** embedded on the site yet (files live under `assets/social/youtube/long/`).

---

## Adding a new breath practice (checklist)

1. **Define flow** in `tmp/flows.py`:
   - Unique `slug`, `category`, phases, copy blocks
   - Set `total` (reel length) — typical 60–120s for social

2. **Mirror** the same flow in `breathing-reel/script.js` (`FLOWS` object)

3. **Generate assets:**
   ```bash
   python3 tmp/make_audio.py
   python3 tmp/make_reel_cards.py
   python3 tmp/render_reel.py
   ```

4. **Preview** in browser: `?flow=<yourFlowId>`

5. **Optional:** Add to `videos.html` with poster + `<video>` source

6. **Optional:** If duration ≠ 90/120s, update copy in `reel.sub`, `cover.eyebrow`, etc.

For a **long YouTube** version: no extra config — renderer loops any flow to 300s automatically using `-long` master audio.

---

## Renderer architecture (`tmp/render_reel.py`)

```
flows.py
    ↓
make_audio.py → master-<slug>.wav / master-<slug>-long.wav
    ↓
render_reel.py
    ├── FORMATS["reel"]    → 1080×1920, flow total, no intro
    └── FORMATS["youtube"] → 1920×1080, 300s, 6s intro card
    ↓
assets/social/{instagram|youtube}/...
    ↓
copy_shorts() → youtube/shorts/ (from instagram reel)
```

Per format:

1. `make_layout(fmt)` — all pixel positions
2. `build_assets(L)` — base gradient, orb sprite, glow, mist (cached per format)
3. For each frame: phase_at → orb scale → draw layers → intro/end crossfades
4. ffmpeg mux via imageio-ffmpeg with master WAV

---

## Audio architecture (`tmp/make_audio.py`)

```
ambient(flow, dur)     → breath-envelope drone
bell()                 → session markers
cue("inhale"|"exhale"|"hold") → phase transitions

make_master():
  ambient + open bell + close bell + scheduled cues → WAV
```

Phase schedule: walk timeline with `phase_starts(flow, until)`, mix cue at each boundary.

---

## Troubleshooting

| Issue | Check |
|-------|--------|
| Video has no audio | Run `make_audio.py` first; confirm `tmp/master-<slug>.wav` exists |
| Timing feels wrong | Compare `flows.py` vs `script.js`; re-run audio + render |
| Layout looks off in landscape | `REEL_TEST=1 REEL_FORMAT=youtube` → inspect `tmp/frame_*.png` |
| Shorts out of date | Re-run full `render_reel.py` (copies after reel format) or manually copy reel + cover |
| Pillow deprecation warnings | Harmless; `Image.fromarray(..., mode)` warnings in Pillow 12+ |
| Render very slow | Expected for 9000-frame long videos; use `REEL_FLOW` / `REEL_FORMAT` to render one at a time |

---

## Quick reference — all commands

```bash
# Guided practice videos (main pipeline)
python3 tmp/make_audio.py
python3 tmp/make_reel_cards.py
python3 tmp/render_reel.py

# Static social PNGs
python3 tmp/make_reels.py      # text reels + posts
python3 tmp/make_post.py       # 4:5 carousel
python3 tmp/make_cover.py      # YouTube founder cover
python3 tmp/make_endscreen.py  # YouTube founder end screen

# Web preview
cd breathing-reel && ./serve.sh 8080
```

---

## File index

| Script | Input | Output |
|--------|-------|--------|
| `flows.py` | — | Flow config (imported by others) |
| `make_audio.py` | `flows.py` | MP3s + `tmp/master-*.wav` |
| `make_reel_cards.py` | `flows.py` | `cover.png`, `end.png` per practice |
| `render_reel.py` | `flows.py` + master WAV | `reel.mp4`, `youtube.mp4`, Shorts copy |
| `make_reels.py` | Deck data in script | Text-reel frames + posts |
| `make_post.py` | Frame data in script | Carousel PNGs |
| `make_cover.py` | — | Founder YouTube cover |
| `make_endscreen.py` | — | Founder YouTube end screen |

---

*Last updated: reflects multi-format pipeline (Instagram Reel, YouTube Shorts, long 16:9 YouTube), brand pillar highlighting on covers and in-video, and phase audio cues baked into all video masters.*
