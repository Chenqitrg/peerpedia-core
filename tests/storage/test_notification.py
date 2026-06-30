# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for storage/db/crud_notification.py — notification CRUD operations."""

import pytest

from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.storage.db.engine import get_session

from tests.crud.conftest import make_article, make_user


# ═══════════════════════════════════════════════════════════════════════════════
# create_notification
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateNotification:
    def test_basic(self, engine):
        """Creates a notification with required fields — flush sets the id."""
        from peerpedia_core.storage.db.crud_notification import create_notification

        session = get_session(engine)
        user = make_user(session, "alice")
        n = create_notification(session, user_id=user.id, event="review", message="New review")
        assert n.id is not None
        assert n.user_id == user.id
        assert n.event == "review"
        assert n.message == "New review"
        assert n.read == 0
        session.close()

    def test_with_optional_fields(self, engine):
        """Optional article_id and actor_id are stored correctly."""
        from peerpedia_core.storage.db.crud_notification import create_notification

        session = get_session(engine)
        user = make_user(session, "alice")
        actor = make_user(session, "bob")
        article = make_article(session, authors=[user.id])
        n = create_notification(
            session,
            user_id=user.id, event="merge", message="Merge proposed",
            article_id=article.id, actor_id=actor.id,
        )
        assert n.article_id == article.id
        assert n.actor_id == actor.id
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ensure_notification
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnsureNotification:
    def test_creates_new(self, engine):
        """First call creates a notification — idempotent insert for sync."""
        from peerpedia_core.storage.db.crud_notification import ensure_notification

        session = get_session(engine)
        user = make_user(session, "alice")
        n = ensure_notification(session, user_id=user.id, event="share", message="Shared")
        assert n.id is not None
        session.close()

    def test_dedup_returns_existing(self, engine):
        """Same (user, event, actor, article, message) returns the existing row —
        prevents duplicate notifications from repeated syncs."""
        from peerpedia_core.storage.db.crud_notification import ensure_notification

        session = get_session(engine)
        user = make_user(session, "alice")
        actor = make_user(session, "bob")
        article = make_article(session, authors=[user.id])
        n1 = ensure_notification(
            session,
            user_id=user.id, event="review", message="Reviewed",
            article_id=article.id, actor_id=actor.id,
        )
        n2 = ensure_notification(
            session,
            user_id=user.id, event="review", message="Reviewed",
            article_id=article.id, actor_id=actor.id,
        )
        assert n1.id == n2.id
        session.close()

    def test_different_message_creates_new(self, engine):
        """Different message with same other fields creates a new notification."""
        from peerpedia_core.storage.db.crud_notification import ensure_notification

        session = get_session(engine)
        user = make_user(session, "alice")
        n1 = ensure_notification(session, user_id=user.id, event="review", message="First")
        n2 = ensure_notification(session, user_id=user.id, event="review", message="Second")
        assert n1.id != n2.id
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# get_notifications
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetNotifications:
    def test_newest_first(self, engine):
        """Notifications are returned newest first — user sees latest first."""
        from peerpedia_core.storage.db.crud_notification import create_notification, get_notifications

        session = get_session(engine)
        user = make_user(session, "alice")
        n1 = create_notification(session, user_id=user.id, event="e1", message="m1")
        n2 = create_notification(session, user_id=user.id, event="e2", message="m2")
        n3 = create_notification(session, user_id=user.id, event="e3", message="m3")
        results = get_notifications(session, user.id)
        assert [r.id for r in results] == [n3.id, n2.id, n1.id]
        session.close()

    def test_unread_only(self, engine):
        """unread_only=True filters out read notifications."""
        from peerpedia_core.storage.db.crud_notification import create_notification, get_notifications, mark_read

        session = get_session(engine)
        user = make_user(session, "alice")
        n1 = create_notification(session, user_id=user.id, event="e1", message="m1")
        n2 = create_notification(session, user_id=user.id, event="e2", message="m2")
        mark_read(session, n1.id)
        results = get_notifications(session, user.id, unread_only=True)
        assert len(results) == 1
        assert results[0].id == n2.id
        session.close()

    def test_respects_limit(self, engine):
        """limit caps the number of returned notifications."""
        from peerpedia_core.storage.db.crud_notification import create_notification, get_notifications

        session = get_session(engine)
        user = make_user(session, "alice")
        for i in range(5):
            create_notification(session, user_id=user.id, event=f"e{i}", message=f"m{i}")
        results = get_notifications(session, user.id, limit=2)
        assert len(results) == 2
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# mark_read
# ═══════════════════════════════════════════════════════════════════════════════


class TestMarkRead:
    def test_sets_read_flag(self, engine):
        """mark_read sets read=1 — notification marked as seen."""
        from peerpedia_core.storage.db.crud_notification import create_notification, mark_read

        session = get_session(engine)
        user = make_user(session, "alice")
        n = create_notification(session, user_id=user.id, event="e", message="m")
        mark_read(session, n.id)
        assert n.read == 1
        session.close()

    def test_already_read_noop(self, engine):
        """Marking an already-read notification is harmless — idempotent."""
        from peerpedia_core.storage.db.crud_notification import create_notification, mark_read

        session = get_session(engine)
        user = make_user(session, "alice")
        n = create_notification(session, user_id=user.id, event="e", message="m")
        mark_read(session, n.id)
        mark_read(session, n.id)  # second call should not error
        assert n.read == 1
        session.close()

    def test_not_found_raises(self, engine):
        """Non-existent notification id raises NotFoundError —
        caller must handle missing notification gracefully."""
        from peerpedia_core.storage.db.crud_notification import mark_read

        session = get_session(engine)
        with pytest.raises(NotFoundError, match="NOTIFICATION_NOT_FOUND"):
            mark_read(session, "nonexistent-id")
        session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# count_unread_notifications
# ═══════════════════════════════════════════════════════════════════════════════


class TestCountUnreadNotifications:
    def test_correct_count(self, engine):
        """Returns the exact number of unread notifications for a user —
        used for badge displays."""
        from peerpedia_core.storage.db.crud_notification import (
            count_unread_notifications, create_notification, mark_read,
        )

        session = get_session(engine)
        user = make_user(session, "alice")
        create_notification(session, user_id=user.id, event="e1", message="m1")
        n2 = create_notification(session, user_id=user.id, event="e2", message="m2")
        create_notification(session, user_id=user.id, event="e3", message="m3")
        mark_read(session, n2.id)
        assert count_unread_notifications(session, user.id) == 2
        session.close()

    def test_zero_when_all_read(self, engine):
        """Returns 0 when all notifications have been read."""
        from peerpedia_core.storage.db.crud_notification import (
            count_unread_notifications, create_notification, mark_read,
        )

        session = get_session(engine)
        user = make_user(session, "alice")
        n = create_notification(session, user_id=user.id, event="e", message="m")
        mark_read(session, n.id)
        assert count_unread_notifications(session, user.id) == 0
        session.close()
