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
    _add_missing_columns(_engine)
    _factory = sessionmaker(_engine, expire_on_commit=False)
    return _engine


def _add_missing_columns(engine: sa.Engine) -> None:
    """create_all makes new tables but never alters old ones; there are no migrations yet, so add new nullable
    columns to tables that already exist (a database created before the column was introduced)."""
    inspector = sa.inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        have = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name not in have and col.nullable and not col.primary_key:
                ddl = f'ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(engine.dialect)}'
                with engine.begin() as conn:
                    conn.execute(sa.text(ddl))


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
