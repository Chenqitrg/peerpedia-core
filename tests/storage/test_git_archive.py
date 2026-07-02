# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for storage/git/archive.py — full-repo pack/unpack operations."""

import pytest

from peerpedia_core.exceptions import ConflictError
from tests.conftest import commit_article_signed


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_repo_with_content(base: str, filename: str, content: str):
    """Create an initialized repo, write content, and make a signed commit."""
    from peerpedia_core.storage.git.ops import init_article_repo
    from pathlib import Path

    rp = Path(base)
    init_article_repo(rp)
    (rp / filename).write_text(content)
    commit_article_signed(rp, "Initial commit", "Author", "author@peerpedia")
    return rp


# ═══════════════════════════════════════════════════════════════════════════════
# ingest_article_repo
# ═══════════════════════════════════════════════════════════════════════════════


class TestIngestArticleRepo:
    def test_valid_payload_unpacks_to_path(self, tmp_path):
        """A packed repo is unpacked correctly — content and HEAD hash recovered."""
        from peerpedia_core.storage.git.archive import ingest_article_repo, pack_article_repo

        # Create source repo in isolated dir
        src_dir = tmp_path / "source" / "my-article"
        _make_repo_with_content(str(src_dir), "article.md", "# My Article\n\nContent here.")

        payload = pack_article_repo(src_dir)

        # Ingest to a different location — dst_dir name must match arcname ("my-article")
        dst_parent = tmp_path / "dest"
        dst_parent.mkdir()
        dst_repo = dst_parent / "my-article"
        head = ingest_article_repo(dst_repo, {"repo_bundle": payload})
        assert len(head) == 40  # SHA hex
        assert (dst_repo / "article.md").read_text() == "# My Article\n\nContent here."
        assert (dst_repo / ".git").is_dir()

    def test_missing_bundle_key_raises(self, tmp_path):
        """Payload without 'repo_bundle' key raises KeyError."""
        from peerpedia_core.storage.git.archive import ingest_article_repo

        dst = tmp_path / "dest" / "missing-key"
        with pytest.raises(KeyError):
            ingest_article_repo(dst, {"wrong_key": "data"})


# ═══════════════════════════════════════════════════════════════════════════════
# ingest_article
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# pack_article_repo round-trip
# ═══════════════════════════════════════════════════════════════════════════════


class TestPackArticleRepo:
    def test_preserves_git_history(self, tmp_path):
        """Multiple commits survive pack → unpack — git history is intact."""
        from peerpedia_core.storage.git.archive import ingest_article_repo, pack_article_repo
        from peerpedia_core.storage.git.ops import init_article_repo
        from peerpedia_core.storage.git.read import get_commit_history

        src_dir = tmp_path / "source" / "my-article"
        rp = init_article_repo(src_dir)
        (rp / "article.md").write_text("Version 1")
        commit_article_signed(rp, "First commit", "Author", "author@peerpedia")
        (rp / "article.md").write_text("Version 2")
        commit_article_signed(rp, "Second commit", "Author", "author@peerpedia")

        payload = pack_article_repo(src_dir)

        dst_parent = tmp_path / "dest"
        dst_parent.mkdir()
        dst_repo = dst_parent / "my-article"
        ingest_article_repo(dst_repo, {"repo_bundle": payload})

        history = get_commit_history(dst_repo)
        assert len(history) >= 2
        # commit_article_signed appends a Pubkey: trailer to the message
        assert history[0]["message"].startswith("Second commit")
        assert history[1]["message"].startswith("First commit")
