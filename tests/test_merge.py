# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for merge orchestration — accept_merge and create_merge_proposal."""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from peerpedia_core.exceptions import BadRequestError, NotAuthorizedError, NotFoundError
from peerpedia_core.commands.merge import accept_merge, create_merge_proposal, withdraw_merge_proposal
from peerpedia_core.storage.db.crud_article import create_article, get_article
from peerpedia_core.storage.db.crud_merge import create_merge_proposal as _db_create_mp
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.crud_maintainer import add_maintainer
from peerpedia_core.storage.db.models import User
import peerpedia_core.storage.git_backend as git_backend
from peerpedia_core.storage.git_backend import init_article_repo, commit_article, MergeConflictError
from tests.conftest import commit_article_signed


def _create_user(db: Session, user_id: str, name: str = "Test Author"):
    u = User(id=user_id, name=name)
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


@pytest.fixture
def articles_dir():
    """Temporary directory for article repos — isolates tests from each other.

    Patches DEFAULT_ARTICLES_DIR in every module that imports it, since
    Python modules bind the value at import time and won't see a base-module
    patch.
    """
    with tempfile.TemporaryDirectory() as tmp:
        # Patch every module that imports DEFAULT_ARTICLES_DIR
        _submodules = [
            "peerpedia_core.commands.articles.create",
            "peerpedia_core.commands.articles.delete",
            "peerpedia_core.commands.articles.fork",
            "peerpedia_core.commands.articles.publish",
            "peerpedia_core.commands.articles.rollback",
            "peerpedia_core.commands.articles.update",
            "peerpedia_core.commands.articles._helpers",
        ]
        patches = [
            patch.object(git_backend, "DEFAULT_ARTICLES_DIR", Path(tmp)),
            patch("peerpedia_core.commands.merge.DEFAULT_ARTICLES_DIR", Path(tmp)),
            patch("peerpedia_core.commands.articles.DEFAULT_ARTICLES_DIR", Path(tmp)),
        ] + [patch(f"{m}.DEFAULT_ARTICLES_DIR", Path(tmp)) for m in _submodules]
        for p in patches:
            p.start()
        try:
            yield Path(tmp)
        finally:
            for p in patches:
                p.stop()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_article_with_repo(db, articles_dir, article_id, authors, status="published"):
    """Create an article DB record and a matching git repo with one commit.

    Seeds all authors as maintainers (matching create_article_with_content).
    """
    article = create_article(db, id=article_id, title="Test Article", authors=authors, status=status)
    db.flush()
    for aid in authors:
        add_maintainer(db, article_id, aid)

    rp = articles_dir / article_id
    init_article_repo(rp)
    (rp / "article.md").write_text("# Test\n\nContent.")
    commit_article_signed(rp, "Initial commit", "Author", f"{authors[0]}@peerpedia")
    return article


# ── accept_merge ──────────────────────────────────────────────────────────────


