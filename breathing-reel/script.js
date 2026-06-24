/* ===========================================================================
   THE BREATH RESET — config-driven breath flows (vertical reel)
   ---------------------------------------------------------------------------
   One engine, many flows. A single requestAnimationFrame clock drives the orb,
   glow, rings, mist, cue, dots, the box path, and the end card — all tied to
   PHASE PROGRESS (never an arbitrary CSS loop), so timing is exact.

   ┌─ HOW TO SWITCH FLOW ─────────────────────────────────────────────────┐
   │ Add ?flow=<id> to the URL:                                            │
   │   index.html?flow=coherent        5s in / 5s out, 90s                 │
   │   index.html?flow=extendedExhale  4s in / 6s out, 90s (slow downshift)│
   │   index.html?flow=boxBreathing    4-4-4-4 with holds, 120s            │
   │ Or change DEFAULT_FLOW below.                                         │
   └──────────────────────────────────────────────────────────────────────┘

   ┌─ WHERE TO ADJUST ────────────────────────────────────────────────────┐
   │ • Phase durations / order ...... FLOWS[id].phases[].dur               │
   │ • Orb size per phase ............ FLOWS[id].phases[].orb [start,end]   │
   │ • Total length / end card ....... FLOWS[id].total / .endCard          │
   │ • On-screen copy ................ FLOWS[id].reel / .end               │
   │ • Colours ....................... styles.css  (:root variables)        │
   └──────────────────────────────────────────────────────────────────────┘

   HOLDS (box breathing): a phase named "hold" keeps the orb steady (orb start
   == end). The dots and the box comet keep moving, plus a tiny glow shimmer,
   so a hold reads as a calm, deliberate pause — never a frozen animation.

   THE BOX PATH: for flows with box:true, a soft rounded square is shown and a
   glowing comet travels exactly one lap per breath cycle. With four equal
   phases the comet crosses a side per phase: up the left (inhale), across the
   top (hold), down the right (exhale), across the bottom (hold). See boxPoint.
   =========================================================================== */

const DEFAULT_FLOW = "coherent";

const FLOWS = {
  coherent: {
    slug: "coherent", total: 90, endCard: 3,
    orbMin: 0.70, orbMax: 1.00,
    hint: "90 seconds · coherent breathing",
    phases: [
      { name: "inhale", label: "Breathe in",  dur: 5, dots: 5, orb: [0.70, 1.00] },
      { name: "exhale", label: "Breathe out", dur: 5, dots: 5, orb: [1.00, 0.70] },
    ],
    reel: { eyebrow: "For when your body feels switched on",
            sub: "A 90-second coherent breath reset" },
    end: { lines: ["Take one normal breath.", "Notice what feels different."],
           tagline: "Relax. Retrain. Release.",
           cta: "Save this for when you need to come back to yourself." },
  },

  extendedExhale: {
    slug: "extended-exhale", total: 90, endCard: 3,
    orbMin: 0.62, orbMax: 0.95,
    settleDown: true,                 // mist settles downward on the long exhale
    hint: "90 seconds · slow exhale",
    phases: [
      { name: "inhale", label: "Breathe in",  dur: 4, dots: 4, orb: [0.72, 0.95] },
      { name: "exhale", label: "Breathe out", dur: 6, dots: 6, orb: [0.95, 0.62] },
    ],
    reel: { eyebrow: "For when you need to come down",
            sub: "A slow exhale breath reset" },
    end: { lines: ["Let your breath return to normal.", "Notice the weight of your body."],
           tagline: "Relax. Retrain. Release.",
           cta: "Save this for the end of a stressful day." },
  },

  boxBreathing: {
    slug: "box-breathing", total: 120, endCard: 3,
    orbMin: 0.65, orbMax: 0.95,
    box: true,                        // show the rounded-square progress path
    hint: "2 minutes · box breathing",
    phases: [
      { name: "inhale", label: "Breathe in",  dur: 4, dots: 4, orb: [0.65, 0.95] },
      { name: "hold",   label: "Hold",        dur: 4, dots: 4, orb: [0.95, 0.95] },
      { name: "exhale", label: "Breathe out", dur: 4, dots: 4, orb: [0.95, 0.65] },
      { name: "hold",   label: "Hold",        dur: 4, dots: 4, orb: [0.65, 0.65] },
    ],
    reel: { eyebrow: "For when your mind feels scattered",
            sub: "A 2-minute box breathing reset" },
    end: { lines: ["Take one easy breath.", "Notice the space around your thoughts."],
           tagline: "Relax. Retrain. Release.",
           cta: "Save this before work, calls, or hard conversations." },
  },
};

