import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import REPO_ROOT, Settings
from app.main import create_app
from app.routers.stations import get_latest_readings
from app.services.influx import combine_latest, latest_readings
from app.services.stations import load_seed

T1 = datetime(2026, 11, 19, 10, 0, tzinfo=UTC)
T0 = datetime(2026, 11, 19, 9, 59, 50, tzinfo=UTC)


def client_with(settings: Settings, latest: dict) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_latest_readings] = lambda: latest
    return TestClient(app)


def test_seeded_stations_are_returned_without_readings(client) -> None:
    response = client.get("/api/stations")

    assert response.status_code == 200
    body = response.json()
    assert [s["station_id"] for s in body] == ["station-1", "station-2"]
    assert all(s["latest"] is None for s in body)
    assert set(body[0]) == {"station_id", "name", "lat", "lon", "description", "latest"}


def test_latest_reading_is_attached(settings) -> None:
    latest = {
        "station-1": {
            "temperature": 17.4,
            "humidity": 62.0,
            "light": 540.0,
            "condition": "good",
            "timestamp": T1,
        }
    }

    with client_with(settings, latest) as client:
        body = client.get("/api/stations").json()

    assert body[0]["latest"] == {
        "temperature": 17.4,
        "humidity": 62.0,
        "light": 540.0,
        "condition": "good",
        "timestamp": "2026-11-19T10:00:00Z",
    }
    assert body[1]["latest"] is None


def test_readings_of_unknown_stations_are_ignored(settings) -> None:
    latest = {
        "station-9": {
            "temperature": 1.0,
            "humidity": None,
            "light": None,
            "condition": "poor",
            "timestamp": T1,
        }
    }

    with client_with(settings, latest) as client:
        body = client.get("/api/stations").json()

    assert [s["station_id"] for s in body] == ["station-1", "station-2"]


def test_endpoint_is_documented_in_openapi(client) -> None:
    spec = client.get("/openapi.json").json()

    assert "/api/stations" in spec["paths"]
    assert "StationResponse" in spec["components"]["schemas"]


def write_seed(path: Path, stations: list[dict]) -> Path:
    path.write_text(json.dumps(stations), encoding="utf-8")
    return path


def test_seed_is_upserted_on_every_start(tmp_path) -> None:
    seed = write_seed(
        tmp_path / "stations.json",
        [{"station_id": "a", "name": "Old", "lat": 1, "lon": 2}],
    )
    settings = Settings(database_path=tmp_path / "db.sqlite", stations_file=seed, influxdb_token="")
    with TestClient(create_app(settings)):
        pass

    write_seed(
        seed,
        [
            {"station_id": "a", "name": "New", "lat": 1, "lon": 2},
            {"station_id": "b", "name": "B", "lat": 3, "lon": 4},
        ],
    )
    with TestClient(create_app(settings)) as client:
        body = client.get("/api/stations").json()

    assert [(s["station_id"], s["name"]) for s in body] == [("a", "New"), ("b", "B")]


def test_missing_seed_file_does_not_stop_the_app(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "db.sqlite",
        stations_file=tmp_path / "missing.json",
        influxdb_token="",
    )

    with TestClient(create_app(settings)) as client:
        assert client.get("/api/stations").json() == []


def test_repository_seed_has_both_demo_checkpoints() -> None:
    seeds = load_seed(REPO_ROOT / "deploy" / "stations.json")

    assert [s.station_id for s in seeds] == ["station-1", "station-2"]
    # Both lie in Parque de Doña Casilda Iturrizar, Bilbao.
    for s in seeds:
        assert 43.262 < s.lat < 43.268
        assert -2.947 < s.lon < -2.936


@pytest.mark.parametrize(
    "stations",
    [
        [
            {"station_id": "a", "name": "A", "lat": 1, "lon": 2},
            {"station_id": "a", "name": "B", "lat": 1, "lon": 2},
        ],
        [{"station_id": "a b", "name": "A", "lat": 1, "lon": 2}],
        [{"station_id": "a", "name": "A", "lat": 100, "lon": 2}],
        [{"station_id": "a", "lat": 1, "lon": 2}],
    ],
)
def test_invalid_seed_is_rejected(tmp_path, stations) -> None:
    with pytest.raises(ValueError):
        load_seed(write_seed(tmp_path / "s.json", stations))


def test_combine_latest_uses_only_the_newest_message() -> None:
    records = [
        ("station-1", "temperature", 17.4, T1),
        ("station-1", "humidity", 55.0, T0),  # humidity failed in the newest message
        ("station-1", "light", 540.0, T1),
        ("station-1", "condition", "good", T1),
        ("station-2", "condition", "fault", T0),
    ]

    assert combine_latest(records) == {
        "station-1": {
            "temperature": 17.4,
            "humidity": None,
            "light": 540.0,
            "condition": "good",
            "timestamp": T1,
        },
        "station-2": {
            "temperature": None,
            "humidity": None,
            "light": None,
            "condition": "fault",
            "timestamp": T0,
        },
    }


def test_combine_latest_of_nothing_is_empty() -> None:
    assert combine_latest([]) == {}


class FakeRecord:
    def __init__(self, station_id, field, value, time) -> None:
        self.values = {"station_id": station_id}
        self.field, self.value, self.time = field, value, time

    def __getitem__(self, key):
        return self.values[key]

    def get_field(self):
        return self.field

    def get_value(self):
        return self.value

    def get_time(self):
        return self.time


class FakeInflux:
    def __init__(self, tables=None, error: Exception | None = None) -> None:
        self.tables, self.error, self.calls = tables or [], error, []

    def query_api(self):
        return self

    def query(self, query):
        self.calls.append(query)
        if self.error:
            raise self.error
        return self.tables


def test_latest_readings_queries_the_bucket() -> None:
    table = type("T", (), {"records": [FakeRecord("station-1", "condition", "poor", T1)]})
    client = FakeInflux(tables=[table])

    result = latest_readings(client, "environment")

    assert 'from(bucket: "environment")' in client.calls[0]
    assert result["station-1"]["condition"] == "poor"


def test_latest_readings_survives_influx_errors() -> None:
    assert latest_readings(FakeInflux(error=ConnectionError("down")), "environment") == {}


def test_latest_readings_without_client_is_empty() -> None:
    assert latest_readings(None, "environment") == {}
