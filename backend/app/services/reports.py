"""Daily environmental report (#25): avg / median / min / max / trend per sensor."""

import json
import logging
import statistics
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from influxdb_client import InfluxDBClient

from app.services.rules import LOCAL_TZ

log = logging.getLogger(__name__)

NUMERIC_FIELDS = ("temperature", "humidity", "light")
# Relative change between the first and last quarter of the day that counts as a trend.
TREND_THRESHOLD = 0.05

DAY_QUERY = """
from(bucket: {bucket})
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r._measurement == "environment" and r.station_id == {station})
  |> keep(columns: ["_time", "_field", "_value"])
"""


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """UTC start and end of a calendar day in Bilbao (handles the DST switch days)."""
    start = datetime.combine(day, time.min, LOCAL_TZ)
    end = datetime.combine(day + timedelta(days=1), time.min, LOCAL_TZ)
    return start.astimezone(UTC), end.astimezone(UTC)


def trend(values: Sequence[float]) -> str:
    if len(values) < 4:
        return "steady"
    quarter = len(values) // 4
    first = statistics.fmean(values[:quarter])
    last = statistics.fmean(values[-quarter:])
    scale = max(abs(first), 1.0)
    change = (last - first) / scale
    if change > TREND_THRESHOLD:
        return "rising"
    if change < -TREND_THRESHOLD:
        return "falling"
    return "steady"


def summarize(values: Sequence[float]) -> dict[str, Any] | None:
    """Summary of the values of one sensor, in time order. None if there are none."""
    if not values:
        return None
    return {
        "avg": round(statistics.fmean(values), 2),
        "median": round(statistics.median(values), 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "trend": trend(values),
    }


def build_report(
    station_id: str, day: date, rows: Sequence[tuple[datetime, str, Any]]
) -> dict[str, Any]:
    """Report from `(time, field, value)` rows of one station and day."""
    ordered = sorted(rows, key=lambda row: row[0])
    series: dict[str, list[float]] = {field: [] for field in NUMERIC_FIELDS}
    conditions: Counter[str] = Counter()
    times: set[datetime] = set()
    for ts, field, value in ordered:
        times.add(ts)
        if field in series and isinstance(value, int | float):
            series[field].append(float(value))
        elif field == "condition" and isinstance(value, str):
            conditions[value] += 1
    return {
        "station_id": station_id,
        "date": day.isoformat(),
        "samples": len(times),
        **{field: summarize(values) for field, values in series.items()},
        "conditions": dict(conditions),
    }


def daily_report(
    client: InfluxDBClient | None, bucket: str, station_id: str, day: date
) -> dict[str, Any] | None:
    """Report for one station and day, or None if InfluxDB is not configured or reachable."""
    if client is None:
        return None
    start, stop = day_bounds(day)
    query = DAY_QUERY.format(
        bucket=json.dumps(bucket),
        start=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        stop=stop.strftime("%Y-%m-%dT%H:%M:%SZ"),
        station=json.dumps(station_id),
    )
    try:
        tables = client.query_api().query(query)
    except Exception:
        log.exception("could not read the daily report from InfluxDB")
        return None
    rows = [
        (record.get_time(), record.get_field(), record.get_value())
        for table in tables
        for record in table.records
    ]
    return build_report(station_id, day, rows)
