"""Visitor pages: check-in page opened by an NFC tag (#18) and privacy notice (#34)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from app.db import get_session
from app.models import Station
from app.templating import templates

router = APIRouter(tags=["pages"])


@router.get("/c/{station_id}", response_class=HTMLResponse, summary="Check-in page")
def checkin_page(
    station_id: str, request: Request, session: Annotated[Session, Depends(get_session)]
) -> HTMLResponse:
    """Opened by the NFC tag of a checkpoint. The page sends `POST /api/checkins` itself."""
    station = session.get(Station, station_id)
    if station is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown station")
    goal = request.app.state.settings.reward_stamps
    return templates.TemplateResponse(request, "checkin.html", {"station": station, "goal": goal})


@router.get("/privacy", response_class=HTMLResponse, summary="Privacy notice")
def privacy_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "privacy.html")
