"""
Atmos — AI Environmental Impact Calculator
Flask backend v2.1

Changes from v2.0:
  - Loads environment variables from a .env file via python-dotenv, so
    ELECTRICITYMAPS_API_KEY (and anything else in .env) is actually picked
    up when running `python app.py` directly. load_dotenv() runs BEFORE
    `import electricitymaps`, since that module reads os.environ at
    call-time inside get_live_intensity() — but being safe/explicit here
    avoids any import-order surprises.

Changes from v1:
  - Input validation with descriptive error messages (validate_inputs helper)
  - Numeric clamping and type coercion done in one place (coerce_inputs)
  - global_avg now has a proper electricityMaps zone fallback (EU/global)
  - /api/health endpoint for uptime monitoring
  - All routes return consistent {"ok": bool, "result"|"error": ...} shape
  - No breaking changes to the calculation engine itself
"""
from __future__ import annotations

import math
import time
from typing import Any

from dotenv import load_dotenv

load_dotenv()  # reads .env in the working directory into os.environ

import electricitymaps
from flask import Flask, jsonify, render_template, request, send_from_directory

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Reference datasets
# ---------------------------------------------------------------------------

HARDWARE: dict[str, dict] = {
    "a100":       {"label": "NVIDIA A100 (80GB)", "power_kw": 0.400, "perf_index": 1.0},
    "h100":       {"label": "NVIDIA H100",         "power_kw": 0.700, "perf_index": 1.8},
    "v100":       {"label": "NVIDIA V100",          "power_kw": 0.300, "perf_index": 0.55},
    "rtx4090":    {"label": "NVIDIA RTX 4090",      "power_kw": 0.450, "perf_index": 0.9},
    "tpu_v4":     {"label": "Google TPU v4",        "power_kw": 0.350, "perf_index": 1.3},
    "cpu_server": {"label": "General CPU Server",   "power_kw": 0.250, "perf_index": 0.15},
}

# Grid carbon intensity (gCO2eq/kWh) sourced from LowCarbonPower.org 2025
# national electricity datasets (Ember / IEA / EIA aggregates). Pulled June 2026.
# Water (L/kWh): NREL/Macknick et al. power-plant water-use estimates weighted
# by each region's generation mix. Treat as modelled approximations; see SOURCES.md.
REGIONS: dict[str, dict] = {
    "nigeria":      {"label": "Nigeria (national grid)",       "carbon_g_kwh": 340, "water_l_kwh": 1.9},
    "south_africa": {"label": "South Africa (national grid)",  "carbon_g_kwh": 673, "water_l_kwh": 2.4},
    "kenya":        {"label": "Kenya (national grid)",          "carbon_g_kwh": 122, "water_l_kwh": 1.0},
    "egypt":        {"label": "Egypt (national grid)",          "carbon_g_kwh": 438, "water_l_kwh": 2.0},
    "ghana":        {"label": "Ghana (national grid)",          "carbon_g_kwh": 330, "water_l_kwh": 1.7},
    "us_east":      {"label": "US East (Virginia)",             "carbon_g_kwh": 380, "water_l_kwh": 1.8},
    "eu_north":     {"label": "EU North (Sweden)",              "carbon_g_kwh": 30,  "water_l_kwh": 0.6},
    "asia_south":   {"label": "South Asia (India)",             "carbon_g_kwh": 700, "water_l_kwh": 2.3},
    "global_avg":   {"label": "Global Average",                  "carbon_g_kwh": 475, "water_l_kwh": 1.8},
}

MODE: dict[str, dict] = {
    "training":  {"label": "Training",  "complexity_exp": 0.35, "base_units": 64},
    "inference": {"label": "Inference", "complexity_exp": 0.15, "base_units": 1},
}

# Real-world comparison constants
_KM_PER_KG_CO2_CAR     = 1 / 0.12   # 0.12 kg CO2 per km, average petrol car
_KWH_PER_HOUSEHOLD_DAY = 10.5        # kWh per average household per day
_LITRES_PER_SHOWER     = 65          # litres per 5-minute shower

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _err(msg: str) -> tuple:
    """Return a 400 JSON error response."""
    return jsonify({"ok": False, "error": msg}), 400


