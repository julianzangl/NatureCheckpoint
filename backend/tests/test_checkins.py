import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.config import Settings
from app.main import create_app
from app.models import CheckIn, Visitor
from app.services.rules import count_stamps_in_month, local_date, month_range, record_checkin
from app.visitors import VISITOR_COOKIE

STATIONS = [
    {"station_id": "station-1", "name": "Duck pond", "lat": 43.2657, "lon": -2.9405},
    {"station_id": "station-2", "name": "Park entrance", "lat": 43.266, "lon": -2.9389},
]


@pytest.fixture
def settings(tmp_path) -> Settings:
    stations_file = tmp_path / "stations.json"
    stations_file.write_text(json.dumps(STATIONS), encoding="utf-8")
    return Settings(
        database_path=tmp_path / "test.db",
        public_base_url="http://testserver",
        stations_file=stations_file,
        influxdb_token="",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
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


def checkin(client: TestClient, station_id: str = "station-1"):
    return client.post("/api/checkins", json={"station_id": station_id})


# --- endpoint ---------------------------------------------------------------------------------


def test_checkin_returns_stamp_count_and_goal(client):
    response = checkin(client)

    assert response.status_code == 200
    assert response.json() == {
        "status": "stamped",
        "station": "Duck pond",
        "stamps_this_month": 1,
        "goal": 6,
        "reward": None,
    }


def test_checkin_creates_visitor_cookie(client):
    response = checkin(client)

    assert VISITOR_COOKIE in response.cookies


def test_stamps_at_different_stations_add_up(client):
    checkin(client, "station-1")
    response = checkin(client, "station-2")

    assert response.json()["stamps_this_month"] == 2


def test_stamps_are_counted_per_visitor(client):
    checkin(client, "station-1")
    # Second client on the same app: own cookie jar, i.e. a different visitor.
    other_visitor = TestClient(client.app)
    response = checkin(other_visitor, "station-2")

    assert response.json()["stamps_this_month"] == 1


def test_checkin_is_stored(client, session):
    checkin(client, "station-2")

    stored = session.exec(select(CheckIn)).one()
    assert stored.station_id == "station-2"
    assert stored.qualifying is True
    assert stored.local_date == local_date(stored.ts_utc.replace(tzinfo=UTC))


def test_unknown_station_is_rejected(client, session):
    response = checkin(client, "station-99")

    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown station"}
    assert session.exec(select(CheckIn)).all() == []


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"station_id": ""},
        {"station_id": "station 1"},
        {"station_id": "x" * 65},
        {"station_id": "station-1", "tag_payload": "x" * 513},
    ],
)
def test_malformed_body_is_rejected(client, body):
    assert client.post("/api/checkins", json=body).status_code == 422


def test_goal_comes_from_settings(settings):
    with TestClient(create_app(settings.model_copy(update={"reward_stamps": 3}))) as client:
        assert checkin(client).json()["goal"] == 3


# --- rules ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ts_utc", "expected"),
    [
        # Winter time: Bilbao is UTC+1.
        (datetime(2026, 11, 25, 22, 59, tzinfo=UTC), date(2026, 11, 25)),
        (datetime(2026, 11, 25, 23, 1, tzinfo=UTC), date(2026, 11, 26)),
        (datetime(2026, 11, 30, 23, 30, tzinfo=UTC), date(2026, 12, 1)),
        # Summer time: Bilbao is UTC+2.
        (datetime(2026, 7, 1, 21, 59, tzinfo=UTC), date(2026, 7, 1)),
        (datetime(2026, 7, 1, 22, 1, tzinfo=UTC), date(2026, 7, 2)),
    ],
)
def test_local_date_uses_bilbao_time(ts_utc, expected):
    assert local_date(ts_utc) == expected


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 11, 25), (date(2026, 11, 1), date(2026, 12, 1))),
        (date(2026, 12, 31), (date(2026, 12, 1), date(2027, 1, 1))),
        (date(2027, 1, 1), (date(2027, 1, 1), date(2027, 2, 1))),
    ],
)
def test_month_range(day, expected):
    assert month_range(day) == expected


