"""Stamp rules. Time is always passed in, so tests can control it."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

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


def record_checkin(
    session: Session, visitor_id: UUID, station_id: str, now: datetime
) -> CheckInResult:
    """Store a check-in and return the visitor's stamp count for the current month."""
    day = local_date(now)
    session.add(
        CheckIn(
            visitor_id=visitor_id,
            station_id=station_id,
            ts_utc=now,
            local_date=day,
            qualifying=True,
        )
    )
    session.commit()
    return CheckInResult("stamped", count_stamps_in_month(session, visitor_id, day))
