# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Bookmarks, shares, maintainers — social features."""

import pytest

from peerpedia_core.exceptions import ConflictError
from tests.core.conftest import make_signing_key, make_user


def _make_article(db, articles_dir, author, title="Test"):
    from peerpedia_core.core import create_article_with_content
    key, pubkey = make_signing_key(f"{author.id}@peerpedia")
    result = create_article_with_content(
        db, title=title, content="# X", author_ids=[author.id],
        signing_key_bytes=key, pubkey_hex=pubkey,
    )
    db.flush()
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# S1 — Bookmarks
# ═══════════════════════════════════════════════════════════════════════════════


class TestBookmarks:
    def test_add_and_remove(self, db, articles_dir):
        from peerpedia_core.core.bookmarks import add_bookmark, get_bookmarks_for_user, remove_bookmark
        reader = make_user(db, "Reader")
        author = make_user(db, "Author")
        a = _make_article(db, articles_dir, author)

        add_bookmark(db, reader.id, a["id"])
        assert len(get_bookmarks_for_user(db, reader.id)) == 1

        remove_bookmark(db, reader.id, a["id"])
        assert len(get_bookmarks_for_user(db, reader.id)) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# S2 — Shares
# ═══════════════════════════════════════════════════════════════════════════════


class TestShares:
    def test_add_and_remove(self, db, articles_dir):
        from peerpedia_core.core.shares import add_share, get_shares_for_user, remove_share
        sharer = make_user(db, "Sharer")
        author = make_user(db, "Author")
        a = _make_article(db, articles_dir, author)

        s = add_share(db, sharer.id, a["id"], comment="Good read")
        assert s["sharer_id"] == sharer.id

        shares = get_shares_for_user(db, sharer.id)
        assert len(shares) == 1

        remove_share(db, sharer.id, a["id"])
        assert len(get_shares_for_user(db, sharer.id)) == 0

    def test_feed_shows_followed_shares(self, db, articles_dir):
        from peerpedia_core.core.shares import add_share, get_feed_shares
        from peerpedia_core.core.users import create_user, follow_user
        viewer = make_user(db, "Viewer")
        followed = make_user(db, "Followed")
        another = make_user(db, "Another")
        author = make_user(db, "Author")
        a = _make_article(db, articles_dir, author)

        follow_user(db, viewer.id, followed.id)
        add_share(db, followed.id, a["id"], comment="Check this")
        add_share(db, another.id, a["id"], comment="Me too")

        feed = get_feed_shares(db, viewer.id)
        # Only articles shared by followed users appear
        assert len(feed) == 1
        assert feed[0]["id"] == a["id"]


# ═══════════════════════════════════════════════════════════════════════════════
# S3 — Maintainers
# ═══════════════════════════════════════════════════════════════════════════════


class TestMaintainers:
    def test_author_is_maintainer_after_create(self, db, articles_dir):
        from peerpedia_core.core.maintainers import list_maintainers
        owner = make_user(db, "Owner")
        a = _make_article(db, articles_dir, owner)
        maintainers = list_maintainers(db, a["id"])
        assert owner.id in maintainers

    def test_add_maintainer_via_storage_layer(self, db, articles_dir):
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer, get_maintainer_ids
        owner = make_user(db, "Owner")
        helper = make_user(db, "Helper")
        a = _make_article(db, articles_dir, owner)
        # Storage-layer add bypasses authorization; the author is already a maintainer
        add_maintainer(db, a["id"], helper.id)
        db.flush()
        mids = get_maintainer_ids(db, a["id"])
        assert owner.id in mids
        assert helper.id in mids
