# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for storage/db/ingest.py — P2P sync data ingestion functions."""

import pytest

from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.types.entities import (
    ArticleMetaExchange,
    BookmarkExchange,
    FollowExchange,
    MaintainerExchange,
    NotificationExchange,
    ShareExchange,
    UserExchange,
)

from tests.crud.conftest import make_article, make_user


# ═══════════════════════════════════════════════════════════════════════════════
# ingest_users
# ═══════════════════════════════════════════════════════════════════════════════


class TestIngestUsers:
    def test_inserts_new_users(self, engine):
        """UserExchange entries become UserStorage rows — lazy social discovery."""
        from peerpedia_core.storage.db.ingest import ingest_users

        session = get_session(engine)
        entries = [
            UserExchange(id="peer-alice", name="Alice", address="peer.example.com"),
            UserExchange(id="peer-bob", name="Bob"),
        ]
        count = ingest_users(session, entries)
        assert count == 2
        # Verify users were created
        from peerpedia_core.storage.db.crud_user import get_user_by_id
        assert get_user_by_id(session, "peer-alice") is not None
        assert get_user_by_id(session, "peer-bob") is not None
        session.close()

    def test_idempotent_on_duplicate(self, engine):
        """Duplicate IDs don't crash — ensure_user is idempotent."""
        from peerpedia_core.storage.db.ingest import ingest_users

        session = get_session(engine)
        entries = [UserExchange(id="peer-c", name="Carol")]
        ingest_users(session, entries)
        # Second ingestion with same ID should be harmless
        count = ingest_users(session, entries)
        assert count == 1  # len(entries) is still returned
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ingest_following / sync_following
# ═══════════════════════════════════════════════════════════════════════════════


class TestIngestFollowing:
    def test_adds_follows(self, engine):
        """FollowExchange entries create FollowStorage rows for the follower."""
        from peerpedia_core.storage.db.ingest import ingest_following

        session = get_session(engine)
        alice = make_user(session, "alice")
        bob = make_user(session, "bob")
        carol = make_user(session, "carol")
        entries = [FollowExchange(id=bob.id), FollowExchange(id=carol.id)]
        count = ingest_following(session, alice.id, entries)
        assert count == 2
        from peerpedia_core.storage.db.crud_follow import get_following
        assert {u.id for u in get_following(session, alice.id)} == {bob.id, carol.id}
        session.close()


class TestSyncFollowing:
    def test_adds_and_prunes_stale_follows(self, engine):
        """sync_following soft-deletes follows not in the new set —
        ensures remote server is the source of truth."""
        from peerpedia_core.storage.db.ingest import ingest_following, sync_following

        session = get_session(engine)
        alice = make_user(session, "alice")
        bob = make_user(session, "bob")
        carol = make_user(session, "carol")

        # First: ingest both follows
        ingest_following(session, alice.id,
                        [FollowExchange(id=bob.id), FollowExchange(id=carol.id)])

        # Then sync with only bob — carol should be pruned
        sync_following(session, alice.id, [FollowExchange(id=bob.id)])

        from peerpedia_core.storage.db.models import FollowStorage
        all_follows = session.query(FollowStorage).filter(
            FollowStorage.follower_id == alice.id,
        ).all()
        assert len(all_follows) == 2  # both rows still exist
        # Carol's follow is soft-deleted
        carol_follow = [f for f in all_follows if f.followed_id == carol.id][0]
        assert carol_follow.deleted_at is not None
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ingest_followers / sync_followers
# ═══════════════════════════════════════════════════════════════════════════════


class TestIngestFollowers:
    def test_adds_followers(self, engine):
        """Follower relationships ingested symmetrically to following."""
        from peerpedia_core.storage.db.ingest import ingest_followers

        session = get_session(engine)
        alice = make_user(session, "alice")
        bob = make_user(session, "bob")
        entries = [FollowExchange(id=bob.id)]
        count = ingest_followers(session, alice.id, entries)
        assert count == 1
        from peerpedia_core.storage.db.crud_follow import get_followers
        assert {u.id for u in get_followers(session, alice.id)} == {bob.id}
        session.close()


class TestSyncFollowers:
    def test_adds_and_prunes_stale_followers(self, engine):
        """sync_followers soft-deletes stale follower rows — symmetric to following."""
        from peerpedia_core.storage.db.ingest import ingest_followers, sync_followers

        session = get_session(engine)
        alice = make_user(session, "alice")
        bob = make_user(session, "bob")
        carol = make_user(session, "carol")

        ingest_followers(session, alice.id,
                        [FollowExchange(id=bob.id), FollowExchange(id=carol.id)])
        sync_followers(session, alice.id, [FollowExchange(id=bob.id)])

        from peerpedia_core.storage.db.models import FollowStorage
        all_follows = session.query(FollowStorage).filter(
            FollowStorage.followed_id == alice.id,
        ).all()
        carol_follow = [f for f in all_follows if f.follower_id == carol.id][0]
        assert carol_follow.deleted_at is not None
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ingest_articles
# ═══════════════════════════════════════════════════════════════════════════════


