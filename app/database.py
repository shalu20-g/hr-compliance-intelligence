"""Users database: engine, sessions and initialisation.

PostgreSQL is the production user database (``DATABASE_URL`` like
``postgresql://user:pass@host:5432/db``). A local SQLite file is used when
``DATABASE_URL`` points at sqlite (dev/test default). The same SQLAlchemy
models work on both backends.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _connect_args(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        # Needed for the FastAPI dev server's threaded workers.
        return {"check_same_thread": False}
    return {}


def _driver_url(database_url: str) -> str:
    # SQLAlchemy needs an explicit psycopg driver for ``postgresql://`` URLs.
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


@lru_cache(maxsize=8)
def _cached_engine(database_url: str):
    return create_engine(_driver_url(database_url), connect_args=_connect_args(database_url))


def get_engine(settings: Settings | None = None):
    """Return a cached engine for the configured ``DATABASE_URL``."""
    settings = settings or get_settings()
    return _cached_engine(settings.database_url)


def get_session_factory(settings: Settings | None = None) -> sessionmaker:
    return sessionmaker(bind=get_engine(settings), expire_on_commit=False)


def get_session(settings: Settings | None = None) -> Iterator[Session]:
    """Yield a request-scoped database session (closes afterwards)."""
    factory = get_session_factory(settings)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def init_db(settings: Settings | None = None) -> None:
    """Create all tables (users, ...). Safe to run repeatedly."""
    from app.models import user as _user_models  # noqa: F401 — register models

    settings = settings or get_settings()
    Base.metadata.create_all(bind=get_engine(settings))
    logger.info("Database initialised (url=%s).", _safe_url(settings.database_url))


def _safe_url(url: str) -> str:
    """Strip any password before logging a database URL."""
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            _, hostpart = rest.rsplit("@", 1)
            return f"{scheme}://***@{hostpart}"
    return url


__all__ = ["Base", "get_engine", "get_session_factory", "get_session", "init_db"]