def _validate_inputs(data: dict) -> str | None:
    """
    Validate all incoming fields. Returns an error message string on
    the first failure, or None if everything is fine.
    """
    # Numeric presence & bounds
    checks = [
        ("model_size_b",   "Model size",       0.01,  1_000),
        ("exec_hours",     "Execution time",   0.01,  87_600),   # 10 years max
        ("utilization_pct","Utilization rate", 1,     100),
        ("num_units",      "Number of units",  1,     10_000),
    ]
    for field, label, lo, hi in checks:
        raw = data.get(field)
        if raw is None:
            return f"Missing field: {field}."
        try:
            val = float(raw)
        except (TypeError, ValueError):
            return f"{label} must be a number."
        if math.isnan(val) or math.isinf(val):
            return f"{label} must be a finite number."
        if val < lo or val > hi:
            return f"{label} must be between {lo} and {hi:,}."

    # Key lookups
    if data.get("hardware") not in HARDWARE:
        return f"Unknown hardware key '{data.get('hardware')}'. Valid: {', '.join(HARDWARE)}."
    if data.get("region") not in REGIONS:
        return f"Unknown region key '{data.get('region')}'. Valid: {', '.join(REGIONS)}."
    if data.get("mode") not in MODE:
        return f"Unknown mode key '{data.get('mode')}'. Valid: {', '.join(MODE)}."

    return None


def _coerce(data: dict) -> dict:
    """Return a new dict with all fields coerced to their correct types."""
    return {
        "model_size_b":    float(data["model_size_b"]),
        "hardware_key":    data["hardware"],
        "exec_hours":      float(data["exec_hours"]),
        "utilization_pct": float(data["utilization_pct"]),
        "region_key":      data["region"],
        "mode_key":        data["mode"],
        "num_units":       max(1, int(float(data["num_units"]))),
        "use_live":        bool(data.get("use_live", False)),
    }

# ---------------------------------------------------------------------------
# Calculation engine (unchanged from v1 — only internal references updated)
# ---------------------------------------------------------------------------

def calculate_footprint(
    model_size_b: float,
    hardware_key: str,
    exec_hours: float,
    utilization_pct: float,
    region_key: str,
    mode_key: str,
    num_units: int,
    carbon_g_kwh_override: float | None = None,
) -> dict:
    hw     = HARDWARE[hardware_key]
    region = REGIONS[region_key]
    mode   = MODE[mode_key]

    carbon_g_kwh = carbon_g_kwh_override if carbon_g_kwh_override is not None \
                   else region["carbon_g_kwh"]

    utilization = max(0.01, min(utilization_pct, 100) / 100.0)
    units       = max(1, num_units)

    # Sub-linear size scale: compute need grows with model size but
    # softened so the tool stays illustrative, not a hardware simulator.
    size_scale = max(0.05, model_size_b) ** mode["complexity_exp"]

    power_kw  = hw["power_kw"] * units
    energy_kwh = power_kw * exec_hours * utilization * size_scale

    carbon_kg = energy_kwh * carbon_g_kwh / 1000.0
    water_l   = energy_kwh * region["water_l_kwh"]

    # Efficiency: performance per kWh relative to A100 baseline
    efficiency_score = round(
        (hw["perf_index"] / max(energy_kwh, 0.0001)) * 100, 2
    )

    comparisons = {
        "car_km":          round(carbon_kg * _KM_PER_KG_CO2_CAR, 1),
        "household_days":  round(energy_kwh / _KWH_PER_HOUSEHOLD_DAY, 2),
        "showers":         round(water_l / _LITRES_PER_SHOWER, 1),
    }

    return {
        "energy_kwh":        round(energy_kwh, 3),
        "carbon_kg":         round(carbon_kg, 3),
        "water_l":           round(water_l, 2),
        "efficiency_score":  efficiency_score,
        "comparisons":       comparisons,
        "carbon_g_kwh_used": carbon_g_kwh,
        "carbon_source":     "live" if carbon_g_kwh_override is not None else "static_reference",
        "inputs_echo": {
            "model_size_b":    model_size_b,
            "hardware":        hw["label"],
            "exec_hours":      exec_hours,
            "utilization_pct": utilization_pct,
            "region":          region["label"],
            "mode":            mode["label"],
            "num_units":       units,
        },
    }


