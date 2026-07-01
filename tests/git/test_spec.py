# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Executable specifications for the git layer — closed-loop workflows.

STATUS: LOCKED

Each specification is a multi-step scenario that exercises several git
functions together, describing observable product behavior without
reference to implementation details.

Specification inventory
-----------------------
S1 — Article lifecycle
    create repo → write content → commit → edit → commit → get history → get diff → get source
S2 — Article deletion
    create → commit → delete repo → repo is gone
S3 — Status markers
    create → commit → set status → set new status → read latest status
S4 — Author discovery
    create → commit by A → commit by B → get authors → verify set
S5 — Review files
    create → write review scores → list dirs → read scores back
S6 — Bundle sync
    create source repo → create full bundle → apply to target → verify hash match
"""

import json
import tempfile
from pathlib import Path

import pytest

from tests.conftest import commit_article_signed


@pytest.fixture
def articles_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


# ═══════════════════════════════════════════════════════════════════════════════
# S1 — Article lifecycle: create → commit → edit → commit → history → diff → source
# ═══════════════════════════════════════════════════════════════════════════════


class TestArticleLifecycle:
    """A complete article creation and editing workflow."""

    def test_create_commit_edit_read(self, articles_dir):
        from peerpedia_core.storage.git import (
            commit_article, get_commit_history, get_diff_between,
            init_article_repo, read_article_source,
        )

        # ── Create ──
        rp = init_article_repo(articles_dir / "lifecycle")
        (rp / "article.md").write_text("# My Paper\n\nAbstract here.\n")
        h1 = commit_article_signed(rp, "initial draft", "Alice", "alice@peerpedia")
        assert len(h1) == 40

        # ── Edit ──
        (rp / "article.md").write_text("# My Paper\n\nAbstract here.\n\n## Results\n\nData shows...\n")
        h2 = commit_article_signed(rp, "add results", "Alice", "alice@peerpedia")
        assert h2 != h1

        # ── History ──
        history = get_commit_history(rp)
        assert len(history) >= 2
        assert history[0]["message"].startswith("add results")  # newest first

        # ── Diff ──
        first_commit = history[1]["hash"]
        last_commit = history[0]["hash"]
        diff = get_diff_between(rp, first_commit, last_commit)
        assert "Data shows" in diff.diff_text

        # ── Source ──
        content, fmt = read_article_source(rp)
        assert "## Results" in content
        assert fmt == "markdown"


# ═══════════════════════════════════════════════════════════════════════════════
# S2 — Article deletion
# ═══════════════════════════════════════════════════════════════════════════════


class TestArticleDeletion:
    """Create → commit → delete → repo is gone."""

    def test_delete_removes_repo(self, articles_dir):
        from peerpedia_core.storage.git import (
            commit_article, delete_article_repo, init_article_repo,
        )
        rp = init_article_repo(articles_dir / "to-delete")
        (rp / "article.md").write_text("content")
        commit_article_signed(rp, "init", "A", "a@b.com")
        assert rp.is_dir()

        delete_article_repo(rp)
        assert not rp.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# S3 — Status markers
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatusCycle:
    """Create → commit → set status → set new status → read latest."""

    def test_status_persists_and_updates(self, articles_dir):
        from peerpedia_core.storage.git import (
            commit_article, commit_status_marker, init_article_repo,
            read_status_from_git,
        )
        rp = init_article_repo(articles_dir / "status-cycle")
        (rp / "article.md").write_text("x")
        commit_article_signed(rp, "init", "A", "a@b.com")

        # First status
        commit_status_marker(rp, "sedimentation")
        assert read_status_from_git(rp) == "sedimentation"

        # Second status overwrites
        commit_status_marker(rp, "published")
        assert read_status_from_git(rp) == "published"


# ═══════════════════════════════════════════════════════════════════════════════
# S4 — Author discovery
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthorDiscovery:
    """Multiple authors → get_commit_authors returns correct set."""

    def test_multiple_authors_on_single_repo(self, articles_dir):
        from peerpedia_core.storage.git import (
            commit_article, get_commit_authors, init_article_repo,
        )
        rp = init_article_repo(articles_dir / "authors")
        (rp / "article.md").write_text("v1")
        commit_article_signed(rp, "first", "Alice", "alice@peerpedia")
        (rp / "article.md").write_text("v2")
        commit_article_signed(rp, "second", "Bob", "bob@peerpedia")

        authors = get_commit_authors(rp)
        assert authors == {"alice", "bob"}

    def test_platform_commits_excluded(self, articles_dir):
        """Status and review commits are not counted as authors."""
        from peerpedia_core.storage.git import (
            commit_article, commit_status_marker, get_commit_authors, init_article_repo,
        )
        rp = init_article_repo(articles_dir / "plat-authors")
        (rp / "article.md").write_text("v1")
        commit_article_signed(rp, "content", "Alice", "alice@peerpedia")
        # Platform commit — should NOT appear
        commit_status_marker(rp, "sedimentation")

        authors = get_commit_authors(rp)
        assert authors == {"alice"}


# ═══════════════════════════════════════════════════════════════════════════════
# S5 — Review files
# ═══════════════════════════════════════════════════════════════════════════════


class TestReviewCycle:
    """Ingest review files → list dirs → read scores → verify integrity."""

    def test_write_and_read_review_scores(self, articles_dir):
        from peerpedia_core.storage.git import (
            commit_article, init_article_repo, list_review_dirs, read_review_scores,
        )
        rp = init_article_repo(articles_dir / "review-cycle")
        (rp / "article.md").write_text("x")
        commit_article_signed(rp, "init", "A", "a@b.com")

        # Write review scores for two reviewers
        rv1_scores = {"originality": 4, "rigor": 3, "completeness": 5, "pedagogy": 4, "impact": 4}
        rv2_scores = {"originality": 2, "rigor": 5, "completeness": 3, "pedagogy": 5, "impact": 2}
        (rp / "reviews" / "rv1").mkdir(parents=True)
        (rp / "reviews" / "rv2").mkdir(parents=True)
        (rp / "reviews" / "rv1" / "scores.json").write_text(json.dumps(rv1_scores))
        (rp / "reviews" / "rv2" / "scores.json").write_text(json.dumps(rv2_scores))

        dirs = list_review_dirs(rp)
        assert sorted(dirs) == ["rv1", "rv2"]

        assert read_review_scores(rp, "rv1") == rv1_scores
        assert read_review_scores(rp, "rv2") == rv2_scores
        assert read_review_scores(rp, "nonexistent") is None


# ═══════════════════════════════════════════════════════════════════════════════
# S6 — Bundle sync (full roundtrip)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBundleSync:
    """Create bundle on source → apply to empty target → hashes match."""

    def test_full_bundle_roundtrip(self, articles_dir):
        import git as gitmod

        from peerpedia_core.storage.git import (
            commit_article, get_head_hash, init_article_repo,
        )
        from peerpedia_core.storage.git.bundle import create_bundle, ingest_bundle

        # ── Source: create repo with two commits ──
        src = init_article_repo(articles_dir / "src-article")
        (src / "article.md").write_text("v1")
        commit_article_signed(src, "first", "Author", "author@test.com")
        (src / "article.md").write_text("v2")
        commit_article_signed(src, "second", "Author", "author@test.com")
        src_hash = get_head_hash(src)

        # ── Create full bundle ──
        bundle_bytes = create_bundle(src)  # since_hash=None → full bundle
        assert len(bundle_bytes) > 0

        # ── Target: empty repo (bare init, no commits) ──
        import git as gitmod
        tgt_path = articles_dir / "tgt-article"
        tgt_path.mkdir()
        gitmod.Repo.init(tgt_path, initial_branch="main")
        ingest_bundle(tgt_path, bundle_bytes)
        from peerpedia_core.storage.git.merge import merge_fetch_head
        merge_fetch_head(tgt_path)

        # ── Verify: hashes match ──
        tgt_hash = get_head_hash(tgt_path)
        assert tgt_hash == src_hash, "bundle must preserve commit hash"

    def test_incremental_bundle_roundtrip(self, articles_dir):
        """Incremental bundle (since_hash → HEAD) applied to a clone works."""
        from peerpedia_core.storage.git import (
            clone_article_repo, commit_article, get_head_hash, init_article_repo,
        )
        from peerpedia_core.storage.git.bundle import create_bundle, ingest_bundle
        from peerpedia_core.storage.git.merge import merge_fetch_head

        # ── Source: create repo with two commits ──
        src = init_article_repo(articles_dir / "src-inc")
        (src / "article.md").write_text("v1")
        h1 = commit_article_signed(src, "first", "Author", "author@test.com")
        (src / "article.md").write_text("v2")
        commit_article_signed(src, "second", "Author", "author@test.com")
        src_head = get_head_hash(src)

        # ── Clone source to target (simulates peer's local copy) ──
        tgt = articles_dir / "tgt-inc"
        clone_article_repo(src, tgt)
        assert get_head_hash(tgt) == src_head

        # ── Add a third commit to source ──
        (src / "article.md").write_text("v3")
        commit_article_signed(src, "third", "Author", "author@test.com")
        new_head = get_head_hash(src)
        assert new_head != src_head

        # ── Incremental bundle (since h1) ──
        bundle_bytes = create_bundle(src, since_hash=h1)
        assert len(bundle_bytes) > 0

        # ── Apply to target ──
        ingest_bundle(tgt, bundle_bytes)
        merge_fetch_head(tgt)
        assert get_head_hash(tgt) == new_head
