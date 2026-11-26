"""Monthly progress of a visitor (#19)."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import Station, utc_now
from app.schemas import ProgressResponse
from app.services.rewards import Progress, monthly_progress
from app.templating import templates
from app.visitors import CurrentVisitor

router = APIRouter(tags=["progress"])


def _progress(request: Request, session: Session, visitor: CurrentVisitor) -> Progress:
    settings = request.app.state.settings
    stations = list(session.exec(select(Station.station_id).order_by(Station.station_id)).all())
    return monthly_progress(
        session,
        visitor.visitor_id,
        utc_now(),
        stations,
        settings.reward_stamps,
        settings.reward_min_stations,
    )


@router.get("/api/progress", summary="Stamps and reward status this month")
def get_progress(
    request: Request, visitor: CurrentVisitor, session: Annotated[Session, Depends(get_session)]
) -> ProgressResponse:
    """Progress of the visitor in the `nc_visitor` cookie. Resets on the 1st of each month."""
    return ProgressResponse(**asdict(_progress(request, session, visitor)))


@router.get("/progress", response_class=HTMLResponse, tags=["pages"], summary="Progress page")
def progress_page(
    request: Request, visitor: CurrentVisitor, session: Annotated[Session, Depends(get_session)]
) -> HTMLResponse:
    progress = _progress(request, session, visitor)
    names = dict(session.exec(select(Station.station_id, Station.name)).all())
    return templates.TemplateResponse(
        request, "progress.html", {"progress": progress, "names": names}
    )
