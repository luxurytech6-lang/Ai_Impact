/* =====================================================================
   ATMOS — app.js v2.0
   ===================================================================== */

"use strict";

/* ---- Tiny DOM helper ---- */
const $ = (id) => document.getElementById(id);

/* =====================================================================
   DIAL TICK MARKS
   Generate SVG tick marks for each dial on init
   ===================================================================== */
function buildTicks(svgGroupId) {
  const g = $(svgGroupId);
  if (!g) return;
  const cx = 54, cy = 54, r = 44;
  const totalAngle = 270; // sweep in degrees (starting from 225° going to 135°)
  const startAngle = 225; // degrees from right (CSS transform -90° applied to svg)
  const count = 20;

  for (let i = 0; i <= count; i++) {
    const frac = i / count;
    const angleDeg = startAngle + frac * totalAngle;
    const rad = (angleDeg * Math.PI) / 180;
    const isLarge = i % 5 === 0;
    const inner = r - (isLarge ? 8 : 5);
    const outer = r + 0;
    const x1 = cx + inner * Math.cos(rad);
    const y1 = cy + inner * Math.sin(rad);
    const x2 = cx + outer * Math.cos(rad);
    const y2 = cy + outer * Math.sin(rad);
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", x1.toFixed(2));
    line.setAttribute("y1", y1.toFixed(2));
    line.setAttribute("x2", x2.toFixed(2));
    line.setAttribute("y2", y2.toFixed(2));
    line.setAttribute("class", "dial-tick");
    line.setAttribute("stroke-width", isLarge ? "1.5" : "0.8");
    g.appendChild(line);
  }
}

/* =====================================================================
   DIAL ANIMATION
   r=44 → circumference = 2π×44 ≈ 276.46 (using 276)
   But we only sweep 270° (¾ of 360°), so arc = 276 × 0.75 ≈ 207
   The CSS stroke-dasharray is set to full circumference (276);
   we control what's shown by offsetting.
   ===================================================================== */
const ARC = 276; // full circle circumference at r=44
const SWEEP_FRAC = 0.75; // 270° / 360°

function setDial(metricId, value, max) {
  const fill = $(`dial-fill-${metricId}`);
  if (!fill) return;
  const pct = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  const drawn = ARC * SWEEP_FRAC * pct;
  // We need the arc to start at the "right" position: 225° when SVG is rotated -90°
  // The remaining gap sits at the bottom. We achieve this by:
  // dasharray = [drawn arc] [gap to 270° arc] [remaining to close the full circle]
  const sweepLen = ARC * SWEEP_FRAC; // 207
  const gapLen = ARC - sweepLen;     // 69 (the 90° gap at bottom)
  fill.setAttribute("stroke-dasharray", `${drawn.toFixed(2)} ${(sweepLen - drawn + gapLen).toFixed(2)}`);
  fill.setAttribute("stroke-dashoffset", "0");

  // Glow class
  const dialEl = fill.closest(".dial");
  if (dialEl) {
    dialEl.classList.toggle("active", pct > 0.02);
  }
}

/* =====================================================================
   NUMBER FORMATTER
   ===================================================================== */
function fmt(n) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + "M";
  if (n >= 10_000)    return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (n >= 100)       return n.toFixed(1);
  if (n >= 10)        return n.toFixed(2);
  return n.toFixed(3);
}

/* =====================================================================
   FORM VALIDATION
   ===================================================================== */
const VALIDATION_RULES = {
  model_size_b: { min: 0.01, max: 1000,   label: "Model size",      errId: "model-err" },
  num_units:    { min: 1,    max: 10000,  label: "Number of units", errId: "units-err" },
  exec_hours:   { min: 0.01, max: 87600,  label: "Execution time",  errId: "hours-err" },
};

function validateForm() {
  let valid = true;
  for (const [field, rule] of Object.entries(VALIDATION_RULES)) {
    const input = document.querySelector(`[name="${field}"]`);
    const errEl = $(rule.errId);
    if (!input || !errEl) continue;
    const val = parseFloat(input.value);
    let msg = "";
    if (isNaN(val))            msg = `${rule.label} must be a number.`;
    else if (val < rule.min)   msg = `${rule.label} must be ≥ ${rule.min}.`;
    else if (val > rule.max)   msg = `${rule.label} must be ≤ ${rule.max.toLocaleString()}.`;
    if (msg) {
      input.classList.add("invalid");
      errEl.textContent = msg;
      errEl.classList.add("visible");
      valid = false;
    } else {
      input.classList.remove("invalid");
      errEl.textContent = "";
      errEl.classList.remove("visible");
    }
  }
  return valid;
}

