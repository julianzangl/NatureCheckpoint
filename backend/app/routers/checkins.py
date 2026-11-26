"""Stamp collection: by phone (cookie) or by card at a checkpoint reader."""

import hmac
import logging
import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from influxdb_client import Point
from influxdb_client.client.write_api import SYNCHRONOUS
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db import get_session
from app.models import Station, Visitor, utc_now
from app.schemas import CardCheckInRequest, CheckInRequest, CheckInResponse, RewardInfo
from app.services.rewards import issue_voucher_if_earned
from app.services.rules import record_checkin
from app.visitors import CurrentVisitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["checkins"])

ERRORS = {
    404: {"description": "Unknown station"},
    429: {"description": "Too many check-in requests from this visitor"},
}


def _stamp(request: Request, session: Session, visitor_id: UUID, station_id: str):
    limiter = request.app.state.checkin_limiter
    if not limiter.allow(str(visitor_id), time.monotonic()):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many check-ins, try again in a minute"
        )
    station = session.get(Station, station_id)
    if station is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown station")

    settings = request.app.state.settings
    now = utc_now()
    result = record_checkin(session, visitor_id, station.station_id, now=now)
    voucher = issue_voucher_if_earned(
        session, visitor_id, now, settings.reward_stamps, settings.reward_min_stations
    )
    _log_event(request, station.station_id, result.status == "stamped")
    return CheckInResponse(
        status=result.status,
        station=station.name,
        stamps_this_month=result.stamps_this_month,
        goal=settings.reward_stamps,
        reward=RewardInfo(code=voucher.code, month=voucher.month) if voucher else None,
    )


def _log_event(request: Request, station_id: str, qualifying: bool) -> None:
    """Count the tap in InfluxDB for the operator dashboard. No visitor ID is written."""
    influx = request.app.state.influx
    if influx is None:
        return
    settings = request.app.state.settings
    point = (
        Point("checkins")
        .tag("station_id", station_id)
        .field("taps", 1)
        .field("stamps", 1 if qualifying else 0)
    )
    try:
        influx.write_api(write_options=SYNCHRONOUS).write(settings.influxdb_bucket, record=point)
    except Exception as exc:  # the stamp is stored; statistics must not fail the visitor
        logger.warning("could not write check-in event to InfluxDB: %s", exc)


@router.post("/checkins", summary="Collect a stamp with the phone", responses=ERRORS)
def create_checkin(
    body: CheckInRequest,
    visitor: CurrentVisitor,
    session: Annotated[Session, Depends(get_session)],
    request: Request,
) -> CheckInResponse:
    """Called by the check-in page `/c/<station_id>`.

    The visitor is identified by the `nc_visitor` cookie. A first-time visitor gets one here.
    Only the first check-in per station and day counts as a stamp; repeated taps return
    `already_stamped`. `reward` is set once the monthly goal is reached.
    """
    return _stamp(request, session, visitor.visitor_id, body.station_id)


def _require_device(request: Request, authorization: str | None) -> None:
    expected = request.app.state.settings.device_token
    scheme, _, given = (authorization or "").partition(" ")
    valid = scheme == "Bearer" and hmac.compare_digest(given.strip().encode(), expected.encode())
    if not expected or not valid:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/checkins/card",
    summary="Collect a stamp with a card (checkpoint reader)",
    responses={401: {"description": "Missing or wrong device token"}, **ERRORS},
)
def create_card_checkin(
    body: CardCheckInRequest,
    session: Annotated[Session, Depends(get_session)],
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> CheckInResponse:
    """Called by a checkpoint Pi when a card is tapped on its NFC reader.

    The Pi authenticates with `Authorization: Bearer <DEVICE_TOKEN>`. The card stands for the
    visitor: the first tap of an unknown card creates a pseudonymous visitor. Same stamp and
    reward rules as the phone check-in.
    """
    _require_device(request, authorization)
    # Check the station first, so an unknown station never creates a visitor.
    if session.get(Station, body.station_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown station")
    visitor = _visitor_for_card(session, body.card_hash)
    return _stamp(request, session, visitor.visitor_id, body.station_id)


def _visitor_for_card(session: Session, card_hash: str) -> Visitor:
    query = select(Visitor).where(Visitor.card_hash == card_hash)
    visitor = session.exec(query).first()
    if visitor is not None:
        return visitor
    visitor = Visitor(card_hash=card_hash)
    session.add(visitor)
    try:
        session.commit()
    except IntegrityError:
        # Two taps of a new card at the same time: the other request created it first.
        session.rollback()
        return session.exec(query).one()
    session.refresh(visitor)
    return visitor