/* Visual tuning shared across flows */
const RENDER = {
  particleCount: 46,
  particleLift: 70,                   // px the mist rises on a full inhale
  orbCenter: { x: 540, y: 980 },      // where mist gathers (stage px)
  cueFade: 0.6,                       // dots/cue settle window (s)
};

/* ----------------------------- pick flow --------------------------- */
const flowId = new URLSearchParams(location.search).get("flow") || DEFAULT_FLOW;
const FLOW = FLOWS[flowId] || FLOWS[DEFAULT_FLOW];

const CYCLE = FLOW.phases.reduce((s, p) => s + p.dur, 0);
const TOTAL = FLOW.total;
const END_START = TOTAL - FLOW.endCard;

/* ----------------------------- DOM refs ---------------------------- */
const stage       = document.getElementById("stage");
const cueText      = document.getElementById("cueText");
const dotsEl      = document.getElementById("dots");
const startScreen = document.getElementById("startScreen");
const beginBtn    = document.getElementById("beginBtn");
const canvas      = document.getElementById("mist");
const ctx         = canvas.getContext("2d");
const progressBar = document.getElementById("progressBar");
const boxComet    = document.getElementById("boxComet");

/* Inject per-flow copy */
document.getElementById("eyebrow").textContent    = FLOW.reel.eyebrow;
document.getElementById("subeyebrow").textContent = FLOW.reel.sub;
document.getElementById("startTitle").textContent = FLOW.reel.eyebrow;
document.getElementById("startHint").textContent  = FLOW.hint;
document.getElementById("endLine1").textContent   = FLOW.end.lines[0];
document.getElementById("endLine2").textContent   = FLOW.end.lines[1] || "";
document.querySelector(".end-tag").textContent    = FLOW.end.tagline;
document.getElementById("endCta").textContent     = FLOW.end.cta;
if (FLOW.box) stage.classList.add("is-box");

/* Progress arc geometry — must match the <circle r> in index.html */
const ARC_R = 315;
const ARC_CIRC = 2 * Math.PI * ARC_R;
progressBar.style.strokeDasharray = ARC_CIRC.toFixed(1);
progressBar.style.strokeDashoffset = ARC_CIRC.toFixed(1);

/* ----------------------- Fit stage to screen ----------------------- */
function fitStage() {
  const scale = Math.min(window.innerWidth / 1080, window.innerHeight / 1920);
  stage.style.transform = `scale(${scale})`;
}
window.addEventListener("resize", fitStage);
fitStage();

/* --------------------------- Mist field ---------------------------- */
const DPR = Math.min(window.devicePixelRatio || 1, 2);
canvas.width  = 1080 * DPR;
canvas.height = 1920 * DPR;
ctx.scale(DPR, DPR);

const sprite = (() => {
  const s = document.createElement("canvas");
  s.width = s.height = 64;
  const c = s.getContext("2d");
  const g = c.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0,   "rgba(193, 205, 186, 0.9)");
  g.addColorStop(0.4, "rgba(143, 165, 138, 0.45)");
  g.addColorStop(1,   "rgba(143, 165, 138, 0)");
  c.fillStyle = g;
  c.fillRect(0, 0, 64, 64);
  return s;
})();

