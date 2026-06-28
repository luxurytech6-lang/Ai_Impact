"""
Thin client for the electricityMaps API (https://www.electricitymaps.com/),
used to fetch live grid carbon intensity for a given zone.

Requires a free-tier API key, set as the ELECTRICITYMAPS_API_KEY environment
variable. Get one at: https://api-portal.electricitymaps.com/

If no key is configured, or the request fails for any reason (network,
rate limit, invalid zone), callers should fall back to the static
REGIONS reference values in app.py — this module never raises to the
caller, it returns a dict with ok=False instead.
"""
import os
import time
import requests

API_BASE = "https://api.electricitymap.org/v3"
API_KEY_ENV = "5Ts7x9rxPpHYp8EXjzEm"

# zone codes used by electricityMaps for the countries this app supports
ZONE_MAP = {
    "nigeria": "NG",
    "south_africa": "ZA",
    "kenya": "KE",
    "egypt": "EG",
    "ghana": "GH",
    "us_east": "US-MIDA-PJM",
    "eu_north": "SE",
    "asia_south": "IN-NO",
}

_CACHE_TTL_SECONDS = 300  # 5 minutes — stay well within free-tier rate limits
_cache = {}  # zone -> (timestamp, payload)


def _get_api_key():
    return os.environ.get(API_KEY_ENV)


def get_live_intensity(region_key):
    """
    Fetch live carbon intensity (gCO2eq/kWh) for the given internal region key.
    Returns: {"ok": bool, "carbon_g_kwh": float|None, "zone": str|None,
              "datetime": str|None, "source": "electricitymaps"|"cache"|None,
              "error": str|None}
    """
    zone = ZONE_MAP.get(region_key)
    if not zone:
        return {"ok": False, "error": f"No electricityMaps zone mapped for '{region_key}'."}

    api_key = _get_api_key()
    if not api_key:
        return {"ok": False, "error": "ELECTRICITYMAPS_API_KEY is not set."}

    now = time.time()
    cached = _cache.get(zone)
    if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
        payload = dict(cached[1])
        payload["source"] = "cache"
        return payload

    try:
        resp = requests.get(
            f"{API_BASE}/carbon-intensity/latest",
            params={"zone": zone},
            headers={"auth-token": api_key},
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
        result = {
            "ok": True,
            "carbon_g_kwh": data.get("carbonIntensity"),
            "zone": data.get("zone", zone),
            "datetime": data.get("datetime"),
            "source": "electricitymaps",
            "error": None,
        }
        _cache[zone] = (now, result)
        return result
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": f"electricityMaps request failed: {e}"}
    except ValueError as e:
        return {"ok": False, "error": f"electricityMaps returned invalid JSON: {e}"}
