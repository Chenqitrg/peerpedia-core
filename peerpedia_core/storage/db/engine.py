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
import logging

from sqlalchemy import Engine, create_engine, text
from sqlalchemy import exc as sa_exc
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


JSONType = _make_json_type()
"""Store Python list or dict as JSON string in SQLite."""

JSONList = JSONType   # alias for backward compat
JSONDict = JSONType   # alias for backward compat


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
    """Apply schema migrations — add columns that don't exist yet.

    SQLite has no ``IF NOT EXISTS`` for ``ALTER TABLE ADD COLUMN``, so
    we catch the duplicate-column error and ignore it.
    """
    _log = logging.getLogger(__name__)
    _migrations = [
        "ALTER TABLE articles ADD COLUMN publish_consents TEXT",
        "ALTER TABLE articles ADD COLUMN witnessed_at DATETIME",
        "ALTER TABLE follows ADD COLUMN deleted_at DATETIME",
        "ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN locked_until DATETIME",
        "ALTER TABLE users ADD COLUMN deleted_at DATETIME",
        "CREATE TABLE IF NOT EXISTS aliases ("
        "  owner_id TEXT NOT NULL REFERENCES users(id),"
        "  target_id TEXT NOT NULL REFERENCES users(id),"
        "  alias TEXT NOT NULL,"
        "  PRIMARY KEY (owner_id, target_id),"
        "  UNIQUE (owner_id, alias)"
        ")",
        "CREATE TABLE IF NOT EXISTS shares ("
        "  id TEXT PRIMARY KEY,"
        "  sharer_id TEXT NOT NULL REFERENCES users(id),"
        "  article_id TEXT NOT NULL REFERENCES articles(id),"
        "  recipient_id TEXT REFERENCES users(id),"
        "  comment TEXT,"
        "  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
        "  UNIQUE (sharer_id, article_id)"
        ")",
        "CREATE TABLE IF NOT EXISTS notifications ("
        "  id TEXT PRIMARY KEY,"
        "  user_id TEXT NOT NULL REFERENCES users(id),"
        "  event TEXT NOT NULL,"
        "  article_id TEXT REFERENCES articles(id),"
        "  actor_id TEXT REFERENCES users(id),"
        "  message TEXT NOT NULL,"
        "  read INTEGER NOT NULL DEFAULT 0,"
        "  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
        ")",
        "CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications(user_id)",
        "ALTER TABLE reviews ADD COLUMN status VARCHAR NOT NULL DEFAULT 'submitted'",
    ]
    with engine.connect() as conn:
        for sql in _migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
                _log.info("Migration applied: %s", sql)
            except sa_exc.OperationalError as e:
                # SQLite has no IF NOT EXISTS for ALTER TABLE ADD COLUMN.
                # Only suppress duplicate-column errors; re-raise anything
                # else (syntax errors, FK violations, etc.) to fail fast.
                msg = str(e).lower()
                if "duplicate column" not in msg and "already exists" not in msg:
                    raise
                conn.rollback()


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
