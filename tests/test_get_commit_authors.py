# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for ``get_commit_authors`` — commit author filtering.

Covers the dual filter (message tag + email domain) that prevents
review, status, and merge commits from being counted as article authors.
"""

import tempfile
from pathlib import Path

import pytest

from tests.conftest import commit_article_signed


@pytest.fixture
def article_repo():
    """An initialized article repo for testing commit author extraction."""
    from peerpedia_core.storage.git import commit_article, init_article_repo

    with tempfile.TemporaryDirectory() as tmp:
        rp = init_article_repo(Path(tmp) / "test-article")
        (rp / "article.md").write_text("# Test\n")
        commit_article_signed(rp, "Initial content", "Alice", "alice@peerpedia")
        yield rp


# ── Happy path ──────────────────────────────────────────────────────────────


def test_extracts_content_author(article_repo):
    """Content commits with @peerpedia email are counted as authors."""
    from peerpedia_core.storage.git import commit_article, get_commit_authors

    (article_repo / "article.md").write_text("# Test\n\nNew section.")
    commit_article_signed(article_repo, "Add section", "Bob", "bob@peerpedia")

    authors = get_commit_authors(article_repo)
    assert "alice" in authors
    assert "bob" in authors


# ── Message tag filtering ───────────────────────────────────────────────────


def _touch_file(repo_path: Path, name: str = "reviews/test/scores.json") -> None:
    """Write a dummy file so commit_article has something to commit.

    Must match ``ARTICLE_REPO_TRACKED_PATTERNS`` in ``config/git.py``
    so the file is not git-ignored.
    """
    f = repo_path / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text('{"score": 0}\n')


def test_filters_review_commit(article_repo):
    """[review] commit is excluded even though email is @peerpedia."""
    from peerpedia_core.storage.git import commit_article, get_commit_authors

    _touch_file(article_repo)
    commit_article_signed(article_repo, "[review] Reviewer One", "Reviewer One", "reviewer-1@peerpedia")

    authors = get_commit_authors(article_repo)
    assert "reviewer-1" not in authors
    assert "alice" in authors  # original content author still present


def test_filters_status_commit(article_repo):
    """[status] commit is excluded (author is system@peerpedia)."""
    from peerpedia_core.storage.git import commit_article, get_commit_authors

    _touch_file(article_repo)
    commit_article_signed(article_repo, "[status] published", "PeerPedia", "system@peerpedia")

    authors = get_commit_authors(article_repo)
    assert "system" not in authors


def test_filters_merge_commit(article_repo):
    """[merge] commit is excluded."""
    from peerpedia_core.storage.git import commit_article, get_commit_authors

    _touch_file(article_repo)
    commit_article_signed(article_repo, "[merge] fork-123", "Merger", "merger@peerpedia")

    authors = get_commit_authors(article_repo)
    assert "merger" not in authors


def test_message_with_leading_whitespace(article_repo):
    """Tag after whitespace is still detected (git messages can start with newlines)."""
    from peerpedia_core.storage.git import commit_article, get_commit_authors

    _touch_file(article_repo)
    commit_article_signed(article_repo, "\n[review] Spaced Reviewer", "Spaced", "spaced@peerpedia")

    authors = get_commit_authors(article_repo)
    assert "spaced" not in authors


# ── Email domain filtering ──────────────────────────────────────────────────


def test_filters_non_peerpedia_email(article_repo):
    """Commits with non-@peerpedia emails are excluded (system git config)."""
    from peerpedia_core.storage.git import commit_article, get_commit_authors

    _touch_file(article_repo)
    commit_article_signed(article_repo, "Some edit", "Ghost", "ghost@gmail.com")

    authors = get_commit_authors(article_repo)
    assert "ghost" not in authors


def test_filters_email_without_domain(article_repo):
    """Email without @peerpedia suffix is excluded."""
    from peerpedia_core.storage.git import commit_article, get_commit_authors

    _touch_file(article_repo)
    commit_article_signed(article_repo, "Edit", "NoDomain", "nodomain@other")

    authors = get_commit_authors(article_repo)
    assert "nodomain" not in authors


# ── since_hash ──────────────────────────────────────────────────────────────


def test_since_hash_limits_scan(article_repo):
    """Only commits after since_hash are scanned."""
    from peerpedia_core.storage.git import commit_article, get_commit_authors
    import git

    (article_repo / "article.md").write_text("# Test\n\nSecond update.")
    commit_article_signed(article_repo, "Second content", "Bob", "bob@peerpedia")
    repo = git.Repo(article_repo)

    # Get the hash of Alice's content commit (second-oldest; oldest is the
    # init commit from init_article_repo).
    first_hash = list(repo.iter_commits())[-2].hexsha  # first content commit

    # Scanning from first_hash should only see Bob
    authors = get_commit_authors(article_repo, since_hash=first_hash)
    assert "bob" in authors
    assert "alice" not in authors