class TestAcceptMerge:
    def test_success(self, db, articles_dir):
        """Happy path: accept a merge proposal from fork into target."""
        import git as gitmod

        _create_user(db, "alice", "Alice")

        target = _build_article_with_repo(db, articles_dir, "art-target", ["alice"], status="published")

        # Fork shares target's history — clone then add its own commit.
        fork_rp = articles_dir / "art-fork"
        gitmod.Repo.clone_from(str(articles_dir / "art-target"), str(fork_rp))
        (fork_rp / "article.md").write_text("# Fork\n\nModified content.")
        from tests.conftest import commit_article_signed
        commit_article_signed(fork_rp, "Fork commit", "Alice", "alice@peerpedia")
        fork = create_article(db, id="art-fork", title="Fork Article", authors=["alice"], status="draft")
        add_maintainer(db, "art-fork", "alice")
        db.flush()

        mp = _db_create_mp(db, fork.id, target.id, "alice")
        db.flush()

        result = accept_merge(db, target.id, mp.id, "alice")

        assert result is not None
        assert "commit_hash" in result
        assert result["id"] == target.id
        assert result["title"] == target.title

    def test_user_not_found(self, db, articles_dir):
        """Nonexistent user raises NotFoundError."""
        _create_user(db, "alice", "Alice")
        target = _build_article_with_repo(db, articles_dir, "art-target", ["alice"], status="published")
        _build_article_with_repo(db, articles_dir, "art-fork", ["alice"], status="draft")
        mp = _db_create_mp(db, "art-fork", "art-target", "alice")
        db.flush()

        with pytest.raises(NotFoundError, match="User not found"):
            accept_merge(db, target.id, mp.id, "nonexistent")

    def test_proposal_not_found(self, db, articles_dir):
        """Nonexistent proposal raises NotFoundError."""
        _create_user(db, "alice", "Alice")
        target = _build_article_with_repo(db, articles_dir, "art-target", ["alice"], status="published")
        db.flush()

        with pytest.raises(NotFoundError, match="Merge proposal not found"):
            accept_merge(db, target.id, "fake-proposal-id", "alice")

    def test_proposal_wrong_article(self, db, articles_dir):
        """Proposal does not target this article raises BadRequestError."""
        _create_user(db, "alice", "Alice")

        target_a = _build_article_with_repo(db, articles_dir, "art-a", ["alice"], status="published")
        target_b = _build_article_with_repo(db, articles_dir, "art-b", ["alice"], status="published")
        _build_article_with_repo(db, articles_dir, "art-fork", ["alice"], status="draft")

        mp = _db_create_mp(db, "art-fork", target_a.id, "alice")
        db.flush()

        with pytest.raises(BadRequestError, match="Proposal does not belong"):
            accept_merge(db, target_b.id, mp.id, "alice")

    def test_not_author(self, db, articles_dir):
        """Non-author cannot accept merge."""
        _create_user(db, "alice", "Alice")
        _create_user(db, "bob", "Bob")

        target = _build_article_with_repo(db, articles_dir, "art-target", ["alice"], status="published")
        _build_article_with_repo(db, articles_dir, "art-fork", ["alice"], status="draft")
        mp = _db_create_mp(db, "art-fork", target.id, "bob")
        db.flush()

        with pytest.raises(NotAuthorizedError, match="is not a maintainer"):
            accept_merge(db, target.id, mp.id, "bob")

    def test_target_repo_not_found(self, db, articles_dir):
        """Target repo doesn't exist on disk.

        Uses a unique ID not shared with any other test to avoid leftover
        repos from prior tests in the same class.
        """
        _create_user(db, "alice", "Alice")

        # Only DB record — no git repo on disk
        target_id = "art-no-target-repo"
        target = create_article(db, id=target_id, title="Target", authors=["alice"], status="published")
        add_maintainer(db, target_id, "alice")
        db.flush()

        _build_article_with_repo(db, articles_dir, "art-fork-no-target", ["alice"], status="draft")
        mp = _db_create_mp(db, "art-fork-no-target", target.id, "alice")
        db.flush()

        with pytest.raises(NotFoundError, match="Target article repo not found"):
            accept_merge(db, target.id, mp.id, "alice")

    def test_fork_repo_not_found(self, db, articles_dir):
        """Fork repo doesn't exist on disk."""
        _create_user(db, "alice", "Alice")

        _build_article_with_repo(db, articles_dir, "art-target-no-fork", ["alice"], status="published")

        # Fork DB record without git repo
        fork_id = "art-fork-no-repo"
        fork = create_article(db, id=fork_id, title="Fork", authors=["alice"], status="draft")
        db.flush()

        mp = _db_create_mp(db, fork.id, "art-target-no-fork", "alice")
        db.flush()

        with pytest.raises(NotFoundError, match="Fork article repo not found"):
            accept_merge(db, "art-target-no-fork", mp.id, "alice")

    def test_merge_conflict_returns_conflict_status(self, db, articles_dir):
        """Merge conflict returns status=conflict instead of raising."""
        _create_user(db, "alice", "Alice")

        _build_article_with_repo(db, articles_dir, "art-target-conflict", ["alice"], status="published")
        _build_article_with_repo(db, articles_dir, "art-fork-conflict", ["alice"], status="draft")
        mp = _db_create_mp(db, "art-fork-conflict", "art-target-conflict", "alice")
        db.flush()

        with patch("peerpedia_core.commands.merge.merge_git_repos") as mock_merge:
            mock_merge.side_effect = MergeConflictError("conflict")
            result = accept_merge(db, "art-target-conflict", mp.id, "alice")

        assert result["status"] == "conflict"
        assert "Merge conflicts" in result["message"]

    def test_published_target_triggers_sedimentation(self, db, articles_dir):
        """G2b: merging into a published article triggers 3-day sedimentation."""
        import git as gitmod

        _create_user(db, "alice", "Alice")

        _build_article_with_repo(db, articles_dir, "art-target-pub", ["alice"], status="published")

        # Fork clones target so they share history.
        fork_rp = articles_dir / "art-fork-pub"
        gitmod.Repo.clone_from(str(articles_dir / "art-target-pub"), str(fork_rp))
        (fork_rp / "article.md").write_text("# Fork\n\nModified.")
        from tests.conftest import commit_article_signed
        commit_article_signed(fork_rp, "Fork commit", "Alice", "alice@peerpedia")
        fork = create_article(db, id="art-fork-pub", title="Fork", authors=["alice"], status="draft")
        add_maintainer(db, "art-fork-pub", "alice")
        db.flush()

        mp = _db_create_mp(db, "art-fork-pub", "art-target-pub", "alice")
        db.flush()

        result = accept_merge(db, "art-target-pub", mp.id, "alice")

        assert result["status"] != "conflict"
        article = get_article(db, "art-target-pub")
        assert article.sink_start is not None
        assert article.sink_duration_days == 3

    def test_merge_into_sedimentation_rejected(self, db, articles_dir):
        """P0-3: Merging into a sedimentation article is now allowed."""
        _create_user(db, "alice", "Alice")

        _build_article_with_repo(db, articles_dir, "art-target-sed", ["alice"], status="sedimentation")
        _build_article_with_repo(db, articles_dir, "art-fork-sed", ["alice"], status="draft")
        mp = _db_create_mp(db, "art-fork-sed", "art-target-sed", "alice")
        db.flush()

        result = accept_merge(db, "art-target-sed", mp.id, "alice")
        assert result is not None