def test_stamps_from_last_month_do_not_count(session, visitor):
    record_checkin(session, visitor.visitor_id, "station-1", datetime(2026, 11, 30, 12, tzinfo=UTC))

    result = record_checkin(
        session, visitor.visitor_id, "station-2", datetime(2026, 12, 1, 12, tzinfo=UTC)
    )

    assert result.stamps_this_month == 1


def test_count_ignores_other_visitors(session, visitor):
    now = datetime(2026, 11, 25, 12, tzinfo=UTC)
    record_checkin(session, visitor.visitor_id, "station-1", now)

    assert count_stamps_in_month(session, uuid4(), now.date()) == 0


# --- one stamp per station and day ------------------------------------------------------------


def test_second_tap_same_station_same_day_is_not_a_stamp(client, session):
    checkin(client, "station-1")
    response = checkin(client, "station-1")

    assert response.status_code == 200
    assert response.json()["status"] == "already_stamped"
    assert response.json()["stamps_this_month"] == 1
    # Every tap is stored, but only one qualifies.
    stored = session.exec(select(CheckIn)).all()
    assert [c.qualifying for c in stored] == [True, False]


def test_same_station_next_day_counts_again(session, visitor):
    vid = visitor.visitor_id
    record_checkin(session, vid, "station-1", datetime(2026, 11, 25, 9, tzinfo=UTC))

    result = record_checkin(session, vid, "station-1", datetime(2026, 11, 26, 9, tzinfo=UTC))

    assert result.status == "stamped"
    assert result.stamps_this_month == 2


def test_day_boundary_is_midnight_in_bilbao(session, visitor):
    vid = visitor.visitor_id
    # 23:50 and 00:10 Bilbao time (UTC+1): two different days.
    record_checkin(session, vid, "station-1", datetime(2026, 11, 25, 22, 50, tzinfo=UTC))

    result = record_checkin(session, vid, "station-1", datetime(2026, 11, 25, 23, 10, tzinfo=UTC))

    assert result.status == "stamped"


def test_different_utc_days_but_same_bilbao_day_is_a_duplicate(session, visitor):
    vid = visitor.visitor_id
    # Nov 25 23:10 UTC and Nov 26 08:00 UTC are both Nov 26 in Bilbao (00:10 and 09:00).
    record_checkin(session, vid, "station-1", datetime(2026, 11, 25, 23, 10, tzinfo=UTC))

    result = record_checkin(session, vid, "station-1", datetime(2026, 11, 26, 8, tzinfo=UTC))

    assert result.status == "already_stamped"


def test_database_rejects_a_second_qualifying_stamp(session, visitor):
    day = date(2026, 11, 25)
    for _ in range(2):
        session.add(
            CheckIn(
                visitor_id=visitor.visitor_id,
                station_id="station-1",
                local_date=day,
                qualifying=True,
            )
        )
    with pytest.raises(IntegrityError):
        session.commit()


def test_simultaneous_taps_count_only_once(session, visitor, monkeypatch):
    now = datetime(2026, 11, 25, 12, tzinfo=UTC)
    record_checkin(session, visitor.visitor_id, "station-1", now)
    # Simulate the race: the second request checked before the first one was stored.
    monkeypatch.setattr("app.services.rules.has_stamp_today", lambda *args: False)

    result = record_checkin(session, visitor.visitor_id, "station-1", now)

    assert result.status == "already_stamped"
    assert result.stamps_this_month == 1


# --- rate limit -------------------------------------------------------------------------------


def test_too_many_checkins_are_rejected(settings):
    limited = settings.model_copy(update={"checkin_rate_limit": 3})
    with TestClient(create_app(limited)) as client:
        codes = [checkin(client).status_code for _ in range(4)]

    assert codes == [200, 200, 200, 429]


def test_rate_limit_is_per_visitor(settings):
    limited = settings.model_copy(update={"checkin_rate_limit": 1})
    with TestClient(create_app(limited)) as client:
        assert checkin(client).status_code == 200
        assert checkin(client).status_code == 429
        assert checkin(TestClient(client.app)).status_code == 200
