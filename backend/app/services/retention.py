"""Data retention (#34): check-ins and vouchers are kept for 12 months, then deleted."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlmodel import Session

from app.models import CheckIn, Voucher
from app.services.rules import local_date

log = logging.getLogger(__name__)

RETENTION_DAYS = 365


def purge_old_data(session: Session, now: datetime, days: int = RETENTION_DAYS) -> int:
    """Delete check-ins and vouchers older than `days`. Returns the number of deleted rows."""
    cutoff = local_date(now) - timedelta(days=days)
    checkins = session.exec(delete(CheckIn).where(CheckIn.local_date < cutoff))
    vouchers = session.exec(delete(Voucher).where(Voucher.month < f"{cutoff:%Y-%m}"))
    session.commit()
    deleted = checkins.rowcount + vouchers.rowcount
    if deleted:
        log.info("retention: deleted %d rows older than %s", deleted, cutoff)
    return deleted
