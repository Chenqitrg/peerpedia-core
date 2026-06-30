# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Review commands."""

from tests.app.conftest import login


def _create_article(ctx, title="Test"):
    from peerpedia_core.app.commands.article import create
    return create(ctx, title=title, content="# X")


class TestReview:
    def test_list_reviews_empty(self, ctx, articles_dir):
        from peerpedia_core.app.commands.review import list_reviews
        alice = login(ctx, "Alice")
        a = _create_article(alice)
        result = list_reviews(alice, article_ref=a.data["id"])
        assert result.data["reviews"] == []

    def test_invite_reviewer(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import publish
        from peerpedia_core.app.commands.review import invite_reviewer
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer
        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = _create_article(alice)
        # Publish to sedimentation for inviting
        publish(alice, article_ref=a.data["id"], scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4")
        # Add Bob as maintainer so he can be invited
        add_maintainer(ctx.db, a.data["id"], bob.current_user_id)
        ctx.db.flush()

        invite_reviewer(alice, article_ref=a.data["id"], user_ref=bob.current_user_id)
        # No exception → success

    def test_accept_invitation(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import publish
        from peerpedia_core.app.commands.review import invite_reviewer, accept
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer
        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = _create_article(alice)
        publish(alice, article_ref=a.data["id"], scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4")
        add_maintainer(ctx.db, a.data["id"], bob.current_user_id)
        ctx.db.flush()
        invite_reviewer(alice, article_ref=a.data["id"], user_ref=bob.current_user_id)

        r = accept(bob, article_ref=a.data["id"])
        assert r.code == "INVITATION_ACCEPTED"

    def test_decline_invitation(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import publish
        from peerpedia_core.app.commands.review import invite_reviewer, decline
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer
        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = _create_article(alice)
        publish(alice, article_ref=a.data["id"], scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4")
        add_maintainer(ctx.db, a.data["id"], bob.current_user_id)
        ctx.db.flush()
        invite_reviewer(alice, article_ref=a.data["id"], user_ref=bob.current_user_id)

        r = decline(bob, article_ref=a.data["id"])
        assert r.code == "INVITATION_DECLINED"


class TestSubmitReview:
    """Full review submission — the complete invite → accept → submit cycle."""

    def _setup(self, ctx, articles_dir):
        """Create article, publish to sedimentation, add maintainer,
        invite, and accept — all via app commands.  Returns (alice, bob, article)."""
        from peerpedia_core.app.commands.article import create, publish
        from peerpedia_core.app.commands.review import invite_reviewer, accept
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer

        alice = login(ctx, "Alice")
        bob = login(ctx, "Bob")
        a = create(alice, title="Review Target", content="# Abstract\n\nContent here.")
        publish(alice, article_ref=a.data["id"],
                scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4")
        add_maintainer(ctx.db, a.data["id"], bob.current_user_id)
        ctx.db.flush()
        invite_reviewer(alice, article_ref=a.data["id"], user_ref=bob.current_user_id)
        accept(bob, article_ref=a.data["id"])
        return alice, bob, a

    def test_submit_review(self, ctx, articles_dir):
        from peerpedia_core.app.commands.review import submit
        _, bob, a = self._setup(ctx, articles_dir)

        comment = (
            "This paper presents a novel approach to the problem. "
            "The methodology is rigorous and the results are compelling. "
            "I recommend acceptance with minor revisions. " * 3
        )
        r = submit(bob, article_ref=a.data["id"],
                   scores_str="orig=5,rigor=5,comp=5,ped=5,imp=5",
                   comment=comment)
        assert r.code == "REVIEW_SUBMITTED"

    def test_submit_without_invite_succeeds(self, ctx, articles_dir):
        """Reviews don't require invitation — any user can review a
        sedimentation/published article."""
        from peerpedia_core.app.commands.article import create, publish
        from peerpedia_core.app.commands.review import submit
        alice = login(ctx, "Alice")
        stranger = login(ctx, "Stranger")
        a = create(alice, title="Paper", content="# X")
        publish(alice, article_ref=a.data["id"],
                scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4")

        r = submit(stranger, article_ref=a.data["id"],
                   scores_str="orig=3,rigor=3,comp=3,ped=3,imp=3",
                   comment="This is an unsolicited review from a stranger. "
                           "Review does not require invitation — anyone can "
                           "submit a review on a sedimentation article. " * 2)
        assert r.code == "REVIEW_SUBMITTED"
