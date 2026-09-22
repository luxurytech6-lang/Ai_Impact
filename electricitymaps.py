"""
Thin client for the electricityMaps API (https://www.electricitymaps.com/).

Changes from v1:
  - Added global_avg → "DE" (Germany, close to IEA global average) as a
    reasonable fallback zone. The real global average doesn't exist as a
    single electricityMaps zone; Germany (≈380 gCO2/kWh) is a defensible
    proxy that keeps the live-toggle from silently failing.
  - Added _ZONE_NOTES for transparency in responses.
  - Improved error messages to be more actionable.

Requires a free-tier API key set as the ELECTRICITYMAPS_API_KEY environment
variable. Falls back gracefully (ok=False) without one.
"""
from __future__ import annotations

import os
import time

import requests

API_BASE    = "https://api.electricitymap.org/v3"
API_KEY_ENV = "ELECTRICITYMAPS_API_KEY"

ZONE_MAP: dict[str, str] = {
    "nigeria":      "NG",
    "south_africa": "ZA",
    "kenya":        "KE",
    "egypt":        "EG",
    "ghana":        "GH",
    "us_east":      "US-MIDA-PJM",
    "eu_north":     "SE",
    "asia_south":   "IN-NO",
    # Fixed: was missing in v1, caused silent failure for global_avg.
    # Germany is used as the closest single-zone proxy for the IEA global average.
    "global_avg":   "DE",
}

_ZONE_NOTES: dict[str, str] = {
    "global_avg": "Live reading for Germany (DE) used as a proxy for the global average zone.",
}

_CACHE_TTL = 300  # 5 minutes — well within free-tier rate limits
_cache: dict[str, tuple[float, dict]] = {}


def _get_api_key() -> str | None:
    return os.environ.get(API_KEY_ENV)


def get_live_intensity(region_key: str) -> dict:
    """
    Fetch live carbon intensity (gCO2eq/kWh) for the given internal region key.

    Returns:
        {
          "ok":           bool,
          "carbon_g_kwh": float | None,
          "zone":         str | None,
          "datetime":     str | None,
          "source":       "electricitymaps" | "cache" | None,
          "note":         str | None,     # present when a proxy zone is used
          "error":        str | None,
        }
    """
    zone = ZONE_MAP.get(region_key)
    if not zone:
        return {
            "ok": False,
            "carbon_g_kwh": None, "zone": None, "datetime": None,
            "source": None,
            "error": (
                f"No electricityMaps zone is mapped for region '{region_key}'. "
                f"Available regions: {', '.join(ZONE_MAP)}."
            ),
        }

    api_key = _get_api_key()
    if not api_key:
        return {
            "ok": False,
            "carbon_g_kwh": None, "zone": zone, "datetime": None,
            "source": None,
            "error": (
                f"{API_KEY_ENV} is not set. "
                "Get a free key at https://api-portal.electricitymaps.com/ "
                "and set it before starting the app."
            ),
        }

    # Cache check
    now    = time.time()
    cached = _cache.get(zone)
    if cached and (now - cached[0]) < _CACHE_TTL:
        payload = dict(cached[1])
        payload["source"] = "cache"
        return payload

    # Live fetch
    try:
        resp = requests.get(
            f"{API_BASE}/carbon-intensity/latest",
            params={"zone": zone},
            headers={"auth-token": api_key},
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()

        result: dict = {
            "ok":           True,
            "carbon_g_kwh": data.get("carbonIntensity"),
            "zone":         data.get("zone", zone),
            "datetime":     data.get("datetime"),
            "source":       "electricitymaps",
            "error":        None,
        }
        note = _ZONE_NOTES.get(region_key)
        if note:
            result["note"] = note

        _cache[zone] = (now, result)
        return result

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        return {
            "ok": False, "carbon_g_kwh": None, "zone": zone, "datetime": None,
            "source": None,
            "error": (
                f"electricityMaps returned HTTP {status}. "
                "Check your API key and that the zone is available on your plan."
            ),
        }
    except requests.exceptions.Timeout:
        return {
            "ok": False, "carbon_g_kwh": None, "zone": zone, "datetime": None,
            "source": None,
            "error": "electricityMaps request timed out after 6 s. Try again shortly.",
        }
    except requests.exceptions.RequestException as e:
        return {
            "ok": False, "carbon_g_kwh": None, "zone": zone, "datetime": None,
            "source": None,
            "error": f"electricityMaps request failed: {e}",
        }
    except ValueError as e:
        return {
            "ok": False, "carbon_g_kwh": None, "zone": zone, "datetime": None,
            "source": None,
            "error": f"electricityMaps returned invalid JSON: {e}",
        }