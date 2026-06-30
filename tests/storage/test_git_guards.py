# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for storage/git/guards.py — git-layer guard functions."""

from pathlib import Path

import pytest

from peerpedia_core.exceptions import BadRequestError, NotFoundError


# ═══════════════════════════════════════════════════════════════════════════════
# require_valid_article_status
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireValidArticleStatus:
    def test_valid_statuses_pass(self):
        """Known article statuses don't raise — draft, sedimentation, published, rejected."""
        from peerpedia_core.storage.git.guards import require_valid_article_status

        for status in ("draft", "sedimentation", "published", "rejected"):
            require_valid_article_status(status)  # should not raise

    def test_invalid_status_raises(self):
        """Unknown status raises INVALID_ARTICLE_STATUS — guards against typos."""
        from peerpedia_core.storage.git.guards import require_valid_article_status

        with pytest.raises(BadRequestError, match="INVALID_ARTICLE_STATUS"):
            require_valid_article_status("nonexistent")


# ═══════════════════════════════════════════════════════════════════════════════
# require_commit_signing_key
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireCommitSigningKey:
    def test_platform_commit_skips_check(self):
        """Platform commits (platform@...) don't require signing keys —
        platform can create status-marker commits without a user key."""
        from peerpedia_core.storage.git.guards import require_commit_signing_key

        from peerpedia_core.config.params import PLATFORM_EMAIL
        require_commit_signing_key(None, None, PLATFORM_EMAIL)  # should not raise

    def test_user_commit_without_key_raises(self):
        """User commits without signing key raise MISSING_SIGNING_KEY —
        every user-authored commit must be verifiable."""
        from peerpedia_core.storage.git.guards import require_commit_signing_key

        with pytest.raises(BadRequestError, match="MISSING_SIGNING_KEY"):
            require_commit_signing_key(None, None, "author@peerpedia")


# ═══════════════════════════════════════════════════════════════════════════════
# require_signing_key_for_pubkey
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireSigningKeyForPubkey:
    def test_both_present_ok(self):
        """pubkey_hex with signing_key passes — key matches the claimed identity."""
        from peerpedia_core.storage.git.guards import require_signing_key_for_pubkey

        require_signing_key_for_pubkey(b"key", "abc123")  # should not raise

    def test_pubkey_without_key_raises(self):
        """pubkey_hex provided without signing_key raises MISSING_SIGNING_KEY —
        can't claim an identity you can't sign for."""
        from peerpedia_core.storage.git.guards import require_signing_key_for_pubkey

        with pytest.raises(BadRequestError, match="MISSING_SIGNING_KEY"):
            require_signing_key_for_pubkey(None, "abc123")

    def test_no_pubkey_passes(self):
        """Missing pubkey_hex means no signing check needed —
        user may not have registered a key yet."""
        from peerpedia_core.storage.git.guards import require_signing_key_for_pubkey

        require_signing_key_for_pubkey(None, None)  # should not raise


# ═══════════════════════════════════════════════════════════════════════════════
# extract_pubkey_from_message
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtractPubkeyFromMessage:
    def test_found(self):
        """Extracts the hex after 'Pubkey: ' — standard commit trailer format."""
        from peerpedia_core.storage.git.guards import extract_pubkey_from_message

        message = "Some commit\nPubkey: deadbeef1234\nMore text"
        assert extract_pubkey_from_message(message) == "deadbeef1234"

    def test_not_found(self):
        """Returns None when no Pubkey trailer present."""
        from peerpedia_core.storage.git.guards import extract_pubkey_from_message

        assert extract_pubkey_from_message("Just a normal commit message") is None

    def test_empty_value_returns_none(self):
        """'Pubkey: ' with no value returns None — malformed trailer."""
        from peerpedia_core.storage.git.guards import extract_pubkey_from_message

        assert extract_pubkey_from_message("Pubkey: \nOther text") is None

    def test_case_sensitive_prefix(self):
        """Extraction requires exact 'Pubkey: ' prefix — case matters."""
        from peerpedia_core.storage.git.guards import extract_pubkey_from_message

        assert extract_pubkey_from_message("pubkey: abc\n") is None


# ═══════════════════════════════════════════════════════════════════════════════
# guard_not_empty
# ═══════════════════════════════════════════════════════════════════════════════


