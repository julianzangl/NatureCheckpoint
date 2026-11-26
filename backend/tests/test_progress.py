import pytest

from app.config import Settings
from app.models import utc_now
from app.services.rewards import month_key
from app.services.rules import local_date


@pytest.fixture
def settings(park_settings: Settings) -> Settings:
    return park_settings


def test_progress_of_a_new_visitor(client) -> None:
    response = client.get("/api/progress")

    assert response.status_code == 200
    assert response.json() == {
        "month": month_key(local_date(utc_now())),
        "stamps": 0,
        "goal": 6,
        "stations_visited": [],
        "stations_missing": ["station-1", "station-2"],
        "reward_status": "locked",
        "voucher_code": None,
    }


def test_progress_uses_the_checkin_cookie_visitor(client) -> None:
    client.post("/api/checkins", json={"station_id": "station-2"})

    progress = client.get("/api/progress").json()

    assert progress["stamps"] == 1
    assert progress["stations_visited"] == ["station-2"]
    assert progress["stations_missing"] == ["station-1"]


def test_progress_page_lists_the_stations(client) -> None:
    client.post("/api/checkins", json={"station_id": "station-1"})

    response = client.get("/progress")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Duck pond" in response.text
    assert "Park entrance" in response.text
    assert "<strong>1</strong> of 6" in response.text
