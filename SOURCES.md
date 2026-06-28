# Data Sources

## Live grid carbon intensity (electricityMaps)
The app can optionally fetch **live, real-time** grid carbon intensity from
the [electricityMaps API](https://www.electricitymaps.com/) instead of using
the static reference table below. This is wired into `electricitymaps.py`
and surfaced via the "Use live grid carbon intensity" checkbox in the UI.

Setup:
1. Get a free-tier API key: https://api-portal.electricitymaps.com/
2. Set it as an environment variable before running the app:
   ```bash
   export ELECTRICITYMAPS_API_KEY=5Ts7x9rxPpHYp8EXjzEm
   python3 app.py
   ```
3. Without a key set, the checkbox still works in the UI but the app
   automatically falls back to the static reference values below and
   tells you why (shown under the toggle).

Zone codes used (electricityMaps' own country/region codes — see
`electricitymaps.py:ZONE_MAP`): Nigeria `NG`, South Africa `ZA`, Kenya `KE`,
Egypt `EG`, Ghana `GH`, Sweden `SE`, India `IN-NO`, US PJM region
`US-MIDA-PJM`.

Note: electricityMaps' free tier has limited country coverage and rate
limits — if a zone isn't available on your plan, the app will report the
specific API error and continue using the static figure.

## Downloading the raw reference dataset
Run `python3 download_dataset.py` to pull the real, public LowCarbonPower.org
generation-mix dataset (by country, fuel source, and year, 1900–2025) into
`data/`. This is genuine downloadable data, not something I fabricated —
see https://lowcarbonpower.org/ for the live site and methodology.

**Important caveat:** this dataset is electricity *generation* in TWh by
fuel type, not a precomputed gCO2/kWh table. To turn it into carbon
intensity yourself, you'd weight each country's per-fuel generation share
by standard emission factors (e.g. IPCC/IEA default gCO2/kWh by fuel —
coal ≈ 820, gas ≈ 490, hydro/wind/solar/nuclear ≈ 0–24). That's the
rigorous approach. The static `REGIONS` values in `app.py` instead use
LowCarbonPower's own *already-computed* 2025 carbon-intensity figures
(visible on each country's page), which is a reasonable shortcut for a
course project but one step less rigorous than deriving it from the raw
generation data yourself.

## Grid carbon intensity (gCO2eq/kWh) — static reference table
Primary source: **LowCarbonPower.org** national electricity datasets (2025),
which aggregate **Ember**, **IEA**, and **EIA** generation-mix data.
Downloadable raw dataset: https://lowcarbonpower.org/data-including-net-imports.csv
(JSON version also available at the same path with a `.json` extension).

Values used in `app.py` (`REGIONS` dict), pulled June 2026:

| Region | Carbon intensity (gCO2eq/kWh) | Notes | Source page |
|---|---|---|---|
| Nigeria | 340 | 2025 national grid; ~70% gas, ~30% hydro | https://lowcarbonpower.org/region/Nigeria |
| South Africa | 673 | 2025 national grid; ~80% coal | https://lowcarbonpower.org/region/South_Africa |
| Kenya | 122 | 2025 national grid; ~82% low-carbon (geothermal/hydro/wind) | https://lowcarbonpower.org/region/Kenya |
| Egypt | 438 | 2025 national grid; ~79% gas | https://lowcarbonpower.org/region/Egypt |
| Ghana | 330 | 2019 estimate (most recent figure found); ~61% fossil / 39% hydro as of 2023 | https://1p5ndc-pathways.climateanalytics.org/countries/ghana/sectors/power/ ; https://lowcarbonpower.org/region/Ghana |
| US East (Virginia), EU North (Sweden), South Asia (India), Global Average | — | Carried over as broad reference points for comparison; same LowCarbonPower/IEA family of sources, not re-verified line-by-line for this build | https://lowcarbonpower.org/ |

The IEA also publishes a more rigorous, citation-grade **Emission Factors** database
(updated annually, paid licence for derived-data use): https://www.iea.org/data-and-statistics/data-product/emissions-factors-2025
If this project is submitted academically, citing the IEA database directly alongside
Ember's free, open `electricity-data-explorer` is the stronger combination.

## Water usage (L/kWh)
**No public, Nigeria- or Africa-specific water-use-efficiency (WUE) dataset
exists for power generation or datacenters.** The `water_l_kwh` figures in
`app.py` are **not** drawn from a verified national dataset — they are
estimates based on the general relationship in NREL/Macknick et al. power-
plant water-withdrawal literature (thermal/gas-fired generation requires
materially more cooling water per kWh than hydro, solar, or wind), scaled
to roughly match each region's known generation mix. Treat these as
illustrative, not citable, figures. If your project needs defensible water
numbers, the most credible path is:
- Macknick, J. et al. (NREL), *"Operational water consumption and withdrawal
  factors for electricity generating technologies"* — defines L/kWh by
  generation technology (coal, gas, hydro, etc.), which you can then weight
  by each country's actual generation mix (available from the same
  LowCarbonPower/Ember dataset above) to get a defensible national number.
- Lawrence Berkeley National Laboratory datacenter water-use studies, for
  the *cooling-side* water use of the AI hardware itself (separate from the
  grid's generation-side water use).

## Hardware power draw (kW)
GPU/TPU figures in `app.py` are based on publicly listed TDP (thermal design
power) specifications from NVIDIA and Google's own spec sheets, not
independently re-verified for this build. For a citable source, link directly
to:
- NVIDIA A100/H100 datasheets (nvidia.com)
- Google Cloud TPU v4 specifications (cloud.google.com)

## What this means for your project writeup
You can legitimately cite the **carbon intensity** numbers for Nigeria, South
Africa, Kenya, and Egypt — they trace to Ember/IEA/EIA via LowCarbonPower.org.
The **water** and **hardware power** figures should be presented as
*modeled estimates based on published methodology*, not as directly sourced
national statistics, unless you do the additional NREL-weighting step above.
