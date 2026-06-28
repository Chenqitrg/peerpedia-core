# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Article lifecycle — create, update, delete, fork."""

from tests.core.conftest import make_signing_key, make_user


# ═══════════════════════════════════════════════════════════════════════════════
# S1 — Create, update, delete, fork (full lifecycle)
# ═══════════════════════════════════════════════════════════════════════════════


class TestArticleLifecycle:
    def test_create_and_retrieve(self, db, articles_dir):
        from peerpedia_core.core import create_article_with_content, get_article
        author = make_user(db, "Author")
        key, pubkey = make_signing_key("author@peerpedia")

        result = create_article_with_content(
            db, title="My Paper", content="# Intro\n\nHello.",
            author_ids=[author.id], signing_key_bytes=key, pubkey_hex=pubkey,
        )
        fetched = get_article(db, result["id"])
        assert fetched.title == "My Paper"
        assert fetched.status == "draft"

    def test_create_then_update(self, db, articles_dir):
        from peerpedia_core.core import create_article_with_content, get_article, update_article_content
        author = make_user(db, "Author")
        key, pubkey = make_signing_key("author@peerpedia")

        a = create_article_with_content(
            db, title="V1", content="# Old", author_ids=[author.id],
            signing_key_bytes=key, pubkey_hex=pubkey,
        )
        key2, pubkey2 = make_signing_key("author@peerpedia")
        update_article_content(
            db, a["id"], content="# New Content", message="update", user_id=author.id,
            signing_key_bytes=key2, pubkey_hex=pubkey2,
        )
        fetched = get_article(db, a["id"])
        assert fetched.updated_at is not None

    def test_create_then_delete(self, db, articles_dir):
        from peerpedia_core.core import create_article_with_content, delete_article, get_article
        from peerpedia_core.config.paths import article_repo_path
        author = make_user(db, "Author")
        key, pubkey = make_signing_key("author@peerpedia")

        a = create_article_with_content(
            db, title="To Delete", content="# Bye", author_ids=[author.id],
            signing_key_bytes=key, pubkey_hex=pubkey,
        )
        aid = a["id"]
        assert get_article(db, aid) is not None

        delete_article(db, aid, user_id=author.id)
        assert get_article(db, aid) is None
        assert not article_repo_path(aid).exists()

    def test_fork_creates_new_article(self, db, articles_dir):
        from peerpedia_core.core import create_article_with_content, fork_article, get_article
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer
        author = make_user(db, "Author")
        forker = make_user(db, "Forker")
        key, pubkey = make_signing_key("author@peerpedia")

        orig = create_article_with_content(
            db, title="Original", content="# Original", author_ids=[author.id],
            signing_key_bytes=key, pubkey_hex=pubkey,
        )
        # Add forker directly via storage layer (bypasses the NOT_MAINTAINER guard)
        add_maintainer(db, orig["id"], forker.id)
        db.flush()
        result = fork_article(db, orig["id"], forker.id)
        fork = get_article(db, result["id"])
        assert fork.forked_from == orig["id"]


# ═══════════════════════════════════════════════════════════════════════════════
# S2 — Diff
# ═══════════════════════════════════════════════════════════════════════════════


class TestArticleDiff:
    def test_diff_between_two_commits(self, db, articles_dir):
        from peerpedia_core.core import create_article_with_content, diff_article, update_article_content
        from peerpedia_core.config.paths import article_repo_path
        from peerpedia_core.storage.git import get_commit_history
        author = make_user(db, "Author")
        key, pubkey = make_signing_key("author@peerpedia")

        a = create_article_with_content(
            db, title="Diff Test", content="line1\n", author_ids=[author.id],
            signing_key_bytes=key, pubkey_hex=pubkey,
        )
        rp = article_repo_path(a["id"])
        history = get_commit_history(rp)
        h2 = history[0]["hash"]

        key2, pubkey2 = make_signing_key("author@peerpedia")
        update_article_content(
            db, a["id"], content="line1\nline2\n", message="update", user_id=author.id,
            signing_key_bytes=key2, pubkey_hex=pubkey2,
        )
        history = get_commit_history(rp)
        h3 = history[0]["hash"]

        result = diff_article(a["id"], h2, h3)
        assert "diff_text" in result
        assert "line2" in result["diff_text"]
