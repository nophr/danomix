const PALETTE = ["#8a5bff", "#4ad6ff", "#ff6bd6", "#ffb84a", "#7affaa",
                 "#b9a5ff", "#ff9a9a", "#a5e6ff", "#d3c9ff", "#ffd57a"];
const MOVE_ICON = { open: "+", add: "▲", trim: "▼", close: "×" };
const MOVE_LABEL = {
  open:  "Opened Position",
  add:   "Increased Position",
  trim:  "Reduced Position",
  close: "Closed Position",
};

function formatDateLong(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US",
    { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
}

function businessDaysBetween(isoA, isoB) {
  const a = new Date(isoA + "T00:00:00Z");
  const b = new Date(isoB + "T00:00:00Z");
  let count = 0;
  const step = new Date(a);
  while (step < b) {
    step.setUTCDate(step.getUTCDate() + 1);
    const dow = step.getUTCDay();
    if (dow !== 0 && dow !== 6) count += 1;
  }
  return count;
}

function renderHeaderChips(snap) {
  const chip = document.getElementById("chipUpdated");
  const todayIso = new Date().toISOString().slice(0, 10);
  const businessDaysOld = businessDaysBetween(snap.updated_at, todayIso);
  if (businessDaysOld > 4) {
    chip.className = "pg-chip pg-chip--warn";
    chip.textContent = "⚠ Last updated " + formatDateLong(snap.updated_at);
  } else {
    chip.className = "pg-chip pg-chip--ok";
    chip.textContent = "● Updated " + formatDateLong(snap.updated_at);
  }
  document.getElementById("chipLeverage").textContent =
    "Leverage " + snap.nav.leverage.toFixed(2) + "×";
}

function renderDonut(holdings) {
  const el = document.getElementById("donut");
  let acc = 0;
  const stops = holdings.map((h, i) => {
    const from = acc;
    acc += h.percent;
    const color = PALETTE[i % PALETTE.length];
    return `${color} ${from}% ${acc}%`;
  });
  if (acc < 100) stops.push(`#2b244a ${acc}% 100%`);
  el.style.background = `conic-gradient(${stops.join(",")})`;
  document.getElementById("holdingCount").textContent = holdings.length;
}

function renderHoldingRows(holdings) {
  const host = document.getElementById("holdingRows");
  host.innerHTML = "";
  holdings.forEach((h, i) => {
    const color = PALETTE[i % PALETTE.length];
    const row = document.createElement("div");
    row.className = "pg-row";
    row.innerHTML = `
      <span class="pg-dot" style="background:${color}"></span>
      <span class="sym">${h.display}</span>
      <span class="bar"><span style="width:${Math.min(h.percent, 100)}%"></span></span>
      <span class="pct">${h.percent.toFixed(1)}%</span>
    `;
    host.appendChild(row);
  });
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  document.getElementById("themeToggle").textContent = theme === "dark" ? "☾" : "☀";
}

function setupThemeToggle() {
  const stored = localStorage.getItem("theme");
  applyTheme(stored === "light" ? "light" : "dark");
  document.getElementById("themeToggle").addEventListener("click", () => {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    localStorage.setItem("theme", next);
    applyTheme(next);
  });
}

async function main() {
  setupThemeToggle();
  const res = await fetch("/data/snapshot.json", { cache: "no-cache" });
  if (!res.ok) throw new Error("snapshot.json not available: " + res.status);
  const snap = await res.json();

  renderHeaderChips(snap);
  renderDonut(snap.holdings);
  renderHoldingRows(snap.holdings);

  window._snap = snap;  // expose for later tasks
}

main().catch(err => {
  console.error(err);
  document.getElementById("chipUpdated").textContent = "⚠ Data unavailable";
  document.getElementById("chipUpdated").className = "pg-chip pg-chip--warn";
});
