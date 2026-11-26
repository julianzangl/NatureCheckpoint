import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import Settings
from app.main import create_app
from app.models import Visitor

CARD_A = "a" * 32
CARD_B = "b" * 32
AUTH = {"Authorization": "Bearer secret"}


@pytest.fixture
def settings(park_settings: Settings) -> Settings:
    return park_settings.model_copy(update={"device_token": "secret"})


def tap(client: TestClient, card: str = CARD_A, station_id: str = "station-1", headers=AUTH):
    return client.post(
        "/api/checkins/card", json={"station_id": station_id, "card_hash": card}, headers=headers
    )


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer wrong"}, {"Authorization": "Bearer "}],
)
def test_missing_or_wrong_token_is_rejected(client, headers) -> None:
    response = tap(client, headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_card_checkins_are_off_without_a_device_token(park_settings) -> None:
    with TestClient(create_app(park_settings)) as client:
        assert tap(client).status_code == 401
        # Even an empty bearer token must not match the empty setting.
        assert tap(client, headers={"Authorization": "Bearer "}).status_code == 401


def test_first_tap_creates_a_card_visitor_and_stamps(client, session: Session) -> None:
    response = tap(client)

    assert response.status_code == 200
    assert response.json() == {
        "status": "stamped",
        "station": "Duck pond",
        "stamps_this_month": 1,
        "goal": 6,
        "reward": None,
    }
    visitor = session.exec(select(Visitor)).one()
    assert visitor.card_hash == CARD_A


def test_same_card_same_station_same_day_is_already_stamped(client) -> None:
    tap(client)
    response = tap(client)

    assert response.json()["status"] == "already_stamped"
    assert response.json()["stamps_this_month"] == 1


def test_same_card_at_other_station_adds_a_stamp(client, session: Session) -> None:
    tap(client, station_id="station-1")
    response = tap(client, station_id="station-2")

    assert response.json()["status"] == "stamped"
    assert response.json()["stamps_this_month"] == 2
    assert len(session.exec(select(Visitor)).all()) == 1


def test_other_card_is_another_visitor(client, session: Session) -> None:
    tap(client, CARD_A)
    response = tap(client, CARD_B)

    assert response.json()["stamps_this_month"] == 1
    hashes = {v.card_hash for v in session.exec(select(Visitor)).all()}
    assert hashes == {CARD_A, CARD_B}


@pytest.mark.parametrize("card", ["", "a" * 15, "a" * 65, "A" * 32, "g" * 32, "de:ad:be:ef"])
def test_invalid_card_hash_is_rejected(client, card) -> None:
    assert tap(client, card).status_code == 422


def test_unknown_station_is_rejected(client) -> None:
    response = tap(client, station_id="station-99")

    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown station"}


def test_card_and_phone_visitors_are_separate(client) -> None:
    tap(client)
    response = client.post("/api/checkins", json={"station_id": "station-1"})

    assert response.json()["status"] == "stamped"
    assert response.json()["stamps_this_month"] == 1


def test_unknown_station_does_not_create_a_visitor(settings):
    from sqlmodel import Session, select

    from app.main import create_app
    from app.models import Visitor

    app = create_app(settings.model_copy(update={"device_token": "secret"}))
    with TestClient(app) as client:
        response = client.post(
            "/api/checkins/card",
            json={"station_id": "station-99", "card_hash": "ab" * 16},
            headers={"Authorization": "Bearer secret"},
        )
        assert response.status_code == 404
        with Session(app.state.engine) as session:
            assert session.exec(select(Visitor)).all() == []


def test_token_without_bearer_scheme_is_rejected(settings):
    from app.main import create_app

    app = create_app(settings.model_copy(update={"device_token": "secret"}))
    with TestClient(app) as client:
        response = client.post(
            "/api/checkins/card",
            json={"station_id": "station-1", "card_hash": "ab" * 16},
            headers={"Authorization": "secret"},
        )
    assert response.status_code == 401
