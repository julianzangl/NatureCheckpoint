from pathlib import Path

from app import __version__
from app.config import REPO_ROOT, Settings


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_docs_are_served(client):
    spec = client.get("/openapi.json").json()

    assert spec["info"]["title"] == "NatureCheckpoint API"
    assert spec["info"]["version"] == __version__
    assert "/health" in spec["paths"]
    assert client.get("/docs").status_code == 200


def test_database_file_is_created_on_startup(client, settings):
    assert settings.database_path.exists()


def test_relative_database_path_is_resolved_against_repo_root():
    settings = Settings(database_path=Path("data/x.db"))

    assert settings.database_path == REPO_ROOT / "data" / "x.db"
