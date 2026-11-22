"""Map MQTT messages from the checkpoints to InfluxDB points.

Pure functions without I/O, so the mapping can be unit-tested. The payloads and the InfluxDB
schema are defined in docs/architecture.md (section 4).
"""

import json
import math
import re
from datetime import UTC, datetime
from typing import Any

from influxdb_client import Point, WritePrecision

TOPIC_RE = re.compile(
    r"^naturecheckpoint/(?P<station_id>[A-Za-z0-9_-]{1,64})/(?P<kind>readings|health)$"
)

CONDITIONS = frozenset({"good", "fair", "poor", "fault"})

# Per topic kind: measurement name, numeric fields with their type, and keys that are
# allowed in the payload but not stored.
MEASUREMENTS: dict[str, str] = {"readings": "environment", "health": "device_health"}
NUMERIC_FIELDS: dict[str, dict[str, type]] = {
    "readings": {"temperature": float, "humidity": float, "light": float},
    "health": {"cpu_temp": float, "load1": float, "uptime_s": int},
}
IGNORED_KEYS: dict[str, frozenset[str]] = {
    "readings": frozenset({"condition_reason"}),
    "health": frozenset(),
}


class InvalidMessage(ValueError):
    """The message does not match the contract and is skipped."""


def payload_to_point(topic: str, payload: bytes | str) -> Point:
    """Convert one MQTT message into an InfluxDB point.

    Raises InvalidMessage if the topic, the JSON or any field does not match the contract.
    A sensor value of `null` means the sensor failed; the field is then left out.
    """
    match = TOPIC_RE.match(topic)
    if match is None:
        raise InvalidMessage(f"unexpected topic {topic!r}")
    station_id, kind = match["station_id"], match["kind"]

    data = _parse_json(payload)

    numeric = NUMERIC_FIELDS[kind]
    known = {"station_id", "timestamp"} | numeric.keys() | IGNORED_KEYS[kind]
    if kind == "readings":
        known |= {"condition"}
    unknown = sorted(data.keys() - known)
    if unknown:
        raise InvalidMessage(f"unknown fields {unknown}")

    if data.get("station_id") != station_id:
        raise InvalidMessage(
            f"station_id {data.get('station_id')!r} does not match topic station {station_id!r}"
        )

    point = (
        Point(MEASUREMENTS[kind])
        .tag("station_id", station_id)
        .time(_parse_timestamp(data.get("timestamp")), WritePrecision.S)
    )

    has_field = False
    for name, field_type in numeric.items():
        value = _number(name, data.get(name), field_type)
        if value is not None:
            point.field(name, value)
            has_field = True

    if kind == "readings":
        condition = data.get("condition")
        if condition is not None:
            if condition not in CONDITIONS:
                raise InvalidMessage(f"condition {condition!r} is not one of {sorted(CONDITIONS)}")
            point.field("condition", condition)
            has_field = True

    if not has_field:
        raise InvalidMessage("message has no values to store")
    return point


def _parse_json(payload: bytes | str) -> dict[str, Any]:
    try:
        data = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidMessage(f"payload is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise InvalidMessage("payload is not a JSON object")
    return data


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise InvalidMessage("timestamp is missing or not a string")
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise InvalidMessage(f"timestamp {value!r} is not ISO 8601") from exc
    # A timestamp without offset is ambiguous; the contract requires UTC.
    if timestamp.tzinfo is None:
        raise InvalidMessage(f"timestamp {value!r} has no timezone")
    return timestamp.astimezone(UTC)


def _number(name: str, value: Any, field_type: type) -> float | int | None:
    if value is None:
        return None
    # bool is a subclass of int, but `true` is never a valid sensor value.
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidMessage(f"{name} must be a number or null, got {value!r}")
    if not math.isfinite(value):
        raise InvalidMessage(f"{name} must be finite, got {value!r}")
    if field_type is int:
        if value != int(value):
            raise InvalidMessage(f"{name} must be a whole number, got {value!r}")
        return int(value)
    # Always store floats so InfluxDB keeps one type per field (17 and 17.0 would clash).
    return float(value)