/* Clear validation on input */
["model_size_b", "num_units", "exec_hours"].forEach((name) => {
  const el = document.querySelector(`[name="${name}"]`);
  if (el) {
    el.addEventListener("input", () => {
      el.classList.remove("invalid");
      const rule = VALIDATION_RULES[name];
      if (rule) {
        const errEl = $(rule.errId);
        if (errEl) { errEl.textContent = ""; errEl.classList.remove("visible"); }
      }
    });
  }
});

/* =====================================================================
   FORM READ
   ===================================================================== */
function readForm() {
  return {
    mode:            $("mode").value,
    model_size_b:    parseFloat($("model_size_b").value),
    hardware:        $("hardware").value,
    num_units:       Math.max(1, parseInt($("num_units").value, 10) || 1),
    exec_hours:      parseFloat($("exec_hours").value),
    utilization_pct: parseFloat($("utilization_pct").value),
    region:          $("region").value,
    use_live:        $("use_live").checked,
  };
}

/* =====================================================================
   SLIDER ↔ NUMBER INPUT SYNC
   ===================================================================== */
$("model_size_b_range").addEventListener("input", (e) => {
  $("model_size_b").value = parseFloat(e.target.value).toFixed(
    parseFloat(e.target.value) < 10 ? 1 : 0
  );
});

$("model_size_b").addEventListener("input", (e) => {
  const v = parseFloat(e.target.value);
  if (!isNaN(v) && v >= 0.1 && v <= 1000) {
    $("model_size_b_range").value = v;
  }
});

$("utilization_pct").addEventListener("input", (e) => {
  const v = parseInt(e.target.value, 10);
  $("util-readout").textContent = `${v}%`;
  $("utilization_pct").setAttribute("aria-valuenow", v);
});

/* =====================================================================
   TOAST
   ===================================================================== */
let toastTimer = null;

