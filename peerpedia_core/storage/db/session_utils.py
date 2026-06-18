# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Database session utilities.

Provides a context manager for session lifecycle so callers don't
repeat engine/session/rollback boilerplate.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.engine import get_engine, get_session, init_db


@contextmanager
def db_session_scope(database_url: str) -> Generator[Session, None, None]:
    """Context manager that yields a SQLAlchemy Session with auto-commit/rollback.

    Usage:
        with db_session_scope(database_url) as session:
            article = get_article(session, article_id)
            # session commits on exit; rolls back on exception
    """
    engine = get_engine(database_url)
    init_db(engine)
    session = get_session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