def sensitivity_sweep(
    model_size_b: float,
    hardware_key: str,
    exec_hours: float,
    utilization_pct: float,
    region_key: str,
    mode_key: str,
    num_units: int,
) -> dict:
    """Vary one factor at a time to show impact on footprint."""
    base = calculate_footprint(
        model_size_b, hardware_key, exec_hours,
        utilization_pct, region_key, mode_key, num_units,
    )

    hardware_sweep = [
        {
            "key": k, "label": hw["label"],
            **{m: calculate_footprint(model_size_b, k, exec_hours, utilization_pct,
                                      region_key, mode_key, num_units)[m]
               for m in ("carbon_kg", "energy_kwh", "water_l")},
        }
        for k, hw in HARDWARE.items()
    ]

    region_sweep = [
        {
            "key": k, "label": reg["label"],
            **{m: calculate_footprint(model_size_b, hardware_key, exec_hours, utilization_pct,
                                      k, mode_key, num_units)[m]
               for m in ("carbon_kg", "energy_kwh", "water_l")},
        }
        for k, reg in REGIONS.items()
    ]

    utilization_sweep = [
        {
            "utilization": u,
            **{m: calculate_footprint(model_size_b, hardware_key, exec_hours, u,
                                      region_key, mode_key, num_units)[m]
               for m in ("carbon_kg", "energy_kwh", "water_l")},
        }
        for u in [10, 25, 50, 75, 100]
    ]

    return {
        "base":              base,
        "hardware_sweep":    hardware_sweep,
        "region_sweep":      region_sweep,
        "utilization_sweep": utilization_sweep,
    }

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", hardware=HARDWARE, regions=REGIONS, modes=MODE)


@app.route("/api/health")
def api_health():
    """Simple health-check endpoint for uptime monitors."""
    return jsonify({"ok": True, "ts": time.time(), "service": "atmos"})


@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        return _err("Request body must be a JSON object.")

    err = _validate_inputs(data)
    if err:
        return _err(err)

    args    = _coerce(data)
    region_key     = args["region_key"]
    carbon_override = None
    live_info       = None

    if args["use_live"]:
        live_info = electricitymaps.get_live_intensity(region_key)
        if live_info.get("ok"):
            carbon_override = live_info["carbon_g_kwh"]

    result = calculate_footprint(
        model_size_b        = args["model_size_b"],
        hardware_key        = args["hardware_key"],
        exec_hours          = args["exec_hours"],
        utilization_pct     = args["utilization_pct"],
        region_key          = region_key,
        mode_key            = args["mode_key"],
        num_units           = args["num_units"],
        carbon_g_kwh_override = carbon_override,
    )
    if live_info is not None:
        result["live_lookup"] = live_info

    return jsonify({"ok": True, "result": result})


@app.route("/api/sensitivity", methods=["POST"])
def api_sensitivity():
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        return _err("Request body must be a JSON object.")

    err = _validate_inputs(data)
    if err:
        return _err(err)

    args = _coerce(data)
    result = sensitivity_sweep(
        model_size_b    = args["model_size_b"],
        hardware_key    = args["hardware_key"],
        exec_hours      = args["exec_hours"],
        utilization_pct = args["utilization_pct"],
        region_key      = args["region_key"],
        mode_key        = args["mode_key"],
        num_units       = args["num_units"],
    )
    return jsonify({"ok": True, "result": result})


@app.route("/api/live-intensity", methods=["GET"])
def api_live_intensity():
    region_key = request.args.get("region", "nigeria")
    if region_key not in REGIONS:
        return jsonify({"ok": False, "error": f"Unknown region key '{region_key}'."}), 400
    info   = electricitymaps.get_live_intensity(region_key)
    status = 200 if info.get("ok") else 503
    return jsonify(info), status


@app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    return send_from_directory("static/js", "sw.js", mimetype="application/javascript")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)