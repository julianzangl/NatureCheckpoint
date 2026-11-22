"""Checkpoint metadata and latest conditions."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from app.db import get_session
from app.schemas import StationResponse
from app.services import influx
from app.services.stations import list_stations

router = APIRouter(prefix="/api", tags=["stations"])


def get_latest_readings(request: Request) -> dict[str, dict[str, Any]]:
    """Dependency, so tests can replace InfluxDB with fixed data."""
    return influx.latest_readings(
        request.app.state.influx, request.app.state.settings.influxdb_bucket
    )


@router.get("/stations", summary="Checkpoints with location and current conditions")
def get_stations(
    session: Annotated[Session, Depends(get_session)],
    latest: Annotated[dict[str, dict[str, Any]], Depends(get_latest_readings)],
) -> list[StationResponse]:
    """All checkpoints with their coordinates and the newest reading.

    `latest` is null for a station that has not sent any data in the last 30 days, or when
    the time-series database is not reachable.
    """
    return [
        StationResponse(**station.model_dump(), latest=latest.get(station.station_id))
        for station in list_stations(session)
    ]
