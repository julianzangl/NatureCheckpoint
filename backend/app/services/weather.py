"""Regional weather from Open-Meteo (#26), shown next to the local readings.

No API key needed. Results are cached, and a failing API only hides the weather box.
"""

import logging
import threading
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_S = 600
CURRENT = "temperature_2m,relative_humidity_2m,uv_index,weather_code"

# WMO weather interpretation codes, grouped.
WMO_GROUPS = [
    ({0}, "clear sky"),
    ({1, 2}, "partly cloudy"),
    ({3}, "overcast"),
    ({45, 48}, "fog"),
    ({51, 53, 55, 56, 57}, "drizzle"),
    ({61, 63, 65, 66, 67, 80, 81, 82}, "rain"),
    ({71, 73, 75, 77, 85, 86}, "snow"),
    ({95, 96, 99}, "thunderstorm"),
]


def describe(code: int | None) -> str:
    for codes, text in WMO_GROUPS:
        if code in codes:
            return text
    return "unknown"


def parse_current(data: dict[str, Any]) -> dict[str, Any]:
    current = data["current"]
    return {
        "temperature": current.get("temperature_2m"),
        "humidity": current.get("relative_humidity_2m"),
        "uv_index": current.get("uv_index"),
        "weather_code": current.get("weather_code"),
        "description": describe(current.get("weather_code")),
        "time": current.get("time"),
        "source": "Open-Meteo",
    }


class WeatherCache:
    def __init__(self, lat: float, lon: float, client: httpx.Client | None = None) -> None:
        self.lat = lat
        self.lon = lon
        self._client = client or httpx.Client(timeout=4)
        self._value: dict[str, Any] | None = None
        self._fetched = 0.0
        self._lock = threading.Lock()

    def current(self, now: float | None = None) -> dict[str, Any] | None:
        now = time.monotonic() if now is None else now
        with self._lock:
            if self._value is not None and now - self._fetched < CACHE_S:
                return self._value
            try:
                reply = self._client.get(
                    OPEN_METEO_URL,
                    params={
                        "latitude": self.lat,
                        "longitude": self.lon,
                        "current": CURRENT,
                        "timezone": "Europe/Madrid",
                    },
                )
                reply.raise_for_status()
                self._value = parse_current(reply.json())
                self._fetched = now
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                log.warning("Open-Meteo not available: %s", exc)
                # Keep serving the last value for a while rather than nothing.
            return self._value
