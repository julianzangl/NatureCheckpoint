"""Request and response models of the REST API (see the contracts in docs/architecture.md)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]


class StationSeed(BaseModel):
    """One entry of deploy/stations.json."""

    station_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    name: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    description: str = ""


class LatestReading(BaseModel):
    """Newest message of a station. A value is null if that sensor failed."""

    temperature: float | None = Field(description="°C")
    humidity: float | None = Field(description="%")
    light: float | None = Field(description="Raw light sensor value (relative)")
    condition: Literal["good", "fair", "poor", "fault"] | None = Field(
        description="Walk-condition rating of the checkpoint"
    )
    timestamp: datetime = Field(description="Time of the message (UTC)")


class StationResponse(BaseModel):
    station_id: str = Field(examples=["station-1"])
    name: str = Field(examples=["Duck pond"])
    lat: float = Field(examples=[43.2657])
    lon: float = Field(examples=[-2.9405])
    description: str
    latest: LatestReading | None = Field(description="null if the station has sent no data yet")


class CheckInRequest(BaseModel):
    """The visitor comes from the `nc_visitor` cookie, not from the body."""

    station_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$", examples=["station-1"])
    tag_payload: str | None = Field(
        default=None, max_length=512, description="Raw NFC payload, if the client has one"
    )


class CheckInResponse(BaseModel):
    status: Literal["stamped", "already_stamped"] = Field(
        description="`already_stamped`: this station was already stamped today, no new stamp"
    )
    station: str = Field(description="Name of the station", examples=["Duck pond"])
    stamps_this_month: int = Field(ge=0, examples=[4])
    goal: int = Field(description="Stamps needed for this month's reward", examples=[6])
