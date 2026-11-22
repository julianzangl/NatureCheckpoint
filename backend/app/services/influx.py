"""Read the latest sensor readings per station from InfluxDB."""

import json
import logging
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from influxdb_client import InfluxDBClient

log = logging.getLogger(__name__)

READING_FIELDS = ("temperature", "humidity", "light", "condition")

# last() per field is pushed down to the storage engine, so it stays cheap even over 30 days.
# InfluxDB OSS has no query parameters, so the bucket (from our own config) is inserted
# as a JSON string literal, which is also a valid Flux string.
LATEST_QUERY = """
from(bucket: {bucket})
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "environment")
  |> last()
  |> keep(columns: ["station_id", "_field", "_value", "_time"])
"""

Record = tuple[str, str, Any, datetime]


def combine_latest(records: Iterable[Record]) -> dict[str, dict[str, Any]]:
    """Turn `(station_id, field, value, time)` rows from `last()` into one reading per station.

    `last()` returns the newest value of each field separately. If a sensor failed in the
    newest message, its last value is older. Only fields from the newest message are used,
    the others are None, so the response never mixes old and new values.
    """
    by_station: dict[str, list[Record]] = {}
    for record in records:
        by_station.setdefault(record[0], []).append(record)

    latest: dict[str, dict[str, Any]] = {}
    for station_id, rows in by_station.items():
        newest = max(time for _, _, _, time in rows)
        reading: dict[str, Any] = dict.fromkeys(READING_FIELDS)
        for _, field, value, time in rows:
            if time == newest and field in reading:
                reading[field] = value
        reading["timestamp"] = newest
        latest[station_id] = reading
    return latest


def latest_readings(client: InfluxDBClient | None, bucket: str) -> dict[str, dict[str, Any]]:
    """Latest reading per station. Returns {} if InfluxDB is not configured or not reachable,
    so the station list still works without time-series data."""
    if client is None:
        return {}
    try:
        tables = client.query_api().query(LATEST_QUERY.format(bucket=json.dumps(bucket)))
    except Exception:
        log.exception("could not read latest readings from InfluxDB")
        return {}
    return combine_latest(
        (record["station_id"], record.get_field(), record.get_value(), record.get_time())
        for table in tables
        for record in table.records
    )
