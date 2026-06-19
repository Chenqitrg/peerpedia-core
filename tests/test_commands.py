# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for orchestration commands."""

from __future__ import annotations

import pytest
from peerpedia_core.exceptions import ConflictError, NotAuthorizedError, NotFoundError
from peerpedia_core.commands import (
    create_article_with_content,
    fork_article,
    rollback_article,
    update_article_content,
)
from peerpedia_core.storage.db.crud_article import get_article
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import User


def _create_user(db, user_id: str, name: str = "Test Author"):
    """Create a minimal user for testing."""
    u = User(id=user_id, username=name, password_hash="$2b$12$test", name=name)
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def db(engine):
    """Session from temporary SQLite (uses conftest.py engine fixture)."""
    session = get_session(engine)
    yield session
    session.rollback()
    session.close()


def test_fork_article_creates_record(db):
    """Happy path: fork a published article -> new draft with fork metadata."""
    _create_user(db, "alice", "Alice")
    _create_user(db, "bob", "Bob")

    from peerpedia_core.storage.db.crud_article import create_article
    from peerpedia_core.storage.db.crud_review import upsert_review

    article = create_article(
        db, id="art-1", title="Test Article", authors=["alice"], status="published",
    )
    upsert_review(
        db, article_id="art-1", commit_hash="abc123", reviewer_id="alice",
        scope="pool",
        scores={"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
    )
    db.flush()

    from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, init_article_repo, commit_article
    rp = DEFAULT_ARTICLES_DIR / "art-1"
    init_article_repo(rp)
    (rp / "article.md").write_text("# Test Article\n\nContent.")
    commit_article(rp, "Initial commit", "Alice", "alice@peerpedia")

    result = fork_article(db, "art-1", "bob")

    assert result["forked_from"] == "art-1"
    assert result["status"] == "draft"
    assert result["id"] != "art-1"

    fork = get_article(db, result["id"])
    assert fork is not None
    assert fork.title == "Test Article"
    assert fork.forked_from == "art-1"

    original = get_article(db, "art-1")
    assert original.fork_count == 1


def test_fork_fails_for_nonexistent_user(db):
    """Fork by nonexistent user raises NotFoundError."""
    _create_user(db, "alice", "Alice")
    from peerpedia_core.storage.db.crud_article import create_article

    create_article(db, id="art-1", title="Test", authors=["alice"], status="published")
    db.flush()

    with pytest.raises(NotFoundError, match="User not found"):
        fork_article(db, "art-1", "nonexistent")


def test_fork_fails_for_draft_article(db):
    """Fork a draft article raises NotAuthorizedError."""
    _create_user(db, "alice", "Alice")
    _create_user(db, "bob", "Bob")
    from peerpedia_core.storage.db.crud_article import create_article

    create_article(db, id="art-1", title="Draft", authors=["alice"], status="draft")
    db.flush()

    with pytest.raises(NotAuthorizedError, match="Only published articles can be forked"):
        fork_article(db, "art-1", "bob")


def test_fork_fails_for_duplicate(db):
    """Fork the same article twice raises ConflictError."""
    _create_user(db, "alice", "Alice")
    _create_user(db, "bob", "Bob")
    from peerpedia_core.storage.db.crud_article import create_article
    from peerpedia_core.storage.db.crud_review import upsert_review

    create_article(db, id="art-1", title="Test", authors=["alice"], status="published")
    upsert_review(
        db, article_id="art-1", commit_hash="abc", reviewer_id="alice",
        scope="pool",
        scores={"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
    )
    db.flush()

    from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, init_article_repo, commit_article
    rp = DEFAULT_ARTICLES_DIR / "art-1"
    init_article_repo(rp)
    (rp / "article.md").write_text("# Test\n\nContent.")
    commit_article(rp, "Initial commit", "Alice", "alice@peerpedia")

    fork_article(db, "art-1", "bob")
    db.flush()

    with pytest.raises(ConflictError, match="Already forked"):
        fork_article(db, "art-1", "bob")


# ── Rollback tests ───────────────────────────────────────────────────────


def test_rollback_creates_revert_commit(db):
    """Rollback creates a new commit with zero-score review."""
    _create_user(db, "alice", "Alice")
    from peerpedia_core.storage.db.crud_article import create_article

    create_article(db, id="art-1", title="Test", authors=["alice"], status="draft")
    db.flush()

    from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, init_article_repo, commit_article

    rp = DEFAULT_ARTICLES_DIR / "art-1"
    if not (rp / ".git").is_dir():
        init_article_repo(rp)
    (rp / "article.md").write_text("# Test Content")
    commit_article(rp, "Initial", "Alice", "alice@peerpedia")

    result = rollback_article(db, "art-1", "HEAD", "alice")

    assert "commit_hash" in result
    assert result["commit_hash"] != ""
    assert "Rollback to" in result["message"]


def test_rollback_fails_for_nonexistent_user(db):
    """Rollback by nonexistent user raises NotFoundError."""
    _create_user(db, "alice", "Alice")
    from peerpedia_core.storage.db.crud_article import create_article

    create_article(db, id="art-1", title="Test", authors=["alice"], status="draft")
    db.flush()

    with pytest.raises(NotFoundError):
        rollback_article(db, "art-1", "HEAD", "nonexistent")


# ── Create tests ─────────────────────────────────────────────────────────


def test_create_article_writes_file_and_commits(db):
    """Create article with content writes file to git and returns metadata."""
    _create_user(db, "alice", "Alice")

    result = create_article_with_content(
        db, title="Hello", content="# Test", format="markdown", user_id="alice",
    )

    assert result["title"] == "Hello"
    assert result["status"] == "draft"
    assert "commit_hash" in result

    from peerpedia_core.storage.db.crud_article import get_article
    article = get_article(db, result["id"])
    assert article is not None
    assert article.title == "Hello"


def test_create_article_with_publish(db):
    """Create + publish sets sink_start."""
    _create_user(db, "alice", "Alice")

    result = create_article_with_content(
        db, title="Pub", content="# Publish test", user_id="alice",
        publish=True,
        self_review={"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
    )

    assert result["status"] == "sedimentation"  # publish sets sink_start -> sedimentation
    from peerpedia_core.storage.db.crud_article import get_article
    article = get_article(db, result["id"])
    assert article.sink_start is not None  # sink timer started


def test_create_fails_publish_without_self_review(db):
    """Publish without self_review raises BadRequestError."""
    _create_user(db, "alice", "Alice")

    from peerpedia_core.exceptions import BadRequestError
    with pytest.raises(BadRequestError, match="self_review"):
        create_article_with_content(
            db, title="Bad", content="x", user_id="alice", publish=True,
        )


# ── Update tests ─────────────────────────────────────────────────────────


def test_update_article_changes_content(db):
    """Update content creates a new commit."""
    _create_user(db, "alice", "Alice")

    result = create_article_with_content(
        db, title="Original", content="# Original", user_id="alice",
    )
    aid = result["id"]

    updated = update_article_content(
        db, aid, content="# Updated", user_id="alice",
    )

    assert updated["id"] == aid
    assert updated["commit_hash"] != result["commit_hash"]


def test_update_fails_for_non_author(db):
    """Non-author cannot edit."""
    _create_user(db, "alice", "Alice")
    _create_user(db, "bob", "Bob")

    result = create_article_with_content(
        db, title="Mine", content="# Mine", user_id="alice",
    )

    from peerpedia_core.exceptions import NotAuthorizedError
    with pytest.raises(NotAuthorizedError):
        update_article_content(db, result["id"], content="# Hacked", user_id="bob")
