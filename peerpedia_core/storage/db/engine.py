# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Database engine, session factory, and utility types.

Provides:
- JSONList / JSONDict type decorators for SQLite
- Engine creation with WAL mode + foreign keys
- Session factory
- Declarative Base
"""

from __future__ import annotations

import json

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import Text, TypeDecorator

# ── JSON column types for list/dict fields ───────────────────────────────────


def _make_json_type():
    """Factory for JSON column TypeDecorators (avoids duplicate implementations)."""

    class _JSONType(TypeDecorator):
        impl = Text
        cache_ok = True

        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            return json.dumps(value, ensure_ascii=False)

        def process_result_value(self, value, dialect):
            if value is None:
                return None
            return json.loads(value)

    return _JSONType


JSONList = _make_json_type()
"""Store Python list as JSON string in SQLite."""

JSONDict = _make_json_type()
"""Store Python dict as JSON string in SQLite."""


# ── Base + Engine ────────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


_engine_cache: dict[str, Engine] = {}


def get_engine(database_url: str) -> Engine:
    """Return a cached SQLAlchemy engine, creating one on first call per URL.

    Caching avoids creating a new engine + connection pool on every request.
    SQLAlchemy Engine is thread-safe and designed to be a process singleton.
    """
    if database_url in _engine_cache:
        return _engine_cache[database_url]

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        echo=False,
    )
    if "sqlite" in database_url:
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    _engine_cache[database_url] = engine
    return engine


def init_db(engine: Engine) -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)


def migrate_db(engine: Engine) -> None:
    """Run schema migrations that can't be expressed via create_all (e.g. column additions)."""
    import sqlalchemy as sa

    with engine.connect() as conn:
        # Check if last_author_rebuild_hash column exists
        insp = sa.inspect(conn)
        columns = [c["name"] for c in insp.get_columns("articles")]
        if "last_author_rebuild_hash" not in columns:
            conn.execute(sa.text("ALTER TABLE articles ADD COLUMN last_author_rebuild_hash TEXT"))
            conn.commit()


_factory_cache: dict = {}


def get_session(engine: Engine) -> Session:
    """Create a new session bound to the given engine.

    sessionmaker is cached per engine so the factory class is not
    recreated on every call.
    """
    key = engine.url
    if key not in _factory_cache:
        _factory_cache[key] = sessionmaker(bind=engine, expire_on_commit=False)
    return _factory_cache[key]()
