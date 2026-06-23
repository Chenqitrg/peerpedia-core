# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for orchestration commands."""

from __future__ import annotations

import pytest
from peerpedia_core.exceptions import ConflictError, NotAuthorizedError, NotFoundError
from peerpedia_core.commands import (
    create_article_with_content,
    fork_article,
    publish_article,
    rollback_article,
    update_article_content,
)
from peerpedia_core.storage.db.crud_article import create_article, get_article
from peerpedia_core.storage.db.crud_maintainer import add_maintainer
from peerpedia_core.storage.db.crud_review import upsert_review
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import User
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, commit_article, init_article_repo
from tests.conftest import commit_article_signed

def _create_user(db, user_id: str, name: str = "Test Author"):
    """Create a minimal user for testing."""
    u = User(id=user_id,  name=name)
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

def test_fork_article_creates_record(db, test_signing_key_bytes, test_pubkey_hex):
    """Happy path: fork a published article -> new draft with fork metadata."""
    _create_user(db, "alice", "Alice")
    _create_user(db, "bob", "Bob")

    article = create_article(
        db, id="art-1", title="Test Article", authors=["alice"], status="published",
    )
    upsert_review(
        db, article_id="art-1", commit_hash="abc123", reviewer_id="alice",
        scores={"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
    )
    db.flush()

    rp = DEFAULT_ARTICLES_DIR / "art-1"
    init_article_repo(rp)
    (rp / "article.md").write_text("# Test Article\n\nContent.")
    commit_article_signed(rp, "Initial commit", "Alice", "alice@peerpedia")

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

def test_fork_fails_for_nonexistent_user(db, test_signing_key_bytes, test_pubkey_hex):
    """Fork by nonexistent user raises NotFoundError."""
    _create_user(db, "alice", "Alice")

    create_article(db, id="art-1", title="Test", authors=["alice"], status="published")
    db.flush()

    with pytest.raises(NotFoundError, match="User not found"):
        fork_article(db, "art-1", "nonexistent")

def test_fork_fails_for_draft_article(db, test_signing_key_bytes, test_pubkey_hex):
    """Fork a draft article raises NotAuthorizedError."""
    _create_user(db, "alice", "Alice")
    _create_user(db, "bob", "Bob")

    create_article(db, id="art-1", title="Draft", authors=["alice"], status="draft")
    db.flush()

    with pytest.raises(NotAuthorizedError, match="Only published articles can be forked"):
        fork_article(db, "art-1", "bob")

def test_fork_fails_for_duplicate(db, test_signing_key_bytes, test_pubkey_hex):
    """Fork the same article twice raises ConflictError."""
    _create_user(db, "alice", "Alice")
    _create_user(db, "bob", "Bob")

    create_article(db, id="art-1", title="Test", authors=["alice"], status="published")
    upsert_review(
        db, article_id="art-1", commit_hash="abc", reviewer_id="alice",
        scores={"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
    )
    db.flush()

    rp = DEFAULT_ARTICLES_DIR / "art-1"
    init_article_repo(rp)
    (rp / "article.md").write_text("# Test\n\nContent.")
    commit_article_signed(rp, "Initial commit", "Alice", "alice@peerpedia")

    fork_article(db, "art-1", "bob")
    db.flush()

    with pytest.raises(ConflictError, match="Already forked"):
        fork_article(db, "art-1", "bob")

# ── Rollback tests ───────────────────────────────────────────────────────

def test_rollback_creates_revert_commit(db, test_signing_key_bytes, test_pubkey_hex):
    """Rollback creates a new commit with zero-score review."""
    _create_user(db, "alice", "Alice")

    create_article(db, id="art-1", title="Test", authors=["alice"], status="draft")
    add_maintainer(db, "art-1", "alice")
    db.flush()

    rp = DEFAULT_ARTICLES_DIR / "art-1"
    # Clean up from previous test runs to avoid test pollution.
    import shutil
    if (rp / ".git").is_dir():
        shutil.rmtree(rp)
    init_article_repo(rp)
    (rp / "article.md").write_text("# Test Content")
    h1 = commit_article_signed(rp, "Initial", "Alice", "alice@peerpedia")

    # Create a second commit so we have something to roll back from.
    # Must write different content to ensure is_dirty returns True.
    (rp / "article.md").write_text("# Test Content\n\nMore content.\n")
    h2 = commit_article_signed(rp, "Second", "Alice", "alice@peerpedia")

    # Rollback from HEAD to the first commit
    result = rollback_article(db, "art-1", h1, "alice", signing_key_bytes=test_signing_key_bytes, pubkey_hex=test_pubkey_hex)

    assert "commit_hash" in result
    assert result["commit_hash"] != ""
    assert "Rollback to" in result["message"]

def test_rollback_fails_for_nonexistent_user(db, test_signing_key_bytes, test_pubkey_hex):
    """Rollback by nonexistent user raises NotFoundError."""
    _create_user(db, "alice", "Alice")

    create_article(db, id="art-1", title="Test", authors=["alice"], status="draft")
    db.flush()

    with pytest.raises(NotFoundError):
        rollback_article(db, "art-1", "HEAD", "nonexistent", signing_key_bytes=test_signing_key_bytes, pubkey_hex=test_pubkey_hex)


def test_rollback_requires_signing_keys(db, test_signing_key_bytes, test_pubkey_hex):
    """rollback_article without signing keys raises ValueError — fail fast."""
    _create_user(db, "alice", "Alice")
    create_article(db, id="art-1", title="Test", authors=["alice"], status="draft")
    from peerpedia_core.storage.db.crud_maintainer import add_maintainer
    add_maintainer(db, "art-1", "alice")
    db.flush()

    # Set up the git repo so we get past the NotFoundError check.
    from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, init_article_repo
    rp = DEFAULT_ARTICLES_DIR / "art-1"
    import shutil
    if (rp / ".git").is_dir():
        shutil.rmtree(rp)
    init_article_repo(rp)
    (rp / "article.md").write_text("# Test")
    from tests.conftest import commit_article_signed
    h1 = commit_article_signed(rp, "Initial", "Alice", "alice@peerpedia")
    (rp / "article.md").write_text("# Test\n\nMore.")
    commit_article_signed(rp, "Second", "Alice", "alice@peerpedia")

    with pytest.raises(ValueError, match="required for rollback"):
        rollback_article(db, "art-1", h1, "alice",
                         signing_key_bytes=None, pubkey_hex=None)

# ── Create tests ─────────────────────────────────────────────────────────

def test_create_article_writes_file_and_commits(db, test_signing_key_bytes, test_pubkey_hex):
    """Create article with content writes file to git and returns metadata."""
    _create_user(db, "alice", "Alice")

    result = create_article_with_content(
        db, title="Hello", content="# Test", format="markdown", author_ids=["alice"], signing_key_bytes=test_signing_key_bytes, pubkey_hex=test_pubkey_hex)

    assert result["title"] == "Hello"
    assert result["status"] == "draft"
    assert "commit_hash" in result

    article = get_article(db, result["id"])
    assert article is not None
    assert article.title == "Hello"

def test_create_article_with_publish(db, test_signing_key_bytes, test_pubkey_hex):
    """Create + publish sets sink_start."""
    _create_user(db, "alice", "Alice")

    result = create_article_with_content(
        db, title="Pub", content="# Publish test", author_ids=["alice"], signing_key_bytes=test_signing_key_bytes, pubkey_hex=test_pubkey_hex)
    result = publish_article(
        db, result["id"], "alice",
        {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3}, signing_key_bytes=test_signing_key_bytes, pubkey_hex=test_pubkey_hex)

    assert result["status"] == "sedimentation"
    article = get_article(db, result["id"])
    assert article.sink_start is not None

# ── Update tests ─────────────────────────────────────────────────────────

def test_update_article_changes_content(db, test_signing_key_bytes, test_pubkey_hex):
    """Update content creates a new commit."""
    _create_user(db, "alice", "Alice")

    result = create_article_with_content(
        db, title="Original", content="# Original", author_ids=["alice"], signing_key_bytes=test_signing_key_bytes, pubkey_hex=test_pubkey_hex)
    aid = result["id"]

    updated = update_article_content(
        db, aid, content="# Updated", user_id="alice", message="Update content", signing_key_bytes=test_signing_key_bytes, pubkey_hex=test_pubkey_hex)

    assert updated["id"] == aid
    assert updated["commit_hash"] != result["commit_hash"]

def test_update_fails_for_non_author(db, test_signing_key_bytes, test_pubkey_hex):
    """Non-author cannot edit."""
    _create_user(db, "alice", "Alice")
    _create_user(db, "bob", "Bob")

    result = create_article_with_content(
        db, title="Mine", content="# Mine", author_ids=["alice"], signing_key_bytes=test_signing_key_bytes, pubkey_hex=test_pubkey_hex)

    from peerpedia_core.exceptions import NotAuthorizedError
    with pytest.raises(NotAuthorizedError):
        update_article_content(db, result["id"], content="# Hacked", user_id="bob", message="Hack attempt", signing_key_bytes=test_signing_key_bytes, pubkey_hex=test_pubkey_hex)

# ── Format tests ─────────────────────────────────────────────────────────

def test_article_has_frontmatter(db, test_signing_key_bytes, test_pubkey_hex):
    """New-format article.md starts with YAML frontmatter containing title."""
    _create_user(db, "alice", "Alice")
    result = create_article_with_content(
        db, title="Hello", content="# Test", author_ids=["alice"], signing_key_bytes=test_signing_key_bytes, pubkey_hex=test_pubkey_hex)
    article_text = (DEFAULT_ARTICLES_DIR / result["id"] / "article.md").read_text()
    assert article_text.startswith("---"), "article.md should start with frontmatter"
    import yaml
    parts = article_text.split("---", 2)
    fm = yaml.safe_load(parts[1])
    assert fm["title"] == "Hello"
    assert "# Test" in article_text

def test_self_review_creates_file(db, test_signing_key_bytes, test_pubkey_hex):
    """Self-review creates reviews/{author}/scores.json in git repo."""
    _create_user(db, "alice", "Alice")
    result = create_article_with_content(
        db, title="Pub", content="# Publish test", author_ids=["alice"], signing_key_bytes=test_signing_key_bytes, pubkey_hex=test_pubkey_hex)
    result = publish_article(
        db, result["id"], "alice",
        {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3}, signing_key_bytes=test_signing_key_bytes, pubkey_hex=test_pubkey_hex)
    import json
    scores_path = DEFAULT_ARTICLES_DIR / result["id"] / "reviews" / "alice" / "scores.json"
    assert scores_path.exists(), "Self-review scores.json should exist in git"
    scores = json.loads(scores_path.read_text())
    assert scores["originality"] == 3

def test_metadata_only_update_commits(db, test_signing_key_bytes, test_pubkey_hex):
    """Updating only title (no content change) produces a git commit."""
    _create_user(db, "alice", "Alice")
    result = create_article_with_content(
        db, title="Original", content="# Original", author_ids=["alice"], signing_key_bytes=test_signing_key_bytes, pubkey_hex=test_pubkey_hex)
    aid = result["id"]

    updated = update_article_content(
        db, aid, title="Updated Title", user_id="alice", message="Update title", signing_key_bytes=test_signing_key_bytes, pubkey_hex=test_pubkey_hex)
    assert updated["commit_hash"] != result["commit_hash"]
    # Verify frontmatter was updated
    from peerpedia_core.frontmatter import parse_frontmatter
    article_text = (DEFAULT_ARTICLES_DIR / aid / "article.md").read_text()
    fm = parse_frontmatter(article_text)
    assert fm["title"] == "Updated Title"

def test_frontmatter_roundtrip(test_signing_key_bytes, test_pubkey_hex):
    """make_article_frontmatter → parse_frontmatter roundtrip preserves data."""
    from peerpedia_core.frontmatter import make_article_frontmatter, parse_frontmatter
    fm = make_article_frontmatter("Test", "Abstract text", ["kw1", "kw2"], ["cat"])
    parsed = parse_frontmatter(fm + "# Content body")
    assert parsed["title"] == "Test"
    assert parsed["abstract"] == "Abstract text"
    assert parsed["keywords"] == ["kw1", "kw2"]
    assert parsed["categories"] == ["cat"]
