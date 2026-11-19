"""FastAPI application: REST API, OpenAPI docs and visitor web pages."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__, db
from app.config import Settings, get_settings
from app.routers import checkins, progress, reports, stations
from app.schemas import HealthResponse

STATIC_DIR = Path(__file__).resolve().parent / "static"

DESCRIPTION = """
Backend of **NatureCheckpoint**: IoT checkpoints in Bilbao's green spaces.

- Visitors collect stamps by tapping their phone at a checkpoint.
- Checkpoints report environmental conditions.

Visitors are identified only by a random pseudonymous ID in the `nc_visitor` cookie.
Sensor readings arrive via MQTT, not via this API.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = db.create_db_engine(settings.database_path)
        db.create_db_and_tables(engine)
        app.state.engine = engine
        yield
        engine.dispose()

    app = FastAPI(
        title="NatureCheckpoint API",
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    for router in (stations.router, checkins.router, progress.router, reports.router):
        app.include_router(router)

    @app.get("/health", tags=["system"], summary="Service status")
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    return app


app = create_app()
