# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Spec: App-layer closed-loop workflows.

STATUS: LOCKED

Each specification is a multi-step user journey using ONLY the app
command interface.  No direct DB access, no storage-layer imports.
The app command functions ARE the interface under specification.

Specification inventory
-----------------------
S1 — New user journey
    register → whoami → create article → list mine → show → delete
S2 — Social network
    two users register → follow → follow back → share → bookmark → feed
S3 — Review cycle
    create → publish → invite reviewer → accept → list reviews
S4 — Fork workflow
    create → fork → propose merge → withdraw
"""

from tests.app.conftest import login


# ═══════════════════════════════════════════════════════════════════════════════
# S1 — New user journey
# ═══════════════════════════════════════════════════════════════════════════════


class TestNewUserJourney:
    """Register → whoami → create → list mine → show → delete."""

    def test_full_lifecycle(self, ctx, articles_dir):
        from peerpedia_core.app.commands.account import register
        from peerpedia_core.app.commands.article import create, delete, list_articles, show
        from peerpedia_core.core import list_users_by_name

        # ── Register ──
        register(ctx, name="Newton", password="calculus")
        users = list_users_by_name(ctx.db, "Newton")
        assert len(users) == 1
        newton = login(ctx, "Newton")

        # ── Create two articles ──
        a1 = create(newton, title="Principia", content="# Gravity\n\nF = ma")
        assert a1.code == "ARTICLE_CREATED"

        a2 = create(newton, title="Opticks", content="# Light\n\nPrisms.")
        assert a2.code == "ARTICLE_CREATED"

        # ── List mine ──
        mine = list_articles(newton, mine=True)
        titles = {a["title"] for a in mine.data["items"]}
        assert titles == {"Principia", "Opticks"}

        # ── Show one ──
        view = show(newton, article_ref=a1.data["id"])
        assert view.data["title"] == "Principia"
        assert view.data["status"] == "draft"

        # ── Delete ──
        d = delete(newton, article_ref=a1.data["id"])
        assert d.code == "ARTICLE_DELETED"

        mine_after = list_articles(newton, mine=True)
        assert len(mine_after.data["items"]) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# S2 — Social network
# ═══════════════════════════════════════════════════════════════════════════════


class TestSocialNetwork:
    """Two users → follow → follow back → share → bookmark → feed."""

    def test_social_graph(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.social import (
            bookmark, follow, list_followers, list_following, share,
        )

        # ── Register two users ──
        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = create(alice, title="Alice's Theory", content="# E=mc^2")

        # ── Follow each other ──
        r = follow(alice, target_ref=bob.current_user_id)
        assert r.code == "FOLLOWING"
        r = follow(bob, target_ref=alice.current_user_id)
        assert r.code == "FOLLOWING"

        # ── Verify mutual following ──
        alice_following = {f["name"] for f in list_following(alice, user_ref=alice.current_user_id).data["items"]}
        assert "Bob" in alice_following

        bob_followers = {f["name"] for f in list_followers(bob, user_ref=bob.current_user_id).data["items"]}
        assert "Alice" in bob_followers

        # ── Share article ──
        r = share(alice, article_ref=a.data["id"])
        assert r.code == "SHARED"

        # ── Bookmark ──
        r = bookmark(bob, article_ref=a.data["id"])
        assert r.code == "BOOKMARKED"


# ═══════════════════════════════════════════════════════════════════════════════
# S3 — Review cycle
# ═══════════════════════════════════════════════════════════════════════════════


class TestReviewCycle:
    """Create → publish → invite → accept → list reviews."""

    def test_invite_flow(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, publish
        from peerpedia_core.app.commands.review import accept, list_reviews, invite_reviewer
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer

        # ── Setup ──
        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = create(alice, title="Paper", content="# Abstract")

        # ── Publish to sedimentation ──
        publish(alice, article_ref=a.data["id"],
                scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4")

        # ── Add Bob as maintainer so he can be invited ──
        add_maintainer(ctx.db, a.data["id"], bob.current_user_id)
        ctx.db.flush()

        # ── Invite + accept ──
        invite_reviewer(alice, article_ref=a.data["id"], user_ref=bob.current_user_id)
        accept(bob, article_ref=a.data["id"])

        # ── List reviews (shows invitation accepted) ──
        reviews = list_reviews(alice, article_ref=a.data["id"])
        assert len(reviews.data["reviews"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# S4 — Fork workflow
# ═══════════════════════════════════════════════════════════════════════════════


class TestForkWorkflow:
    """Create → fork → propose merge → withdraw."""

    def test_fork_and_merge_flow(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.fork import fork, merge_propose, merge_withdraw
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer

        # ── Setup ──
        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        original = create(alice, title="Original", content="# Original")

        # Bob needs maintainer access to fork
        add_maintainer(ctx.db, original.data["id"], bob.current_user_id)
        ctx.db.flush()

        # ── Fork ──
        f = fork(bob, article_ref=original.data["id"])
        assert f.code == "FORKED"
        assert f.data["forked_from"] == original.data["id"]

        # ── Propose merge ──
        mp = merge_propose(bob, fork_ref=f.data["id"], target_ref=original.data["id"])
        assert mp.code == "MERGE_PROPOSED"

        # ── Withdraw ──
        wd = merge_withdraw(bob, proposal_ref=mp.data["id"])
        assert wd.code == "MERGE_WITHDRAWN"
