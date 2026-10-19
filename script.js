const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

/* ---------- Header + nav ---------- */

const header = document.querySelector("[data-header]");
const nav = document.querySelector("[data-nav]");
const navToggle = document.querySelector("[data-nav-toggle]");

const setHeaderState = () => {
  header?.classList.toggle("is-scrolled", window.scrollY > 12);
};

setHeaderState();
window.addEventListener("scroll", setHeaderState, { passive: true });

const setNavOpen = (open) => {
  if (!nav || !navToggle) return;
  nav.classList.toggle("is-open", open);
  document.body.classList.toggle("nav-open", open);
  navToggle.setAttribute("aria-expanded", String(open));
  navToggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
};

navToggle?.addEventListener("click", () => setNavOpen(!nav.classList.contains("is-open")));
nav?.addEventListener("click", (event) => {
  if (event.target.closest("a")) setNavOpen(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && nav?.classList.contains("is-open")) {
    setNavOpen(false);
    navToggle.focus();
  }
});

/* ---------- Reveal on scroll ---------- */

const revealTargets = document.querySelectorAll(".reveal, .trace-draw");

if ("IntersectionObserver" in window && !reduceMotion.matches) {
  const revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        revealObserver.unobserve(entry.target);
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
  );
  revealTargets.forEach((el) => revealObserver.observe(el));
} else {
  revealTargets.forEach((el) => el.classList.add("is-visible"));
}

/* ---------- Breath traces ----------
   Each trace is a stylised breathing waveform. Two-part traces shift from
   segment `a` (how breathing tends to look in that state) to segment `b`
   (what we practise). Illustrative only. */

const TRACES = {
  wired: {
    a: { freq: 13, amp: 0.5, ratio: 0.42, hold: 0, jitter: 0.55 },
    b: { freq: 4.2, amp: 0.34, ratio: 0.38, hold: 0.08, jitter: 0 }
  },
  scattered: {
    a: { freq: 8, amp: 0.8, ratio: 0.5, hold: 0, jitter: 0.9 },
    b: { freq: 6, amp: 0.6, ratio: 0.5, hold: 0, jitter: 0 }
  },
  everyday: {
    a: { freq: 7, amp: 0.95, ratio: 0.45, hold: 0, jitter: 0.3 },
    b: { freq: 6, amp: 0.3, ratio: 0.42, hold: 0.18, jitter: 0 }
  },
  training: {
    a: { freq: 6.5, amp: 0.5, ratio: 0.45, hold: 0, jitter: 0.1 },
    b: { freq: 2.6, amp: 0.5, ratio: 0.45, hold: 0.55, jitter: 0 }
  },
  explore: {
    a: { freq: 6, amp: 0.38, ratio: 0.45, hold: 0.1, jitter: 0.1 },
    b: { freq: 9.5, amp: 1, ratio: 0.5, hold: 0, jitter: 0 }
  },
  relax: { a: { freq: 5, amp: 0.55, ratio: 0.38, hold: 0.06, jitter: 0 } },
  retrain: { a: { freq: 7, amp: 0.35, ratio: 0.45, hold: 0.32, jitter: 0 } },
  release: { a: { freq: 11, amp: 0.9, ratio: 0.5, hold: 0, jitter: 0.08 } }
};

const SVG_NS = "http://www.w3.org/2000/svg";

const seeded = (n) => {
  const s = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return s - Math.floor(s);
};

const breathAt = (t, ratio, hold) => {
  const active = 1 - hold;
  if (t >= active) return 0;
  const u = t / active;
  return u < ratio
    ? (1 - Math.cos((Math.PI * u) / ratio)) / 2
    : (1 + Math.cos((Math.PI * (u - ratio)) / (1 - ratio))) / 2;
};

const smoothstep = (e0, e1, x) => {
  const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
};

const mix = (a, b, w) => a + (b - a) * w;

const buildTrace = (svg) => {
  const spec = TRACES[svg.dataset.trace];
  if (!spec) return;
  const { a } = spec;
  const b = spec.b || a;
  const twoPart = Boolean(spec.b);
  let phase = 0;
  let d = "";

  for (let x = 0; x <= 1000; x += 2) {
    const w = twoPart ? smoothstep(430, 570, x) : 0;
    const p = {
      freq: mix(a.freq, b.freq, w),
      amp: mix(a.amp, b.amp, w),
      ratio: mix(a.ratio, b.ratio, w),
      hold: mix(a.hold, b.hold, w),
      jitter: mix(a.jitter, b.jitter, w)
    };
    const cycle = Math.floor(phase);
    const wobble = 1 - p.jitter * seeded(cycle + 1) * 0.75;
    const v = breathAt(phase - cycle, p.ratio, p.hold);
    const y = 50 + (0.5 - v) * p.amp * wobble * 90;
    d += `${x === 0 ? "M" : "L"}${x} ${y.toFixed(2)}`;
    phase += (p.freq / 1000) * 2 * (1 + p.jitter * 0.35 * Math.sin(x * 0.031 + cycle));
  }

  if (twoPart) {
    const mid = document.createElementNS(SVG_NS, "path");
    mid.setAttribute("class", "trace-mid");
    mid.setAttribute("d", "M500 0L500 100");
    svg.append(mid);
  }

  const line = document.createElementNS(SVG_NS, "path");
  line.setAttribute("class", "trace-line");
  line.setAttribute("pathLength", "1");
  line.setAttribute("d", d);
  svg.append(line);
};

