import json

import pytest

from ingest.points import InvalidMessage, payload_to_point

READINGS_TOPIC = "naturecheckpoint/station-1/readings"
HEALTH_TOPIC = "naturecheckpoint/station-1/health"

# 2026-11-19T10:00:00Z in seconds since the epoch.
TS = 1795082400


def readings(**overrides: object) -> bytes:
    payload = {
        "station_id": "station-1",
        "timestamp": "2026-11-19T10:00:00Z",
        "temperature": 17.4,
        "humidity": 62.0,
        "light": 540,
        "condition": "good",
        "condition_reason": "all values in comfort range",
    }
    payload.update(overrides)
    return json.dumps(payload).encode()


def health(**overrides: object) -> bytes:
    payload = {
        "station_id": "station-1",
        "timestamp": "2026-11-19T10:00:00Z",
        "cpu_temp": 52.1,
        "load1": 0.31,
        "uptime_s": 3600,
    }
    payload.update(overrides)
    return json.dumps(payload).encode()


def test_readings_map_to_environment_point() -> None:
    point = payload_to_point(READINGS_TOPIC, readings())

    assert point.to_line_protocol() == (
        "environment,station_id=station-1 "
        'condition="good",humidity=62,light=540,temperature=17.4 '
        f"{TS}"
    )


def test_health_maps_to_device_health_point() -> None:
    point = payload_to_point(HEALTH_TOPIC, health())

    assert point.to_line_protocol() == (
        f"device_health,station_id=station-1 cpu_temp=52.1,load1=0.31,uptime_s=3600i {TS}"
    )


def test_payload_may_be_a_string() -> None:
    assert payload_to_point(READINGS_TOPIC, readings().decode()).to_line_protocol()


def test_failed_sensor_is_left_out() -> None:
    line = payload_to_point(READINGS_TOPIC, readings(humidity=None)).to_line_protocol()

    assert "humidity" not in line
    assert "temperature=17.4" in line


def test_fault_without_any_sensor_value_is_stored() -> None:
    payload = readings(temperature=None, humidity=None, light=None, condition="fault")

    line = payload_to_point(READINGS_TOPIC, payload).to_line_protocol()

    assert line == f'environment,station_id=station-1 condition="fault" {TS}'


def test_timestamp_with_offset_is_converted_to_utc() -> None:
    payload = readings(timestamp="2026-11-19T11:00:00+01:00")

    assert payload_to_point(READINGS_TOPIC, payload).to_line_protocol().endswith(f" {TS}")


def test_integer_values_are_stored_as_float() -> None:
    line = payload_to_point(READINGS_TOPIC, readings(temperature=17)).to_line_protocol()

    # Line protocol writes floats without a suffix and integers with "i".
    assert "temperature=17," in line or line.endswith("temperature=17 " + str(TS))
    assert "temperature=17i" not in line


def test_whole_float_uptime_is_stored_as_integer() -> None:
    line = payload_to_point(HEALTH_TOPIC, health(uptime_s=3600.0)).to_line_protocol()

    assert "uptime_s=3600i" in line


@pytest.mark.parametrize(
    "topic",
    [
        "naturecheckpoint/station-1/unknown",
        "naturecheckpoint/station-1",
        "other/station-1/readings",
        "naturecheckpoint/bad id/readings",
        "naturecheckpoint/station-1/readings/extra",
    ],
)
def test_unexpected_topic_is_rejected(topic: str) -> None:
    with pytest.raises(InvalidMessage, match="topic"):
        payload_to_point(topic, readings())


@pytest.mark.parametrize(
    "payload",
    [b"not json", b"", b"\xff\xfe", b"[1, 2]", b'"text"', b"null"],
)
def test_invalid_json_is_rejected(payload: bytes) -> None:
    with pytest.raises(InvalidMessage):
        payload_to_point(READINGS_TOPIC, payload)


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(InvalidMessage, match="unknown fields"):
        payload_to_point(READINGS_TOPIC, readings(pressure=1013))


def test_health_field_in_readings_is_rejected() -> None:
    with pytest.raises(InvalidMessage, match="unknown fields"):
        payload_to_point(READINGS_TOPIC, readings(cpu_temp=50))


@pytest.mark.parametrize("station_id", ["station-2", None, 1])
def test_station_id_must_match_topic(station_id: object) -> None:
    with pytest.raises(InvalidMessage, match="station_id"):
        payload_to_point(READINGS_TOPIC, readings(station_id=station_id))


def test_missing_station_id_is_rejected() -> None:
    payload = json.loads(readings())
    del payload["station_id"]

    with pytest.raises(InvalidMessage, match="station_id"):
        payload_to_point(READINGS_TOPIC, json.dumps(payload))


@pytest.mark.parametrize(
    "timestamp",
    [None, 1795082400, "yesterday", "2026-11-19T10:00:00", "2026-13-01T10:00:00Z"],
)
def test_bad_timestamp_is_rejected(timestamp: object) -> None:
    with pytest.raises(InvalidMessage, match="timestamp"):
        payload_to_point(READINGS_TOPIC, readings(timestamp=timestamp))


@pytest.mark.parametrize("value", ["17.4", True, [17.4], {"v": 1}])
def test_non_numeric_value_is_rejected(value: object) -> None:
    with pytest.raises(InvalidMessage, match="temperature"):
        payload_to_point(READINGS_TOPIC, readings(temperature=value))


def test_nan_is_rejected() -> None:
    payload = readings().replace(b"17.4", b"NaN")

    with pytest.raises(InvalidMessage, match="finite"):
        payload_to_point(READINGS_TOPIC, payload)


def test_fractional_uptime_is_rejected() -> None:
    with pytest.raises(InvalidMessage, match="uptime_s"):
        payload_to_point(HEALTH_TOPIC, health(uptime_s=1.5))


@pytest.mark.parametrize("condition", ["great", "", 1])
def test_unknown_condition_is_rejected(condition: object) -> None:
    with pytest.raises(InvalidMessage, match="condition"):
        payload_to_point(READINGS_TOPIC, readings(condition=condition))


def test_message_without_values_is_rejected() -> None:
    payload = readings(temperature=None, humidity=None, light=None, condition=None)

    with pytest.raises(InvalidMessage, match="no values"):
        payload_to_point(READINGS_TOPIC, payload)