class TestGuardNotEmpty:
    def test_dirty_repo_passes(self, tmp_path):
        """A repo with uncommitted changes passes — there's something to commit."""
        import git as _git
        from peerpedia_core.storage.git.guards import guard_not_empty

        rp = tmp_path / "repo"
        rp.mkdir()
        repo = _git.Repo.init(rp)
        # Make an initial commit so HEAD is valid
        (rp / "file.txt").write_text("initial")
        repo.index.add(["file.txt"])
        repo.index.commit("init")
        # Now make it dirty
        (rp / "file.txt").write_text("modified")
        guard_not_empty(repo, allow_empty=False)  # should not raise

    def test_clean_repo_with_allow_empty_false_raises(self, tmp_path):
        """Clean repo with allow_empty=False raises REPO_IS_CLEAN —
        prevents empty commits that add no value."""
        import git as _git
        from peerpedia_core.storage.git.guards import guard_not_empty

        rp = tmp_path / "repo"
        rp.mkdir()
        repo = _git.Repo.init(rp)
        (rp / "file.txt").write_text("content")
        repo.index.add(["file.txt"])
        repo.index.commit("init")
        with pytest.raises(ValueError, match="REPO_IS_CLEAN"):
            guard_not_empty(repo, allow_empty=False)

    def test_clean_repo_with_allow_empty_true_passes(self, tmp_path):
        """Clean repo with allow_empty=True passes — caller explicitly allows."""
        import git as _git
        from peerpedia_core.storage.git.guards import guard_not_empty

        rp = tmp_path / "repo"
        rp.mkdir()
        repo = _git.Repo.init(rp)
        (rp / "file.txt").write_text("content")
        repo.index.add(["file.txt"])
        repo.index.commit("init")
        guard_not_empty(repo, allow_empty=True)  # should not raise


# ═══════════════════════════════════════════════════════════════════════════════
# require_article_repo
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireArticleRepo:
    def test_existing_repo_returns_path(self, tmp_path, monkeypatch):
        """Returns the repo path when .git directory exists —
        allows git operations to proceed."""
        from peerpedia_core.storage.git.guards import require_article_repo

        article_dir = tmp_path / "articles"
        rp = article_dir / "test-article"
        (rp / ".git").mkdir(parents=True)
        monkeypatch.setattr(
            "peerpedia_core.storage.git.guards.article_repo_path",
            lambda aid: article_dir / aid,
        )
        result = require_article_repo("test-article")
        assert result == rp

    def test_missing_repo_raises(self, tmp_path, monkeypatch):
        """Missing .git directory raises ARTICLE_REPO_NOT_FOUND —
        prevents operations on non-existent repos."""
        from peerpedia_core.storage.git.guards import require_article_repo

        article_dir = tmp_path / "articles"
        monkeypatch.setattr(
            "peerpedia_core.storage.git.guards.article_repo_path",
            lambda aid: article_dir / aid,
        )
        with pytest.raises(NotFoundError, match="ARTICLE_REPO_NOT_FOUND"):
            require_article_repo("nonexistent")


# ═══════════════════════════════════════════════════════════════════════════════
# require_review_scores
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireReviewScores:
    def test_valid_scores_returned(self, tmp_path):
        """Parsed review scores returned when scores file exists."""
        from peerpedia_core.storage.git.guards import require_review_scores

        rp = tmp_path / "repo"
        scores_dir = rp / "reviews" / "alice-reviewer"
        scores_dir.mkdir(parents=True)
        (scores_dir / "scores.json").write_text(
            '{"originality": 4, "rigor": 3, "completeness": 5, "pedagogy": 4, "impact": 4}'
        )
        result = require_review_scores(rp, "alice-reviewer", "art-1")
        assert result == {"originality": 4.0, "rigor": 3.0, "completeness": 5.0, "pedagogy": 4.0, "impact": 4.0}

    def test_missing_scores_raises(self, tmp_path):
        """Missing scores file raises REVIEW_SCORES_NOT_FOUND."""
        from peerpedia_core.storage.git.guards import require_review_scores

        rp = tmp_path / "repo"
        # No reviews/ directory at all
        with pytest.raises(NotFoundError, match="REVIEW_SCORES_NOT_FOUND"):
            require_review_scores(rp, "nonexistent-reviewer", "art-1")


# ═══════════════════════════════════════════════════════════════════════════════
# assert_repo_on_main
# ═══════════════════════════════════════════════════════════════════════════════


class TestAssertRepoOnMain:
    def test_repo_on_main_passes(self, tmp_path):
        """Repo with HEAD on main branch passes — article repos use trunk model."""
        import git as _git
        from peerpedia_core.storage.git.guards import assert_repo_on_main

        rp = tmp_path / "repo"
        rp.mkdir()
        repo = _git.Repo.init(rp)
        (rp / "file.txt").write_text("content")
        repo.index.add(["file.txt"])
        repo.index.commit("init")
        assert_repo_on_main(rp)  # should not raise

    def test_detached_head_raises(self, tmp_path):
        """Detached HEAD raises RuntimeError — all operations must be on a branch."""
        import git as _git
        from peerpedia_core.storage.git.guards import assert_repo_on_main

        rp = tmp_path / "repo"
        rp.mkdir()
        repo = _git.Repo.init(rp)
        (rp / "file.txt").write_text("content")
        repo.index.add(["file.txt"])
        repo.index.commit("init")
        # Checkout a different branch to leave main
        repo.git.checkout("-b", "other")
        with pytest.raises(RuntimeError):
            assert_repo_on_main(rp)
