# Atmos — AI Environmental Impact Console (Flask PWA)

A Flask-based, installable Progressive Web App that estimates the energy,
carbon, and water footprint of AI training/inference workloads based on
model size, hardware, execution time, utilization, deployment region,
and unit count. Includes live sensitivity charts and real-world comparisons.

## Run locally

```bash
pip install -r requirements.txt
python3 app.py
```

Then open http://localhost:5000

## Live grid data (optional)
To use real-time carbon intensity instead of the static reference table,
get a free electricityMaps API key (https://api-portal.electricitymaps.com/)
and set it before running:
```bash
export ELECTRICITYMAPS_API_KEY=your_key_here
python3 app.py
```
Then check "Use live grid carbon intensity" in the app. Without a key, the
toggle still works but falls back to the static reference values and tells
you why. See `SOURCES.md` for zone codes and rate-limit notes.

## Downloading the reference dataset
```bash
python3 download_dataset.py
```
Pulls the real LowCarbonPower.org generation-mix dataset into `data/` —
see `SOURCES.md` for what it contains and its limitations.

## PWA features
- `static/manifest.json` — app name, icons, standalone display mode
- `static/js/sw.js` (served at `/sw.js`) — caches the app shell so it loads offline;
  API calls go network-first and fail gracefully offline
- "Install app" pill appears in the top bar when the browser fires `beforeinstallprompt`
  (Chrome/Edge/Android). On iOS Safari, use Share → "Add to Home Screen".

## Structure
```
app.py                  Flask routes + calculation/sensitivity engine
templates/index.html    Console UI (parameters, dial readout, charts)
static/css/style.css    Visual design
static/js/app.js        Form handling, dials, Chart.js, SW registration, install prompt
static/js/sw.js         Service worker (offline caching)
static/manifest.json    PWA manifest
static/icons/           App icons (192/512/512-maskable)
```

## Notes on the model
The carbon/water/energy figures are simplified, illustrative approximations
built from public sustainability reference points (regional grid carbon
intensity, datacenter water usage effectiveness, typical GPU power draw).
They're meant for awareness and sensitivity exploration, not a precision
carbon audit.

## Deploying with HTTPS
Service workers and install prompts require HTTPS (localhost is exempt).
Deploy behind any HTTPS host (Render, Fly.io, Railway, PythonAnywhere, etc.)
to get full installability on phones and desktops.
