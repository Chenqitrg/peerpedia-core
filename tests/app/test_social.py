# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Social commands — follow, bookmark, share, alias."""

from tests.app.conftest import login


# ═══════════════════════════════════════════════════════════════════════════════
# Follow / unfollow
# ═══════════════════════════════════════════════════════════════════════════════


class TestFollow:
    def test_follow_and_unfollow(self, ctx):
        from peerpedia_core.app.commands.social import follow, list_following, unfollow
        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")

        r = follow(alice, target_ref=bob.current_user_id)
        assert r.code == "FOLLOWING"

        following = list_following(alice, user_ref=alice.current_user_id)
        names = [f.name for f in following.data["items"]]
        assert "Bob" in names

        r = unfollow(alice, target_ref=bob.current_user_id)
        assert r.code == "UNFOLLOWED"

    def test_follow_by_name(self, ctx):
        from peerpedia_core.app.commands.social import follow
        alice = login(ctx, "Alice")
        login(ctx, "Bob")
        r = follow(alice, target_ref="@Bob")
        assert r.code == "FOLLOWING"


# ═══════════════════════════════════════════════════════════════════════════════
# Bookmark
# ═══════════════════════════════════════════════════════════════════════════════


class TestBookmark:
    def test_bookmark_and_unbookmark(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.social import bookmark, unbookmark
        alice = login(ctx, "Alice")
        a = create(alice, title="Paper", content="# X")

        r = bookmark(alice, article_ref=a.data["id"])
        assert r.code == "BOOKMARKED"

        r = unbookmark(alice, article_ref=a.data["id"])
        assert r.code == "BOOKMARK_REMOVED"


# ═══════════════════════════════════════════════════════════════════════════════
# Alias
# ═══════════════════════════════════════════════════════════════════════════════


class TestListFollowers:
    def test_list_followers(self, ctx):
        from peerpedia_core.app.commands.social import follow, list_followers
        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        follow(alice, target_ref=bob.current_user_id)
        result = list_followers(bob, user_ref=bob.current_user_id)
        names = [f.name for f in result.data["items"]]
        assert "Alice" in names


class TestShare:
    def test_share_and_unshare(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.social import share, unshare, share_list
        alice = login(ctx, "Alice")
        a = create(alice, title="Paper", content="# X")

        r = share(alice, article_ref=a.data["id"], comment="Check this")
        assert r.code == "SHARED"

        items = share_list(alice, mine=True).data["items"]
        assert len(items) >= 1

        r = unshare(alice, article_ref=a.data["id"])
        assert r.code == "UNSHARED"


class TestSchool:
    def test_school_local(self, ctx):
        from peerpedia_core.app.commands.social import school
        alice = login(ctx, "Alice")
        login(ctx, "Bob")
        result = school(alice, local=True)
        assert len(result.data["items"]) >= 2  # all users listed


class TestAlias:
    def test_set_and_list_alias(self, ctx):
        from peerpedia_core.app.commands.social import alias, alias_list, follow
        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        follow(alice, target_ref=bob.current_user_id)

        r = alias(alice, user_ref="@Bob", alias="bobby")
        assert r.code == "ALIAS_SET"

        items = alias_list(alice).data["items"]
        assert any(a["alias"] == "bobby" for a in items)

    def test_unalias(self, ctx):
        from peerpedia_core.app.commands.social import alias, alias_list, follow, unalias
        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        follow(alice, target_ref=bob.current_user_id)
        alias(alice, user_ref="@Bob", alias="temp")
        r = unalias(alice, user_ref="@Bob")
        assert r.code == "ALIAS_REMOVED"
        items = alias_list(alice).data["items"]
        assert not any(a["alias"] == "temp" for a in items)
