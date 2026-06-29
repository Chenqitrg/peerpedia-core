# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: App-level guards and reference resolution."""

import pytest

from peerpedia_core.exceptions import (
    BadRequestError, NotFoundError, NotAuthorizedError,
)
from tests.app.conftest import login


# ═══════════════════════════════════════════════════════════════════════════════
# require_user
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireUser:
    def test_logged_in_returns_id(self, ctx):
        from peerpedia_core.app.refs import require_user
        alice = login(ctx, "Alice")
        assert require_user(alice) == alice.current_user_id

    def test_not_logged_in_raises(self, ctx):
        from peerpedia_core.app.refs import require_user
        with pytest.raises(NotAuthorizedError, match="UNAUTHORIZED"):
            require_user(ctx)


# ═══════════════════════════════════════════════════════════════════════════════
# require_article
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireArticle:
    def test_by_exact_id(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.refs import require_article
        alice = login(ctx, "Alice")
        a = create(alice, title="Paper", content="# X")
        article = require_article(ctx.db, a.data["id"])
        assert article.id == a.data["id"]

    def test_by_title_keyword(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.refs import require_article
        alice = login(ctx, "Alice")
        a = create(alice, title="Quantum Mechanics 101", content="# Q")
        article = require_article(ctx.db, "Quantum")
        assert article.id == a.data["id"]

    def test_ambiguous_raises(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.refs import require_article
        alice = login(ctx, "Alice")
        create(alice, title="Quantum A", content="# A")
        create(alice, title="Quantum B", content="# B")
        with pytest.raises(BadRequestError, match="AMBIGUOUS_NAME"):
            require_article(ctx.db, "Quantum")

    def test_nonexistent_raises(self, ctx, articles_dir):
        from peerpedia_core.app.refs import require_article
        with pytest.raises(NotFoundError):
            require_article(ctx.db, "nonexistent-article-title")


# ═══════════════════════════════════════════════════════════════════════════════
# require_user_by_ref
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireUserByRef:
    def test_by_id(self, ctx):
        from peerpedia_core.app.refs import require_user_by_ref
        alice = login(ctx, "Alice")
        u = require_user_by_ref(ctx.db, alice.current_user_id)
        assert u.name == "Alice"

    def test_by_at_name(self, ctx):
        from peerpedia_core.app.refs import require_user_by_ref
        login(ctx, "Bob")
        u = require_user_by_ref(ctx.db, "@Bob")
        assert u.name == "Bob"

    def test_ambiguous_raises(self, ctx):
        from peerpedia_core.app.refs import require_user_by_ref
        login(ctx, "Alice")
        login(ctx, "Alice2")
        with pytest.raises(BadRequestError, match="AMBIGUOUS_NAME"):
            require_user_by_ref(ctx.db, "Alice")

    def test_nonexistent_raises(self, ctx):
        from peerpedia_core.app.refs import require_user_by_ref
        with pytest.raises(NotFoundError):
            require_user_by_ref(ctx.db, "NoSuchUser")


# ═══════════════════════════════════════════════════════════════════════════════
# guard_name_available
# ═══════════════════════════════════════════════════════════════════════════════


class TestGuardNameAvailable:
    def test_available(self, ctx):
        from peerpedia_core.app.refs import guard_name_available
        guard_name_available(ctx.db, "NewName")  # should not raise

    def test_taken_raises(self, ctx):
        from peerpedia_core.app.refs import guard_name_available
        login(ctx, "Alice")
        with pytest.raises(BadRequestError, match="DUPLICATE_NAME"):
            guard_name_available(ctx.db, "Alice")


# ═══════════════════════════════════════════════════════════════════════════════
# require_user_by_name
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireUserByName:
    def test_single_match(self, ctx):
        from peerpedia_core.app.refs import require_user_by_name
        login(ctx, "Charlie")
        uid = require_user_by_name(ctx.db, "Charlie")
        assert uid is not None

    def test_ambiguous_raises(self, ctx):
        from peerpedia_core.app.refs import require_user_by_name
        login(ctx, "Dup")
        login(ctx, "Dup")
        with pytest.raises(BadRequestError, match="AMBIGUOUS_NAME"):
            require_user_by_name(ctx.db, "Dup")

    def test_nonexistent_raises(self, ctx):
        from peerpedia_core.app.refs import require_user_by_name
        with pytest.raises(NotFoundError):
            require_user_by_name(ctx.db, "Nobody")

    def test_empty_name_raises(self, ctx):
        from peerpedia_core.app.refs import require_user_by_name
        with pytest.raises(BadRequestError, match="AMBIGUOUS_ARGS"):
            require_user_by_name(ctx.db, "")


# ═══════════════════════════════════════════════════════════════════════════════
# require_notification
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# guard_user_id_available
# ═══════════════════════════════════════════════════════════════════════════════


class TestGuardUserIdAvailable:
    def test_available(self, ctx):
        from peerpedia_core.app.refs import guard_user_id_available
        guard_user_id_available(ctx.db, "new-uuid-1234")  # should not raise

    def test_taken_raises(self, ctx):
        from peerpedia_core.app.refs import guard_user_id_available
        alice = login(ctx, "Alice")
        with pytest.raises(BadRequestError, match="DUPLICATE_USER_LOCAL"):
            guard_user_id_available(ctx.db, alice.current_user_id)


# ═══════════════════════════════════════════════════════════════════════════════
# require_notification
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireNotification:
    def test_own_notification(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.refs import require_notification
        from peerpedia_core.core.notifications import create_notification
        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = create(alice, title="P", content="# X")
        create_notification(
            ctx.db, user_id=alice.current_user_id, event="follow",
            article_id=a.data["id"], actor_id=bob.current_user_id,
            message="Bob followed you",
        )
        ctx.db.commit()

        from peerpedia_core.app.commands.notification import list_notifications
        nid = list_notifications(alice).data["items"][0]["id"]
        notif = require_notification(ctx.db, nid, alice.current_user_id)
        assert notif is not None

    def test_not_owned_raises(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.refs import require_notification
        from peerpedia_core.core.notifications import create_notification
        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = create(alice, title="P", content="# X")
        create_notification(
            ctx.db, user_id=alice.current_user_id, event="follow",
            article_id=a.data["id"], actor_id=bob.current_user_id,
            message="msg",
        )
        ctx.db.commit()

        from peerpedia_core.app.commands.notification import list_notifications
        nid = list_notifications(alice).data["items"][0]["id"]
        with pytest.raises(NotAuthorizedError, match="NOT_YOUR_NOTIFICATION"):
            require_notification(ctx.db, nid, bob.current_user_id)

    def test_nonexistent_raises(self, ctx):
        from peerpedia_core.app.refs import require_notification
        alice = login(ctx, "Alice")
        with pytest.raises(NotFoundError, match="NOTIFICATION_NOT_FOUND"):
            require_notification(ctx.db, "nonexistent-id", alice.current_user_id)
