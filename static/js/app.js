// ----------------------- Helpers -----------------------
const $ = (id) => document.getElementById(id);

function setDial(metricId, value, max) {
  const circumference = 314; // 2 * pi * r(50)
  const pct = Math.max(0, Math.min(1, value / max));
  const offset = circumference - pct * circumference;
  $(`dial-fill-${metricId}`).style.strokeDashoffset = offset;
}

function fmt(n) {
  if (n === null || n === undefined) return "—";
  if (n >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (n >= 10) return n.toFixed(1);
  return n.toFixed(2);
}

function readForm() {
  return {
    mode: $("mode").value,
    model_size_b: parseFloat($("model_size_b").value),
    hardware: $("hardware").value,
    num_units: parseInt($("num_units").value, 10) || 1,
    exec_hours: parseFloat($("exec_hours").value),
    utilization_pct: parseFloat($("utilization_pct").value),
    region: $("region").value,
    use_live: $("use_live").checked,
  };
}

// keep slider/number pair for model size in sync
$("model_size_b_range").addEventListener("input", (e) => {
  $("model_size_b").value = e.target.value;
});
$("model_size_b").addEventListener("input", (e) => {
  $("model_size_b_range").value = e.target.value;
});
$("utilization_pct").addEventListener("input", (e) => {
  $("util-readout").textContent = `${e.target.value}%`;
});

// ----------------------- Chart setup -----------------------
const chartColors = {
  carbon: "#E8745A",
  grid: "#26342C",
  text: "#8FA39A",
};

function baseChartOptions(yLabel) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: chartColors.text, font: { size: 10 } }, grid: { color: chartColors.grid } },
      y: {
        ticks: { color: chartColors.text, font: { size: 10 } },
        grid: { color: chartColors.grid },
        title: { display: true, text: yLabel, color: chartColors.text, font: { size: 10 } },
      },
    },
  };
}

let hardwareChart, regionChart, utilizationChart;

function initCharts() {
  hardwareChart = new Chart($("chart-hardware"), {
    type: "bar",
    data: { labels: [], datasets: [{ data: [], backgroundColor: chartColors.carbon, borderRadius: 4 }] },
    options: baseChartOptions("kg CO₂e"),
  });
  regionChart = new Chart($("chart-region"), {
    type: "bar",
    data: { labels: [], datasets: [{ data: [], backgroundColor: "#4EC5D6", borderRadius: 4 }] },
    options: baseChartOptions("kg CO₂e"),
  });
  utilizationChart = new Chart($("chart-utilization"), {
    type: "line",
    data: {
      labels: [],
      datasets: [{ data: [], borderColor: "#F2C14E", backgroundColor: "rgba(242,193,78,0.15)", fill: true, tension: 0.35 }],
    },
    options: baseChartOptions("kg CO₂e"),
  });
}

function updateCharts(sens) {
  hardwareChart.data.labels = sens.hardware_sweep.map((h) => h.label);
  hardwareChart.data.datasets[0].data = sens.hardware_sweep.map((h) => h.carbon_kg);
  hardwareChart.update();

  regionChart.data.labels = sens.region_sweep.map((r) => r.label);
  regionChart.data.datasets[0].data = sens.region_sweep.map((r) => r.carbon_kg);
  regionChart.update();

  utilizationChart.data.labels = sens.utilization_sweep.map((u) => `${u.utilization}%`);
  utilizationChart.data.datasets[0].data = sens.utilization_sweep.map((u) => u.carbon_kg);
  utilizationChart.update();
}

