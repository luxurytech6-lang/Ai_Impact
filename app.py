from flask import Flask, render_template, request, jsonify, send_from_directory
import math
import electricitymaps

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Reference datasets (simplified, publicly-informed approximations)
# ---------------------------------------------------------------------------

HARDWARE = {
    "a100": {"label": "NVIDIA A100 (80GB)", "power_kw": 0.400, "perf_index": 1.0},
    "h100": {"label": "NVIDIA H100", "power_kw": 0.700, "perf_index": 1.8},
    "v100": {"label": "NVIDIA V100", "power_kw": 0.300, "perf_index": 0.55},
    "rtx4090": {"label": "NVIDIA RTX 4090", "power_kw": 0.450, "perf_index": 0.9},
    "tpu_v4": {"label": "Google TPU v4", "power_kw": 0.350, "perf_index": 1.3},
    "cpu_server": {"label": "General CPU Server", "power_kw": 0.250, "perf_index": 0.15},
}

# Grid carbon intensity (gCO2eq/kWh) — sourced from LowCarbonPower.org's
# 2025 national electricity datasets (which aggregate Ember, IEA, and EIA
# generation-mix data). Pulled June 2026; see SOURCES.md for citations and
# the raw dataset download links.
#
# Water usage (L/kWh) is a thermoelectric/datacenter cooling water-use
# factor. No public, country-specific WUE dataset exists for Nigeria or
# most African grids, so these use the widely-cited global benchmarks
# from Lawrence Berkeley National Laboratory / Macknick et al. (NREL)
# power-plant water-use studies, adjusted upward for regions dominated by
# thermal (gas/coal) generation, which needs far more cooling water than
# hydro or solar. Treat these water figures as a generic benchmark, not a
# nationally verified number — flagged clearly in SOURCES.md.
REGIONS = {
    "nigeria":      {"label": "Nigeria (national grid)",        "carbon_g_kwh": 340, "water_l_kwh": 1.9},
    "south_africa": {"label": "South Africa (national grid)",   "carbon_g_kwh": 673, "water_l_kwh": 2.4},
    "kenya":        {"label": "Kenya (national grid)",           "carbon_g_kwh": 122, "water_l_kwh": 1.0},
    "egypt":        {"label": "Egypt (national grid)",           "carbon_g_kwh": 438, "water_l_kwh": 2.0},
    "ghana":        {"label": "Ghana (national grid)",           "carbon_g_kwh": 330, "water_l_kwh": 1.7},
    "us_east":      {"label": "US East (Virginia)",              "carbon_g_kwh": 380, "water_l_kwh": 1.8},
    "eu_north":     {"label": "EU North (Sweden)",                "carbon_g_kwh": 30,  "water_l_kwh": 0.6},
    "asia_south":   {"label": "South Asia (India)",              "carbon_g_kwh": 700, "water_l_kwh": 2.3},
    "global_avg":   {"label": "Global Average",                   "carbon_g_kwh": 475, "water_l_kwh": 1.8},
}

MODE = {
    "training": {"label": "Training", "complexity_exp": 0.35, "base_units": 64},
    "inference": {"label": "Inference", "complexity_exp": 0.15, "base_units": 1},
}

# Real-world comparison constants
KM_PER_KG_CO2_CAR = 1 / 0.12          # ~0.12 kg CO2 per km for an average petrol car
KWH_PER_HOUSEHOLD_DAY = 10.5           # average household electricity use per day
LITRES_PER_SHOWER = 65


def calculate_footprint(model_size_b, hardware_key, exec_hours, utilization_pct,
                         region_key, mode_key, num_units, carbon_g_kwh_override=None):
    hw = HARDWARE[hardware_key]
    region = REGIONS[region_key]
    mode = MODE[mode_key]

    carbon_g_kwh = carbon_g_kwh_override if carbon_g_kwh_override is not None else region["carbon_g_kwh"]

    utilization = max(0.01, min(utilization_pct, 100) / 100.0)
    units = max(1, num_units)

    # Scale factor approximates how compute need grows with model size,
    # softened by a sub-linear exponent so the tool stays illustrative,
    # not a precise hardware simulator.
    size_scale = max(0.05, model_size_b) ** mode["complexity_exp"]

    power_kw = hw["power_kw"] * units
    energy_kwh = power_kw * exec_hours * utilization * size_scale

    carbon_kg = energy_kwh * carbon_g_kwh / 1000.0
    water_l = energy_kwh * region["water_l_kwh"]

    # Efficiency: useful "performance" delivered per kWh, relative to A100 baseline
    efficiency_score = round((hw["perf_index"] / max(energy_kwh, 0.0001)) * 100, 2)

    comparisons = {
        "car_km": round(carbon_kg * KM_PER_KG_CO2_CAR, 1),
        "household_days": round(energy_kwh / KWH_PER_HOUSEHOLD_DAY, 2),
        "showers": round(water_l / LITRES_PER_SHOWER, 1),
    }

    return {
        "energy_kwh": round(energy_kwh, 3),
        "carbon_kg": round(carbon_kg, 3),
        "water_l": round(water_l, 2),
        "efficiency_score": efficiency_score,
        "comparisons": comparisons,
        "carbon_g_kwh_used": carbon_g_kwh,
        "carbon_source": "live" if carbon_g_kwh_override is not None else "static_reference",
        "inputs_echo": {
            "model_size_b": model_size_b,
            "hardware": hw["label"],
            "exec_hours": exec_hours,
            "utilization_pct": utilization_pct,
            "region": region["label"],
            "mode": mode["label"],
            "num_units": units,
        }
    }


