"""Stamp collection."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session

from app.db import get_session
from app.models import Station, utc_now
from app.schemas import CheckInRequest, CheckInResponse
from app.services.rules import record_checkin
from app.visitors import CurrentVisitor

router = APIRouter(prefix="/api", tags=["checkins"])


@router.post(
    "/checkins",
    summary="Collect a stamp",
    responses={404: {"description": "Unknown station"}},
)
def create_checkin(
    body: CheckInRequest,
    visitor: CurrentVisitor,
    session: Annotated[Session, Depends(get_session)],
    request: Request,
) -> CheckInResponse:
    """Called by the check-in page that the checkpoint's NFC tag opens.

    The visitor is identified by the `nc_visitor` cookie. A first-time visitor gets one here.
    """
    station = session.get(Station, body.station_id)
    if station is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown station")

    result = record_checkin(session, visitor.visitor_id, station.station_id, now=utc_now())
    return CheckInResponse(
        status=result.status,
        station=station.name,
        stamps_this_month=result.stamps_this_month,
        goal=request.app.state.settings.reward_stamps,
    )
