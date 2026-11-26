from datetime import UTC, date, datetime

from sqlmodel import Session, SQLModel, create_engine, select

from app.models import CheckIn, Station, Visitor, Voucher
from app.services.retention import purge_old_data

NOW = datetime(2026, 11, 26, 12, tzinfo=UTC)


def make_session() -> Session:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_old_checkins_and_vouchers_are_deleted_recent_ones_kept():
    session = make_session()
    visitor = Visitor()
    session.add_all([visitor, Station(station_id="s1", name="S1", lat=0, lon=0)])
    session.commit()
    for day in (date(2025, 11, 1), date(2025, 11, 30), date(2026, 11, 1)):
        session.add(
            CheckIn(visitor_id=visitor.visitor_id, station_id="s1", local_date=day, qualifying=True)
        )
    session.add_all(
        [
            Voucher(visitor_id=visitor.visitor_id, month="2025-10", code="NC-OLD00000"),
            Voucher(visitor_id=visitor.visitor_id, month="2026-11", code="NC-NEW00000"),
        ]
    )
    session.commit()

    deleted = purge_old_data(session, NOW)

    # Cutoff is 2025-11-26: one check-in and the October 2025 voucher are older.
    assert deleted == 2
    assert [c.local_date for c in session.exec(select(CheckIn))] == [
        date(2025, 11, 30),
        date(2026, 11, 1),
    ]
    assert [v.code for v in session.exec(select(Voucher))] == ["NC-NEW00000"]


def test_nothing_to_delete_returns_zero():
    assert purge_old_data(make_session(), NOW) == 0
