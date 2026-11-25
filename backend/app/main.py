"""FastAPI application: REST API, OpenAPI docs and visitor web pages."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from influxdb_client import InfluxDBClient

from app import __version__, db
from app.config import Settings, get_settings
from app.routers import checkins, progress, reports, stations
from app.schemas import HealthResponse
from app.services.ratelimit import SlidingWindowRateLimiter
from app.services.stations import seed_stations

STATIC_DIR = Path(__file__).resolve().parent / "static"

DESCRIPTION = """
Backend of **NatureCheckpoint**: IoT checkpoints in Bilbao's green spaces.

- Visitors collect stamps by tapping their phone at a checkpoint.
- Checkpoints report environmental conditions.

Visitors are identified only by a random pseudonymous ID in the `nc_visitor` cookie.
Sensor readings arrive via MQTT, not via this API.
"""


def create_influx_client(settings: Settings) -> InfluxDBClient | None:
    if not settings.influxdb_token:
        return None
    # Short timeout: a slow database must not block the visitor pages.
    return InfluxDBClient(
        url=settings.influxdb_url,
        token=settings.influxdb_token,
        org=settings.influxdb_org,
        timeout=3_000,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = db.create_db_engine(settings.database_path)
        db.create_db_and_tables(engine)
        seed_stations(engine, settings.stations_file)
        app.state.engine = engine
        app.state.influx = create_influx_client(settings)
        yield
        if app.state.influx is not None:
            app.state.influx.close()
        engine.dispose()

    app = FastAPI(
        title="NatureCheckpoint API",
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.checkin_limiter = SlidingWindowRateLimiter(
        settings.checkin_rate_limit, settings.checkin_rate_window_s
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    for router in (stations.router, checkins.router, progress.router, reports.router):
        app.include_router(router)

    @app.get("/health", tags=["system"], summary="Service status")
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    return app


app = create_app()