const particles = Array.from({ length: RENDER.particleCount }, () => {
  const angle = Math.random() * Math.PI * 2;
  const dist  = 120 + Math.random() * 460;
  return {
    x: RENDER.orbCenter.x + Math.cos(angle) * dist * 0.9,
    y: RENDER.orbCenter.y + Math.sin(angle) * dist,
    size: 26 + Math.random() * 70,
    baseAlpha: 0.04 + Math.random() * 0.10,
    wobAmp: 6 + Math.random() * 12,
    wobSpeed: 0.2 + Math.random() * 0.5,
    phase: Math.random() * Math.PI * 2,
    drift: 0.1 + Math.random() * 0.25,
  };
});

function drawMist(t, b) {
  ctx.clearRect(0, 0, 1080, 1920);
  ctx.globalCompositeOperation = "lighter";
  for (const p of particles) {
    const lift = b * RENDER.particleLift;
    const wob  = Math.sin(t * p.wobSpeed + p.phase) * p.wobAmp;
    const slow = ((t * p.drift * 30) % 80) - 40;
    let y = p.y - lift + slow;
    if (FLOW.settleDown) y += (1 - b) * 42;     // extra downward settle on exhale
    const a = p.baseAlpha * (0.35 + 0.65 * b);
    ctx.globalAlpha = a;
    ctx.drawImage(sprite, p.x + wob - p.size / 2, y - p.size / 2, p.size, p.size);
  }
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = "source-over";
}

/* ----------------------- Easing (organic) -------------------------- */
const easeInOut = (p) => (1 - Math.cos(Math.PI * p)) / 2;

/* ----------------------- Box path geometry ------------------------- */
/* u in [0,1) → point on the rounded square, matching the four sides to the
   four breath phases (up-left, top, down-right, bottom). */
function boxPoint(u) {
  const C = 360, Q = 330;                       // centre, half-size (viewBox 720)
  const pts = [[C - Q, C + Q], [C - Q, C - Q], [C + Q, C - Q], [C + Q, C + Q]]; // BL,TL,TR,BR
  const seg = Math.min(Math.floor(u * 4), 3);
  const f = u * 4 - seg;
  const a = pts[seg], bb = pts[(seg + 1) % 4];
  return [a[0] + (bb[0] - a[0]) * f, a[1] + (bb[1] - a[1]) * f];
}

/* --------------------------- Dots ---------------------------------- */
let dotCount = 0;
function buildDots(n) {
  if (n === dotCount) return;
  dotsEl.innerHTML = "";
  for (let i = 0; i < n; i++) dotsEl.appendChild(document.createElement("i"));
  dotCount = n;
}
function setActiveDots(active) {
  const items = dotsEl.children;
  for (let i = 0; i < items.length; i++) items[i].classList.toggle("on", i < active);
}

/* --------------------------- State --------------------------------- */
let startTime = null, rafId = null, running = false;
let lastIdx = -1, lastActive = -1, endedTriggered = false;

/* --------------------------- Main loop ----------------------------- */
function frame(now) {
  if (startTime === null) startTime = now;
  let t = (now - startTime) / 1000;
  if (t >= TOTAL) { render(TOTAL); finishSession(); return; }
  render(t);
  rafId = requestAnimationFrame(frame);
}