# ── create_merge_proposal ─────────────────────────────────────────────────────


class TestCreateMergeProposal:
    def test_create(self, db, articles_dir):
        """Thin wrapper: creates a merge proposal in DB."""
        _create_user(db, "alice", "Alice")
        _build_article_with_repo(db, articles_dir, "art-original", ["alice"], status="published")
        _build_article_with_repo(db, articles_dir, "art-fork", ["alice"], status="draft")

        mp = create_merge_proposal(db, "art-fork", "art-original", "alice")

        assert mp is not None
        assert mp.fork_article_id == "art-fork"
        assert mp.target_article_id == "art-original"
        assert mp.proposer_id == "alice"
        assert mp.status == "open"


class TestWithdrawMergeProposal:
    def test_withdraw_open_proposal(self, db):
        """Proposer can withdraw their own open proposal."""
        _create_user(db, "alice", "Alice")
        _create_user(db, "bob", "Bob")

        create_article(db, id="art-target", title="Target", authors=["bob"], status="published")
        create_article(db, id="art-fork", title="Fork", authors=["alice"], status="draft")

        mp = create_merge_proposal(db, "art-fork", "art-target", "alice")

        result = withdraw_merge_proposal(db, mp.id, "alice")
        assert result["status"] == "withdrawn"
        assert result["id"] == mp.id

    def test_withdraw_other_users_proposal_fails(self, db):
        """Non-proposer cannot withdraw someone else's proposal."""
        _create_user(db, "alice", "Alice")
        _create_user(db, "bob", "Bob")

        create_article(db, id="art-target", title="Target", authors=["bob"], status="published")
        create_article(db, id="art-fork", title="Fork", authors=["alice"], status="draft")

        mp = create_merge_proposal(db, "art-fork", "art-target", "alice")

        with pytest.raises(NotAuthorizedError):
            withdraw_merge_proposal(db, mp.id, "bob")

    def test_withdraw_accepted_proposal_fails(self, db, articles_dir):
        """Cannot withdraw a proposal that was already accepted."""
        _create_user(db, "alice", "Alice")
        _create_user(db, "bob", "Bob")

        _build_article_with_repo(db, articles_dir, "art-target", ["bob"], status="published")
        _build_article_with_repo(db, articles_dir, "art-fork", ["alice"], status="draft")

        mp = create_merge_proposal(db, "art-fork", "art-target", "alice")
        accept_merge(db, "art-target", mp.id, "bob")

        with pytest.raises(BadRequestError, match="already"):
            withdraw_merge_proposal(db, mp.id, "alice")
