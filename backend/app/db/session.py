from __future__ import annotations

from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Base

_engine: sa.Engine | None = None
_factory: sessionmaker[Session] | None = None


def init_db(url: str | None = None) -> sa.Engine:
    """Create the engine and tables. Tests pass sqlite://; runtime uses DATABASE_URL (PostgreSQL)."""
    global _engine, _factory
    url = url or settings.database_url
    kw: dict = {}
    if url.startswith("sqlite"):
        in_memory = url in ("sqlite://", "sqlite:///:memory:")
        kw["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if in_memory:
            kw["poolclass"] = sa.pool.StaticPool   # the database lives in the connection, so everyone must share it
    _engine = sa.create_engine(url, **kw)
    Base.metadata.create_all(_engine)
    _factory = sessionmaker(_engine, expire_on_commit=False)
    return _engine


def is_initialized() -> bool:
    return _factory is not None


@contextmanager
def session_scope():
    """For background work outside a request."""
    if _factory is None:
        init_db()
    with _factory() as s:
        yield s


def get_session():
    """FastAPI dependency."""
    if _factory is None:
        init_db()
    with _factory() as s:
        yield s
