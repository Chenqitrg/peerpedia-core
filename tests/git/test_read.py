# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for git read operations — status, head, format, reviews."""

import json
import tempfile
from pathlib import Path

import pytest

from tests.conftest import commit_article_signed


@pytest.fixture
def articles_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def repo(articles_dir):
    from peerpedia_core.storage.git import commit_article, init_article_repo
    rp = init_article_repo(articles_dir / "test-article")
    (rp / "article.md").write_text("# Test\n\nHello world.\n")
    commit_article_signed(rp, "initial", "Author", "a@b.com")
    return rp


# ═══════════════════════════════════════════════════════════════════════════════
# read_status_from_git
# ═══════════════════════════════════════════════════════════════════════════════


class TestReadStatusFromGit:
    def test_no_status_returns_none(self, repo):
        from peerpedia_core.storage.git import read_status_from_git
        assert read_status_from_git(repo) is None

    def test_reads_latest_status(self, articles_dir):
        from peerpedia_core.storage.git import (
            commit_status_marker, init_article_repo, read_status_from_git,
        )
        rp = init_article_repo(articles_dir / "test-status")
        (rp / "article.md").write_text("x")
        commit_article_signed(rp, "init", "A", "a@b.com")
        commit_status_marker(rp, "sedimentation")
        commit_status_marker(rp, "published")
        assert read_status_from_git(rp) == "published"


# ═══════════════════════════════════════════════════════════════════════════════
# get_head_commit / get_head_or_none
# ═══════════════════════════════════════════════════════════════════════════════


class TestHeadFunctions:
    def test_get_head_commit_returns_dict(self, repo):
        from peerpedia_core.storage.git import get_head_commit
        head = get_head_commit(repo)
        assert head is not None
        assert "hash" in head
        assert len(head["hash"]) == 40
        assert "message" in head

    def test_get_head_commit_empty_repo_raises(self, articles_dir):
        import git
        from peerpedia_core.storage.git import get_head_commit
        rp = articles_dir / "empty"
        rp.mkdir()
        git.Repo.init(rp)
        with pytest.raises(ValueError, match="REPO_NO_COMMITS"):
            get_head_commit(rp)

    def test_get_head_or_none_returns_str(self, repo):
        from peerpedia_core.storage.git import get_head_or_none
        h = get_head_or_none(repo)
        assert isinstance(h, str)
        assert len(h) == 40

    def test_get_head_or_none_empty_returns_none(self, articles_dir):
        import git
        from peerpedia_core.storage.git import get_head_or_none
        rp = articles_dir / "empty2"
        rp.mkdir()
        git.Repo.init(rp)
        assert get_head_or_none(rp) is None


# ═══════════════════════════════════════════════════════════════════════════════
# resolve_article_format
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveArticleFormat:
    def test_markdown_detected(self, repo):
        from peerpedia_core.storage.git import resolve_article_format
        assert resolve_article_format(repo) == "markdown"

    def test_typst_detected(self, articles_dir):
        from peerpedia_core.storage.git import init_article_repo, resolve_article_format
        rp = init_article_repo(articles_dir / "typst-article")
        (rp / "article.typ").write_text("= Test")
        assert resolve_article_format(rp) == "typst"

    def test_no_file_defaults_to_markdown(self, articles_dir):
        import git
        from peerpedia_core.storage.git import resolve_article_format
        rp = articles_dir / "bare"
        rp.mkdir()
        git.Repo.init(rp, initial_branch="main")
        assert resolve_article_format(rp) == "markdown"


# ═══════════════════════════════════════════════════════════════════════════════
# is_ancestor
# ═══════════════════════════════════════════════════════════════════════════════


class TestIsAncestor:
    def test_first_is_ancestor_of_second(self, articles_dir):
        from peerpedia_core.storage.git import (
            commit_article, get_commit_history, init_article_repo, is_ancestor,
        )
        rp = init_article_repo(articles_dir / "ancestor-test")
        (rp / "article.md").write_text("v1")
        h1 = commit_article_signed(rp, "first", "A", "a@b.com")
        (rp / "article.md").write_text("v2")
        commit_article_signed(rp, "second", "A", "a@b.com")
        assert is_ancestor(rp, h1) is True

    def test_unrelated_hash_returns_false(self, repo):
        from peerpedia_core.storage.git import is_ancestor
        # A random hash that doesn't exist in this repo
        fake = "0" * 40
        assert is_ancestor(repo, fake) is False


# ═══════════════════════════════════════════════════════════════════════════════
# read_article_source
# ═══════════════════════════════════════════════════════════════════════════════


class TestReadArticleSource:
    def test_reads_content_and_format(self, repo):
        from peerpedia_core.storage.git import read_article_source
        content, fmt = read_article_source(repo)
        assert content == "# Test\n\nHello world.\n"
        assert fmt == "markdown"

    def test_no_file_returns_none(self, articles_dir):
        from peerpedia_core.storage.git import init_article_repo, read_article_source
        rp = init_article_repo(articles_dir / "empty-src")
        # article.md doesn't exist (only .gitignore was committed)
        assert read_article_source(rp) is None


# ═══════════════════════════════════════════════════════════════════════════════
# list_review_dirs / read_review_scores
# ═══════════════════════════════════════════════════════════════════════════════


class TestReviewFiles:
    def test_no_reviews_dir_returns_empty(self, repo):
        from peerpedia_core.storage.git import list_review_dirs
        # init_article_repo creates reviews/ but it's empty
        # Remove it to test the "no dir" path
        import shutil
        shutil.rmtree(repo / "reviews")
        assert list_review_dirs(repo) == []

    def test_lists_review_dirs(self, repo):
        from peerpedia_core.storage.git import list_review_dirs
        (repo / "reviews" / "r1").mkdir(parents=True, exist_ok=True)
        (repo / "reviews" / "r2").mkdir(parents=True, exist_ok=True)
        (repo / "reviews" / "not-a-dir.txt").write_text("nope")
        dirs = list_review_dirs(repo)
        assert sorted(dirs) == ["r1", "r2"]

    def test_read_review_scores(self, repo):
        from peerpedia_core.storage.git import read_review_scores
        (repo / "reviews" / "rv1").mkdir(parents=True, exist_ok=True)
        scores = {"originality": 4, "rigor": 3, "completeness": 5, "pedagogy": 4, "impact": 4}
        (repo / "reviews" / "rv1" / "scores.json").write_text(json.dumps(scores))
        assert read_review_scores(repo, "rv1") == scores

    def test_read_review_scores_missing_returns_none(self, repo):
        from peerpedia_core.storage.git import read_review_scores
        assert read_review_scores(repo, "nonexistent") is None
