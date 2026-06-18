# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared fixtures for backend tests."""

import tempfile

import pytest
from peerpedia_api.deps import create_token
from peerpedia_core.storage.db.engine import Base, get_engine, get_session, init_db
from peerpedia_core.storage.db.models import *  # noqa: F401,F403 — register all models
from peerpedia_core.storage.db.models import Article, ArticleAuthor, User  # noqa: F401 — explicit imports
from sqlalchemy.orm import Session


def make_article(session: Session, /, *, authors: list | None = None, **kwargs):
    """Create an Article with optional author rows in the join table."""
    a = Article(**kwargs)
    session.add(a)
    session.flush()
    if authors:
        for pos, aid in enumerate(authors):
            session.add(ArticleAuthor(article_id=a.id, author_id=aid, position=pos))
    session.commit()
    return a


@pytest.fixture
def db_engine():
    """Temporary SQLite database for backend integration tests."""
    with tempfile.TemporaryDirectory() as tmp:
        db_url = f"sqlite:///{tmp}/test.db"
        eng = get_engine(db_url)
        Base.metadata.drop_all(eng)
        init_db(eng)
        yield eng
        eng.dispose()


@pytest.fixture
def auth_header():
    """Return a helper that creates an Authorization header for a user ID."""

    def _make(user_id: str) -> dict:
        token = create_token(user_id)
        return {"Authorization": f"Bearer {token}"}

    return _make


def _make_client_fixture(app, db_engine, db_override_only=False):
    """Create a TestClient with dep overrides. If db_override_only, does NOT
    override require_user — tests must pass auth_header explicitly."""

    def override_db():
        session = get_session(db_engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides.clear()
    from peerpedia_api import deps

    app.dependency_overrides[deps.get_db] = override_db

    if not db_override_only:
        # Create a default user and override require_user for convenience.
        s = get_session(db_engine)
        _u = User(username="test_auth_user", password_hash="", name="AuthUser", anonymous_name="anon", affiliation="TestU")
        s.add(_u)
        s.commit()
        _uid = _u.id
        _user_obj = s.get(User, _uid)
        s.close()

        def override_require_user():
            return _user_obj

        app.dependency_overrides[deps.require_user] = override_require_user

    from fastapi.testclient import TestClient

    return TestClient(app)
