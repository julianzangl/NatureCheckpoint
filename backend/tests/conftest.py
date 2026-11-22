from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    # No InfluxDB token: tests never reach a real database, even if a local .env has one.
    return Settings(
        database_path=tmp_path / "test.db",
        public_base_url="http://testserver",
        influxdb_token="",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    # Using the client as a context manager runs the app's lifespan (DB setup).
    with TestClient(create_app(settings)) as test_client:
        yield test_client
