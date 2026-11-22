"""Station registry: seed data from deploy/stations.json, kept in SQLite."""

import json
import logging
from pathlib import Path

from pydantic import TypeAdapter
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.models import Station
from app.schemas import StationSeed

log = logging.getLogger(__name__)

_SEEDS = TypeAdapter(list[StationSeed])


def load_seed(path: Path) -> list[StationSeed]:
    """Read and validate the seed file. Duplicate IDs are an error, not a silent overwrite."""
    seeds = _SEEDS.validate_python(json.loads(path.read_text(encoding="utf-8")))
    ids = [seed.station_id for seed in seeds]
    duplicates = sorted({sid for sid in ids if ids.count(sid) > 1})
    if duplicates:
        raise ValueError(f"duplicate station_id in {path}: {duplicates}")
    return seeds


def upsert_stations(engine: Engine, seeds: list[StationSeed]) -> None:
    """Insert new stations and update existing ones. Stations not in the file are kept,
    because check-ins may refer to them."""
    with Session(engine) as session:
        for seed in seeds:
            station = session.get(Station, seed.station_id)
            if station is None:
                session.add(Station(**seed.model_dump()))
            else:
                station.sqlmodel_update(seed.model_dump())
                session.add(station)
        session.commit()


def seed_stations(engine: Engine, path: Path) -> None:
    if not path.exists():
        log.warning("station seed file %s not found, keeping stations as they are", path)
        return
    seeds = load_seed(path)
    upsert_stations(engine, seeds)
    log.info("seeded %d stations from %s", len(seeds), path)


def list_stations(session: Session) -> list[Station]:
    return list(session.exec(select(Station).order_by(Station.station_id)))
