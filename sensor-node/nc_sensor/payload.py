"""MQTT payloads, exactly as in the contract in docs/architecture.md."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from nc_sensor.conditions import Thresholds, rate


def iso_utc(now: datetime) -> str:
    return now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_reading(
    station_id: str,
    now: datetime,
    values: Mapping[str, float | None],
    thresholds: Thresholds,
) -> dict[str, Any]:
    """`readings` payload. A failed sensor is sent as null; light is rounded to whole units."""
    temperature = values.get("temperature")
    humidity = values.get("humidity")
    light = values.get("light")
    condition, reason = rate({"temperature": temperature, "humidity": humidity}, thresholds)
    return {
        "station_id": station_id,
        "timestamp": iso_utc(now),
        "temperature": None if temperature is None else round(temperature, 1),
        "humidity": None if humidity is None else round(humidity, 1),
        "light": None if light is None else round(light),
        "condition": condition,
        "condition_reason": reason,
    }


def readings_topic(station_id: str) -> str:
    return f"naturecheckpoint/{station_id}/readings"


def health_topic(station_id: str) -> str:
    return f"naturecheckpoint/{station_id}/health"