document.querySelectorAll("svg[data-trace]").forEach(buildTrace);

/* ---------- Breath Lab ---------- */

const LAB_MODES = {
  check: {
    kind: "check",
    duration: 60,
    idleCue: "Notice",
    intro: "<strong>Don't change anything.</strong> Put one hand on your chest and one on your belly, breathe however you're breathing, and press start.",
    prompts: [
      [0, "Which hand moves first?"],
      [15, "Is the air coming in through your nose or your mouth?"],
      [30, "Can you hear your breathing? Is it smooth or uneven?"],
      [45, "Is there a natural pause after you breathe out?"]
    ],
    done: "<strong>Done.</strong> Write down one thing you noticed. Try it again tonight, or after exercise, and compare."
  },
  coherent: {
    kind: "paced",
    duration: 90,
    phases: [["in", 5], ["out", 5]],
    idleCue: "Ready",
    intro: "<strong>In for 5, out for 5.</strong> Through the nose if that's comfortable. Follow the light, and don't try to fill up completely.",
    done: "<strong>Done.</strong> Take one normal breath and notice what's different, if anything.",
    more: { href: "practice.html#coherent", text: "Or follow the guided video" }
  },
  exhale: {
    kind: "paced",
    duration: 90,
    phases: [["in", 4], ["out", 6]],
    idleCue: "Ready",
    intro: "<strong>In for 4, out for 6.</strong> Keep the exhale slow and unhurried, through the nose or softly pursed lips.",
    done: "<strong>Done.</strong> Let your breath go back to normal. Notice the weight of your body on whatever you're sitting on.",
    more: { href: "practice.html#extended-exhale", text: "Or follow the guided video" }
  },
  hold: {
    kind: "stopwatch",
    idleCue: "Exhale, then hold",
    intro: "<strong>Breathe normally through your nose for a minute.</strong> After a relaxed exhale, pinch your nose and press start. Press stop at the first clear urge to breathe, not when you can't hold any longer. Then breathe gently through your nose.",
    caveat: "Skip this if you're pregnant, or have a heart condition, epilepsy or high blood pressure. Stop if you feel dizzy.",
    done: (s) => `<strong>${s} seconds.</strong> That's a reference point, not a score. Try again at the same time of day next week and see how it moves.`
  }
};

const lab = document.querySelector("[data-lab]");

