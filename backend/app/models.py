"""Database tables (SQLite via SQLModel)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class Visitor(SQLModel, table=True):
    """Pseudonymous visitor. Deliberately stores nothing but a random ID and its creation time."""

    visitor_id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)