def sensitivity_sweep(model_size_b, hardware_key, exec_hours, utilization_pct,
                       region_key, mode_key, num_units):
    """Vary one factor at a time (hardware, region, utilization) to show impact."""
    base = calculate_footprint(model_size_b, hardware_key, exec_hours, utilization_pct,
                                region_key, mode_key, num_units)

    hardware_sweep = []
    for key, hw in HARDWARE.items():
        r = calculate_footprint(model_size_b, key, exec_hours, utilization_pct,
                                 region_key, mode_key, num_units)
        hardware_sweep.append({"key": key, "label": hw["label"], "carbon_kg": r["carbon_kg"],
                                "energy_kwh": r["energy_kwh"], "water_l": r["water_l"]})

    region_sweep = []
    for key, reg in REGIONS.items():
        r = calculate_footprint(model_size_b, hardware_key, exec_hours, utilization_pct,
                                 key, mode_key, num_units)
        region_sweep.append({"key": key, "label": reg["label"], "carbon_kg": r["carbon_kg"],
                              "energy_kwh": r["energy_kwh"], "water_l": r["water_l"]})

    utilization_sweep = []
    for u in [10, 25, 50, 75, 100]:
        r = calculate_footprint(model_size_b, hardware_key, exec_hours, u,
                                 region_key, mode_key, num_units)
        utilization_sweep.append({"utilization": u, "carbon_kg": r["carbon_kg"],
                                   "energy_kwh": r["energy_kwh"], "water_l": r["water_l"]})

    return {
        "base": base,
        "hardware_sweep": hardware_sweep,
        "region_sweep": region_sweep,
        "utilization_sweep": utilization_sweep,
    }


@app.route("/")
def index():
    return render_template(
        "index.html",
        hardware=HARDWARE,
        regions=REGIONS,
        modes=MODE,
    )


@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    data = request.get_json(force=True)
    try:
        region_key = data.get("region", "nigeria")
        carbon_override = None
        live_info = None

        if data.get("use_live"):
            live_info = electricitymaps.get_live_intensity(region_key)
            if live_info.get("ok"):
                carbon_override = live_info["carbon_g_kwh"]

        result = calculate_footprint(
            model_size_b=float(data.get("model_size_b", 7)),
            hardware_key=data.get("hardware", "a100"),
            exec_hours=float(data.get("exec_hours", 1)),
            utilization_pct=float(data.get("utilization_pct", 70)),
            region_key=region_key,
            mode_key=data.get("mode", "inference"),
            num_units=int(data.get("num_units", 1)),
            carbon_g_kwh_override=carbon_override,
        )
        if live_info is not None:
            result["live_lookup"] = live_info
        return jsonify({"ok": True, "result": result})
    except (KeyError, ValueError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/api/live-intensity", methods=["GET"])
def api_live_intensity():
    region_key = request.args.get("region", "nigeria")
    info = electricitymaps.get_live_intensity(region_key)
    status = 200 if info.get("ok") else 503
    return jsonify(info), status


@app.route("/api/sensitivity", methods=["POST"])
def api_sensitivity():
    data = request.get_json(force=True)
    try:
        result = sensitivity_sweep(
            model_size_b=float(data.get("model_size_b", 7)),
            hardware_key=data.get("hardware", "a100"),
            exec_hours=float(data.get("exec_hours", 1)),
            utilization_pct=float(data.get("utilization_pct", 70)),
            region_key=data.get("region", "nigeria"),
            mode_key=data.get("mode", "inference"),
            num_units=int(data.get("num_units", 1)),
        )
        return jsonify({"ok": True, "result": result})
    except (KeyError, ValueError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    # Serve from root scope so it can control the whole app
    return send_from_directory("static/js", "sw.js", mimetype="application/javascript")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
