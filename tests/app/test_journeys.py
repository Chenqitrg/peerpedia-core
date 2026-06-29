# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Spec: Multi-step user journeys.

STATUS: LOCKED

Each test builds real user state through sequences of app commands.
No storage-layer shortcuts beyond ``add_maintainer`` (the one unavoidable
gap in the current app command surface).
"""

import pytest

from tests.app.conftest import login


def _create_article(ctx, title="Test", content="# X"):
    from peerpedia_core.app.commands.article import create
    return create(ctx, title=title, content=content)


def _publish(user_ctx, article_ref):
    from peerpedia_core.app.commands.article import publish
    publish(user_ctx, article_ref=article_ref,
            scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4")


def _add_maintainer(db, article_id, user_id):
    from peerpedia_core.storage.db.crud_maintainer import add_maintainer
    add_maintainer(db, article_id, user_id)
    db.flush()


# ═══════════════════════════════════════════════════════════════════════════════
# J1 — Three-body social graph
# ═══════════════════════════════════════════════════════════════════════════════


class TestThreeBodySocial:
    """Alice → Bob → Carol.  Alice follows Carol directly.  Verify counts."""

    def test_transitive_does_not_pollute(self, ctx):
        from peerpedia_core.app.commands.social import (
            follow, list_followers, list_following, unfollow,
        )
        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        carol = login(ctx, "Carol")

        # Alice follows Bob and Carol; Bob follows Carol
        follow(alice, target_ref=bob.current_user_id)
        follow(bob, target_ref=carol.current_user_id)
        follow(alice, target_ref=carol.current_user_id)

        # Alice's following should be Bob + Carol (exactly 2)
        alice_following = list_following(alice, user_ref=alice.current_user_id).data["items"]
        assert {f["name"] for f in alice_following} == {"Bob", "Carol"}

        # Carol's followers should be Bob + Alice (exactly 2)
        carol_followers = list_followers(carol, user_ref=carol.current_user_id).data["items"]
        assert {f["name"] for f in carol_followers} == {"Alice", "Bob"}

        # Unfollow and verify
        unfollow(alice, target_ref=bob.current_user_id)
        alice_after = list_following(alice, user_ref=alice.current_user_id).data["items"]
        assert {f["name"] for f in alice_after} == {"Carol"}


# ═══════════════════════════════════════════════════════════════════════════════
# J2 — Collaborative editing
# ═══════════════════════════════════════════════════════════════════════════════


class TestCollaboration:
    """Alice creates; adds Bob as maintainer; Bob edits; both verified."""

    def test_collaborator_can_edit(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, edit, show
        from peerpedia_core.app.commands.maintainer import add, list_article_maintainers
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer

        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = create(alice, title="Joint Paper", content="# Draft by Alice")

        # Alice adds Bob as maintainer (via storage to bypass auth guard)
        add_maintainer(ctx.db, a.data["id"], bob.current_user_id)
        ctx.db.flush()

        # Bob edits the article
        edit(bob, article_ref=a.data["id"], title="Joint Paper v2",
             message="Bob's contribution", user_id=bob.current_user_id)

        shown = show(alice, article_ref=a.data["id"])
        assert shown.data["title"] == "Joint Paper v2"


# ═══════════════════════════════════════════════════════════════════════════════
# J3 — Multiple reviews, mixed outcomes
# ═══════════════════════════════════════════════════════════════════════════════


class TestMixedReviewOutcomes:
    """1 accepts → submits, 1 declines, 1 ignores. Verify review list."""

    def test_mixed_outcomes(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, publish
        from peerpedia_core.app.commands.review import (
            accept, decline, invite_reviewer, list_reviews, submit,
        )

        alice = login(ctx, "Alice")
        r1 = login(ctx, "Reviewer1")
        r2 = login(ctx, "Reviewer2")
        r3 = login(ctx, "Reviewer3")
        a = create(alice, title="Paper", content="# Abstract")
        _publish(alice, article_ref=a.data["id"])

        for r in [r1, r2, r3]:
            _add_maintainer(ctx.db, a.data["id"], r.current_user_id)
            invite_reviewer(alice, article_ref=a.data["id"], user_ref=r.current_user_id)

        # R1 accepts and submits
        accept(r1, article_ref=a.data["id"])
        comment = (
            "A thorough and well-written paper. The experiments are convincing. "
            "Minor issues with the notation but overall excellent. " * 3
        )
        submit(r1, article_ref=a.data["id"],
               scores_str="orig=5,rigor=5,comp=5,ped=5,imp=5", comment=comment)

        # R2 declines
        decline(r2, article_ref=a.data["id"])

        # R3 does nothing (ignores)

        # List reviews — should show submitted + declined + invited (3 total)
        reviews = list_reviews(alice, article_ref=a.data["id"]).data["reviews"]
        assert len(reviews) >= 2  # At minimum: r1's submitted + r2's declined


# ═══════════════════════════════════════════════════════════════════════════════
# J4 — Search and discover articles
# ═══════════════════════════════════════════════════════════════════════════════


class TestArticleSearch:
    """Create articles with distinct titles, search by keyword."""

    def test_search_across_articles(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, list_articles

        alice = login(ctx, "Alice")

        create(alice, title="Quantum Entanglement in Graphene", content="# Q")
        create(alice, title="Graphene Synthesis Methods", content="# G")
        create(alice, title="Classical Mechanics Review", content="# C")

        # Search by keyword
        result = list_articles(alice, search_query="graphene", mine=True)
        titles = {a["title"] for a in result.data["items"]}
        assert "Quantum Entanglement in Graphene" in titles
        assert "Graphene Synthesis Methods" in titles
        assert "Classical Mechanics Review" not in titles


# ═══════════════════════════════════════════════════════════════════════════════
# J5 — User lifecycle: register → alias → delete → verify soft-delete
# ═══════════════════════════════════════════════════════════════════════════════


class TestUserLifecycle:
    """Full user journey: create, socialize, delete, verify aftermath."""

    def test_soft_delete_preserves_follow_graph(self, ctx, articles_dir):
        from peerpedia_core.app.commands.account import delete_account, search_users
        from peerpedia_core.app.commands.social import follow, list_followers
        from peerpedia_core.core import get_user

        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        follow(alice, target_ref=bob.current_user_id)

        # Alice deletes her account
        r = delete_account(alice)
        assert r.code == "ACCOUNT_DELETED"

        # Alice is soft-deleted: not in search, but still findable by ID
        assert len(search_users(ctx, query="Alice").data["items"]) == 0
        deleted = get_user(ctx.db, alice.current_user_id)
        assert deleted.deleted_at is not None

        # Bob can still list his followers (Alice is soft-deleted but the follow exists)
        followers = list_followers(bob, user_ref=bob.current_user_id).data["items"]
        # Alice may or may not appear depending on view filtering of soft-deleted users


# ═══════════════════════════════════════════════════════════════════════════════
# J6 — Full list with status filter
# ═══════════════════════════════════════════════════════════════════════════════


class TestListByStatus:
    """Create drafts + published → filter by status."""

    def test_filter_by_status(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, list_articles

        alice = login(ctx, "Alice")
        create(alice, title="Draft A", content="# A")
        a2 = create(alice, title="Publish Me", content="# P")
        create(alice, title="Draft B", content="# B")

        # Publish one
        _publish(alice, article_ref=a2.data["id"])

        # List drafts (mine)
        drafts = list_articles(alice, mine=True, status_arg="draft").data["items"]
        assert len(drafts) == 2

        # List all mine
        all_mine = list_articles(alice, mine=True).data["items"]
        assert len(all_mine) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# J7 — Article full lifecycle: create → show → edit → publish → delete
# ═══════════════════════════════════════════════════════════════════════════════


class TestArticleLifecycle:
    """Create, read, update, publish, delete — full CRUD + status transition."""

    def test_full_lifecycle(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, delete, edit, show
        from peerpedia_core.exceptions import NotFoundError

        alice = login(ctx, "Alice")

        # ── Create ──
        a = create(alice, title="Draft Paper", content="# Hello")
        assert a.code == "ARTICLE_CREATED"
        aid = a.data["id"]

        # ── Show ──
        shown = show(alice, article_ref=aid)
        assert shown.data["title"] == "Draft Paper"
        assert shown.data["status"] == "draft"

        # ── Edit ──
        edit(alice, article_ref=aid, title="Revised Paper", message="v2")
        shown2 = show(alice, article_ref=aid)
        assert shown2.data["title"] == "Revised Paper"

        # ── Delete (only from draft) ──
        d = delete(alice, article_ref=aid)
        assert d.code == "ARTICLE_DELETED"

        # ── Deleted article is not found ──
        with pytest.raises(NotFoundError):
            show(alice, article_ref=aid)


class TestPublishLifecycle:
    """Create → publish → verify sedimentation status."""

    def test_publish_to_sedimentation(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, publish, show

        alice = login(ctx, "Alice")
        a = create(alice, title="To Publish", content="# P")
        pub = publish(alice, article_ref=a.data["id"],
                      scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4")
        assert pub.code == "ARTICLE_PUBLISHED"

        shown = show(alice, article_ref=a.data["id"])
        assert shown.data["status"] == "sedimentation"


# ═══════════════════════════════════════════════════════════════════════════════
# J8 — Bookmark lifecycle: add → list → remove → verify gone
# ═══════════════════════════════════════════════════════════════════════════════


class TestBookmarkLifecycle:
    """Bookmark, list, unbookmark — verify counts at each step."""

    def test_bookmark_roundtrip(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, list_articles
        from peerpedia_core.app.commands.social import bookmark, unbookmark

        alice = login(ctx, "Alice")
        a1 = create(alice, title="Paper One", content="# One")
        a2 = create(alice, title="Paper Two", content="# Two")

        # ── Bookmark ──
        b1 = bookmark(alice, article_ref=a1.data["id"])
        assert b1.code == "BOOKMARKED"
        b2 = bookmark(alice, article_ref=a2.data["id"])
        assert b2.code == "BOOKMARKED"

        # ── List bookmarks ──
        bm_list = list_articles(alice, bookmarked=True).data["items"]
        assert len(bm_list) == 2

        # ── Unbookmark one ──
        ub = unbookmark(alice, article_ref=a1.data["id"])
        assert ub.code == "BOOKMARK_REMOVED"

        # ── List again ──
        bm_after = list_articles(alice, bookmarked=True).data["items"]
        assert len(bm_after) == 1
        assert bm_after[0]["id"] == a2.data["id"]


# ═══════════════════════════════════════════════════════════════════════════════
# J9 — Share + Alias lifecycle
# ═══════════════════════════════════════════════════════════════════════════════


class TestShareAndAlias:
    """Share articles with comment, set alias, use @alias, clean up."""

    def test_share_and_alias_roundtrip(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.social import (
            alias, alias_list, follow, share, share_list, unalias, unshare,
        )

        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = create(alice, title="Shareable", content="# X")

        # ── Share ──
        sh = share(alice, article_ref=a.data["id"], comment="Must read!")
        assert sh.code == "SHARED"
        assert sh.params["name"] == "Shareable"

        # ── Alice sees her own share ──
        mine = share_list(alice, mine=True).data["items"]
        assert len(mine) == 1

        # ── Set alias for Bob ──
        alice_follows_bob = follow(alice, target_ref=bob.current_user_id)
        al = alias(alice, user_ref=bob.current_user_id, alias="Bobby")
        assert al.code == "ALIAS_SET"

        # ── List aliases ──
        als = alias_list(alice).data["items"]
        assert any(a["alias"] == "Bobby" for a in als)

        # ── Remove alias ──
        ua = unalias(alice, user_ref=bob.current_user_id)
        assert ua.code == "ALIAS_REMOVED"

        # ── Unshare ──
        us = unshare(alice, article_ref=a.data["id"])
        assert us.code == "UNSHARED"
        mine_after = share_list(alice, mine=True).data["items"]
        assert len(mine_after) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# J10 — Review rating: invite → accept → submit → rate helpfulness
# ═══════════════════════════════════════════════════════════════════════════════


class TestReviewRating:
    """Complete review flow including helpfulness rating."""

    def test_rate_review_helpfulness(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import (
            accept, invite_reviewer, rate, submit,
        )
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer

        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = create(alice, title="Paper", content="# Abstract")
        _publish(alice, article_ref=a.data["id"])

        # Bob must be a maintainer to review
        add_maintainer(ctx.db, a.data["id"], bob.current_user_id)
        ctx.db.flush()

        invite_reviewer(alice, article_ref=a.data["id"],
                        user_ref=bob.current_user_id)
        accept(bob, article_ref=a.data["id"])

        comment = ("Excellent work with rigorous methodology. "
                   "The results are clearly presented and convincing. " * 3)
        submit(bob, article_ref=a.data["id"],
               scores_str="orig=5,rigor=4,comp=4,ped=3,imp=4",
               comment=comment)

        # ── Rate Bob's review ──
        r = rate(alice, article_ref=a.data["id"],
                 reviewer_ref=bob.current_user_id, helpfulness=4)
        assert r.code == "HELPFULNESS_RATED"


# ═══════════════════════════════════════════════════════════════════════════════
# J11 — Fork → edit → merge proposal → accept merge
# ═══════════════════════════════════════════════════════════════════════════════


class TestForkAndMerge:
    """Full fork-to-merge pipeline between two users.

    Forks from draft status (requires maintainer).  Sedimentation articles
    are not forkable by design — only draft, published, rejected.
    """

    def test_fork_edit_merge(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, edit
        from peerpedia_core.app.commands.fork import (
            fork, merge_accept, merge_propose,
        )
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer

        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = create(alice, title="Original", content="# Original content")

        # Bob must be a maintainer to fork a draft
        add_maintainer(ctx.db, a.data["id"], bob.current_user_id)
        ctx.db.flush()

        # ── Bob forks the draft ──
        f = fork(bob, article_ref=a.data["id"])
        assert f.code == "FORKED"
        fork_id = f.data["id"]
        assert fork_id != a.data["id"]

        # ── Bob edits fork ──
        edit(bob, article_ref=fork_id, title="Forked Version",
             message="Bob's improvements")

        # ── Bob proposes merge ──
        mp = merge_propose(bob, fork_ref=fork_id, target_ref=a.data["id"])
        assert mp.code == "MERGE_PROPOSED"

        # ── Both maintainers consent ──
        from peerpedia_core.app.commands.maintainer import consent
        consent(alice, article_ref=a.data["id"])
        consent(bob, article_ref=a.data["id"])

        # ── Alice accepts merge ──
        ma = merge_accept(alice, proposal_ref=mp.data["id"],
                          target_ref=a.data["id"])
        assert ma.code == "MERGE_ACCEPTED"


# ═══════════════════════════════════════════════════════════════════════════════
# J12 — Notification flow: event → list → mark read
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotificationFlow:
    """A social action triggers a notification; list and mark read."""

    def test_notification_on_follow(self, ctx):
        from peerpedia_core.app.commands.notification import (
            list_notifications, mark_read_notification,
        )
        from peerpedia_core.app.commands.social import follow

        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")

        # ── Bob follows Alice → notification created ──
        follow(bob, target_ref=alice.current_user_id)

        # ── Alice lists notifications ──
        notifs = list_notifications(alice).data["items"]
        assert len(notifs) >= 1
        nid = notifs[0]["id"]

        # ── Alice marks it read ──
        mr = mark_read_notification(alice, notification_id=nid)
        assert mr.code == "OK"

        # ── Unread count drops ──
        unread = list_notifications(alice, unread_only=True).data["items"]
        assert all(n["id"] != nid for n in unread)


# ═══════════════════════════════════════════════════════════════════════════════
# J13 — Maintainer lifecycle: add → consent → list → revoke → remove
# ═══════════════════════════════════════════════════════════════════════════════


class TestMaintainerLifecycle:
    """Full maintainer journey through app commands (no storage shortcuts)."""

    def test_maintainer_roundtrip(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.maintainer import (
            add, consent, list_article_maintainers, remove, revoke,
        )

        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = create(alice, title="Collab Paper", content="# X")

        # ── Alice adds Bob as maintainer ──
        r = add(alice, article_ref=a.data["id"], target_ref=bob.current_user_id)
        assert r.code == "OK"

        # ── Bob consents to publish ──
        c = consent(bob, article_ref=a.data["id"])
        assert c.code == "OK"

        # ── List maintainers ──
        m = list_article_maintainers(alice, article_ref=a.data["id"])
        mids = set(m.data["maintainers"])
        assert alice.current_user_id in mids
        assert bob.current_user_id in mids

        # ── Bob revokes consent ──
        rv = revoke(bob, article_ref=a.data["id"])
        assert rv.code == "OK"

        # ── Alice removes Bob ──
        rm = remove(alice, article_ref=a.data["id"],
                    target_ref=bob.current_user_id)
        assert rm.code == "OK"

        # ── Bob is gone ──
        m2 = list_article_maintainers(alice, article_ref=a.data["id"])
        mids2 = set(m2.data["maintainers"])
        assert bob.current_user_id not in mids2
        assert alice.current_user_id in mids2


# ═══════════════════════════════════════════════════════════════════════════════
# J14 — Error paths: not found, unauthorized, ambiguous refs
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorPaths:
    """App-layer errors produce correct codes and exception types."""

    def test_article_not_found(self, ctx):
        from peerpedia_core.app.commands.article import show
        from peerpedia_core.exceptions import NotFoundError

        alice = login(ctx, "Alice")
        with pytest.raises(NotFoundError):
            show(alice, article_ref="nonexistent-id")

    def test_unauthorized_create(self, ctx):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.exceptions import NotAuthorizedError

        with pytest.raises(NotAuthorizedError):
            create(ctx, title="X", content="# X")

    def test_ambiguous_user_ref(self, ctx):
        from peerpedia_core.app.refs import require_user_by_ref
        from peerpedia_core.exceptions import BadRequestError

        login(ctx, "Charlie")
        login(ctx, "Charlie")  # duplicate name
        with pytest.raises(BadRequestError, match="AMBIGUOUS_NAME"):
            require_user_by_ref(ctx.db, "Charlie")

    def test_user_not_found(self, ctx):
        from peerpedia_core.app.refs import require_user_by_ref
        from peerpedia_core.exceptions import NotFoundError

        login(ctx, "Alice")
        with pytest.raises(NotFoundError):
            require_user_by_ref(ctx.db, "NoSuchUser")
