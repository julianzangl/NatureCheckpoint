import re
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import Settings
from app.main import create_app
from app.models import Voucher
from app.services.rewards import (
    CODE_LENGTH,
    goal_reached,
    issue_voucher_if_earned,
    month_key,
    monthly_progress,
    new_code,
)
from app.services.rules import record_checkin

CODE_RE = re.compile(r"^NC-[A-Z0-9]{8}$")
STATIONS = ["station-1", "station-2"]


@pytest.fixture
def settings(park_settings: Settings) -> Settings:
    return park_settings


def day(n: int, month: int = 11) -> datetime:
    return datetime(2026, month, n, 12, tzinfo=UTC)


def stamp(session: Session, visitor_id, station_id: str, now: datetime):
    record_checkin(session, visitor_id, station_id, now)
    return issue_voucher_if_earned(session, visitor_id, now, goal=3, min_stations=2)


# --- pure helpers -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stamps", "stations", "expected"),
    [(6, 2, True), (7, 3, True), (5, 2, False), (6, 1, False), (0, 0, False)],
)
def test_goal_reached(stamps: int, stations: int, expected: bool) -> None:
    assert goal_reached(stamps, stations, goal=6, min_stations=2) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(date(2026, 11, 25), "2026-11"), (date(2027, 1, 1), "2027-01"), (date(999, 3, 1), "0999-03")],
)
def test_month_key(value: date, expected: str) -> None:
    assert month_key(value) == expected


def test_new_code_format() -> None:
    codes = {new_code() for _ in range(50)}

    assert all(CODE_RE.match(code) for code in codes)
    assert CODE_LENGTH == 8
    # Random codes: 50 draws from 36^8 should not collide.
    assert len(codes) == 50


# --- issuing ------------------------------------------------------------------------------------


def test_voucher_after_goal_at_two_stations(session: Session, visitor) -> None:
    vid = visitor.visitor_id
    assert stamp(session, vid, "station-1", day(23)) is None
    assert stamp(session, vid, "station-1", day(24)) is None

    voucher = stamp(session, vid, "station-2", day(25))

    assert voucher is not None
    assert CODE_RE.match(voucher.code)
    assert voucher.month == "2026-11"


def test_no_voucher_for_stamps_at_one_station(session: Session, visitor) -> None:
    vid = visitor.visitor_id
    results = [stamp(session, vid, "station-1", day(n)) for n in (23, 24, 25)]

    assert results == [None, None, None]
    assert session.exec(select(Voucher)).all() == []


def test_voucher_is_issued_once_per_month(session: Session, visitor) -> None:
    vid = visitor.visitor_id
    for station, n in [("station-1", 23), ("station-1", 24), ("station-2", 25)]:
        first = stamp(session, vid, station, day(n))

    again = stamp(session, vid, "station-2", day(26))

    assert first is not None and again is not None
    assert again.code == first.code
    assert len(session.exec(select(Voucher)).all()) == 1


def test_new_month_needs_a_new_voucher(session: Session, visitor) -> None:
    vid = visitor.visitor_id
    for station, n in [("station-1", 23), ("station-1", 24), ("station-2", 25)]:
        november = stamp(session, vid, station, day(n))

    assert stamp(session, vid, "station-1", day(1, month=12)) is None
    stamp(session, vid, "station-1", day(2, month=12))
    december = stamp(session, vid, "station-2", day(3, month=12))

    assert november is not None and december is not None
    assert december.month == "2026-12"
    assert december.code != november.code


# --- progress -----------------------------------------------------------------------------------


def test_progress_before_the_goal(session: Session, visitor) -> None:
    record_checkin(session, visitor.visitor_id, "station-1", day(25))

    progress = monthly_progress(session, visitor.visitor_id, day(26), STATIONS, 3, 2)

    assert progress.month == "2026-11"
    assert progress.stamps == 1
    assert progress.goal == 3
    assert progress.stations_visited == ["station-1"]
    assert progress.stations_missing == ["station-2"]
    assert progress.reward_status == "locked"
    assert progress.voucher_code is None


def test_progress_after_the_goal(session: Session, visitor) -> None:
    vid = visitor.visitor_id
    for station, n in [("station-1", 23), ("station-1", 24), ("station-2", 25)]:
        voucher = stamp(session, vid, station, day(n))

    progress = monthly_progress(session, vid, day(26), STATIONS, 3, 2)

    assert progress.stations_missing == []
    assert progress.reward_status == "unlocked"
    assert voucher is not None and progress.voucher_code == voucher.code


def test_progress_resets_next_month(session: Session, visitor) -> None:
    record_checkin(session, visitor.visitor_id, "station-1", day(30))

    progress = monthly_progress(session, visitor.visitor_id, day(1, month=12), STATIONS, 3, 2)

    assert progress.month == "2026-12"
    assert progress.stamps == 0
    assert progress.stations_missing == STATIONS


# --- endpoints ----------------------------------------------------------------------------------


def test_reward_in_card_checkin_response(park_settings: Settings, monkeypatch) -> None:
    clock = {"now": day(24)}
    monkeypatch.setattr("app.routers.checkins.utc_now", lambda: clock["now"])
    settings = park_settings.model_copy(update={"device_token": "secret", "reward_stamps": 3})
    body = {"card_hash": "c" * 32}
    auth = {"Authorization": "Bearer secret"}

    with TestClient(create_app(settings)) as client:

        def tap(station_id: str) -> dict:
            json = {**body, "station_id": station_id}
            return client.post("/api/checkins/card", json=json, headers=auth).json()

        first = tap("station-1")
        second = tap("station-2")
        clock["now"] = day(25)
        third = tap("station-1")
        repeat = tap("station-1")

    assert first["reward"] is None and second["reward"] is None
    assert third["stamps_this_month"] == 3
    assert CODE_RE.match(third["reward"]["code"])
    assert third["reward"]["month"] == "2026-11"
    # The voucher stays in later responses, with the same code.
    assert repeat["status"] == "already_stamped"
    assert repeat["reward"] == third["reward"]
