# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Test that seed.py produces a consistent, queryable dataset."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from seed import seed


@pytest.fixture(scope="module")
def seeded_db():
    """Run seed once and return the DB URL + articles dir."""
    with tempfile.TemporaryDirectory() as tmp:
        db_url = f"sqlite:///{tmp}/peerpedia.db"
        articles_dir = Path(tmp) / "articles"
        articles_dir.mkdir()
        seed(db_url, articles_dir)
        yield db_url, articles_dir


@pytest.fixture(scope="module")
def session(seeded_db):
    """SQLAlchemy session connected to the seeded DB."""
    from peerpedia_core.storage.db.engine import get_engine, get_session, init_db

    db_url, _ = seeded_db
    engine = get_engine(db_url)
    init_db(engine)
    s = get_session(engine)
    yield s
    s.close()
    engine.dispose()


def test_seed_creates_users(session):
    from peerpedia_core.storage.db.models import User

    users = session.query(User).all()
    assert len(users) >= 22, f"Expected >=22 users, got {len(users)}"

    einstein = session.query(User).filter(User.username == "einstein").first()
    assert einstein is not None
    assert einstein.name == "Albert Einstein"
    assert einstein.affiliation == "Princeton"


def test_seed_creates_articles_in_all_statuses(session):
    from peerpedia_core.storage.db.models import Article

    articles = session.query(Article).all()
    assert len(articles) >= 25, f"Expected >=25 articles, got {len(articles)}"

    statuses = {a.status for a in articles}
    assert "published" in statuses
    assert "sedimentation" in statuses
    assert "draft" in statuses


def test_seed_creates_published_article_with_score(session):
    from peerpedia_core.storage.db.models import Article

    article = session.query(Article).filter(Article.title.ilike("%electrodynamics%")).first()
    assert article is not None, "Einstein's relativity paper should exist"
    assert article.status == "published"
    assert article.score is not None
    assert article.score.get("originality", 0) > 0


def test_seed_creates_reviews(session):
    from peerpedia_core.storage.db.models import Review

    reviews = session.query(Review).all()
    assert len(reviews) >= 50, f"Expected >=50 reviews, got {len(reviews)}"


def test_seed_creates_follows(session):
    from peerpedia_core.storage.db.models import Follow

    follows = session.query(Follow).all()
    assert len(follows) >= 50, f"Expected >=50 follows, got {len(follows)}"


def test_seed_creates_bookmarks(session):
    from peerpedia_core.storage.db.models import Bookmark

    bookmarks = session.query(Bookmark).all()
    assert len(bookmarks) >= 20, f"Expected >=20 bookmarks, got {len(bookmarks)}"


def test_seed_creates_citations(session):
    from peerpedia_core.storage.db.models import Citation

    citations = session.query(Citation).all()
    assert len(citations) >= 5, f"Expected >=5 citations, got {len(citations)}"


def test_seed_creates_thread_messages(session):
    """At least some reviews should have thread messages."""
    from peerpedia_core.storage.db.models import Review

    reviews_with_threads = session.query(Review).filter(Review.thread != None).all()
    threaded = [r for r in reviews_with_threads if r.thread and len(r.thread) > 0]
    assert len(threaded) >= 5, f"Expected >=5 reviews with threads, got {len(threaded)}"


def test_seed_creates_forks(session):
    from peerpedia_core.storage.db.models import Article

    forks = session.query(Article).filter(Article.forked_from != None).all()
    assert len(forks) >= 2, f"Expected >=2 forks, got {len(forks)}"


def test_seed_is_idempotent(seeded_db):
    """Running seed twice should not crash or duplicate data."""
    db_url, articles_dir = seeded_db
    # Run again — should skip existing records
    seed(db_url, articles_dir)

    from peerpedia_core.storage.db.engine import get_engine, get_session, init_db
    from peerpedia_core.storage.db.models import User

    engine = get_engine(db_url)
    init_db(engine)
    s = get_session(engine)
    users = s.query(User).filter(User.username == "einstein").all()
    assert len(users) == 1, f"Einstein should not be duplicated, got {len(users)}"
    s.close()
    engine.dispose()