function showToast(msg, type = "") {
  const t = $("toast");
  t.textContent = msg;
  t.className = `show ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.className = ""; }, 3500);
}

/* =====================================================================
   CHART SETUP
   ===================================================================== */
const CHART_CFG = {
  bg:     "#090E0C",
  grid:   "#1E2E24",
  text:   "#4D6B58",
  carbon: "#E06B52",
  water:  "#3FC3D4",
  util:   "#F0C14A",
};

function baseCfg(yLabel) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 600, easing: "easeInOutQuart" },
    plugins: { legend: { display: false }, tooltip: {
      backgroundColor: "#111A15",
      borderColor: "#253B2E",
      borderWidth: 1,
      titleColor: "#DFF0E5",
      bodyColor: "#8BB09A",
      titleFont: { family: "'JetBrains Mono', monospace", size: 11 },
      bodyFont: { family: "'JetBrains Mono', monospace", size: 11 },
      callbacks: {
        label: (ctx) => ` ${fmt(ctx.parsed.y)} kg CO₂e`,
      },
    }},
    scales: {
      x: {
        ticks: {
          color: CHART_CFG.text,
          font: { size: 9, family: "'JetBrains Mono', monospace" },
          maxRotation: 40,
          autoSkip: true,
          maxTicksLimit: 8,
        },
        grid: { color: CHART_CFG.grid, lineWidth: 0.5 },
        border: { color: CHART_CFG.grid },
      },
      y: {
        ticks: {
          color: CHART_CFG.text,
          font: { size: 9, family: "'JetBrains Mono', monospace" },
          callback: (v) => fmt(v),
        },
        grid: { color: CHART_CFG.grid, lineWidth: 0.5 },
        border: { color: CHART_CFG.grid },
        title: {
          display: true,
          text: yLabel,
          color: CHART_CFG.text,
          font: { size: 9, family: "'JetBrains Mono', monospace" },
        },
      },
    },
  };
}

let hwChart, rgChart, utilChart;

function initCharts() {
  // Make canvases visible before Chart.js measures them
  ["chart-hardware","chart-region","chart-utilization"].forEach(id => {
    const el = $(id);
    if (el) el.style.display = "block";
  });

  hwChart = new Chart($("chart-hardware"), {
    type: "bar",
    data: {
      labels: [],
      datasets: [{ data: [], backgroundColor: CHART_CFG.carbon, borderRadius: 3, borderSkipped: false }],
    },
    options: baseCfg("kg CO₂e"),
  });

  rgChart = new Chart($("chart-region"), {
    type: "bar",
    data: {
      labels: [],
      datasets: [{ data: [], backgroundColor: CHART_CFG.water, borderRadius: 3, borderSkipped: false }],
    },
    options: baseCfg("kg CO₂e"),
  });

  utilChart = new Chart($("chart-utilization"), {
    type: "line",
    data: {
      labels: [],
      datasets: [{
        data: [],
        borderColor: CHART_CFG.util,
        backgroundColor: "rgba(240,193,74,0.08)",
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointBackgroundColor: CHART_CFG.util,
        pointBorderColor: "#090E0C",
        pointBorderWidth: 2,
      }],
    },
    options: baseCfg("kg CO₂e"),
  });
}

function showCharts() {
  ["hardware","region","utilization"].forEach(key => {
    const ph = $(`ph-${key}`);
    if (ph) ph.style.display = "none";
  });
}

function showPlaceholderLoading() {
  ["hardware","region","utilization"].forEach(key => {
    const ph = $(`ph-${key}`);
    if (ph) {
      ph.style.display = "flex";
      ph.classList.add("loading");
      ph.querySelector(".ph-text").textContent = "Calculating…";
    }
  });
}

function resetPlaceholders() {
  ["hardware","region","utilization"].forEach(key => {
    const ph = $(`ph-${key}`);
    if (ph) {
      ph.classList.remove("loading");
      ph.querySelector(".ph-text").textContent = "Run an estimate to see results";
    }
  });
}

function updateCharts(sens) {
  hwChart.data.labels = sens.hardware_sweep.map((h) => shortenLabel(h.label));
  hwChart.data.datasets[0].data = sens.hardware_sweep.map((h) => h.carbon_kg);
  hwChart.update();

  rgChart.data.labels = sens.region_sweep.map((r) => shortenLabel(r.label));
  rgChart.data.datasets[0].data = sens.region_sweep.map((r) => r.carbon_kg);
  rgChart.update();

  utilChart.data.labels = sens.utilization_sweep.map((u) => `${u.utilization}%`);
  utilChart.data.datasets[0].data = sens.utilization_sweep.map((u) => u.carbon_kg);
  utilChart.update();

  showCharts();
}

/* Trim long labels to keep charts clean */
function shortenLabel(label) {
  const map = {
    "NVIDIA A100 (80GB)": "A100",
    "NVIDIA H100": "H100",
    "NVIDIA V100": "V100",
    "NVIDIA RTX 4090": "RTX 4090",
    "Google TPU v4": "TPU v4",
    "General CPU Server": "CPU",
    "Nigeria (national grid)": "Nigeria",
    "South Africa (national grid)": "S. Africa",
    "Kenya (national grid)": "Kenya",
    "Egypt (national grid)": "Egypt",
    "Ghana (national grid)": "Ghana",
    "US East (Virginia)": "US East",
    "EU North (Sweden)": "EU North",
    "South Asia (India)": "S. Asia",
    "Global Average": "Global",
  };
  return map[label] || label.split(" ")[0];
}

/* =====================================================================
   LOADING STATE
   ===================================================================== */
function setLoading(on) {
  const btn = $("run-btn");
  btn.disabled = on;
  btn.querySelector(".btn-text").textContent = on ? "Calculating…" : "Run estimate";
  btn.classList.toggle("scanning", on);
  if (on) {
    showPlaceholderLoading();
  }
}

/* =====================================================================
   UPDATE READOUT
   ===================================================================== */
function updateReadout(r, sweep, payload) {
  // Dials
  const maxE = sweep ? Math.max(...sweep.hardware_sweep.map((h) => h.energy_kwh), r.energy_kwh) * 1.1 : r.energy_kwh * 1.5 || 1;
  const maxC = sweep ? Math.max(...sweep.hardware_sweep.map((h) => h.carbon_kg), r.carbon_kg) * 1.1 : r.carbon_kg * 1.5 || 1;
  const maxW = sweep ? Math.max(...sweep.hardware_sweep.map((h) => h.water_l),   r.water_l)   * 1.1 : r.water_l   * 1.5 || 1;

  setDial("energy", r.energy_kwh, maxE);
  setDial("carbon", r.carbon_kg,  maxC);
  setDial("water",  r.water_l,    maxW);

  $("val-energy").textContent     = fmt(r.energy_kwh);
  $("val-carbon").textContent     = fmt(r.carbon_kg);
  $("val-water").textContent      = fmt(r.water_l);
  $("val-efficiency").textContent = r.efficiency_score !== undefined ? fmt(r.efficiency_score) : "—";

  // Comparisons
  $("cmp-car").textContent       = fmt(r.comparisons.car_km);
  $("cmp-household").textContent = fmt(r.comparisons.household_days);
  $("cmp-shower").textContent    = fmt(r.comparisons.showers);
  $("comparisons").hidden = false;

  // Source badge
  const badge = $("source-badge");
  const label = $("source-label");
  const liveMsg = $("live-msg");

  if (r.carbon_source === "live") {
    badge.classList.add("live");
    label.textContent = `live · ${fmt(r.carbon_g_kwh_used)} gCO₂/kWh`;
    if (r.live_lookup) {
      const ts = r.live_lookup.datetime
        ? new Date(r.live_lookup.datetime).toLocaleString()
        : "just now";
      liveMsg.textContent = `↑ ${r.live_lookup.zone} · ${ts}`;
      liveMsg.className = "live-msg ok";
    }
  } else {
    badge.classList.remove("live");
    label.textContent = `static · ${fmt(r.carbon_g_kwh_used)} gCO₂/kWh`;
    if (payload.use_live && r.live_lookup && !r.live_lookup.ok) {
      liveMsg.textContent = `Live unavailable: ${r.live_lookup.error} — using static reference.`;
      liveMsg.className = "live-msg err";
    } else {
      liveMsg.textContent = "";
      liveMsg.className = "live-msg";
    }
  }
}

/* =====================================================================
   LAST RESULT (for export)
   ===================================================================== */
let lastResult = null;
let lastPayload = null;

/* =====================================================================
   MAIN CALCULATE
   ===================================================================== */
async function runCalculation(payload) {
  setLoading(true);

  try {
    const [calcRes, sensRes] = await Promise.all([
      fetch("/api/calculate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }),
      fetch("/api/sensitivity", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }),
    ]);

    if (!calcRes.ok) throw new Error(`Server error ${calcRes.status}`);

    const calcData = await calcRes.json();
    const sensData = await sensRes.json();

    if (!calcData.ok) {
      showToast(`Error: ${calcData.error}`, "error");
      resetPlaceholders();
      setLoading(false);
      return;
    }

    lastResult  = calcData.result;
    lastPayload = payload;

    updateReadout(calcData.result, sensData.ok ? sensData.result : null, payload);
    if (sensData.ok) updateCharts(sensData.result);

    showToast("Estimate updated", "success");
  } catch (err) {
    resetPlaceholders();
    showToast(
      navigator.onLine
        ? `Calculation failed: ${err.message}`
        : "Offline — cannot calculate without a connection.",
      "error"
    );
  } finally {
    setLoading(false);
  }
}

/* =====================================================================
   FORM SUBMIT
   ===================================================================== */
$("calc-form").addEventListener("submit", (e) => {
  e.preventDefault();
  if (!validateForm()) {
    showToast("Please fix the highlighted fields.", "error");
    return;
  }
  runCalculation(readForm());
});

/* =====================================================================
   EXPORT
   ===================================================================== */
$("export-btn").addEventListener("click", () => {
  if (!lastResult) {
    showToast("Run an estimate first.", "error");
    return;
  }
  const blob = new Blob(
    [JSON.stringify({ inputs: lastPayload, result: lastResult, generated: new Date().toISOString() }, null, 2)],
    { type: "application/json" }
  );
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `atmos-result-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
  showToast("Result exported.", "success");
});