if (lab) {
  const orb = lab.querySelector("[data-lab-orb]");
  const cue = lab.querySelector("[data-lab-cue]");
  const readout = lab.querySelector("[data-lab-readout]");
  const text = lab.querySelector("[data-lab-text]");
  const startBtn = lab.querySelector("[data-lab-start]");
  const caveat = lab.querySelector("[data-lab-caveat]");
  const more = lab.querySelector("[data-lab-more]");
  const modeButtons = document.querySelectorAll("[data-lab-mode]");

  let mode = "coherent";
  let running = false;
  let startedAt = 0;
  let frame = 0;
  let lastPhase = -1;
  let lastPrompt = -1;

  const fmt = (secs) => {
    const s = Math.max(0, Math.round(secs));
    return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  };

  const setOrb = (scale, seconds) => {
    if (reduceMotion.matches) {
      orb.style.transitionDuration = "0s";
      orb.style.transform = "scale(0.8)";
      orb.style.opacity = scale > 0.8 ? "1" : "0.6";
      return;
    }
    orb.style.transitionDuration = `${seconds}s`;
    orb.style.transform = `scale(${scale})`;
    orb.style.opacity = "";
  };

  const reset = () => {
    const m = LAB_MODES[mode];
    running = false;
    cancelAnimationFrame(frame);
    lastPhase = -1;
    lastPrompt = -1;
    startBtn.textContent = "Start";
    cue.textContent = m.idleCue;
    readout.textContent = m.kind === "stopwatch" ? "00:00" : fmt(m.duration);
    text.innerHTML = m.intro;
    caveat.hidden = !m.caveat;
    caveat.textContent = m.caveat || "";
    more.hidden = !m.more;
    more.innerHTML = m.more ? `<a class="arrow-link" href="${m.more.href}">${m.more.text}</a>` : "";
    setOrb(m.kind === "stopwatch" ? 0.5 : 0.6, 1.2);
  };

  const finish = (html) => {
    running = false;
    cancelAnimationFrame(frame);
    startBtn.textContent = "Again";
    cue.textContent = "Notice";
    text.innerHTML = html;
    setOrb(0.7, 2);
  };

  const tick = () => {
    const m = LAB_MODES[mode];
    const elapsed = (performance.now() - startedAt) / 1000;

    if (m.kind === "stopwatch") {
      readout.textContent = fmt(Math.floor(elapsed));
      frame = requestAnimationFrame(tick);
      return;
    }

    if (elapsed >= m.duration) {
      readout.textContent = fmt(0);
      finish(m.done);
      return;
    }

    readout.textContent = fmt(Math.ceil(m.duration - elapsed));

    if (m.kind === "paced") {
      const cycle = m.phases.reduce((sum, [, d]) => sum + d, 0);
      let t = elapsed % cycle;
      let index = 0;
      while (t >= m.phases[index][1]) {
        t -= m.phases[index][1];
        index += 1;
      }
      const absolute = Math.floor(elapsed / cycle) * m.phases.length + index;
      if (absolute !== lastPhase) {
        lastPhase = absolute;
        const [name, dur] = m.phases[index];
        cue.textContent = name === "in" ? "Breathe in" : "Breathe out";
        setOrb(name === "in" ? 1 : 0.6, dur);
      }
    }

    if (m.kind === "check") {
      const current = m.prompts.reduce((acc, [at], i) => (elapsed >= at ? i : acc), 0);
      if (current !== lastPrompt) {
        lastPrompt = current;
        text.textContent = m.prompts[current][1];
      }
    }

    frame = requestAnimationFrame(tick);
  };

  const start = () => {
    const m = LAB_MODES[mode];
    running = true;
    startedAt = performance.now();
    startBtn.textContent = "Stop";
    caveat.hidden = true;
    if (m.kind === "stopwatch") {
      cue.textContent = "Holding";
      text.innerHTML = "Press stop at the <strong>first clear urge</strong> to breathe.";
      setOrb(0.5, 0.4);
    }
    if (m.kind === "check") {
      cue.textContent = "Notice";
      setOrb(0.72, 1.5);
    }
    tick();
  };

  startBtn.addEventListener("click", () => {
    const m = LAB_MODES[mode];
    if (!running) {
      start();
      return;
    }
    if (m.kind === "stopwatch") {
      const secs = Math.round((performance.now() - startedAt) / 1000);
      finish(m.done(secs));
      return;
    }
    reset();
  });

  modeButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      mode = btn.dataset.labMode;
      modeButtons.forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
      reset();
      if (window.matchMedia("(max-width: 900px)").matches) {
        lab.scrollIntoView({ behavior: reduceMotion.matches ? "auto" : "smooth", block: "center" });
      }
    });
  });

  reset();
}

/* ---------- Founder film (load on demand) ---------- */

document.querySelectorAll("[data-film]").forEach((stage) => {
  const button = stage.querySelector(".film-play");
  button?.addEventListener("click", () => {
    const video = document.createElement("video");
    video.controls = true;
    video.playsInline = true;
    video.preload = "auto";
    video.poster = stage.dataset.poster || "";
    video.setAttribute("aria-label", stage.dataset.label || "Video");
    const source = document.createElement("source");
    source.src = stage.dataset.src;
    source.type = "video/mp4";
    video.append(source);
    stage.replaceChildren(video);
    video.play().catch(() => {});
    video.focus();
  });
});

/* ---------- Waitlist (Formspree) ---------- */

document.querySelectorAll("[data-waitlist]").forEach((form) => {
  const status = form.querySelector(".waitlist-status");
  const button = form.querySelector("button[type='submit']");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (form.action.includes("FORMSPREE_FORM_ID")) {
      status.innerHTML = 'The waitlist isn\'t connected yet. <a href="https://ig.me/m/the.breath.reset" target="_blank" rel="noopener">Message me on Instagram</a> and I\'ll add you.';
      return;
    }

    button.disabled = true;
    status.textContent = "Sending…";

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { Accept: "application/json" }
      });
      if (!response.ok) throw new Error(String(response.status));
      form.classList.add("is-done");
      status.textContent = "You're on the list. I'll be in touch when dates are set.";
    } catch {
      status.innerHTML = 'That didn\'t go through. Try again, or <a href="https://ig.me/m/the.breath.reset" target="_blank" rel="noopener">message me on Instagram</a>.';
    } finally {
      button.disabled = false;
    }
  });
});

/* ---------- Mobile sticky CTA ---------- */

const sticky = document.querySelector("[data-sticky-cta]");

if (sticky && "IntersectionObserver" in window) {
  const blockers = new Set();
  const update = () => {
    const past = window.scrollY > window.innerHeight * 0.7;
    sticky.classList.toggle("is-shown", past && blockers.size === 0);
  };
  const blockObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) blockers.add(entry.target);
      else blockers.delete(entry.target);
    });
    update();
  });
  document.querySelectorAll("[data-waitlist], .site-footer").forEach((el) => blockObserver.observe(el));
  window.addEventListener("scroll", update, { passive: true });
  update();
}
