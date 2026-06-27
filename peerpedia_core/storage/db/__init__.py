# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Storage — database layer.  The facade for all DB access."""

from peerpedia_core.storage.db.engine import (  # noqa: F401 — facade re-exports
    Base,
    JSONDict,
    JSONList,
    Session,
    get_engine,
    get_session,
    init_db,
    migrate_db,
)
from peerpedia_core.storage.db.session_utils import db_session_scope as _db_session_scope


def db_session(database_url: str) -> Session:
    """Context manager for a database session with auto commit/rollback/close."""
    return _db_session_scope(database_url)


def db_repl_setup(database_url: str) -> tuple[Engine, Session]:
    """Set up the database for a long-lived REPL or server session.

    Creates tables, applies migrations.  Returns (engine, session).
    The caller owns the session lifecycle — it must call session.close()
    when done.
    """
    engine = get_engine(database_url)
    init_db(engine)
    migrate_db(engine)
    session = get_session(engine)
    return engine, session
