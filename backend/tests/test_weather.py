import httpx

from app.services.weather import CACHE_S, WeatherCache, describe, parse_current

SAMPLE = {
    "current": {
        "time": "2026-11-26T16:00",
        "temperature_2m": 14.2,
        "relative_humidity_2m": 81,
        "uv_index": 0.4,
        "weather_code": 3,
    }
}


def fake_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_describe_groups_wmo_codes():
    assert describe(0) == "clear sky"
    assert describe(63) == "rain"
    assert describe(None) == "unknown"


def test_parse_current_maps_fields():
    weather = parse_current(SAMPLE)
    assert weather["temperature"] == 14.2
    assert weather["humidity"] == 81
    assert weather["description"] == "overcast"


def test_value_is_cached():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=SAMPLE)

    cache = WeatherCache(43.27, -2.94, fake_client(handler))
    assert cache.current(now=0)["temperature"] == 14.2
    cache.current(now=CACHE_S - 1)
    assert len(calls) == 1
    cache.current(now=CACHE_S + 1)
    assert len(calls) == 2


def test_failure_returns_last_value_or_none():
    responses = [httpx.Response(200, json=SAMPLE), httpx.Response(500)]
    cache = WeatherCache(43.27, -2.94, fake_client(lambda request: responses.pop(0)))
    assert cache.current(now=0) is not None
    # API fails later: the last good value is kept.
    assert cache.current(now=CACHE_S + 1)["temperature"] == 14.2

    broken = WeatherCache(43.27, -2.94, fake_client(lambda request: httpx.Response(500)))
    assert broken.current(now=0) is None
