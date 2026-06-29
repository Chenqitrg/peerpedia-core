# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Notification commands."""

import pytest

from peerpedia_core.exceptions import NotAuthorizedError
from tests.app.conftest import login


class TestNotifications:
    def test_list_empty(self, ctx):
        from peerpedia_core.app.commands.notification import list_notifications
        alice = login(ctx, "Alice")
        result = list_notifications(alice)
        assert result.data["items"] == []
        assert result.data["unread_count"] == 0

    def test_list_with_notifications(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.notification import list_notifications
        from peerpedia_core.core.notifications import create_notification

        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = create(alice, title="Paper", content="# X")
        create_notification(
            ctx.db, user_id=alice.current_user_id, event="review_submitted",
            article_id=a.data["id"], actor_id=bob.current_user_id,
            message="Bob reviewed your article",
        )
        ctx.db.commit()

        result = list_notifications(alice)
        assert result.data["unread_count"] == 1
        items = result.data["items"]
        assert len(items) == 1
        assert items[0]["event"] == "review_submitted"
        assert items[0]["read"] is False

    def test_mark_read(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.notification import list_notifications, mark_read_notification
        from peerpedia_core.core.notifications import create_notification

        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = create(alice, title="Paper", content="# X")
        create_notification(
            ctx.db, user_id=alice.current_user_id, event="follow",
            article_id=None, actor_id=bob.current_user_id,
            message="Bob followed you",
        )
        ctx.db.commit()

        items = list_notifications(alice).data["items"]
        assert items[0]["read"] is False

        r = mark_read_notification(alice, notification_id=items[0]["id"])
        assert r.code == "OK"

        assert list_notifications(alice).data["unread_count"] == 0

    def test_cannot_mark_others_notification(self, ctx, articles_dir):
        """Bob MUST NOT be able to mark Alice's notification as read."""
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.notification import mark_read_notification
        from peerpedia_core.core.notifications import create_notification

        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = create(alice, title="Paper", content="# X")
        create_notification(
            ctx.db, user_id=alice.current_user_id, event="follow",
            article_id=None, actor_id=bob.current_user_id,
            message="Bob followed you",
        )
        ctx.db.commit()

        # Get Alice's notification
        from peerpedia_core.app.commands.notification import list_notifications
        notif = list_notifications(alice).data["items"][0]

        with pytest.raises(NotAuthorizedError, match="NOT_YOUR_NOTIFICATION"):
            mark_read_notification(bob, notification_id=notif["id"])
