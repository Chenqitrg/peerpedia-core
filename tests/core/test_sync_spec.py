# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Spec: Sync protocol — article sync and social graph discovery.

STATUS: LOCKED — these define product behavior for P2P sync operations.
"""

from unittest.mock import Mock

import pytest

from peerpedia_core.exceptions import ProtocolError, TransportError
from peerpedia_core.transport import Transport

from tests.core.conftest import make_signing_key, make_user


def _article(db, author, *, title="Test", content="# X"):
    from peerpedia_core.core import create_article_with_content
    key, pubkey = make_signing_key(f"{author.id}@peerpedia")
    result = create_article_with_content(
        db, title=title, content=content,
        author_ids=[author.id], signing_key_bytes=key, pubkey_hex=pubkey,
    )
    db.flush()
    return result


def _mock_transport(**overrides):
    """Build a Transport with all callbacks mocked — override specific ones as needed."""
    m = Mock()
    defaults = {
        "ancestor_probe": m.ancestor_probe,
        "fetch_head": m.fetch_head,
        "push_bundle": m.push_bundle,
        "fetch_bundle": m.fetch_bundle,
        "fetch_repo": m.fetch_repo,
        "push_repo": m.push_repo,
        "fetch_source": m.fetch_source,
        "fetch_following": m.fetch_following,
        "fetch_followers": m.fetch_followers,
        "fetch_shares": m.fetch_shares,
        "fetch_notifications": m.fetch_notifications,
        "fetch_user_articles": m.fetch_user_articles,
        "fetch_search": m.fetch_search,
        "fetch_meta": m.fetch_meta,
        "fetch_peers": m.fetch_peers,
        "fetch_school": m.fetch_school,
        "fetch_user": m.fetch_user,
        "push_peer_registration": m.push_peer_registration,
        "push_follow": m.push_follow,
        "push_unfollow": m.push_unfollow,
        "push_key_rotation": m.push_key_rotation,
        "push_share": m.push_share,
        "push_share_remove": m.push_share_remove,
        "is_online": m.is_online,
        "check_clock_skew": m.check_clock_skew,
    }
    defaults.update(overrides)
    return Transport(**defaults)


# ═══════════════════════════════════════════════════════════════════════════════
# Article sync
# ═══════════════════════════════════════════════════════════════════════════════


class TestSyncArticle:
    def test_no_local_repo_returns_unsynced(self, db, articles_dir):
        """When the article doesn't exist locally, sync_article
        returns {"synced": False, "head": None} — caller should pull_new_article."""
        from peerpedia_core.core.sync_article import sync_article

        transport = _mock_transport()
        result = sync_article(db, transport, "https://peer.example.com", "nonexistent-id")
        assert result["synced"] is False
        assert result["head"] is None

    def test_already_in_sync_returns_synced(self, db, articles_dir):
        """When server HEAD equals local HEAD, sync_article returns synced=True
        with no bundle transfer needed."""
        from peerpedia_core.core import sync_article as sync_mod
        from peerpedia_core.storage.git import get_head_hash
        from peerpedia_core.config.paths import ARTICLES_DIR, article_repo_path

        author = make_user(db, "Author")
        a = _article(db, author)
        local_head = get_head_hash(article_repo_path(a["id"]))

        m = Mock()
        m.is_online.return_value = True
        m.check_clock_skew.return_value = 0
        m.fetch_head.return_value = local_head  # server matches local
        transport = _mock_transport(
            is_online=m.is_online,
            check_clock_skew=m.check_clock_skew,
            fetch_head=m.fetch_head,
        )
        # sync_article uses its own DEFAULT_ARTICLES_DIR (imported at module level)
        # which may be stale — redirect to the patched ARTICLES_DIR
        orig = sync_mod.DEFAULT_ARTICLES_DIR
        sync_mod.DEFAULT_ARTICLES_DIR = ARTICLES_DIR
        try:
            result = sync_mod.sync_article(db, transport, "https://peer.example.com", a["id"])
        finally:
            sync_mod.DEFAULT_ARTICLES_DIR = orig
        assert result["synced"] is True
        assert result["head"] == local_head

    def test_server_unreachable_raises_transport_error(self, db, articles_dir):
        """When is_online returns False, sync_article raises TransportError —
        caller should retry later or check network."""
        from peerpedia_core.core import sync_article as sync_mod
        from peerpedia_core.config.paths import ARTICLES_DIR

        author = make_user(db, "Author")
        a = _article(db, author)
        m = Mock()
        m.is_online.return_value = False
        transport = _mock_transport(is_online=m.is_online)

        orig = sync_mod.DEFAULT_ARTICLES_DIR
        sync_mod.DEFAULT_ARTICLES_DIR = ARTICLES_DIR
        try:
            with pytest.raises(TransportError):
                sync_mod.sync_article(db, transport, "https://offline.example.com", a["id"])
        finally:
            sync_mod.DEFAULT_ARTICLES_DIR = orig

    def test_clock_skew_rejects_sync(self, db, articles_dir):
        """Clock skew > 30 seconds raises ProtocolError —
        commit timestamps would be unreliable for priority claims."""
        from peerpedia_core.core import sync_article as sync_mod
        from peerpedia_core.config.paths import ARTICLES_DIR

        author = make_user(db, "Author")
        a = _article(db, author)
        m = Mock()
        m.is_online.return_value = True
        m.check_clock_skew.return_value = 300  # 5 min skew
        transport = _mock_transport(
            is_online=m.is_online,
            check_clock_skew=m.check_clock_skew,
        )

        orig = sync_mod.DEFAULT_ARTICLES_DIR
        sync_mod.DEFAULT_ARTICLES_DIR = ARTICLES_DIR
        try:
            with pytest.raises(ProtocolError):
                sync_mod.sync_article(db, transport, "https://skewed.example.com", a["id"])
        finally:
            sync_mod.DEFAULT_ARTICLES_DIR = orig


# ═══════════════════════════════════════════════════════════════════════════════
# Social graph discovery
# ═══════════════════════════════════════════════════════════════════════════════


class TestDiscoverFollowing:
    def test_ingests_following_data(self, db, articles_dir):
        """discover_following fetches following list from server and ingests
        users + follow relationships into the local DB."""
        from peerpedia_core.core.sync_social import discover_following

        alice = make_user(db, "Alice")
        m = Mock()
        m.fetch_following.return_value = [
            {"id": "peer-bob", "name": "Bob"},
            {"id": "peer-carol", "name": "Carol"},
        ]
        transport = _mock_transport(fetch_following=m.fetch_following)

        count = discover_following(db, transport, "https://peer.example.com", alice.id)
        assert count == 2

        # Both users should now exist in DB
        from peerpedia_core.storage.db.crud_user import get_user_by_id
        assert get_user_by_id(db, "peer-bob") is not None
        assert get_user_by_id(db, "peer-carol") is not None

    def test_empty_response_does_not_crash(self, db, articles_dir):
        """Empty following list returns 0 — no users ingested, no error."""
        from peerpedia_core.core.sync_social import discover_following

        alice = make_user(db, "Alice")
        m = Mock()
        m.fetch_following.return_value = []  # empty list
        transport = _mock_transport(fetch_following=m.fetch_following)

        count = discover_following(db, transport, "https://peer.example.com", alice.id)
        assert count == 0


class TestDiscoverArticles:
    def test_ingests_article_stubs(self, db, articles_dir):
        """discover_articles fetches article metadata from server and creates
        stubs for each article authored by the given user."""
        from peerpedia_core.core.sync_social import discover_articles

        alice = make_user(db, "Alice")
        m = Mock()
        m.fetch_user_articles.return_value = [
            {"id": "art-1", "title": "Paper One", "status": "published",
             "authors": [alice.id]},
            {"id": "art-2", "title": "Paper Two", "status": "draft",
             "authors": [alice.id]},
        ]
        transport = _mock_transport(fetch_user_articles=m.fetch_user_articles)

        count = discover_articles(db, transport, "https://peer.example.com", alice.id)
        assert count == 2

        from peerpedia_core.storage.db.crud_article import get_article
        assert get_article(db, "art-1") is not None
        assert get_article(db, "art-2") is not None
