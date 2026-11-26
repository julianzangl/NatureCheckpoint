import json
from types import SimpleNamespace
from typing import Any

import pytest

from ingest.main import Ingest

TOPIC = "naturecheckpoint/station-1/readings"


class FakeWriteApi:
    def __init__(self, error: Exception | None = None) -> None:
        self.records: list[Any] = []
        self.error = error

    def write(self, bucket: str, org: str, record: Any) -> None:
        if self.error:
            raise self.error
        self.records.append(record)


def message(topic: str = TOPIC, **overrides: object) -> SimpleNamespace:
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
    return SimpleNamespace(topic=topic, payload=json.dumps(payload).encode())


def ingest(write_api: FakeWriteApi) -> Ingest:
    # Plain namespace instead of IngestSettings, so a local .env cannot change the test.
    settings = SimpleNamespace(influxdb_bucket="environment", influxdb_org="naturecheckpoint")
    return Ingest(settings, write_api)  # type: ignore[arg-type]


def test_valid_message_is_written() -> None:
    write_api = FakeWriteApi()

    ingest(write_api).on_message(None, None, message())  # type: ignore[arg-type]

    assert len(write_api.records) == 1


@pytest.mark.parametrize(
    "msg",
    [
        message(condition=["good"]),
        message(condition={"level": "good"}),
        message(timestamp="0001-01-01T00:00:00+01:00"),
        message(timestamp="9999-12-31T23:59:59-01:00"),
        message(temperature=10**400),
        message(temperature="warm"),
        message(topic="naturecheckpoint/station-1/other"),
        SimpleNamespace(topic=TOPIC, payload=b"\xff not json"),
        SimpleNamespace(topic=TOPIC, payload=b"[1, 2]"),
    ],
)
def test_malformed_message_is_skipped_without_raising(msg: SimpleNamespace) -> None:
    write_api = FakeWriteApi()

    ingest(write_api).on_message(None, None, msg)  # type: ignore[arg-type]

    assert write_api.records == []


def test_influxdb_error_does_not_stop_the_subscriber() -> None:
    write_api = FakeWriteApi(error=ConnectionError("influxdb down"))

    ingest(write_api).on_message(None, None, message())  # type: ignore[arg-type]
