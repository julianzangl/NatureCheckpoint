import pytest

from app.config import Settings


@pytest.fixture
def settings(park_settings: Settings) -> Settings:
    return park_settings


def test_checkin_page_shows_the_station(client) -> None:
    response = client.get("/c/station-1")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Duck pond" in response.text


def test_checkin_page_of_unknown_station_is_404(client) -> None:
    assert client.get("/c/station-99").status_code == 404


def test_privacy_page(client) -> None:
    response = client.get("/privacy")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
