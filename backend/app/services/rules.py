"""Stamp rules. Time is always passed in, so tests can control it."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app.models import CheckIn

LOCAL_TZ = ZoneInfo("Europe/Madrid")

CheckInStatus = Literal["stamped", "already_stamped"]


@dataclass(frozen=True)
class CheckInResult:
    status: CheckInStatus
    stamps_this_month: int


def local_date(ts_utc: datetime) -> date:
    """Calendar day in Bilbao for a UTC timestamp."""
    return ts_utc.astimezone(LOCAL_TZ).date()


def month_range(day: date) -> tuple[date, date]:
    """First day of the month and first day of the next month."""
    start = day.replace(day=1)
    end = (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )
    return start, end


def count_stamps_in_month(session: Session, visitor_id: UUID, day: date) -> int:
    start, end = month_range(day)
    query = (
        select(func.count())
        .select_from(CheckIn)
        .where(
            CheckIn.visitor_id == visitor_id,
            CheckIn.qualifying,
            CheckIn.local_date >= start,
            CheckIn.local_date < end,
        )
    )
    return session.exec(query).one()


def has_stamp_today(session: Session, visitor_id: UUID, station_id: str, day: date) -> bool:
    query = select(CheckIn.id).where(
        CheckIn.visitor_id == visitor_id,
        CheckIn.station_id == station_id,
        CheckIn.local_date == day,
        CheckIn.qualifying,
    )
    return session.exec(query).first() is not None


def _store(
    session: Session, visitor_id: UUID, station_id: str, now: datetime, day: date, qualifying: bool
) -> None:
    session.add(
        CheckIn(
            visitor_id=visitor_id,
            station_id=station_id,
            ts_utc=now,
            local_date=day,
            qualifying=qualifying,
        )
    )
    session.commit()


def record_checkin(
    session: Session, visitor_id: UUID, station_id: str, now: datetime
) -> CheckInResult:
    """Store a check-in and return the visitor's stamp count for the current month.

    Only the first check-in per visitor, station and day (Europe/Madrid) is a stamp.
    Repeated taps are still stored, as non-qualifying, so the dashboard sees every tap.
    """
    day = local_date(now)
    qualifying = not has_stamp_today(session, visitor_id, station_id, day)

    if qualifying:
        try:
            _store(session, visitor_id, station_id, now, day, qualifying=True)
        except IntegrityError:
            # A simultaneous request stamped this station first (unique index).
            session.rollback()
            qualifying = False

    if not qualifying:
        _store(session, visitor_id, station_id, now, day, qualifying=False)

    status: CheckInStatus = "stamped" if qualifying else "already_stamped"
    return CheckInResult(status, count_stamps_in_month(session, visitor_id, day))


def stations_in_month(session: Session, visitor_id: UUID, day: date) -> list[str]:
    """Stations with at least one stamp of the visitor in the month of `day`, sorted."""
    start, end = month_range(day)
    query = (
        select(CheckIn.station_id)
        .where(
            CheckIn.visitor_id == visitor_id,
            CheckIn.qualifying,
            CheckIn.local_date >= start,
            CheckIn.local_date < end,
        )
        .distinct()
    )
    return sorted(session.exec(query).all())
