# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Notification lifecycle."""

from tests.core.conftest import make_signing_key, make_user


def _make_article(db, articles_dir, author, title="Test"):
    from peerpedia_core.core import create_article_with_content
    key, pubkey = make_signing_key(f"{author.id}@peerpedia")
    return create_article_with_content(
        db, title=title, content="# X", author_ids=[author.id],
        signing_key_bytes=key, pubkey_hex=pubkey,
    )
    db.flush()


class TestNotifications:
    def test_create_and_mark_read(self, db, articles_dir):
        from peerpedia_core.core.notifications import (
            create_notification, get_notifications_for_user, mark_read,
        )
        user = make_user(db, "User")
        author = make_user(db, "Author")
        a = _make_article(db, articles_dir, author)

        n = create_notification(
            db, user_id=user.id, event="review_submitted",
            article_id=a["id"], actor_id=author.id,
            message="New review on your article",
        )
        assert n.id is not None
        assert n.read == 0

        notifs = get_notifications_for_user(db, user.id)
        assert len(notifs) == 1

        mark_read(db, n.id)
        assert n.read == 1

    def test_count_unread(self, db, articles_dir):
        from peerpedia_core.core.notifications import (
            count_unread_notifications, create_notification,
        )
        user = make_user(db, "User")
        author = make_user(db, "Author")
        a = _make_article(db, articles_dir, author)

        create_notification(db, user_id=user.id, event="review", article_id=a["id"],
                            actor_id=author.id, message="m1")
        create_notification(db, user_id=user.id, event="follow", article_id=None,
                            actor_id=author.id, message="m2")
        assert count_unread_notifications(db, user.id) == 2
