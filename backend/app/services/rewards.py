"""Monthly reward rule (#20): enough stamps at enough stations unlock one mock voucher."""

import secrets
import string
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import Voucher
from app.services.rules import count_stamps_in_month, local_date, stations_in_month

CODE_ALPHABET = string.ascii_uppercase + string.digits
CODE_LENGTH = 8

RewardStatus = Literal["locked", "unlocked"]


@dataclass(frozen=True)
class Progress:
    month: str
    stamps: int
    goal: int
    stations_visited: list[str]
    stations_missing: list[str]
    reward_status: RewardStatus
    voucher_code: str | None


def month_key(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def new_code() -> str:
    return "NC-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def goal_reached(stamps: int, stations: int, goal: int, min_stations: int) -> bool:
    return stamps >= goal and stations >= min_stations


def find_voucher(session: Session, visitor_id: UUID, month: str) -> Voucher | None:
    query = select(Voucher).where(Voucher.visitor_id == visitor_id, Voucher.month == month)
    return session.exec(query).first()


def issue_voucher_if_earned(
    session: Session, visitor_id: UUID, now: datetime, goal: int, min_stations: int
) -> Voucher | None:
    """Return this month's voucher, issuing it once when the goal is reached."""
    day = local_date(now)
    month = month_key(day)
    voucher = find_voucher(session, visitor_id, month)
    if voucher is not None:
        return voucher
    stamps = count_stamps_in_month(session, visitor_id, day)
    stations = stations_in_month(session, visitor_id, day)
    if not goal_reached(stamps, len(stations), goal, min_stations):
        return None
    voucher = Voucher(visitor_id=visitor_id, month=month, code=new_code(), issued_at=now)
    session.add(voucher)
    try:
        session.commit()
    except IntegrityError:
        # A simultaneous check-in issued it first (unique index per visitor and month).
        session.rollback()
        return find_voucher(session, visitor_id, month)
    session.refresh(voucher)
    return voucher


def monthly_progress(
    session: Session,
    visitor_id: UUID,
    now: datetime,
    all_stations: list[str],
    goal: int,
    min_stations: int,
) -> Progress:
    day = local_date(now)
    visited = stations_in_month(session, visitor_id, day)
    voucher = find_voucher(session, visitor_id, month_key(day))
    return Progress(
        month=month_key(day),
        stamps=count_stamps_in_month(session, visitor_id, day),
        goal=goal,
        stations_visited=visited,
        stations_missing=[s for s in all_stations if s not in visited],
        reward_status="unlocked" if voucher else "locked",
        voucher_code=voucher.code if voucher else None,
    )