function render(t) {
  // ---- locate the current phase from the master clock ----
  const inc = t % CYCLE;
  let acc = 0, phase = FLOW.phases[0], idx = 0, el = 0;
  for (let i = 0; i < FLOW.phases.length; i++) {
    const ph = FLOW.phases[i];
    if (inc < acc + ph.dur || i === FLOW.phases.length - 1) { phase = ph; idx = i; el = inc - acc; break; }
    acc += ph.dur;
  }
  const p = phase.dur ? el / phase.dur : 1;

  // ---- orb scale (tied to phase progress); holds stay steady ----
  let s = phase.name === "hold"
    ? phase.orb[0]
    : phase.orb[0] + (phase.orb[1] - phase.orb[0]) * easeInOut(p);
  let b = (s - FLOW.orbMin) / (FLOW.orbMax - FLOW.orbMin);
  if (phase.name === "hold") b += 0.03 * Math.sin(t * 1.6);   // alive-but-calm shimmer
  b = Math.max(0, Math.min(1, b));
  stage.style.setProperty("--s", s.toFixed(4));
  stage.style.setProperty("--b", b.toFixed(4));

  // ---- phase change: cue + dots reset (exactly at phase start) ----
  if (idx !== lastIdx) {
    cueText.innerHTML = `<span>${phase.label}</span>`;
    buildDots(phase.dots);
    lastActive = -1;
    lastIdx = idx;
    AudioBus.onPhase(phase.name);
  }
  const active = Math.min(Math.floor(el) + 1, phase.dots);
  if (active !== lastActive) { setActiveDots(active); lastActive = active; }

  // ---- overall progress arc ----
  progressBar.style.strokeDashoffset = (ARC_CIRC * (1 - Math.min(t / TOTAL, 1))).toFixed(1);

  // ---- box comet (one lap per cycle) ----
  if (FLOW.box) {
    const [bx, by] = boxPoint(inc / CYCLE);
    boxComet.setAttribute("cx", bx.toFixed(1));
    boxComet.setAttribute("cy", by.toFixed(1));
  }

  // ---- mist + end card ----
  drawMist(t, b);
  if (t >= END_START && !endedTriggered) {
    stage.classList.add("ending");
    endedTriggered = true;
    AudioBus.bell();
    AudioBus.fadeAmbient();
  }
}

/* ------------------------ Start / finish --------------------------- */
function startSession() {
  if (running) return;
  running = true;
  startTime = null; endedTriggered = false; lastIdx = -1; lastActive = -1;
  stage.classList.remove("ending");
  startScreen.classList.add("hidden");
  AudioBus.start();
  rafId = requestAnimationFrame(frame);
}

function finishSession() {
  running = false;
  cancelAnimationFrame(rafId);
  AudioBus.onEnd();
  stage.addEventListener("click", restart, { once: true });
}

function restart() {
  stage.classList.remove("ending");
  setActiveDots(0);
  running = false;
  startSession();
}

beginBtn.addEventListener("click", startSession);

/* Preview helper: ?preview=12.5 renders one static frame at t=12.5s. */
(() => {
  const m = new URLSearchParams(location.search).get("preview");
  if (m === null) return;
  startScreen.classList.add("hidden");
  render(parseFloat(m) || 0);
})();

/* ===========================================================================
   AUDIO BUS — ambient (per flow) + soft bell ship ready.
   Set enabled = false to mute. Hooks: start / onPhase / bell / fadeAmbient /
   onEnd. The #ambient <source> is chosen per flow below.
   =========================================================================== */
const AudioBus = {
  enabled: true,

  el(id) { return document.getElementById(id); },

  _setAmbientSrc() {
    const a = this.el("ambient");
    if (a && !a.src) a.src = `audio/ambient-${FLOW.slug}.mp3`;
  },

  start() {
    if (!this.enabled) return;
    this._setAmbientSrc();
    const ambient = this.el("ambient");
    if (ambient) { ambient.volume = 0; ambient.play().catch(() => {}); this._fade(ambient, 0.6, 4000); }
    this.bell();
  },

  onPhase(name) {
    if (!this.enabled) return;
    const id = name === "exhale" ? "toneExhale" : name === "hold" ? "toneHold" : "toneInhale";
    const tone = this.el(id);
    if (tone) { tone.currentTime = 0; tone.play().catch(() => {}); }
  },

  bell() {
    if (!this.enabled) return;
    const bell = this.el("bell");
    if (bell) { bell.currentTime = 0; bell.play().catch(() => {}); }
  },

  fadeAmbient() {
    if (!this.enabled) return;
    const ambient = this.el("ambient");
    if (ambient) this._fade(ambient, 0.15, 3000);
  },

  onEnd() {
    if (!this.enabled) return;
    const ambient = this.el("ambient");
    if (ambient) this._fade(ambient, 0, 2000, () => ambient.pause());
  },

  _fade(audio, target, ms, done) {
    const start = audio.volume, t0 = performance.now();
    const step = (now) => {
      const k = Math.min((now - t0) / ms, 1);
      audio.volume = start + (target - start) * k;
      if (k < 1) requestAnimationFrame(step);
      else if (done) done();
    };
    requestAnimationFrame(step);
  },
};
