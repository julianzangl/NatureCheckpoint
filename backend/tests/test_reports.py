from datetime import UTC, date, datetime, timedelta

import pytest

from app.config import Settings
from app.services.reports import build_report, day_bounds, summarize, trend


@pytest.fixture
def settings(park_settings: Settings) -> Settings:
    return park_settings


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, 25, hour, minute, tzinfo=UTC)


# --- day bounds and statistics ------------------------------------------------------------------


def test_winter_day_starts_at_2300_utc_the_day_before() -> None:
    assert day_bounds(date(2026, 11, 25)) == (
        datetime(2026, 11, 24, 23, tzinfo=UTC),
        datetime(2026, 11, 25, 23, tzinfo=UTC),
    )


def test_dst_end_day_is_25_hours_long() -> None:
    start, end = day_bounds(date(2026, 10, 25))

    assert start == datetime(2026, 10, 24, 22, tzinfo=UTC)
    assert end - start == timedelta(hours=25)


def test_dst_start_day_is_23_hours_long() -> None:
    start, end = day_bounds(date(2026, 3, 29))

    assert end - start == timedelta(hours=23)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([10, 10, 10, 10, 12, 12, 12, 12], "rising"),
        ([12, 12, 12, 12, 10, 10, 10, 10], "falling"),
        ([10, 10.2, 10.1, 10, 10.3, 10.2, 10.1, 10.4], "steady"),
        # Near zero the change is measured against 1.0, so noise is not a trend.
        ([0.0, 0.0, 0.0, 0.04], "steady"),
        ([1, 100, 1000], "steady"),
        ([], "steady"),
    ],
)
def test_trend(values: list[float], expected: str) -> None:
    assert trend(values) == expected


def test_summarize_rounds_to_two_decimals() -> None:
    assert summarize([1.111, 3.333, 2.222]) == {
        "avg": 2.22,
        "median": 2.22,
        "min": 1.11,
        "max": 3.33,
        "trend": "steady",
    }


def test_summarize_of_no_values_is_none() -> None:
    assert summarize([]) is None


# --- report -------------------------------------------------------------------------------------


def test_build_report_counts_samples_and_conditions() -> None:
    rows = [
        (at(10), "temperature", 18.0),
        (at(10), "humidity", 60.0),
        (at(10), "condition", "good"),
        (at(11), "temperature", 20.0),
        (at(11), "condition", "good"),
        (at(12), "condition", "fair"),
    ]

    report = build_report("station-1", date(2026, 11, 25), rows)

    assert report["station_id"] == "station-1"
    assert report["date"] == "2026-11-25"
    assert report["samples"] == 3
    assert report["conditions"] == {"good": 2, "fair": 1}
    assert report["temperature"]["avg"] == 19.0
    assert report["humidity"]["max"] == 60.0
    assert report["light"] is None


def test_build_report_sorts_rows_by_time() -> None:
    # Rows arrive newest first; the trend must still be computed in time order.
    rows = [(at(h), "temperature", v) for h, v in [(13, 12), (12, 12), (11, 10), (10, 10)]]

    report = build_report("station-1", date(2026, 11, 25), rows)

    assert report["temperature"]["trend"] == "rising"


def test_build_report_ignores_non_numeric_values() -> None:
    rows = [
        (at(10), "temperature", "warm"),
        (at(10), "light", None),
        (at(10), "condition", 3),
        (at(11), "temperature", 15),
    ]

    report = build_report("station-1", date(2026, 11, 25), rows)

    assert report["temperature"]["avg"] == 15.0
    assert report["light"] is None
    assert report["conditions"] == {}


def test_empty_report() -> None:
    report = build_report("station-1", date(2026, 11, 25), [])

    assert report["samples"] == 0
    assert report["temperature"] is None
    assert report["conditions"] == {}


# --- endpoint -----------------------------------------------------------------------------------

URL = "/api/reports/daily"


def test_unknown_station_is_404(client) -> None:
    response = client.get(URL, params={"station_id": "station-99", "date": "2026-11-25"})

    assert response.status_code == 404


def test_without_influxdb_the_report_is_unavailable(client) -> None:
    # The test settings have no InfluxDB token, so app.state.influx is None.
    response = client.get(URL, params={"station_id": "station-1", "date": "2026-11-25"})

    assert response.status_code == 503


@pytest.mark.parametrize(
    "params",
    [
        {"station_id": "station 1"},
        {"station_id": "station-1", "date": "25.11.2026"},
        {},
    ],
)
def test_bad_query_is_422(client, params) -> None:
    assert client.get(URL, params=params).status_code == 422


def test_report_is_returned(client, monkeypatch) -> None:
    calls = []

    def fake_daily_report(influx, bucket, station_id, day):
        calls.append((bucket, station_id, day))
        return build_report(station_id, day, [(at(10), "temperature", 18.5)])

    monkeypatch.setattr("app.routers.reports.daily_report", fake_daily_report)

    response = client.get(URL, params={"station_id": "station-1", "date": "2026-11-25"})

    assert response.status_code == 200
    assert calls == [("environment", "station-1", date(2026, 11, 25))]
    body = response.json()
    assert body["samples"] == 1
    assert body["temperature"] == {
        "avg": 18.5,
        "median": 18.5,
        "min": 18.5,
        "max": 18.5,
        "trend": "steady",
    }
    assert body["humidity"] is None
