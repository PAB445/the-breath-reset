const timerDurationSeconds = 60;

const params = new URLSearchParams(window.location.search);
const duration = Math.max(1, Number(params.get("duration")) || timerDurationSeconds);
const bg = (params.get("bg") || "transparent").toLowerCase();
const position = (params.get("position") || "top-right").toLowerCase();
const scale = Number(params.get("scale")) || 1;
const showNote = params.get("note") !== "0";

const body = document.body;
const panel = document.getElementById("timerPanel");
const timerValue = document.getElementById("timerValue");
const timerNote = document.getElementById("timerNote");
const ringProgress = document.getElementById("ringProgress");

if (bg === "green") body.classList.add("is-green");
if (bg === "black") body.classList.add("is-black");

const allowedPositions = new Set(["top-right", "top-left", "bottom-right", "bottom-left", "center"]);
panel.className = `timer timer--${allowedPositions.has(position) ? position : "top-right"}`;
document.documentElement.style.setProperty("--timer-scale", String(Math.min(Math.max(scale, 0.55), 1.8)));
timerNote.hidden = !showNote;

const radius = 58;
const circumference = 2 * Math.PI * radius;
ringProgress.style.strokeDasharray = circumference.toFixed(2);
ringProgress.style.strokeDashoffset = circumference.toFixed(2);

const start = performance.now();

function pad(value) {
  return String(value).padStart(2, "0");
}

function formatTime(seconds) {
  const whole = Math.floor(seconds);
  const minutes = Math.floor(whole / 60);
  const remainder = whole % 60;
  return `${pad(minutes)}:${pad(remainder)}`;
}

function render(now) {
  const elapsed = Math.min((now - start) / 1000, duration);
  timerValue.textContent = formatTime(elapsed);

  const minuteProgress = elapsed === duration && duration % 60 === 0
    ? 1
    : (elapsed % 60) / 60;
  ringProgress.style.strokeDashoffset = (circumference * (1 - minuteProgress)).toFixed(2);

  if (elapsed < duration) {
    requestAnimationFrame(render);
  }
}

requestAnimationFrame(render);