/* =====================================================================
   CONNECTIVITY STATUS
   ===================================================================== */
function updateConnStatus() {
  const tag   = $("conn-tag");
  const label = $("conn-label");
  if (navigator.onLine) {
    tag.classList.remove("offline");
    label.textContent = "live";
  } else {
    tag.classList.add("offline");
    label.textContent = "offline";
  }
}
window.addEventListener("online",  updateConnStatus);
window.addEventListener("offline", updateConnStatus);
updateConnStatus();

/* =====================================================================
   PWA — Service Worker + Install Prompt
   ===================================================================== */
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .catch((err) => console.warn("SW registration failed:", err));
  });
}

let deferredInstall = null;
const installBtn = $("install-btn");

window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredInstall = e;
  installBtn.hidden = false;
});

installBtn.addEventListener("click", async () => {
  if (!deferredInstall) return;
  deferredInstall.prompt();
  await deferredInstall.userChoice;
  deferredInstall = null;
  installBtn.hidden = true;
});

window.addEventListener("appinstalled", () => {
  installBtn.hidden = true;
  showToast("Atmos installed!", "success");
});

/* =====================================================================
   INIT
   ===================================================================== */
document.addEventListener("DOMContentLoaded", () => {
  buildTicks("ticks-energy");
  buildTicks("ticks-carbon");
  buildTicks("ticks-water");
  initCharts();
  runCalculation(readForm());
});
