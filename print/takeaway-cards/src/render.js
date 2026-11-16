// Builds the requested output from the card templates in cards.html.
// Usage: cards.html?view=<sheet|sheet-front|sheet-back|a6|card-front|card-back|mockup|sheet-preview>[&tint=0]

(function () {
  const params = new URLSearchParams(location.search);
  const view = params.get("view") || "sheet";
  if (params.get("tint") === "0") document.body.classList.add("no-tint");

  const NS = "http://www.w3.org/2000/svg";

  // Trim geometry in mm. Symmetric on both axes so the back page lines up
  // whether the printer flips on the long or the short edge.
  const CUT_X = [5, 105, 205];
  const CUT_Y = [7.1, 148.5, 289.9];

  const el = (tag, cls, parent) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (parent) parent.appendChild(node);
    return node;
  };

  const card = (side) =>
    document.getElementById("card-" + side).content.firstElementChild.cloneNode(true);

  const pageStyle = (css) => {
    const style = document.createElement("style");
    style.textContent = css;
    document.head.appendChild(style);
  };

  function cropMarks() {
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("class", "marks");
    svg.setAttribute("viewBox", "0 0 210 297");
    const line = (x1, y1, x2, y2) => {
      const l = document.createElementNS(NS, "line");
      Object.entries({ x1, y1, x2, y2 }).forEach(([k, v]) => l.setAttribute(k, v));
      l.setAttribute("stroke", "#3a3430");
      l.setAttribute("stroke-width", "0.12");
      svg.appendChild(l);
    };
    CUT_X.forEach((x) => {
      line(x, 0.8, x, 4.6);
      line(x, 292.4, x, 296.2);
    });
    CUT_Y.forEach((y) => {
      line(0.4, y, 2.6, y);
      line(207.4, y, 209.6, y);
    });
    return svg;
  }

  function sheet(side, parent) {
    const page = el("section", "sheet", parent);
    el("div", "bleed", page);
    const grid = el("div", "grid", page);
    for (let i = 0; i < 4; i++) grid.appendChild(card(side));
    page.appendChild(cropMarks());
    return page;
  }

  // Layout QA: reports, per card, how much room is left above the bottom
  // padding and how many lines each text block wraps to.
  function check() {
    const PX_PER_MM = 96 / 25.4;
    const cards = ["front", "back"].map((side) => document.body.appendChild(card(side)));
    document.fonts.ready.then(() => measure(cards, PX_PER_MM));
  }

  function measure(cards, PX_PER_MM) {
    const report = cards.map((c) => {
      const side = c.classList.contains("front") ? "front" : "back";
      const box = c.getBoundingClientRect();
      const padBottom = parseFloat(getComputedStyle(c.querySelector(".b-body") || c).paddingBottom);
      const blocks = [...c.querySelectorAll("h1, h2, p, li, .b-links")];
      const lowest = Math.max(...blocks.map((b) => b.getBoundingClientRect().bottom));
      const lines = blocks.map((b) => {
        const cs = getComputedStyle(b);
        const lh = parseFloat(cs.lineHeight);
        const textH = b.getBoundingClientRect().height - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
        const avail = b.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
        const range = document.createRange();
        range.selectNodeContents(b);
        b.style.whiteSpace = "nowrap";
        const natural = range.getBoundingClientRect().width;
        b.style.whiteSpace = "";
        const over = ((natural - avail) / PX_PER_MM).toFixed(1);
        return `${Math.round(textH / lh)} line(s), ${over}mm vs measure  ${b.textContent.trim().slice(0, 34)}`;
      });
      const steps = [...c.querySelectorAll(".steps li")].map((li) => {
        const avail = li.clientWidth - parseFloat(getComputedStyle(li).paddingLeft);
        const probe = document.createElement("span");
        probe.style.whiteSpace = "nowrap";
        probe.textContent = li.textContent;
        li.appendChild(probe);
        const need = probe.getBoundingClientRect().width;
        probe.remove();
        return `${((avail - need) / PX_PER_MM).toFixed(2)}mm spare  ${li.textContent.slice(0, 30)}`;
      });
      return {
        side,
        steps,
        spareMm: +((box.bottom - padBottom - lowest) / PX_PER_MM).toFixed(2),
        lines,
      };
    });
    const pre = el("pre", "", document.body);
    pre.id = "check";
    pre.textContent = JSON.stringify(report, null, 1);
  }

  const views = {
    sheet() {
      pageStyle("@page { size: 210mm 297mm; margin: 0; }");
      sheet("front", document.body);
      sheet("back", document.body);
    },
    "sheet-front"() {
      sheet("front", document.body);
    },
    "sheet-back"() {
      sheet("back", document.body);
    },
    a6() {
      pageStyle("@page { size: 111mm 154.5mm; margin: 0; }");
      ["front", "back"].forEach((side) => {
        el("section", "a6-page", document.body).appendChild(card(side));
      });
    },
    "card-front"() {
      el("section", "single", document.body).appendChild(card("front"));
    },
    "card-back"() {
      el("section", "single", document.body).appendChild(card("back"));
    },
    mockup() {
      const scene = el("div", "scene", document.body);
      el("div", "glow", scene);
      const place = (side, left, top, rotate) => {
        const wrap = el("div", "mock-card", scene);
        wrap.style.left = left + "px";
        wrap.style.top = top + "px";
        wrap.style.transform = `scale(1.55) rotate(${rotate}deg)`;
        wrap.appendChild(card(side));
      };
      place("back", 945, 283, 3.5);
      place("front", 285, 283, -3);
    },
    "sheet-preview"() {
      const scene = el("div", "scene", document.body);
      el("div", "glow", scene);
      const scale = 0.84;
      const w = 793.7 * scale;
      const gap = 96;
      const x0 = (1600 - (w * 2 + gap)) / 2;
      ["front", "back"].forEach((side, i) => {
        const wrap = el("div", "mock-sheet", scene);
        wrap.style.left = x0 + i * (w + gap) + "px";
        wrap.style.top = "92px";
        wrap.style.transform = `scale(${scale})`;
        sheet(side, wrap);
        const label = el("p", "mock-label", scene);
        label.textContent = i === 0 ? "Page 1 — Fronts" : "Page 2 — Backs";
        label.style.left = x0 + i * (w + gap) + "px";
        label.style.top = "46px";
      });
    },
  };

  if (view === "check") {
    check();
    return;
  }
  (views[view] || views.sheet)();
})();
