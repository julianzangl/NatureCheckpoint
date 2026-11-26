from datetime import UTC, datetime, timedelta, timezone

from nc_sensor.payload import build_reading, health_topic, iso_utc, readings_topic

THRESHOLDS = {
    "temperature": {"good": [15.0, 25.0], "fair": [8.0, 30.0]},
    "humidity": {"good": [30.0, 70.0], "fair": [20.0, 85.0]},
}
NOW = datetime(2026, 11, 19, 10, 0, tzinfo=UTC)
CONTRACT_KEYS = {
    "station_id",
    "timestamp",
    "temperature",
    "humidity",
    "light",
    "condition",
    "condition_reason",
}


def reading(**values: float | None) -> dict:
    return build_reading("station-1", NOW, values, THRESHOLDS)


def test_reading_has_exactly_the_contract_keys() -> None:
    payload = reading(temperature=17.4, humidity=62.0, light=540)

    assert set(payload) == CONTRACT_KEYS
    assert payload == {
        "station_id": "station-1",
        "timestamp": "2026-11-19T10:00:00Z",
        "temperature": 17.4,
        "humidity": 62.0,
        "light": 540,
        "condition": "good",
        "condition_reason": "all values in comfort range",
    }


def test_timestamp_is_converted_to_utc() -> None:
    madrid = timezone(timedelta(hours=1))

    assert iso_utc(datetime(2026, 11, 19, 11, 0, tzinfo=madrid)) == "2026-11-19T10:00:00Z"


def test_values_are_rounded() -> None:
    payload = reading(temperature=17.44, humidity=61.96, light=540.6)

    assert payload["temperature"] == 17.4
    assert payload["humidity"] == 62.0
    assert payload["light"] == 541
    assert isinstance(payload["light"], int)


def test_missing_values_stay_null() -> None:
    payload = reading(temperature=20.0, humidity=None)

    assert payload["humidity"] is None
    assert payload["light"] is None
    assert payload["condition"] == "good"


def test_no_rated_values_is_a_fault() -> None:
    payload = reading(temperature=None, humidity=None, light=300)

    assert payload["condition"] == "fault"
    assert payload["light"] == 300


def test_poor_value_sets_condition_and_reason() -> None:
    payload = reading(temperature=35.0, humidity=50.0)

    assert payload["condition"] == "poor"
    assert "temperature high" in payload["condition_reason"]


def test_topics() -> None:
    assert readings_topic("station-2") == "naturecheckpoint/station-2/readings"
    assert health_topic("station-2") == "naturecheckpoint/station-2/health"
