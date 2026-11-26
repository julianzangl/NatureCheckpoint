"""Visitor page with a map of all checkpoints (#23)."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.templating import templates

router = APIRouter(tags=["pages"])


@router.get("/map", response_class=HTMLResponse, summary="Map of the checkpoints")
def map_page(request: Request) -> HTMLResponse:
    """Leaflet map. The page loads the stations itself from `GET /api/stations`."""
    return templates.TemplateResponse(request, "map.html")
