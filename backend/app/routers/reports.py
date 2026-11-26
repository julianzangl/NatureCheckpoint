"""Daily environmental reports (#25)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlmodel import Session

from app.db import get_session
from app.models import Station, utc_now
from app.schemas import DailyReport
from app.services.reports import daily_report
from app.services.rules import local_date

router = APIRouter(prefix="/api", tags=["reports"])


@router.get(
    "/reports/daily",
    summary="Daily statistics of one checkpoint",
    responses={
        404: {"description": "Unknown station"},
        503: {"description": "Time-series database not reachable"},
    },
)
def get_daily_report(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    station_id: Annotated[str, Query(pattern=r"^[A-Za-z0-9_-]{1,64}$")],
    day: Annotated[date | None, Query(alias="date", description="Default: today")] = None,
) -> DailyReport:
    """Average, median, minimum, maximum and trend of each sensor for a day (Europe/Madrid)."""
    if session.get(Station, station_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown station")
    settings = request.app.state.settings
    report = daily_report(
        request.app.state.influx,
        settings.influxdb_bucket,
        station_id,
        day or local_date(utc_now()),
    )
    if report is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Time-series database not reachable"
        )
    return DailyReport(**report)
