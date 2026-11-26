"""Database tables (SQLite via SQLModel)."""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Index, text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class Visitor(SQLModel, table=True):
    """Pseudonymous visitor. Deliberately stores nothing but a random ID and its creation time."""

    visitor_id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)
    # Visitors who tap a card at a checkpoint reader: salted hash of the card UID, made on the
    # Pi. The raw UID never reaches the backend. Null for phone (cookie) visitors.
    card_hash: str | None = Field(default=None, unique=True, index=True)


class Station(SQLModel, table=True):
    """A checkpoint. Seeded from deploy/stations.json at startup."""

    station_id: str = Field(primary_key=True)
    name: str
    lat: float
    lon: float
    description: str = ""


class CheckIn(SQLModel, table=True):
    """One tap at a checkpoint. Only qualifying check-ins count as stamps."""

    __table_args__ = (
        # One stamp per visitor, station and day, enforced by the database so that two
        # simultaneous taps cannot both count.
        Index(
            "uq_checkin_one_stamp_per_day",
            "visitor_id",
            "station_id",
            "local_date",
            unique=True,
            sqlite_where=text("qualifying = 1"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    visitor_id: UUID = Field(foreign_key="visitor.visitor_id", index=True)
    station_id: str = Field(foreign_key="station.station_id")
    ts_utc: datetime = Field(default_factory=utc_now)
    # Calendar day in Europe/Madrid. Stored so the daily rule is a simple column comparison.
    local_date: date = Field(index=True)
    qualifying: bool


class Voucher(SQLModel, table=True):
    """Mock reward: one single-use code per visitor and calendar month."""

    __table_args__ = (Index("uq_voucher_per_month", "visitor_id", "month", unique=True),)

    id: int | None = Field(default=None, primary_key=True)
    visitor_id: UUID = Field(foreign_key="visitor.visitor_id", index=True)
    # Calendar month in Europe/Madrid, e.g. "2026-11".
    month: str
    code: str = Field(unique=True)
    issued_at: datetime = Field(default_factory=utc_now)
