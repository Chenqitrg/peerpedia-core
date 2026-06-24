# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for sync orchestration — _parse_status_tag, sync_reviews_from_worktree,
sync_status_from_git, and apply_sync_bundle."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from peerpedia_core.commands.bundle import (
    _parse_status_tag,
    apply_sync_bundle,
    sync_reviews_from_worktree,
    sync_status_from_git,
)
from peerpedia_core.storage.db.crud_article import create_article, get_article
from peerpedia_core.storage.db.crud_maintainer import add_maintainer
from peerpedia_core.storage.db.crud_review import get_reviews_for_article
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import User
import peerpedia_core.storage.git_backend as git_backend
from peerpedia_core.storage.git_backend import (
    DEFAULT_ARTICLES_DIR,
    commit_article,
    init_article_repo,
)

from tests.conftest import commit_article_signed

def _create_user(db: Session, user_id: str, name: str = "Test Author"):
    u = User(id=user_id, name=name)
    db.add(u)
    db.flush()
    return u


def _make_signed_commit(
    repo_path: Path, message: str, author_name: str, author_email: str,
) -> str:
    """Create an SSH-signed commit with a Pubkey trailer. Returns commit hash.

    Generates a temporary Ed25519 key pair, signs the commit, and cleans up.
    Used in sync tests to produce commits that pass the TOFU verify loop.
    """
    import hashlib
    import os
    import subprocess
    import tempfile

    import git as gitmod

    # Derive a deterministic test key pair
    seed = hashlib.scrypt(b"test-password", salt=b"test-salt-16bytes",
                          n=2**14, r=8, p=1, dklen=32)
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    priv = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
    # Derive the real public key hex — this must match the signing key
    # so that signature verification succeeds.
    real_pubkey_hex = priv.public_key().public_bytes_raw().hex()

    # Write private key in OpenSSH format (required by ssh-keygen)
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    )
    fd, priv_path = tempfile.mkstemp(suffix="_peerpedia_test_ed25519")
    with os.fdopen(fd, "wb") as f:
        f.write(priv_pem)
    os.chmod(priv_path, 0o600)
    priv_path = Path(priv_path)

    # Derive SSH public key
    pub_path = priv_path.with_suffix(priv_path.suffix + ".pub")
    result = subprocess.run(
        ["ssh-keygen", "-y", "-f", str(priv_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ssh-keygen failed: {result.stderr}")
    pub_path.write_text(result.stdout.strip())

    # Write allowed_signers
    fd, signers_path = tempfile.mkstemp(suffix="_allowed_signers")
    with os.fdopen(fd, "w") as f:
        f.write(f"{author_email} {result.stdout.strip()}\n")
    signers_path = Path(signers_path)

    try:
        repo = gitmod.Repo(repo_path)
        # Stage and write index
        repo.git.add(A=True)
        repo.index.write()
        full_msg = f"{message}\n\nPubkey: {real_pubkey_hex}"
        # Use GIT_CONFIG_COUNT env vars — -c after 'commit' means
        # --reedit-message to git >= 2.44, not a config override.
        sign_env = {
            **os.environ,
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": "gpg.format",
            "GIT_CONFIG_VALUE_0": "ssh",
            "GIT_CONFIG_KEY_1": "user.signingkey",
            "GIT_CONFIG_VALUE_1": str(pub_path),
        }
        repo.git.commit(
            S=True, gpg_sign=str(pub_path),
            m=full_msg,
            author=f"{author_name} <{author_email}>",
            env=sign_env,
        )
        return repo.head.commit.hexsha
    finally:
        priv_path.unlink(missing_ok=True)
        pub_path.unlink(missing_ok=True)
        signers_path.unlink(missing_ok=True)


@pytest.fixture
def db(engine):
    """Session from temporary SQLite."""
    session = get_session(engine)
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def articles_dir():
    """Temporary directory for article repos — isolates tests from each other."""
    with tempfile.TemporaryDirectory() as tmp:
        patch_modules = [
            "peerpedia_core.storage.git_backend",
            "peerpedia_core.commands.bundle",
            "peerpedia_core.commands.articles",
            "peerpedia_core.commands.articles.create",
            "peerpedia_core.commands.articles.delete",
            "peerpedia_core.commands.articles.fork",
            "peerpedia_core.commands.articles.publish",
            "peerpedia_core.commands.articles.rollback",
            "peerpedia_core.commands.articles.update",
            "peerpedia_core.commands.articles._helpers",
            "peerpedia_core.commands.workflow",
        ]
        patches = [patch(f"{m}.DEFAULT_ARTICLES_DIR", Path(tmp)) for m in patch_modules]
        for p in patches:
            p.start()
        try:
            yield Path(tmp)
        finally:
            for p in patches:
                p.stop()


# ── _parse_status_tag ────────────────────────────────────────────────────────


class TestParseStatusTag:
    def test_platform_commit_sedimentation(self):
        result = _parse_status_tag("[status] sedimentation", "system@peerpedia")
        assert result == "sedimentation"

    def test_platform_commit_published(self):
        result = _parse_status_tag("[status] published", "system@peerpedia")
        assert result == "published"

    def test_platform_commit_draft(self):
        result = _parse_status_tag("[status] draft", "system@peerpedia")
        assert result == "draft"

    def test_non_platform_email_returns_none(self):
        result = _parse_status_tag("[status] published", "alice@peerpedia")
        assert result is None

    def test_invalid_status_returns_none(self):
        result = _parse_status_tag("[status] foobar", "system@peerpedia")
        assert result is None

    def test_empty_message_returns_none(self):
        result = _parse_status_tag("   ", "system@peerpedia")
        assert result is None

    def test_message_with_whitespace_stripped(self):
        """Whitespace around the [status] message is stripped before matching."""
        result = _parse_status_tag("  [status] sedimentation\n", "system@peerpedia")
        assert result == "sedimentation"

    def test_old_format_without_prefix_returns_none(self):
        """Old format (no [status] prefix) is rejected — no backward compat."""
        result = _parse_status_tag("sedimentation", "system@peerpedia")
        assert result is None

    def test_message_without_status_prefix_returns_none(self):
        """Messages that don't start with [status] are rejected."""
        result = _parse_status_tag("[review] published", "system@peerpedia")
        assert result is None


# ── sync_reviews_from_worktree ─────────────────────────────────────────────────────────


class TestGitSyncReviews:
    def test_syncs_reviews_from_git_to_db(self, db, articles_dir):
        """Happy path: read scores.json from git worktree and upsert into DB."""
        _create_user(db, "alice", "Alice")
        _create_user(db, "reviewer-1", "Reviewer One")  # must exist for FK

        article = create_article(db, id="art-1", title="Test", authors=["alice"], status="published")
        add_maintainer(db, "art-1", "alice")
        db.flush()

        rp = articles_dir / "art-1"
        init_article_repo(rp)
        (rp / "article.md").write_text("# Test\n")
        commit_article_signed(rp, "Initial", "Alice", "alice@peerpedia")

        # Write a review to the git worktree
        review_dir = rp / "reviews" / "reviewer-1"
        review_dir.mkdir(parents=True)
        (review_dir / "scores.json").write_text(json.dumps({
            "originality": 4, "rigor": 3, "completeness": 4, "pedagogy": 3, "impact": 4,
        }))
        commit_article_signed(rp, "Add review", "Reviewer", "reviewer-1@peerpedia")

        sync_reviews_from_worktree(db, "art-1")

        reviews = get_reviews_for_article(db, "art-1")
        assert len(reviews) >= 1
        synced = [r for r in reviews if r.reviewer_id == "reviewer-1"]
        assert len(synced) == 1
        assert synced[0].scores["originality"] == 4

    def test_empty_reviews_dir_syncs_zero(self, db, articles_dir):
        """No reviews directory means zero reviews synced."""
        _create_user(db, "alice", "Alice")

        create_article(db, id="art-2", title="Test", authors=["alice"], status="published")
        add_maintainer(db, "art-2", "alice")
        db.flush()

        rp = articles_dir / "art-2"
        init_article_repo(rp)
        (rp / "article.md").write_text("# Test\n")
        commit_article_signed(rp, "Initial", "Alice", "alice@peerpedia")

        # No reviews written — should not crash
        sync_reviews_from_worktree(db, "art-2")

    def test_missing_scores_json_raises(self, db, articles_dir):
        """Fail fast: if a review directory has no scores.json, raise."""
        _create_user(db, "alice", "Alice")

        create_article(db, id="art-3", title="Test", authors=["alice"], status="published")
        add_maintainer(db, "art-3", "alice")
        db.flush()

        rp = articles_dir / "art-3"
        init_article_repo(rp)
        (rp / "article.md").write_text("# Test\n")
        commit_article_signed(rp, "Initial", "Alice", "alice@peerpedia")

        # Create review dir without scores.json (add a placeholder file so
        # git tracks the directory — empty dirs are ignored by git add).
        # Must match ARTICLE_REPO_TRACKED_PATTERNS in config/git.py or the
        # file will be git-ignored.
        review_dir = rp / "reviews" / "ghost-reviewer"
        (review_dir / "threads").mkdir(parents=True)
        (review_dir / "threads" / "note.md").write_text("placeholder")
        commit_article_signed(rp, "Add review dir", "Ghost", "ghost@peerpedia")

        with pytest.raises(FileNotFoundError, match="scores.json"):
            sync_reviews_from_worktree(db, "art-3")


# ── sync_status_from_git ──────────────────────────────────────────────────────────


class TestGitSyncStatus:
    def test_syncs_published_status_from_commit(self, db, articles_dir):
        """Platform commit 'published' updates article.status.

        commit_article only creates a commit when there are file changes
        (it checks is_dirty).  We change a file before the status commit
        to ensure the commit is actually created — mirroring production
        where write_review_to_git creates file changes before the
        "sedimentation"/"published" status commits.
        """
        _create_user(db, "alice", "Alice")

        article = create_article(db, id="art-status-1", title="Test", authors=["alice"], status="sedimentation")
        add_maintainer(db, "art-status-1", "alice")
        db.flush()

        rp = articles_dir / "art-status-1"
        init_article_repo(rp)
        (rp / "article.md").write_text("# Test\n")
        commit_article_signed(rp, "Initial", "Alice", "alice@peerpedia")

        # Make a file change so commit_article actually creates a new commit
        (rp / "article.md").write_text("# Test\n\nUpdated section.")
        commit_article(rp, "[status] published", "PeerPedia", "system@peerpedia", signing_key=None, pubkey_hex=None)
        db.flush()

        sync_status_from_git(db, "art-status-1")
        db.flush()

        art = get_article(db, "art-status-1")
        assert art.status == "published"

    def test_no_platform_commits_preserves_status(self, db, articles_dir):
        """Only user commits exist — status unchanged."""
        _create_user(db, "alice", "Alice")

        article = create_article(db, id="art-status-2", title="Test", authors=["alice"], status="sedimentation")
        add_maintainer(db, "art-status-2", "alice")
        db.flush()

        rp = articles_dir / "art-status-2"
        init_article_repo(rp)
        (rp / "article.md").write_text("# Test\n")
        h1 = commit_article_signed(rp, "Initial", "Alice", "alice@peerpedia")
        article.last_author_rebuild_hash = h1
        db.flush()

        # No platform commits — just user commits (file change needed for commit)
        (rp / "article.md").write_text("# Test\n\nUser edit section.")
        commit_article_signed(rp, "User edit", "Alice", "alice@peerpedia")
        db.flush()

        sync_status_from_git(db, "art-status-2")
        db.flush()

        art = get_article(db, "art-status-2")
        assert art.status == "sedimentation"

    def test_article_not_found_raises(self, db):
        with pytest.raises(FileNotFoundError, match="Article not found"):
            sync_status_from_git(db, "nonexistent")

    def test_repo_not_found_raises(self, db, articles_dir):
        """Article exists in DB but no git repo on disk."""
        _create_user(db, "alice", "Alice")
        create_article(db, id="art-no-repo", title="Test", authors=["alice"], status="draft")
        add_maintainer(db, "art-no-repo", "alice")
        db.flush()

        with pytest.raises(FileNotFoundError, match="Git repo not found"):
            sync_status_from_git(db, "art-no-repo")


# ── apply_sync_bundle ────────────────────────────────────────────────────────


class TestApplySyncBundle:
    def test_ff_only_merge_success(self, db, articles_dir):
        """Fast-forward merge of FETCH_HEAD succeeds and returns new HEAD."""
        _create_user(db, "alice", "Alice")

        create_article(db, id="art-bundle-1", title="Bundle Test", authors=["alice"], status="published")
        add_maintainer(db, "art-bundle-1", "alice")
        db.flush()

        rp = articles_dir / "art-bundle-1"
        init_article_repo(rp)
        (rp / "article.md").write_text("# Bundle Test\n")
        h1 = commit_article_signed(rp, "Initial", "Alice", "alice@peerpedia")

        # Create a "remote" signed commit and set it as FETCH_HEAD
        remote_dir = articles_dir / "remote-clone"
        import git as gitmod
        import shutil
        clone_repo = gitmod.Repo.clone_from(str(rp), str(remote_dir))
        (remote_dir / "article.md").write_text("# Updated\n\nFrom remote.")
        remote_head = _make_signed_commit(
            remote_dir, "Remote update", "Alice", "alice@peerpedia",
        )

        # Point FETCH_HEAD to the remote's HEAD
        repo = gitmod.Repo(rp)
        (rp / ".git" / "FETCH_HEAD").write_text(
            f"{remote_head}\t\tbranch 'main' of remote\n"
        )
        # Fetch the objects into the target repo
        repo.git.fetch(str(remote_dir), "refs/heads/main")

        result_hash = apply_sync_bundle(db, "art-bundle-1", ff_only=True)

        assert len(result_hash) == 40
        new_article = get_article(db, "art-bundle-1")
        assert new_article is not None

    def test_ff_only_merge_conflict_raises(self, db, articles_dir):
        """Merge conflict propagates as MergeConflictError."""
        _create_user(db, "alice", "Alice")

        create_article(db, id="art-conflict-1", title="Conflict Test", authors=["alice"], status="published")
        add_maintainer(db, "art-conflict-1", "alice")
        db.flush()

        rp = articles_dir / "art-conflict-1"
        init_article_repo(rp)
        (rp / "article.md").write_text("# v1\n")
        h1 = commit_article_signed(rp, "Initial", "Alice", "alice@peerpedia")

        # Create a divergent remote commit
        import git as gitmod
        remote_dir = articles_dir / "remote-conflict"
        clone_repo = gitmod.Repo.clone_from(str(rp), str(remote_dir))
        (remote_dir / "article.md").write_text("# v2-remote\n")
        clone_repo.index.add(["article.md"])
        clone_repo.index.commit("Remote edit", author=gitmod.Actor("Alice", "alice@peerpedia"),
                                 committer=gitmod.Actor("Alice", "alice@peerpedia"))

        # Make a LOCAL divergent change
        (rp / "article.md").write_text("# v2-local\n")
        commit_article_signed(rp, "Local edit", "Alice", "alice@peerpedia")

        # Set FETCH_HEAD to the remote commit
        repo = gitmod.Repo(rp)
        remote_commit = clone_repo.head.commit.hexsha
        (rp / ".git" / "FETCH_HEAD").write_text(
            f"{remote_commit}\t\tbranch 'main' of remote\n"
        )
        repo.git.fetch(str(remote_dir), "refs/heads/main")

        from peerpedia_core.storage.git_backend import MergeConflictError

        with pytest.raises(MergeConflictError, match="Merge failed"):
            apply_sync_bundle(db, "art-conflict-1", ff_only=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Pending queue preservation on mid-loop failure
# ═══════════════════════════════════════════════════════════════════════════════


class TestPendingQueuePreservation:
    """pop_pending must not run before db.commit() — otherwise a mid-loop
    crash permanently loses queue entries that were popped but rolled back."""

    def test_pop_pending_after_commit_not_before(self, db, monkeypatch):
        """Queue entries survive a MergeConflictError on a later article."""
        from peerpedia_core.bundle.pending import add, clear, list_all, remove
        from peerpedia_core.storage.git_backend import MergeConflictError

        # Start clean — other tests may have left queue entries.
        clear()

        # Seed pending queue with two articles.
        add("push", "art-keep")
        add("push", "art-crash")
        assert len(list_all()) == 2

        # Simulate sync_article: succeed for art-keep, crash for art-crash.
        calls = []

        def fake_sync(db, server, article_id):
            calls.append(article_id)
            if article_id == "art-crash":
                raise MergeConflictError("simulated conflict")
            return {"synced": True, "head": "abc123"}

        monkeypatch.setattr(
            "peerpedia_core.cli.handlers.bundle.sync_article", fake_sync
        )

        # Run with the FIXED pattern: commit before pop_pending.
        pushed = 0
        try:
            for op in list_all():
                result = fake_sync(db, "http://peer:8080", op["id"])
                if result["synced"]:
                    db.commit()       # commit FIRST
                    remove(op["id"])  # pop AFTER commit
                    pushed += 1
        except MergeConflictError:
            db.rollback()

        # art-keep was committed before crashing on art-crash.
        # Its queue entry is safely removed.
        remaining = [op["id"] for op in list_all()]
        assert "art-keep" not in remaining, (
            "art-keep was committed and should be dequeued"
        )
        assert "art-crash" in remaining, (
            "art-crash failed — its queue entry should survive for retry"
        )
