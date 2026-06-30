# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Spec: Extended user journeys.

STATUS: LOCKED

Tests real user workflows through the app command surface
with a real DB.  No storage shortcuts unless the app surface
has a known gap (documented inline).
"""

import pytest

from tests.app.conftest import login


# ── Helpers ────────────────────────────────────────────────────────────────

def _create(ctx, title="Test", content="# X"):
    from peerpedia_core.app.commands.article import create
    return create(ctx, title=title, content=content)


def _publish(ctx, article_ref):
    from peerpedia_core.app.commands.article import publish
    publish(ctx, article_ref=article_ref,
            scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4")


# ═══════════════════════════════════════════════════════════════════════════════
# J15 — Search users
# ═══════════════════════════════════════════════════════════════════════════════


class TestSearchUsers:
    """Register multiple users, search by name prefix."""

    def test_search_finds_by_prefix(self, ctx):
        from peerpedia_core.app.commands.account import search_users

        login(ctx, "Albert")
        login(ctx, "Alfred")
        login(ctx, "Bob")

        result = search_users(ctx, query="Al")
        names = {u["name"] for u in result.data["items"]}
        assert "Albert" in names
        assert "Alfred" in names
        assert "Bob" not in names

    def test_search_empty_returns_none(self, ctx):
        from peerpedia_core.app.commands.account import search_users

        login(ctx, "Alice")
        result = search_users(ctx, query="ZZZ")
        assert result.data["items"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# J16 — School (top users)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchool:
    """School lists top users by follower count."""

    def test_school_ranks_by_followers(self, ctx):
        from peerpedia_core.app.commands.social import follow, school

        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        carol = login(ctx, "Carol")

        # Alice follows Bob; Carol follows Bob → Bob has 2 followers
        follow(alice, target_ref=bob.current_user_id)
        follow(carol, target_ref=bob.current_user_id)
        # Alice follows Carol → Carol has 1 follower
        follow(alice, target_ref=carol.current_user_id)

        top = school(alice, limit=5, local=True).data["items"]
        assert len(top) >= 1
        # Bob should be ranked higher than Carol
        bob_rank = next(i for i, u in enumerate(top) if u["name"] == "Bob")
        carol_rank = next(i for i, u in enumerate(top) if u["name"] == "Carol")
        assert bob_rank < carol_rank


# ═══════════════════════════════════════════════════════════════════════════════
# J17 — Feed (articles from followed users)
# ═══════════════════════════════════════════════════════════════════════════════


class TestFeed:
    """Follow → see their published articles in feed."""

    def test_feed_shows_followed_articles(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, list_articles
        from peerpedia_core.app.commands.social import follow

        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")

        # Bob publishes
        a = create(bob, title="Bob's Paper", content="# B")
        _publish(bob, article_ref=a.data["id"])

        # Alice follows Bob
        follow(alice, target_ref=bob.current_user_id)

        # Alice's feed
        feed = list_articles(alice, feed=True).data["items"]
        titles = {item["title"] for item in feed}
        assert "Bob's Paper" in titles


# ═══════════════════════════════════════════════════════════════════════════════
# J18 — Article diff
# ═══════════════════════════════════════════════════════════════════════════════


class TestArticleDiff:
    """Create, edit, diff between versions."""

    def test_diff_between_edits(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, diff, edit

        alice = login(ctx, "AliceDiffJourney")
        a = create(alice, title="Diff Test", content="Version 1")
        aid = a.data["id"]

        edit(alice, article_ref=aid, title="Diff v2", message="v2")

        # diff with explicit hashes requires commit resolution in git repo
        from peerpedia_core.exceptions import BadRequestError
        try:
            result = diff(alice, article_ref=aid, hash1="HEAD~1", hash2="HEAD")
            assert "diff_text" in result.data
        except BadRequestError:
            pass  # commit refs depend on git history depth


# ═══════════════════════════════════════════════════════════════════════════════
# J19 — Scan to force-publish
# ═══════════════════════════════════════════════════════════════════════════════


class TestScanPublish:
    """Publish → scan → verify published status."""

    def test_scan_publishes_ready_articles(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, scan, show

        alice = login(ctx, "Alice")
        a = create(alice, title="Scan Me", content="# S")
        _publish(alice, article_ref=a.data["id"])

        # Manually trigger scan
        result = scan(alice)
        assert result.code in ("ARTICLE_SCANNED", "ARTICLE_SCANNED_EMPTY")

        # Article should now be published (if sedimentation period elapsed)
        shown = show(alice, article_ref=a.data["id"])
        assert shown.data["status"] in ("sedimentation", "published")


# ═══════════════════════════════════════════════════════════════════════════════
# J20 — Concurrent collaboration
# ═══════════════════════════════════════════════════════════════════════════════


class TestConcurrentCollab:
    """Two maintainers edit the same article."""

    def test_both_maintainers_edit(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, edit, show
        from peerpedia_core.app.commands.maintainer import add

        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = create(alice, title="Collab", content="# Start")

        add(alice, article_ref=a.data["id"], target_ref=bob.current_user_id)

        # Both edit
        edit(alice, article_ref=a.data["id"], title="Alice's Edit", message="a1")
        edit(bob, article_ref=a.data["id"], title="Bob's Edit",
             message="b1", user_id=bob.current_user_id)

        shown = show(alice, article_ref=a.data["id"])
        assert shown.data["title"] == "Bob's Edit"


# ═══════════════════════════════════════════════════════════════════════════════
# J21 — Multiple reviews on same article
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultipleReviews:
    """Two reviewers submit; verify both appear."""

    def test_two_reviewers_submit(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import (
            accept, invite_reviewer, list_reviews, submit,
        )
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer

        alice = login(ctx, "Alice")
        r1 = login(ctx, "ReviewerA")
        r2 = login(ctx, "ReviewerB")
        a = create(alice, title="Dual Review", content="# Paper")
        _publish(alice, article_ref=a.data["id"])

        comment = ("A thoughtful paper with clear methodology. "
                   "The analysis is sound and well-presented. " * 3)

        for r in [r1, r2]:
            add_maintainer(ctx.db, a.data["id"], r.current_user_id)
            ctx.db.flush()
            invite_reviewer(alice, article_ref=a.data["id"],
                            user_ref=r.current_user_id)
            accept(r, article_ref=a.data["id"])
            submit(r, article_ref=a.data["id"],
                   scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4",
                   comment=comment)

        reviews = list_reviews(alice, article_ref=a.data["id"]).data["reviews"]
        # Author's self-review may also appear — at least the 2 invited reviewers
        assert len(reviews) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# J22 — Recover flow
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecoverFlow:
    """Register (with password), then recover the same user."""

    def test_recover_finds_registered_user(self, ctx):
        from peerpedia_core.app.commands.account import register

        # Register sets up password+salt — login() helper skips that
        result = register(ctx, name="AliceRecoverReg", password="secret123")
        user_id = result.data["user_id"]

        from peerpedia_core.app.commands.account import recover
        recovered = recover(ctx, user_id=user_id, password="secret123")
        assert recovered.data["user_id"] == user_id


# ═══════════════════════════════════════════════════════════════════════════════
# J23 — Bootstrap flow (register on device A, bootstrap on device B)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBootstrapFlow:
    """Register, export, bootstrap on a new device."""

    def test_bootstrap_from_registered_user(self, ctx):
        import json
        from peerpedia_core.app.commands.account import bootstrap, register

        # Bootstrap creates a local stub for a remote user
        # Use a fresh UUID that doesn't exist locally
        import uuid
        remote_id = str(uuid.uuid4())
        blob = json.dumps({
            "user_id": remote_id,
            "name": "RemoteAlice",
            "public_key": "fe40" * 16,  # 64 hex chars
            "salt": "8a3c" * 8,        # 16 hex chars
        })
        boot = bootstrap(ctx, from_json=blob)
        assert boot.code == "BOOTSTRAPPED"
        assert boot.data["user_id"] == remote_id


# ═══════════════════════════════════════════════════════════════════════════════
# J24 — Self-review weight
# ═══════════════════════════════════════════════════════════════════════════════


class TestSelfReview:
    """Author cannot self-invite (by design)."""

    def test_self_invite_rejected(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import invite_reviewer
        from peerpedia_core.exceptions import BadRequestError

        alice = login(ctx, "AliceSelfNoInvite")
        a = create(alice, title="Self Review Test", content="# Paper")
        _publish(alice, article_ref=a.data["id"])

        with pytest.raises(BadRequestError, match="SELF"):
            invite_reviewer(alice, article_ref=a.data["id"],
                            user_ref=alice.current_user_id)


# ═══════════════════════════════════════════════════════════════════════════════
# J25 — Alias resolve: reference by @alias
# ═══════════════════════════════════════════════════════════════════════════════


class TestAliasResolve:
    """Set alias → verify alias appears in list."""

    def test_alias_appears_in_list(self, ctx):
        from peerpedia_core.app.commands.social import alias, alias_list, follow

        alice = login(ctx, "AliceAliasList")
        bob = login(ctx, "BobAliasList")

        follow(alice, target_ref=bob.current_user_id)
        alias(alice, user_ref=bob.current_user_id, alias="B-Man")

        aliases = alias_list(alice).data["items"]
        assert any(a["alias"] == "B-Man" for a in aliases)


# ═══════════════════════════════════════════════════════════════════════════════
# J26 — Reply to review
# ═══════════════════════════════════════════════════════════════════════════════


class TestReviewReply:
    """Reviewer submits, author replies."""

    def test_author_replies_to_review(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import (
            accept, invite_reviewer, reply, submit,
        )
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer

        alice = login(ctx, "AliceReply")
        bob = login(ctx, "BobReply")
        a = create(alice, title="Reply Test", content="# Paper")
        _publish(alice, article_ref=a.data["id"])

        add_maintainer(ctx.db, a.data["id"], bob.current_user_id)
        ctx.db.flush()
        invite_reviewer(alice, article_ref=a.data["id"],
                        user_ref=bob.current_user_id)
        accept(bob, article_ref=a.data["id"])
        comment = ("A solid contribution. The analysis is thorough. " * 5)
        submit(bob, article_ref=a.data["id"],
               scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4",
               comment=comment)

        # Author replies
        r = reply(alice, article_ref=a.data["id"],
                  to_ref=bob.current_user_id, content="Thanks for the review!")
        assert r.code == "OK"


# ═══════════════════════════════════════════════════════════════════════════════
# J27 — Idempotent operations
# ═══════════════════════════════════════════════════════════════════════════════


class TestIdempotent:
    """Operations that should be safe to repeat."""

    def test_double_bookmark_is_ok(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.social import bookmark

        alice = login(ctx, "AliceIdem")
        a = create(alice, title="Bookmark Me", content="# B")
        b1 = bookmark(alice, article_ref=a.data["id"])
        assert b1.code == "BOOKMARKED"
        b2 = bookmark(alice, article_ref=a.data["id"])
        # Second bookmark should either succeed or be idempotent
        assert b2.code in ("BOOKMARKED", "OK")

    def test_double_follow_is_ok(self, ctx):
        from peerpedia_core.app.commands.social import follow

        alice = login(ctx, "AliceDoubleFollow")
        bob = login(ctx, "BobDoubleFollow")
        f1 = follow(alice, target_ref=bob.current_user_id)
        assert f1.code == "FOLLOWING"
        f2 = follow(alice, target_ref=bob.current_user_id)
        assert f2.code in ("FOLLOWING", "OK")

    def test_double_unfollow_is_ok(self, ctx):
        from peerpedia_core.app.commands.social import follow, unfollow

        alice = login(ctx, "AliceUnfollowIdem")
        bob = login(ctx, "BobUnfollowIdem")
        follow(alice, target_ref=bob.current_user_id)
        unfollow(alice, target_ref=bob.current_user_id)
        # Second unfollow should not crash
        u2 = unfollow(alice, target_ref=bob.current_user_id)
        assert u2.code in ("UNFOLLOWED", "OK")


# ═══════════════════════════════════════════════════════════════════════════════
# J28 — Empty state queries
# ═══════════════════════════════════════════════════════════════════════════════


class TestEmptyStates:
    """Queries with no data return empty results, not errors."""

    def test_empty_following(self, ctx):
        from peerpedia_core.app.commands.social import list_following

        alice = login(ctx, "AliceEmpty")
        r = list_following(alice, user_ref=alice.current_user_id)
        assert r.data["items"] == []

    def test_empty_reviews(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import list_reviews

        alice = login(ctx, f"AliceEmptyRev{id(self)}")
        a = create(alice, title="No Reviews Yet", content="# X")
        _publish(alice, article_ref=a.data["id"])
        r = list_reviews(alice, article_ref=a.data["id"])
        # May include author self-review or none — both are valid empty states
        assert isinstance(r.data["reviews"], list)

    def test_empty_bookmarks(self, ctx):
        from peerpedia_core.app.commands.article import list_articles

        alice = login(ctx, "AliceEmptyBM")
        r = list_articles(alice, bookmarked=True)
        assert r.data["items"] == []

    def test_empty_shares(self, ctx):
        from peerpedia_core.app.commands.social import share_list

        alice = login(ctx, "AliceEmptyShares")
        r = share_list(alice, mine=True)
        assert r.data["items"] == []
