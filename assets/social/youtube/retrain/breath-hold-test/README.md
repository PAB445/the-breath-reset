# CO2 Tolerance Video Set

This folder contains the Breath Hold Test assets:

- `cover.png` — 1280x720 cover screen
- `end-screen.png` — 1280x720 end screen
- `timer-overlay.html` — browser timer overlay for screen recording
- `timer-overlay.css` / `timer-overlay.js` — overlay styling and timing logic
- `0629.mov` — source talking video
- `0629-timer.mp4` — rendered video with the timer baked in from `03:05` to `04:15`
- `0629-final.mp4` — final assembled video: `4s` cover, full talking video with timer, then `5s` end screen
- `cover-still.png` — source still used in the cover image

## Timer Overlay

Open `timer-overlay.html` in a browser and start recording. The timer starts immediately at `00:00`, counts up in `MM:SS`, and defaults to `01:00`.

Useful URL options:

- `?duration=90` changes the max duration to 90 seconds.
- `?bg=green` uses pure green for chroma keying.
- `?bg=black` uses pure black for luma/key workflows.
- `?position=top-left`, `bottom-right`, `bottom-left`, or `center` moves the timer.
- `?scale=1.2` changes the timer size.
- `?note=0` hides the instruction line.

Examples:

```text
timer-overlay.html?duration=60&bg=green
timer-overlay.html?duration=120&bg=black&position=bottom-right&scale=0.9
```

The page background is transparent by default in CSS. Most normal browser screen recordings do not export a true alpha channel, so use `bg=green` or `bg=black` when you need a reliable keyable overlay in editing software.

## Design Notes

The cover and end screen use the same warm cream, sage, clay, serif/sans typography, faint breathing rings, and soft duotone treatment as the existing founder video cards. This set is marked as a RETRAIN asset in the brand pillar line. The timer overlay uses the darker practice-video palette but removes the decorative background so it can sit cleanly over recorded talking footage.

To regenerate the PNG cards after copy or layout changes:

```bash
python3 tmp/make_co2_tolerance.py
```

To regenerate the sharper rendered talking video with the timer baked in and the final assembled export:

```bash
python3 tmp/render_co2_timer_video.py
```
