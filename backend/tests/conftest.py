import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import Settings
from app.main import create_app
from app.models import Visitor

PARK_STATIONS = [
    {"station_id": "station-1", "name": "Duck pond", "lat": 43.2657, "lon": -2.9405},
    {"station_id": "station-2", "name": "Park entrance", "lat": 43.266, "lon": -2.9389},
]


@pytest.fixture
def settings(tmp_path) -> Settings:
    # No InfluxDB token: tests never reach a real database, even if a local .env has one.
    return Settings(
        database_path=tmp_path / "test.db",
        public_base_url="http://testserver",
        influxdb_token="",
    )


@pytest.fixture
def park_settings(tmp_path) -> Settings:
    """Settings with the two demo stations seeded from a temporary stations.json."""
    stations_file = tmp_path / "stations.json"
    stations_file.write_text(json.dumps(PARK_STATIONS), encoding="utf-8")
    return Settings(
        database_path=tmp_path / "test.db",
        public_base_url="http://testserver",
        stations_file=stations_file,
        influxdb_token="",
        device_token="",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    # Using the client as a context manager runs the app's lifespan (DB setup).
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def session(client: TestClient) -> Iterator[Session]:
    with Session(client.app.state.engine) as db_session:
        yield db_session


@pytest.fixture
def visitor(session: Session) -> Visitor:
    visitor = Visitor()
    session.add(visitor)
    session.commit()
    return visitor
