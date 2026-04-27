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

function renderMoves(moves) {
  const host = document.getElementById("movesList");
  host.innerHTML = "";
  if (!moves.length) {
    host.innerHTML = `<div class="pg-empty">No significant changes in the last 30 days.</div>`;
    return;
  }
  moves.forEach(m => {
    const chgClass = m.delta_pp >= 0 ? "chg-pos" : "chg-neg";
    const sign = m.delta_pp >= 0 ? "+" : "";
    let body = "";
    if (m.type === "open") {
      body = `Initiated a new position in <span class="sym">${m.display}</span> <span class="${chgClass}">(${m.to_pct.toFixed(1)}%)</span>`;
    } else if (m.type === "close") {
      body = `Fully exited <span class="sym">${m.display}</span>, previously held at ${m.from_pct.toFixed(1)}%`;
    } else if (m.type === "add") {
      body = `Added to <span class="sym">${m.display}</span>, allocation moved from ${m.from_pct.toFixed(1)}% to ${m.to_pct.toFixed(1)}% <span class="${chgClass}">(${sign}${m.delta_pp.toFixed(1)}pp)</span>`;
    } else {  // trim
      body = `Trimmed <span class="sym">${m.display}</span>, allocation moved from ${m.from_pct.toFixed(1)}% to ${m.to_pct.toFixed(1)}% <span class="${chgClass}">(${m.delta_pp.toFixed(1)}pp)</span>`;
    }
    const row = document.createElement("div");
    row.className = "pg-move";
    row.innerHTML = `
      <div class="pg-move-icon m-${m.type}">${MOVE_ICON[m.type]}</div>
      <div class="pg-move-body">
        <div class="pg-move-head">
          <span class="pg-move-action">${MOVE_LABEL[m.type]}</span>
          <span class="pg-move-time">${formatDateLong(m.date)}</span>
        </div>
        <div class="pg-move-text">${body}</div>
      </div>
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

function buildChartSeries(snap) {
  const pf = snap.performance.portfolio;
  const bm = snap.performance.benchmark.series;
  const bmByDate = new Map(bm.map(p => [p.date, p.return_pct]));

  const timestamps = pf.map(p => new Date(p.date + "T00:00:00Z").getTime() / 1000);
  const portfolioPct = pf.map(p => p.return_pct);
  const benchmarkPct = pf.map(p => bmByDate.has(p.date) ? bmByDate.get(p.date) : null);
  return [timestamps, portfolioPct, benchmarkPct];
}

function filterByRange(series, range) {
  const [ts, pf, bm] = series;
  if (range === "all") return series;
  const now = ts[ts.length - 1];
  const cutoff =
    range === "ytd" ? new Date(Date.UTC(new Date().getUTCFullYear(), 0, 1)).getTime() / 1000 :
    range === "1y"  ? now - 365 * 24 * 3600 :
    range === "3y"  ? now - 3 * 365 * 24 * 3600 : 0;
  const idx = ts.findIndex(t => t >= cutoff);
  if (idx <= 0) return series;
  return [ts.slice(idx), pf.slice(idx), bm.slice(idx)];
}

let chartInstance = null;

function renderChart(series) {
  const host = document.getElementById("perfChart");
  host.innerHTML = "";

  const tooltip = document.createElement("div");
  tooltip.className = "pg-chart-tip";
  host.appendChild(tooltip);

  const fmtPct = v => v == null ? "—" : (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
  const fmtDate = ts => new Date(ts * 1000).toLocaleDateString("en-US",
    { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });

  const cs = getComputedStyle(host);
  const px = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
  const py = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom);
  const opts = {
    width: Math.max(300, host.clientWidth - px),
    height: Math.max(180, host.clientHeight - py),
    padding: [8, 4, 4, 4],
    scales: { x: { time: true } },
    axes: [
      { stroke: "#6e6792", grid: { stroke: "rgba(255,255,255,0.04)" } },
      {
        stroke: "#6e6792",
        grid: { stroke: "rgba(255,255,255,0.04)" },
        values: (_, ticks) => ticks.map(v => (v >= 0 ? "+" : "") + v.toFixed(0) + "%"),
      },
    ],
    series: [
      {},
      {
        label: "Portfolio",
        stroke: "#8a5bff",
        width: 2.5,
        fill: "rgba(138,91,255,0.15)",
        fillTo: () => -1000,
        points: { show: false },
      },
      {
        label: "S&P 500",
        stroke: "#4ad6ff",
        width: 2,
        spanGaps: true,
        points: { show: false },
      },
    ],
    legend: { show: false },
    cursor: { y: false },
    plugins: [{
      hooks: {
        setCursor: (u) => {
          const idx = u.cursor.idx;
          if (idx == null) { tooltip.style.display = "none"; return; }
          const ts = u.data[0][idx], pf = u.data[1][idx], bm = u.data[2][idx];
          tooltip.innerHTML =
            `<div class="pg-chart-tip-date">${fmtDate(ts)}</div>` +
            `<div class="pg-chart-tip-row"><span class="dot" style="background:#8a5bff"></span>Portfolio<strong>${fmtPct(pf)}</strong></div>` +
            `<div class="pg-chart-tip-row"><span class="dot" style="background:#4ad6ff"></span>S&amp;P 500<strong>${fmtPct(bm)}</strong></div>`;
          tooltip.style.display = "block";
          const halfW = tooltip.offsetWidth / 2;
          let left = u.cursor.left;
          if (left - halfW < 4) left = halfW + 4;
          else if (left + halfW > host.clientWidth - 4) left = host.clientWidth - halfW - 4;
          tooltip.style.left = left + "px";
          tooltip.style.top = Math.max(20, u.cursor.top) + "px";
        },
      },
    }],
  };

  chartInstance = new uPlot(opts, series, host);
}

const RANGE_LABEL = {
  all: "All-Time Return · Since Inception",
  "3y": "3-Year Return",
  "1y": "1-Year Return",
  ytd: "Year-to-Date Return",
};

// Returns total return % for the slice of `series` covered by `range`,
// chained through the inception anchor: ((1+pct_now/100)/(1+pct_start/100)-1)*100
function windowReturn(series, range) {
  if (!series.length) return null;
  if (range === "all") return series[series.length - 1].return_pct;
  const now = series[series.length - 1];
  const cutoffSec =
    range === "ytd" ? new Date(Date.UTC(new Date().getUTCFullYear(), 0, 1)).getTime() / 1000 :
    range === "1y"  ? new Date(now.date + "T00:00:00Z").getTime() / 1000 - 365 * 24 * 3600 :
    range === "3y"  ? new Date(now.date + "T00:00:00Z").getTime() / 1000 - 3 * 365 * 24 * 3600 : 0;
  const start = series.find(p => new Date(p.date + "T00:00:00Z").getTime() / 1000 >= cutoffSec);
  if (!start || start.date === now.date) return now.return_pct;
  const factor_now   = 1 + now.return_pct / 100;
  const factor_start = 1 + start.return_pct / 100;
  return (factor_now / factor_start - 1) * 100;
}

function renderHero(snap, range) {
  const pf = snap.performance.portfolio;
  const bm = snap.performance.benchmark.series;
  document.querySelector(".pg-eyebrow").textContent = RANGE_LABEL[range] || RANGE_LABEL.all;

  const portfolioRet = windowReturn(pf, range);
  if (portfolioRet === null) return;
  document.getElementById("returnBig").textContent =
    (portfolioRet >= 0 ? "+" : "") + portfolioRet.toFixed(1) + "%";

  const bmRet = windowReturn(bm, range);
  if (bmRet !== null) {
    const out = portfolioRet - bmRet;
    document.getElementById("returnSub").innerHTML =
      `S&amp;P 500 <span class="pg-delta">${bmRet >= 0 ? "+" : ""}${bmRet.toFixed(1)}%</span> · ` +
      `Outperformance <span class="pg-delta">${out >= 0 ? "+" : ""}${out.toFixed(1)} pp</span>`;
  }
}

function setupRangeTabs(snap) {
  const series = buildChartSeries(snap);
  document.querySelectorAll("#ranges .pg-range").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#ranges .pg-range").forEach(b => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      const range = btn.dataset.range;
      renderChart(filterByRange(series, range));
      renderHero(snap, range);
    });
  });
  renderChart(series);
  window.addEventListener("resize", () => {
    if (!chartInstance) return;
    const host = document.getElementById("perfChart");
    const cs = getComputedStyle(host);
    const px = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
    chartInstance.setSize({ width: Math.max(300, host.clientWidth - px), height: chartInstance.height });
  });
}

async function main() {
  setupThemeToggle();
  const res = await fetch("data/snapshot.json", { cache: "no-cache" });
  if (!res.ok) throw new Error("snapshot.json not available: " + res.status);
  const snap = await res.json();

  renderHeaderChips(snap);
  renderHero(snap, "all");
  renderDonut(snap.holdings);
  renderHoldingRows(snap.holdings);
  renderMoves(snap.recent_moves);
  setupRangeTabs(snap);

  window._snap = snap;
}

main().catch(err => {
  console.error(err);
  document.getElementById("chipUpdated").textContent = "⚠ Data unavailable";
  document.getElementById("chipUpdated").className = "pg-chip pg-chip--warn";
});
