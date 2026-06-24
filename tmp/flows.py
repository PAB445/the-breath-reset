#!/usr/bin/env python3
"""
Single source of truth for every Breath Reset flow.

Used by:
  tmp/make_audio.py        (per-flow ambient + master mixes)
  tmp/make_reel_cards.py   (cover + end cards)
  tmp/render_reel.py       (the MP4s)

The web player (breathing-reel/script.js) mirrors these same numbers in its
own FLOWS object — keep the two in sync when you change timing or copy.

PHASE MODEL
  Each flow is a list of phases. A phase has:
    name : "inhale" | "exhale" | "hold"
    label: cue text shown on screen
    dur  : seconds (exact)
    dots : number of timing dots for this phase
    orb  : [startScale, endScale]  (orb diameter fraction; holds keep it steady)
  cycle  = sum of phase durations
  total  = full session length (seconds)
  orbMin/orbMax are used to normalise glow/ring brightness (0..1).
"""

# brand palette (matches styles.css / the design guide)
PALETTE = dict(
    BG=(16, 13, 11), BG_LIFT=(26, 21, 18), BG_DEEP=(10, 8, 7),
    SAGE=(143, 165, 138), SAGE_LT=(193, 205, 186), SAGE_DARK=(95, 116, 94),
    OFF=(239, 231, 217), MUTED=(172, 164, 150), CLAY=(209, 144, 115),
    FAINT=(60, 57, 52),
)

FLOWS = {
    # ===================================================================
    "coherent": {
        "slug": "coherent",
        "category": "relax",          # which brand pillar: relax | retrain | release
        "total": 90, "endCard": 3,
        "orbMin": 0.70, "orbMax": 1.00,
        "phases": [
            {"name": "inhale", "label": "Breathe in",  "dur": 5, "dots": 5, "orb": [0.70, 1.00]},
            {"name": "exhale", "label": "Breathe out", "dur": 5, "dots": 5, "orb": [1.00, 0.70]},
        ],
        "reel": {"eyebrow": "FOR WHEN YOUR BODY FEELS SWITCHED ON",
                 "sub": "A 90-second coherent breath reset"},
        "cover": {"eyebrow": "A 90-SECOND COHERENT BREATH RESET",
                  "hook": "For when your body feels |switched on|",
                  "steps": ["Breathe in for 5.", "Breathe out for 5.",
                            "No forcing. Just follow the rhythm."]},
        "end": {"lines": ["Take one normal breath.", "Notice what feels different."],
                "tagline": "Relax. Retrain. Release.",
                "cta": "Save this for when you need to come back to yourself."},
    },
    # ===================================================================
    "extendedExhale": {
        "slug": "extended-exhale",
        "category": "relax",
        "total": 90, "endCard": 3,
        "orbMin": 0.62, "orbMax": 0.95,
        "settleDown": True,     # mist drifts downward; field quietens on exhale
        "phases": [
            {"name": "inhale", "label": "Breathe in",  "dur": 4, "dots": 4, "orb": [0.72, 0.95]},
            {"name": "exhale", "label": "Breathe out", "dur": 6, "dots": 6, "orb": [0.95, 0.62]},
        ],
        "reel": {"eyebrow": "FOR WHEN YOU NEED TO COME DOWN",
                 "sub": "A slow exhale breath reset"},
        "cover": {"eyebrow": "A SLOW EXHALE BREATH RESET",
                  "hook": "For when you need to |come down|",
                  "steps": ["Breathe in for 4.", "Breathe out for 6.",
                            "Let the exhale be soft and unforced."]},
        "end": {"lines": ["Let your breath return to normal.", "Notice the weight of your body."],
                "tagline": "Relax. Retrain. Release.",
                "cta": "Save this for the end of a stressful day."},
    },
    # ===================================================================
    "boxBreathing": {
        "slug": "box-breathing",
        "category": "relax",
        "total": 120, "endCard": 3,
        "orbMin": 0.65, "orbMax": 0.95,
        "box": True,            # draw the rounded-square progress path
        "phases": [
            {"name": "inhale", "label": "Breathe in",  "dur": 4, "dots": 4, "orb": [0.65, 0.95]},
            {"name": "hold",   "label": "Hold",        "dur": 4, "dots": 4, "orb": [0.95, 0.95]},
            {"name": "exhale", "label": "Breathe out", "dur": 4, "dots": 4, "orb": [0.95, 0.65]},
            {"name": "hold",   "label": "Hold",        "dur": 4, "dots": 4, "orb": [0.65, 0.65]},
        ],
        "reel": {"eyebrow": "FOR WHEN YOUR MIND FEELS SCATTERED",
                 "sub": "A 2-minute box breathing reset"},
        "cover": {"eyebrow": "A 2-MINUTE BOX BREATHING RESET",
                  "hook": "For when your mind feels |scattered|",
                  "steps": ["Inhale for 4. Hold for 4.", "Exhale for 4. Hold for 4.",
                            "Move slowly. Stay soft."]},
        "end": {"lines": ["Take one easy breath.", "Notice the space around your thoughts."],
                "tagline": "Relax. Retrain. Release.",
                "cta": "Save this before work, calls, or hard conversations."},
    },
}

def cycle_len(flow):
    return sum(p["dur"] for p in flow["phases"])

def phase_at(flow, t):
    """Return (phase_dict, phase_index, elapsed_in_phase, progress_0_1) at time t."""
    c = cycle_len(flow)
    inc = t % c
    acc = 0.0
    for i, p in enumerate(flow["phases"]):
        if inc < acc + p["dur"] or i == len(flow["phases"]) - 1:
            el = inc - acc
            return p, i, el, (el / p["dur"] if p["dur"] else 1.0)
        acc += p["dur"]
    # fallback (shouldn't hit)
    p = flow["phases"][-1]
    return p, len(flow["phases"]) - 1, 0.0, 0.0

def ease_in_out(p):
    import math
    return (1 - math.cos(math.pi * p)) / 2

def orb_scale_at(flow, t):
    """Eased orb scale at time t. Holds stay steady automatically."""
    p, _, _, prog = phase_at(flow, t)
    o0, o1 = p["orb"]
    if p["name"] == "hold":
        return o0
    return o0 + (o1 - o0) * ease_in_out(prog)