// ----------------------- Main calculate flow -----------------------
async function runCalculation(payload) {
  const [calcRes, sensRes] = await Promise.all([
    fetch("/api/calculate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
    fetch("/api/sensitivity", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
  ]);

  const calcData = await calcRes.json();
  const sensData = await sensRes.json();

  if (!calcData.ok) {
    alert(`Calculation error: ${calcData.error}`);
    return;
  }

  const r = calcData.result;

  // Dials — scale maxes loosely against the sensitivity sweep so they feel proportionate
  const sweep = sensData.ok ? sensData.result : null;
  const maxEnergy = sweep ? Math.max(...sweep.hardware_sweep.map((h) => h.energy_kwh), r.energy_kwh) * 1.1 : r.energy_kwh * 1.5;
  const maxCarbon = sweep ? Math.max(...sweep.hardware_sweep.map((h) => h.carbon_kg), r.carbon_kg) * 1.1 : r.carbon_kg * 1.5;
  const maxWater = sweep ? Math.max(...sweep.hardware_sweep.map((h) => h.water_l), r.water_l) * 1.1 : r.water_l * 1.5;

  setDial("energy", r.energy_kwh, maxEnergy || 1);
  setDial("carbon", r.carbon_kg, maxCarbon || 1);
  setDial("water", r.water_l, maxWater || 1);

  $("val-energy").textContent = fmt(r.energy_kwh);
  $("val-carbon").textContent = fmt(r.carbon_kg);
  $("val-water").textContent = fmt(r.water_l);
  $("val-efficiency").textContent = fmt(r.efficiency_score);

  $("cmp-car").textContent = fmt(r.comparisons.car_km);
  $("cmp-household").textContent = fmt(r.comparisons.household_days);
  $("cmp-shower").textContent = fmt(r.comparisons.showers);
  $("comparisons").hidden = false;

  // Live-data source feedback
  const liveStatus = $("live-status");
  const sourceLabel = $("carbon-source-label");
  if (r.carbon_source === "live") {
    sourceLabel.textContent = `live grid data (${fmt(r.carbon_g_kwh_used)} gCO\u2082/kWh)`;
    if (r.live_lookup) {
      const ts = r.live_lookup.datetime ? new Date(r.live_lookup.datetime).toLocaleString() : "just now";
      liveStatus.textContent = `Live reading for ${r.live_lookup.zone} as of ${ts}`;
      liveStatus.className = "live-status live-ok";
    }
  } else {
    sourceLabel.textContent = `static reference value (${fmt(r.carbon_g_kwh_used)} gCO\u2082/kWh)`;
    if (payload.use_live && r.live_lookup && !r.live_lookup.ok) {
      liveStatus.textContent = `Live lookup unavailable (${r.live_lookup.error}) — using static reference instead.`;
      liveStatus.className = "live-status live-error";
    } else {
      liveStatus.textContent = "";
      liveStatus.className = "live-status";
    }
  }

  if (sweep) updateCharts(sweep);
}

$("calc-form").addEventListener("submit", (e) => {
  e.preventDefault();
  runCalculation(readForm());
});

// ----------------------- Init -----------------------
window.addEventListener("DOMContentLoaded", () => {
  initCharts();
  runCalculation(readForm()); // initial estimate on load
});

// ----------------------- PWA: service worker + install prompt -----------------------
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((err) => {
      console.warn("Service worker registration failed:", err);
    });
  });
}

let deferredInstallPrompt = null;
const installBtn = $("install-btn");

window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
  installBtn.hidden = false;
});

installBtn.addEventListener("click", async () => {
  if (!deferredInstallPrompt) return;
  deferredInstallPrompt.prompt();
  await deferredInstallPrompt.userChoice;
  deferredInstallPrompt = null;
  installBtn.hidden = true;
});

window.addEventListener("appinstalled", () => {
  installBtn.hidden = true;
});

// Simple online/offline indicator
function updateConnStatus() {
  const tag = $("conn-status");
  tag.textContent = navigator.onLine ? "● live" : "● offline (cached)";
  tag.style.color = navigator.onLine ? "var(--accent)" : "#E8745A";
}
window.addEventListener("online", updateConnStatus);
window.addEventListener("offline", updateConnStatus);
updateConnStatus();
