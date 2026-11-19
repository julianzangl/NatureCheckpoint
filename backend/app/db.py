"""SQLite database setup and the per-request session dependency."""

from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine


def create_db_engine(database_path: Path) -> Engine:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    # FastAPI runs sync endpoints in a thread pool, so the connection must be usable across threads.
    return create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})


def create_db_and_tables(engine: Engine) -> None:
    from app import models  # noqa: F401  (importing registers the tables on SQLModel.metadata)

    SQLModel.metadata.create_all(engine)


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session