class TestIngestArticles:
    def test_creates_article_stubs(self, engine):
        """ArticleMetaExchange entries create article stubs in the DB."""
        from peerpedia_core.storage.db.ingest import ingest_articles

        session = get_session(engine)
        alice = make_user(session, "alice")
        entries = [
            ArticleMetaExchange(id="art-1", title="Paper One", status="published",
                               authors=(alice.id,)),
            ArticleMetaExchange(id="art-2", title="Paper Two", status="draft",
                               authors=(alice.id,)),
        ]
        count = ingest_articles(session, entries)
        assert count == 2
        from peerpedia_core.storage.db.crud_article import get_article
        assert get_article(session, "art-1") is not None
        assert get_article(session, "art-2") is not None
        session.close()

    def test_duplicate_returns_zero_count(self, engine):
        """Already-existing article stubs are not double-counted."""
        from peerpedia_core.storage.db.ingest import ingest_articles

        session = get_session(engine)
        alice = make_user(session, "alice")
        entries = [ArticleMetaExchange(id="art-dup", title="Paper", status="draft",
                                       authors=(alice.id,))]
        first = ingest_articles(session, entries)
        second = ingest_articles(session, entries)
        assert first == 1
        assert second == 0  # ensure_article_stub returns None for existing
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ingest_bookmarks
# ═══════════════════════════════════════════════════════════════════════════════


class TestIngestBookmarks:
    def test_adds_bookmarks(self, engine):
        """BookmarkExchange entries create BookmarkStorage rows."""
        from peerpedia_core.storage.db.ingest import ingest_bookmarks

        session = get_session(engine)
        alice = make_user(session, "alice")
        article = make_article(session, authors=[alice.id])
        entries = [BookmarkExchange(article_id=article.id)]
        count = ingest_bookmarks(session, alice.id, entries)
        assert count == 1
        from peerpedia_core.storage.db.crud_bookmark import is_bookmarked
        assert is_bookmarked(session, alice.id, article.id)
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ingest_maintainers
# ═══════════════════════════════════════════════════════════════════════════════


class TestIngestMaintainers:
    def test_adds_maintainers(self, engine):
        """MaintainerExchange entries create ScriptMaintainerStorage rows."""
        from peerpedia_core.storage.db.ingest import ingest_maintainers

        session = get_session(engine)
        alice = make_user(session, "alice")
        bob = make_user(session, "bob")
        article = make_article(session, authors=[alice.id])
        entries = [MaintainerExchange(user_id=bob.id)]
        count = ingest_maintainers(session, article.id, entries)
        assert count == 1
        from peerpedia_core.storage.db.crud_maintainer import is_maintainer
        assert is_maintainer(session, article.id, bob.id)
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ingest_shares
# ═══════════════════════════════════════════════════════════════════════════════


class TestIngestShares:
    def test_adds_shares(self, engine):
        """ShareExchange entries create ShareStorage rows."""
        from peerpedia_core.storage.db.ingest import ingest_shares

        session = get_session(engine)
        alice = make_user(session, "alice")
        article = make_article(session, authors=[alice.id])
        entries = [ShareExchange(article_id=article.id, comment="Check this out")]
        count = ingest_shares(session, alice.id, entries)
        assert count == 1
        from peerpedia_core.storage.db.crud_share import is_shared
        assert is_shared(session, alice.id, article.id)
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ingest_notifications
# ═══════════════════════════════════════════════════════════════════════════════


class TestIngestNotifications:
    def test_creates_notifications(self, engine):
        """NotificationExchange entries create NotificationStorage rows via ensure_notification."""
        from peerpedia_core.storage.db.ingest import ingest_notifications

        session = get_session(engine)
        alice = make_user(session, "alice")
        entries = [
            NotificationExchange(event="review", message="New review received"),
        ]
        count = ingest_notifications(session, alice.id, entries)
        assert count == 1

        from peerpedia_core.storage.db.crud_notification import get_notifications
        results = get_notifications(session, alice.id)
        assert len(results) == 1
        assert results[0].event == "review"
        session.close()

    def test_read_flag_is_set(self, engine):
        """When entry.read=True, the notification is marked as read after creation."""
        from peerpedia_core.storage.db.ingest import ingest_notifications

        session = get_session(engine)
        alice = make_user(session, "alice")
        entries = [
            NotificationExchange(event="share", message="Shared", read=True),
        ]
        ingest_notifications(session, alice.id, entries)

        from peerpedia_core.storage.db.crud_notification import get_notifications
        results = get_notifications(session, alice.id)
        assert results[0].read == 1
        session.close()

    def test_dedup_notifications(self, engine):
        """Same notification ingested twice doesn't create duplicates —
        ensure_notification is the underlying dedup mechanism."""
        from peerpedia_core.storage.db.ingest import ingest_notifications

        session = get_session(engine)
        alice = make_user(session, "alice")
        entry = NotificationExchange(event="merge", message="Merge proposed")
        ingest_notifications(session, alice.id, [entry])
        ingest_notifications(session, alice.id, [entry])

        from peerpedia_core.storage.db.crud_notification import get_notifications
        results = get_notifications(session, alice.id)
        assert len(results) == 1  # dedup'd
        session.close()
