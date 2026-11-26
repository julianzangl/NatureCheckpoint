"""Regional weather next to the checkpoint readings (#26)."""

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["weather"])


class WeatherResponse(BaseModel):
    temperature: float | None = Field(description="°C, 2 m above ground")
    humidity: float | None = Field(description="%")
    uv_index: float | None
    weather_code: int | None = Field(description="WMO weather code")
    description: str = Field(examples=["partly cloudy"])
    time: str | None = Field(description="Local time of the model value (Europe/Madrid)")
    source: str = Field(examples=["Open-Meteo"])


@router.get(
    "/weather",
    summary="Current regional weather at the park",
    responses={503: {"description": "Weather service not reachable"}},
)
def get_weather(request: Request) -> WeatherResponse:
    """Open-Meteo model data for the park, cached for 10 minutes. Context for the local
    readings: the checkpoints measure the microclimate on site, Open-Meteo the region."""
    weather = request.app.state.weather.current()
    if weather is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Weather not available")
    return WeatherResponse(**weather)
