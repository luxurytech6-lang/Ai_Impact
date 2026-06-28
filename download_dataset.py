"""
Downloads the real, public LowCarbonPower.org electricity generation dataset
(by country, fuel type, and year, 1900–present) to data/lowcarbonpower-generation.csv
and the JSON variant to data/lowcarbonpower-generation.json.

This is raw generation data in TWh by fuel source — NOT a direct gCO2/kWh
table. Combining it with per-fuel emission factors (e.g. IPCC/IEA defaults)
lets you compute your own historical carbon-intensity series per country,
which is a more rigorous approach than relying on any single pre-computed
number. The static REGIONS dict in app.py uses LowCarbonPower's own
pre-computed 2025 carbon-intensity figures (visible on their per-country
pages), which is a reasonable shortcut for a course project but not as
defensible as deriving it yourself from this raw dataset.

Usage:
    python3 download_dataset.py

Requires internet access and the `requests` package (already in
requirements.txt).
"""
import os
import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

SOURCES = {
    "lowcarbonpower-generation.csv": "https://lowcarbonpower.org/data-including-net-imports.csv",
    "lowcarbonpower-generation.json": "https://lowcarbonpower.org/data-including-net-imports.json",
    "lowcarbonpower-generation-monthly.csv": "https://lowcarbonpower.org/data-including-net-imports-monthly.csv",
}


def download_all():
    os.makedirs(DATA_DIR, exist_ok=True)
    for filename, url in SOURCES.items():
        dest = os.path.join(DATA_DIR, filename)
        print(f"Downloading {url} -> {dest} ...")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            with open(dest, "wb") as f:
                f.write(resp.content)
            size_kb = len(resp.content) / 1024
            print(f"  done ({size_kb:.0f} KB)")
        except requests.exceptions.RequestException as e:
            print(f"  FAILED: {e}")


if __name__ == "__main__":
    download_all()
