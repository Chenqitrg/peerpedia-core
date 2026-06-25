# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for notification CRUD, facade, and event emissions."""

import pytest
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import User


@pytest.fixture
def db(engine):
    session = get_session(engine)
    yield session
    session.rollback()
    session.close()


def _make_user(db, user_id: str, name: str = "Test User"):
    u = User(id=user_id, name=name, public_key="00" * 32, salt="00" * 16)
    db.add(u)
    db.flush()
    return u


# ── CRUD Tests ───────────────────────────────────────────────────────────


class TestCrudCreateNotification:
    def test_create_minimal(self, db):
        from peerpedia_core.storage.db.crud_notification import create_notification

        _make_user(db, "user-1")
        n = create_notification(db, user_id="user-1", event="new_follower",
                                message="Someone followed you")
        assert n.id is not None
        assert n.user_id == "user-1"
        assert n.event == "new_follower"
        assert n.message == "Someone followed you"
        assert n.read == 0
        assert n.article_id is None
        assert n.actor_id is None

    def test_create_with_optionals(self, db):
        from peerpedia_core.storage.db.crud_notification import create_notification

        _make_user(db, "user-1")
        _make_user(db, "user-2", "Actor")
        n = create_notification(
            db, user_id="user-1", event="new_follower",
            message="Someone followed you", actor_id="user-2",
        )
        assert n.actor_id == "user-2"
        assert n.article_id is None


class TestCrudGetNotifications:
    def test_unread_only(self, db):
        from peerpedia_core.storage.db.crud_notification import (
            create_notification, get_notifications, mark_read,
        )

        _make_user(db, "user-1")
        n1 = create_notification(db, user_id="user-1", event="new_follower",
                                 message="Msg 1")
        n2 = create_notification(db, user_id="user-1", event="new_follower",
                                 message="Msg 2")
        mark_read(db, n1.id)

        unread = get_notifications(db, "user-1", unread_only=True)
        assert len(unread) == 1
        assert unread[0].id == n2.id

    def test_all(self, db):
        from peerpedia_core.storage.db.crud_notification import (
            create_notification, get_notifications, mark_read,
        )

        _make_user(db, "user-1")
        n1 = create_notification(db, user_id="user-1", event="new_follower",
                                 message="Msg 1")
        mark_read(db, n1.id)

        all_notifs = get_notifications(db, "user-1")
        assert len(all_notifs) == 1

    def test_isolation(self, db):
        from peerpedia_core.storage.db.crud_notification import create_notification, get_notifications

        _make_user(db, "user-a")
        _make_user(db, "user-b")
        create_notification(db, user_id="user-a", event="new_follower",
                            message="For A")
        found = get_notifications(db, "user-b")
        assert len(found) == 0

    def test_newest_first(self, db):
        from peerpedia_core.storage.db.crud_notification import create_notification, get_notifications

        _make_user(db, "user-1")
        create_notification(db, user_id="user-1", event="new_follower",
                            message="First")
        create_notification(db, user_id="user-1", event="new_follower",
                            message="Second")
        results = get_notifications(db, "user-1", limit=50)
        assert results[0].message == "Second"
        assert results[1].message == "First"


class TestCrudMarkRead:
    def test_success(self, db):
        from peerpedia_core.storage.db.crud_notification import create_notification, mark_read

        _make_user(db, "user-1")
        n = create_notification(db, user_id="user-1", event="new_follower",
                                message="Test")
        mark_read(db, n.id)
        assert n.read == 1

    def test_idempotent(self, db):
        from peerpedia_core.storage.db.crud_notification import create_notification, mark_read

        _make_user(db, "user-1")
        n = create_notification(db, user_id="user-1", event="new_follower",
                                message="Test")
        mark_read(db, n.id)
        mark_read(db, n.id)  # second call should not raise
        assert n.read == 1

    def test_not_found_raises(self, db):
        from peerpedia_core.storage.db.crud_notification import mark_read

        with pytest.raises(ValueError, match="not found"):
            mark_read(db, "nonexistent-id")


class TestCrudCountUnread:
    def test_counts_correctly(self, db):
        from peerpedia_core.storage.db.crud_notification import (
            count_unread_notifications, create_notification, mark_read,
        )

        _make_user(db, "user-1")
        create_notification(db, user_id="user-1", event="new_follower",
                            message="1")
        n2 = create_notification(db, user_id="user-1", event="new_follower",
                                 message="2")
        mark_read(db, n2.id)
        assert count_unread_notifications(db, "user-1") == 1

    def test_zero(self, db):
        from peerpedia_core.storage.db.crud_notification import count_unread_notifications

        _make_user(db, "user-1")
        assert count_unread_notifications(db, "user-1") == 0


# ── Facade Tests ─────────────────────────────────────────────────────────


class TestCommandsFacade:
    def test_create_delegates(self, db):
        from peerpedia_core.commands.notifications import create_notification

        _make_user(db, "user-1")
        n = create_notification(db, user_id="user-1", event="new_follower",
                                message="Test")
        assert n.id is not None

    def test_get_delegates(self, db):
        from peerpedia_core.commands.notifications import (
            create_notification, get_notifications,
        )

        _make_user(db, "user-1")
        create_notification(db, user_id="user-1", event="new_follower",
                            message="Test")
        assert len(get_notifications(db, "user-1", unread_only=True)) == 1

    def test_mark_read_delegates(self, db):
        from peerpedia_core.commands.notifications import create_notification, mark_read

        _make_user(db, "user-1")
        n = create_notification(db, user_id="user-1", event="new_follower",
                                message="Test")
        mark_read(db, n.id)
        assert n.read == 1

    def test_count_unread_notifications_delegates(self, db):
        from peerpedia_core.commands.notifications import count_unread_notifications, create_notification

        _make_user(db, "user-1")
        create_notification(db, user_id="user-1", event="new_follower",
                            message="Test")
        assert count_unread_notifications(db, "user-1") == 1


# ── Event Emission Tests ─────────────────────────────────────────────────


class TestNewFollowerNotification:
    def test_creates_notification(self, db):
        from peerpedia_core.commands.users import follow_user
        from peerpedia_core.storage.db.crud_notification import get_notifications

        _make_user(db, "follower-user", "Follower")
        _make_user(db, "followed-user", "Followed")

        follow_user(db, "follower-user", "followed-user")

        notifs = get_notifications(db, "followed-user", unread_only=True)
        assert len(notifs) == 1
        assert notifs[0].event == "new_follower"
        assert notifs[0].actor_id == "follower-user"
        assert "Follower" in notifs[0].message


class TestMergeProposedNotification:
    def test_creates_notification(self, db):
        from peerpedia_core.storage.db.crud_article import create_article
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer
        from peerpedia_core.storage.db.crud_notification import get_notifications
        from peerpedia_core.commands.merge import create_merge_proposal

        _make_user(db, "alice", "Alice")
        _make_user(db, "bob", "Bob")

        target = create_article(db, authors=["alice"], title="Target", id="art-target")
        add_maintainer(db, target.id, "alice")
        create_article(db, authors=["bob"], title="Fork", id="art-fork")
        db.flush()

        create_merge_proposal(db, "art-fork", target.id, "bob")
        db.flush()

        notifs = get_notifications(db, "alice", unread_only=True)
        assert len(notifs) == 1
        assert notifs[0].event == "merge_proposed"
        assert notifs[0].article_id == target.id
        assert notifs[0].actor_id == "bob"
