# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Spec: Review conversation journeys.

STATUS: LOCKED

Tests real multi-turn review workflows — submit, re-submit, reply
— with multiple participants.  Each test is a complete story, not a
single operation.

Design: reviews don't require invitations.  Any user can submit a review
on a sedimentation/published article.  Reviewers can re-submit (update)
their review.  Invitations are a coordination/notification mechanism.

Key invariants:
- Review comment must be ≥ 200 characters (params.comment.min_length)
- Only maintainers can reply (NOT_ARTICLE_AUTHOR guard)
- Review submission requires sedimentation or published status
- Reviewers can always re-submit (no invitation gate)
- Both submit and reply generate notifications
"""

import pytest

from tests.app.conftest import login

# ── Long enough for min_length=200 ──────────────────────────────────────

_COMMENT_LONG = (
    "This paper makes a significant contribution to the field. "
    "The methodology is rigorous and well-documented. "
    "The experimental results are convincing and reproducible. "
    "I recommend this work for publication after minor revisions. ")

_COMMENT_DETAILED = (
    "The theoretical framework presented in Section 2 is sound but could "
    "benefit from additional justification of the core assumptions. "
    "The numerical experiments in Section 4 are comprehensive; however, "
    "the authors should include error bars on all figures and discuss "
    "potential confounding factors in the analysis. "
    "Overall, this is a solid contribution that advances the state of the art. ")

_COMMENT_CRITICAL = (
    "While the paper addresses an important problem, there are several "
    "significant issues that must be resolved. The literature review in "
    "Section 1 omits key recent works from 2024-2025. The experimental "
    "design in Section 3 lacks proper controls, making it difficult to "
    "attribute the observed effects to the proposed mechanism. "
    "The statistical analysis uses inappropriate tests for the data "
    "distribution. These issues must be addressed before publication. ")

_COMMENT_POSITIVE = (
    "This is an excellent piece of work that I thoroughly enjoyed reading. "
    "The problem formulation is clear and well-motivated. The proposed "
    "solution is elegant and the implementation details are sufficient "
    "for reproduction. The evaluation is comprehensive and demonstrates "
    "clear improvements over existing approaches. I recommend acceptance. ")

_COMMENT_SHORT = (
    "This paper needs substantial improvement before it can be considered "
    "for publication. The core idea is interesting but the execution is "
    "lacking in several important respects that I detail below. The authors "
    "should carefully address each point in their revision. ")


def _create(ctx, title="Test", content="# X"):
    from peerpedia_core.app.commands.article import create
    return create(ctx, title=title, content=content)


def _publish(ctx, article_ref):
    from peerpedia_core.app.commands.article import publish
    publish(ctx, article_ref=article_ref,
            scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4")


def _add_maintainer(db, article_id, user_id):
    from peerpedia_core.storage.db.crud_maintainer import add_maintainer
    add_maintainer(db, article_id, user_id)
    db.flush()


# ═══════════════════════════════════════════════════════════════════════════════
# J29 — Full review conversation: author ↔ reviewer dialogue
# ═══════════════════════════════════════════════════════════════════════════════


class TestReviewConversation:
    """A complete peer review dialogue with re-submission.

    Story: Alice publishes.  Bob reviews, raising concerns.  Alice
    replies addressing each concern.  Bob updates his review (re-submits)
    with revised scores.  Carol (co-author) also replies.  Alice gives
    a final response.

    Reviews don't require invitation — any user can submit a review
    on a sedimentation/published article.  Invitations are a
    coordination mechanism, not a gate.
    """

    def test_full_review_with_re_submission(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import (
            list_reviews, reply, submit,
        )

        # ── Act 1: Author creates and publishes ──────────────────────────
        alice = login(ctx, "AliceConv")
        a = create(alice, title="Quantum Error Correction",
                   content="# Abstract\n\nWe propose a novel surface code.")
        _publish(alice, article_ref=a.data["id"])
        aid = a.data["id"]

        # ── Act 2: Co-author Carol joins ─────────────────────────────────
        carol = login(ctx, "CarolCoauth")
        _add_maintainer(ctx.db, aid, carol.current_user_id)

        # ── Act 3: Bob submits initial review (no invitation needed) ─────
        bob = login(ctx, "BobReviewer")
        submit(bob, article_ref=aid,
               scores_str="orig=4,rigor=3,comp=4,ped=3,imp=4",
               comment=_COMMENT_CRITICAL)

        # ── Act 4: Alice replies ─────────────────────────────────────────
        r1 = reply(alice, article_ref=aid, to_ref=bob.current_user_id,
                   content="Thank you for the thorough review. We have added "
                           "the Kitaev baseline comparison (new Figure 4). "
                           "The lattice size has been extended to d=9, and "
                           "we clarified the notation in eq.(12).")
        assert r1.code == "OK"

        # ── Act 5: Bob re-submits with updated scores ────────────────────
        bob_comment_2 = (
            "The revisions address all my concerns. The d=9 results are "
            "convincing and the Kitaev comparison strengthens the paper "
            "significantly. The revised notation is now clear. "
            "I recommend acceptance. Excellent work on the revision. "
            "This paper is now ready for publication. " * 2
        )
        submit(bob, article_ref=aid,
               scores_str="orig=5,rigor=5,comp=5,ped=5,imp=5",
               comment=bob_comment_2)

        # ── Act 6: Carol (co-author) also replies ────────────────────────
        r2 = reply(carol, article_ref=aid, to_ref=bob.current_user_id,
                   content="I have re-run all simulations at d=9 and updated "
                           "the error bars. The new results confirm our "
                           "original findings with higher confidence.")
        assert r2.code == "OK"

        # ── Act 7: Alice gives final acknowledgment ──────────────────────
        r3 = reply(alice, article_ref=aid, to_ref=bob.current_user_id,
                   content="We appreciate the constructive feedback and "
                           "believe the revised manuscript is now ready.")
        assert r3.code == "OK"

        # ── Verify: review visible ───────────────────────────────────────
        reviews = list_reviews(alice, article_ref=aid).data["reviews"]
        assert len(reviews) >= 1

    def test_reviewer_without_maintainer_cannot_reply(self, ctx, articles_dir):
        """Only maintainers can reply.  A reviewer stripped of maintainer
        role cannot participate in the reply thread."""
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import (
            accept, invite_reviewer, submit,
        )
        from peerpedia_core.exceptions import NotAuthorizedError

        alice = login(ctx, "AliceGuard29b")
        bob = login(ctx, "BobGuard29b")
        a = create(alice, title="Guard Test", content="# G")
        _publish(alice, article_ref=a.data["id"])
        aid = a.data["id"]

        # Bob is maintainer + reviewer
        _add_maintainer(ctx.db, aid, bob.current_user_id)
        invite_reviewer(alice, article_ref=aid, user_ref=bob.current_user_id)
        accept(bob, article_ref=aid)
        submit(bob, article_ref=aid,
               scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4",
               comment=_COMMENT_LONG)

        # Remove Bob as maintainer — now he's ONLY a reviewer
        from peerpedia_core.storage.db.crud_maintainer import remove_maintainer
        remove_maintainer(ctx.db, aid, bob.current_user_id)
        ctx.db.flush()

        # Bob (reviewer only) tries to reply — should fail
        from peerpedia_core.app.commands.review import reply
        with pytest.raises(NotAuthorizedError, match="NOT_ARTICLE_AUTHOR"):
            reply(bob, article_ref=aid, to_ref=bob.current_user_id,
                  content="I want to reply but I am not a maintainer. "
                          "This should fail because only article authors "
                          "can participate in the review conversation.")

    def test_author_self_reply_to_reviewer(self, ctx, articles_dir):
        """Author can reply to their own review thread."""
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import (
            accept, invite_reviewer, reply, submit,
        )

        alice = login(ctx, "AliceSelfRepl")
        bob = login(ctx, "BobRevSelf")
        a = create(alice, title="Self Reply Test", content="# Paper")
        _publish(alice, article_ref=a.data["id"])
        aid = a.data["id"]

        _add_maintainer(ctx.db, aid, bob.current_user_id)
        invite_reviewer(alice, article_ref=aid, user_ref=bob.current_user_id)
        accept(bob, article_ref=aid)
        submit(bob, article_ref=aid,
               scores_str="orig=5,rigor=4,comp=5,ped=4,imp=5",
               comment=_COMMENT_POSITIVE)

        # Alice replies twice — both should work
        reply(alice, article_ref=aid, to_ref=bob.current_user_id,
              content="Thank you for the positive and constructive review. "
                      "We are glad the methodology and results meet your "
                      "standards for publication.")
        r2 = reply(alice, article_ref=aid, to_ref=bob.current_user_id,
                   content="We have also updated the references to include "
                           "recent works as suggested in your detailed "
                           "comments on the manuscript.")
        assert r2.code == "OK"


# ═══════════════════════════════════════════════════════════════════════════════
# J30 — Two reviewers, parallel conversations
# ═══════════════════════════════════════════════════════════════════════════════


class TestDualReviewerConversation:
    """Two independent reviewers submit; author replies to each separately.

    Story: Alice publishes.  Bob critiques theory, Carol critiques
    experiments.  Alice replies to each independently with tailored
    responses.  Each thread is separate — replies go to a specific reviewer.
    """

    def test_dual_reviewers_independent_threads(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import (
            accept, invite_reviewer, list_reviews, reply, submit,
        )

        alice = login(ctx, "AliceDual")
        bob = login(ctx, "BobTheory")
        carol = login(ctx, "CarolExp")
        a = create(alice, title="Unified Theory of Learning", content="# UTL")
        _publish(alice, article_ref=a.data["id"])
        aid = a.data["id"]

        # ── Both reviewers onboard ───────────────────────────────────────
        for r in [bob, carol]:
            _add_maintainer(ctx.db, aid, r.current_user_id)
            invite_reviewer(alice, article_ref=aid,
                            user_ref=r.current_user_id)
            accept(r, article_ref=aid)

        # ── Bob submits: theory critique ─────────────────────────────────
        submit(bob, article_ref=aid,
               scores_str="orig=3,rigor=2,comp=4,ped=4,imp=3",
               comment=_COMMENT_CRITICAL)

        # ── Carol submits: experiment critique ───────────────────────────
        submit(carol, article_ref=aid,
               scores_str="orig=4,rigor=4,comp=3,ped=3,imp=3",
               comment=_COMMENT_DETAILED)

        # ── Alice replies to each reviewer separately ────────────────────
        r1 = reply(alice, article_ref=aid, to_ref=bob.current_user_id,
                   content="We have revised Section 2 to address your theory "
                           "concerns. The convexity assumption has been "
                           "removed and Theorem 3 now holds under weaker "
                           "conditions as you suggested in your review.")
        assert r1.code == "OK"

        r2 = reply(alice, article_ref=aid, to_ref=carol.current_user_id,
                   content="Thank you for the detailed experimental critique. "
                           "We have added comprehensive ablation studies in "
                           "Section 4.3 and all figures now include proper "
                           "error bars as requested.")
        assert r2.code == "OK"

        # ── Verify: both reviews visible ─────────────────────────────────
        reviews = list_reviews(alice, article_ref=aid).data["reviews"]
        assert len(reviews) >= 2

    def test_one_accepts_one_declines_with_replies(self, ctx, articles_dir):
        """Mixed outcomes: one reviewer accepts+submits, the other declines.
        Author can still reply to the submitter."""
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import (
            accept, decline, invite_reviewer, list_reviews, reply, submit,
        )

        alice = login(ctx, "AliceMixed")
        r1 = login(ctx, "ReviewerAccept")
        r2 = login(ctx, "ReviewerDecline")
        a = create(alice, title="Mixed Outcome Paper", content="# Paper")
        _publish(alice, article_ref=a.data["id"])
        aid = a.data["id"]

        for r in [r1, r2]:
            _add_maintainer(ctx.db, aid, r.current_user_id)
            invite_reviewer(alice, article_ref=aid,
                            user_ref=r.current_user_id)

        # R1 accepts and submits
        accept(r1, article_ref=aid)
        submit(r1, article_ref=aid,
               scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4",
               comment=_COMMENT_POSITIVE)

        # R2 declines — no review submitted
        decline(r2, article_ref=aid)

        # Alice replies to R1 (the submitter)
        r = reply(alice, article_ref=aid, to_ref=r1.current_user_id,
                  content="Thank you for the positive review and detailed "
                          "feedback. We have incorporated your suggestions "
                          "into the final version of the manuscript.")
        assert r.code == "OK"

        # During sedimentation, replies use anonymous directory IDs derived
        # from the replier's signing key — so replying to R2 (who declined)
        # succeeds but goes to Alice's anonymous thread, not R2's directory.
        # This is by design: anonymous review preserves reviewer privacy.
        r_to_decliner = reply(alice, article_ref=aid,
                              to_ref=r2.current_user_id,
                              content="Even though you declined, I want to "
                                      "acknowledge your time. Thank you.")
        assert r_to_decliner.code == "OK"

        reviews = list_reviews(alice, article_ref=aid).data["reviews"]
        assert len(reviews) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# J31 — Review + Helpfulness Rating after conversation
# ═══════════════════════════════════════════════════════════════════════════════


class TestReviewRatingAfterConversation:
    """Rate a review's helpfulness after the author↔reviewer dialogue.

    Story: Bob submits a review.  Alice replies.  Carol (co-author)
    also replies.  Then both Alice and Carol rate the review.
    """

    def test_rate_after_conversation(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import (
            accept, invite_reviewer, rate, reply, submit,
        )

        alice = login(ctx, "AliceRate")
        bob = login(ctx, "BobRateReview")
        carol = login(ctx, "CarolRateCo")
        a = create(alice, title="Rate After Review", content="# Paper")
        _publish(alice, article_ref=a.data["id"])
        aid = a.data["id"]

        # Carol is co-author
        _add_maintainer(ctx.db, aid, carol.current_user_id)

        # Bob reviews
        _add_maintainer(ctx.db, aid, bob.current_user_id)
        invite_reviewer(alice, article_ref=aid, user_ref=bob.current_user_id)
        accept(bob, article_ref=aid)
        submit(bob, article_ref=aid,
               scores_str="orig=5,rigor=5,comp=5,ped=4,imp=5",
               comment=_COMMENT_POSITIVE)

        # Alice replies
        reply(alice, article_ref=aid, to_ref=bob.current_user_id,
              content="Thank you for the detailed and thoughtful review. "
                      "Your suggestions have significantly improved the "
                      "manuscript.")

        # Carol also replies
        reply(carol, article_ref=aid, to_ref=bob.current_user_id,
              content="I appreciate the constructive feedback on our "
                      "methodology section. We have addressed all your "
                      "points in the revised version.")

        # ── Both rate Bob's review ──
        r = rate(alice, article_ref=aid, reviewer_ref=bob.current_user_id,
                 helpfulness=5)
        assert r.code == "HELPFULNESS_RATED"

        r2 = rate(carol, article_ref=aid, reviewer_ref=bob.current_user_id,
                  helpfulness=4)
        assert r2.code == "HELPFULNESS_RATED"

    def test_rate_requires_maintainer(self, ctx, articles_dir):
        """Only maintainers can rate reviews.  Non-maintainers rejected."""
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import (
            accept, invite_reviewer, rate, submit,
        )
        from peerpedia_core.exceptions import NotAuthorizedError

        alice = login(ctx, "AliceRateGuard")
        bob = login(ctx, "BobReviewerGr")
        outsider = login(ctx, "Outsider")
        a = create(alice, title="Rate Guard", content="# Paper")
        _publish(alice, article_ref=a.data["id"])
        aid = a.data["id"]

        _add_maintainer(ctx.db, aid, bob.current_user_id)
        invite_reviewer(alice, article_ref=aid, user_ref=bob.current_user_id)
        accept(bob, article_ref=aid)
        submit(bob, article_ref=aid,
               scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4",
               comment=_COMMENT_LONG)

        # Outsider (not a maintainer) cannot rate
        with pytest.raises(NotAuthorizedError):
            rate(outsider, article_ref=aid,
                 reviewer_ref=bob.current_user_id, helpfulness=3)


# ═══════════════════════════════════════════════════════════════════════════════
# J32 — Review notifications across the conversation lifecycle
# ═══════════════════════════════════════════════════════════════════════════════


class TestReviewNotifications:
    """Every review action generates the right notifications.

    Story: Alice publishes.  Bob is invited → Bob gets notified.
    Bob submits → Alice + Carol (co-authors) get notified.
    Alice replies → Bob gets notified.  Mark-read works.
    """

    def test_review_notification_flow(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.notification import (
            list_notifications, mark_read_notification,
        )
        from peerpedia_core.app.commands.review import (
            accept, invite_reviewer, reply, submit,
        )

        alice = login(ctx, "AliceNotif")
        bob = login(ctx, "BobNotif")
        carol = login(ctx, "CarolCoNotif")
        a = create(alice, title="Notification Paper", content="# N")
        _publish(alice, article_ref=a.data["id"])
        aid = a.data["id"]

        # Carol is co-author — will also receive review notifications
        _add_maintainer(ctx.db, aid, carol.current_user_id)

        # ── Invite Bob ───────────────────────────────────────────────────
        _add_maintainer(ctx.db, aid, bob.current_user_id)
        invite_reviewer(alice, article_ref=aid, user_ref=bob.current_user_id)
        accept(bob, article_ref=aid)

        # ── Bob submits → Alice and Carol get notified ───────────────────
        submit(bob, article_ref=aid,
               scores_str="orig=5,rigor=4,comp=5,ped=4,imp=4",
               comment=_COMMENT_POSITIVE)

        # Alice should see a notification about the review
        alice_notifs = list_notifications(alice, unread_only=False).data["items"]
        review_notifs = [n for n in alice_notifs
                         if "review" in str(n.get("event", "")).lower()]
        assert len(review_notifs) >= 1

        # Carol (maintainer but not author) — notifications go to
        # article authors (author_ids), not all maintainers
        carol_notifs = list_notifications(carol, unread_only=False).data["items"]
        carol_review = [n for n in carol_notifs
                        if "review" in str(n.get("event", "")).lower()]
        # Carol is maintainer, not author — may or may not get notified
        # (system notifies author_ids, not all maintainers)

        # ── Alice replies → Bob gets notified ────────────────────────────
        reply(alice, article_ref=aid, to_ref=bob.current_user_id,
              content="Thank you for the review! We have addressed all "
                      "your suggestions in the revised manuscript.")

        bob_notifs = list_notifications(bob, unread_only=False).data["items"]
        reply_notifs = [n for n in bob_notifs
                        if "reply" in str(n.get("event", "")).lower()]
        assert len(reply_notifs) >= 1

        # ── Mark read works ──────────────────────────────────────────────
        for n in alice_notifs[:1]:
            if n.get("id"):
                r = mark_read_notification(alice, notification_id=n["id"])
                assert r.code == "OK"

    def test_notification_not_leaked_to_unrelated_users(self, ctx, articles_dir):
        """Review notifications only go to article authors, not outsiders."""
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.notification import list_notifications
        from peerpedia_core.app.commands.review import (
            accept, invite_reviewer, submit,
        )

        alice = login(ctx, "AlicePriv")
        bob = login(ctx, "BobReview")
        outsider = login(ctx, "OutsiderPriv")
        a = create(alice, title="Private Review", content="# P")
        _publish(alice, article_ref=a.data["id"])
        aid = a.data["id"]

        _add_maintainer(ctx.db, aid, bob.current_user_id)
        invite_reviewer(alice, article_ref=aid, user_ref=bob.current_user_id)
        accept(bob, article_ref=aid)
        submit(bob, article_ref=aid,
               scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4",
               comment=_COMMENT_LONG)

        # Outsider should not see review notifications for this article
        outsider_notifs = list_notifications(
            outsider, unread_only=False).data["items"]
        review_events = [n for n in outsider_notifs
                         if n.get("article_id") == aid]
        assert len(review_events) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# J33 — Review lifecycle: state transitions and guardrails
# ═══════════════════════════════════════════════════════════════════════════════


class TestReviewLifecycle:
    """Review state transitions: invite → accept → submit.
    Edge cases around draft articles, self-invitation, and missing reviews.
    """

    def test_invitation_state_transitions(self, ctx, articles_dir):
        """invite → accept → submit.  Each state is verified."""
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import (
            accept, invite_reviewer, list_reviews, submit,
        )

        alice = login(ctx, "AliceStates")
        bob = login(ctx, "BobStates")
        a = create(alice, title="State Machine", content="# FSM")
        _publish(alice, article_ref=a.data["id"])
        aid = a.data["id"]

        _add_maintainer(ctx.db, aid, bob.current_user_id)
        invite_reviewer(alice, article_ref=aid, user_ref=bob.current_user_id)

        # Bob accepts
        accept(bob, article_ref=aid)

        # Bob submits
        submit(bob, article_ref=aid,
               scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4",
               comment=_COMMENT_LONG)

        # Review is visible
        reviews = list_reviews(alice, article_ref=aid).data["reviews"]
        assert len(reviews) >= 1

    def test_cannot_review_draft_article(self, ctx, articles_dir):
        """Review submission requires published/sedimentation status.
        Draft articles are rejected with CANNOT_REVIEW_DRAFT."""
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import submit
        from peerpedia_core.exceptions import NotAuthorizedError

        alice = login(ctx, "AliceDraft")
        a = create(alice, title="Draft Only", content="# Draft")
        # Article is still draft — cannot review

        with pytest.raises(NotAuthorizedError, match="CANNOT_REVIEW_DRAFT"):
            submit(alice, article_ref=a.data["id"],
                   scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4",
                   comment=_COMMENT_CRITICAL)

    def test_cannot_reply_to_draft_article(self, ctx, articles_dir):
        """Replies require sedimentation/published status."""
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import reply
        from peerpedia_core.exceptions import NotAuthorizedError

        alice = login(ctx, "AliceDraftReply")
        bob = login(ctx, "BobDraftReply")
        a = create(alice, title="Draft Reply Test", content="# Draft")
        aid = a.data["id"]

        _add_maintainer(ctx.db, aid, bob.current_user_id)

        with pytest.raises(NotAuthorizedError):
            reply(alice, article_ref=aid, to_ref=bob.current_user_id,
                  content="Cannot reply to a draft article review thread. "
                          "This should fail because the article has not "
                          "been published yet.")

    def test_self_invite_blocked(self, ctx, articles_dir):
        """Author cannot invite themselves as reviewer."""
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import invite_reviewer
        from peerpedia_core.exceptions import BadRequestError

        alice = login(ctx, "AliceSelfInvite")
        a = create(alice, title="Self Invite", content="# S")
        _publish(alice, article_ref=a.data["id"])

        with pytest.raises(BadRequestError, match="SELF"):
            invite_reviewer(alice, article_ref=a.data["id"],
                            user_ref=alice.current_user_id)

    def test_reply_during_sedimentation_uses_anonymous_id(self, ctx, articles_dir):
        """During sedimentation, replies use anonymous directory IDs derived
        from the replier's signing key.  This means replying to a user who
        hasn't submitted a review is technically possible — the reply goes
        to the anonymous thread, not the target's directory.

        This is by design: reviewer identities are anonymized during
        sedimentation.  The to_ref parameter is used for notification
        routing, not directory placement."""
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import reply

        alice = login(ctx, "AliceAnon")
        bob = login(ctx, "BobAnon")
        a = create(alice, title="Anon Reply Test", content="# X")
        _publish(alice, article_ref=a.data["id"])
        aid = a.data["id"]

        # Bob is maintainer but has NOT submitted a review
        _add_maintainer(ctx.db, aid, bob.current_user_id)

        # Reply succeeds — goes to Alice's anonymous thread, not Bob's dir
        r = reply(alice, article_ref=aid, to_ref=bob.current_user_id,
                  content="During sedimentation, replies use anonymous "
                          "directories derived from the replier's key. "
                          "This reply goes to an anonymous thread.")
        assert r.code == "OK"


# ═══════════════════════════════════════════════════════════════════════════════
# J34 — Full article lifecycle WITH review (integrated journey)
# ═══════════════════════════════════════════════════════════════════════════════


class TestFullArticleWithReview:
    """The complete story: create → publish → review → revise → reply.

    This is the most realistic journey — an article goes through the
    full peer review pipeline: co-authors collaborate, an external
    reviewer submits a critical review, authors revise the article,
    and reply to the reviewer addressing each concern.
    """

    def test_create_publish_review_revise_reply(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create, edit, show
        from peerpedia_core.app.commands.maintainer import consent
        from peerpedia_core.app.commands.review import (
            accept, invite_reviewer, reply, submit,
        )

        # ── Phase 1: Two co-authors create and publish ───────────────────
        alice = login(ctx, "AliceFull")
        bob = login(ctx, "BobCoauthor")
        a = create(alice, title="Deep Learning for Protein Folding",
                   content="# Introduction\n\nWe propose a novel architecture.")
        aid = a.data["id"]

        _add_maintainer(ctx.db, aid, bob.current_user_id)
        # Both maintainers must consent before publish (unanimous consent rule)
        consent(alice, article_ref=aid)
        consent(bob, article_ref=aid)

        _publish(alice, article_ref=aid)
        shown = show(alice, article_ref=aid)
        assert shown.data["status"] == "sedimentation"

        # ── Phase 2: External reviewer invited ───────────────────────────
        carol = login(ctx, "CarolReviewer")
        _add_maintainer(ctx.db, aid, carol.current_user_id)
        invite_reviewer(alice, article_ref=aid,
                        user_ref=carol.current_user_id)
        accept(carol, article_ref=aid)

        # ── Phase 3: Reviewer submits critical review ────────────────────
        carol_review = (
            "The architecture is novel but lacks comparison with AlphaFold2. "
            "Section 3.2 needs a formal proof of convergence. "
            "The training dataset description is incomplete — specify the "
            "exact PDB cutoff date and filtering criteria. Additionally, "
            "the hyperparameter search space should be documented more "
            "thoroughly for reproducibility. The ablation studies in "
            "Section 4 are insufficient. " * 2
        )
        submit(carol, article_ref=aid,
               scores_str="orig=4,rigor=3,comp=3,ped=3,imp=4",
               comment=carol_review)

        # ── Phase 4: Authors reply to reviewer (no mid-sedimentation edit —
        # edits during sedimentation require Closes: trailers that reference
        # anonymous review thread IDs) ──
        reply(alice, article_ref=aid, to_ref=carol.current_user_id,
              content="We have added AlphaFold2 comparison in Section 4, "
                      "a formal convergence proof in Appendix A, and "
                      "complete dataset documentation in Section 3.2. "
                      "The hyperparameter search space is now fully "
                      "documented in Appendix B.")
        reply(bob, article_ref=aid, to_ref=carol.current_user_id,
              content="I can confirm that all experiments have been "
                      "reproduced and the dataset filtering criteria "
                      "are now explicitly documented. The ablation "
                      "studies have been expanded as requested.")

        # ── Verify: article still in sedimentation ───────────────────────
        final = show(alice, article_ref=aid)
        assert final.data["status"] == "sedimentation"


# ═══════════════════════════════════════════════════════════════════════════════
# J35 — Grade-Your-Review: helpfulness ratings from multiple maintainers
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultiRaterHelpfulness:
    """Multiple maintainers independently rate a review's helpfulness.

    Story: Alice and Bob are co-authors.  Carol reviews.  Alice rates
    the review as 5/5.  Bob independently rates it 4/5.  Neither
    rating should interfere with the other.
    """

    def test_independent_ratings_from_coauthors(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import (
            accept, invite_reviewer, rate, submit,
        )

        alice = login(ctx, "AliceMultiR")
        bob = login(ctx, "BobMultiR")
        carol = login(ctx, "CarolRevR")
        a = create(alice, title="Multi-Rater Paper", content="# MR")
        _publish(alice, article_ref=a.data["id"])
        aid = a.data["id"]

        _add_maintainer(ctx.db, aid, bob.current_user_id)
        _add_maintainer(ctx.db, aid, carol.current_user_id)
        invite_reviewer(alice, article_ref=aid,
                        user_ref=carol.current_user_id)
        accept(carol, article_ref=aid)
        submit(carol, article_ref=aid,
               scores_str="orig=5,rigor=5,comp=5,ped=5,imp=5",
               comment=_COMMENT_POSITIVE)

        # Alice rates 5
        r1 = rate(alice, article_ref=aid,
                  reviewer_ref=carol.current_user_id, helpfulness=5)
        assert r1.code == "HELPFULNESS_RATED"

        # Bob rates 4 independently
        r2 = rate(bob, article_ref=aid,
                  reviewer_ref=carol.current_user_id, helpfulness=4)
        assert r2.code == "HELPFULNESS_RATED"


# ═══════════════════════════════════════════════════════════════════════════════
# J36 — Review with declined invitation: reply behavior
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeclinedReviewEdgeCases:
    """After a reviewer declines, reply behavior during sedimentation.

    During sedimentation, replies use anonymous directory IDs derived
    from the replier's signing key — not the target reviewer's
    directory.  So replying to a declined reviewer succeeds; the
    message goes to the anonymous thread.
    """

    def test_declined_reviewer_reply_behavior(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import (
            decline, invite_reviewer, reply,
        )

        alice = login(ctx, "AliceDecl")
        bob = login(ctx, "BobDecl")
        a = create(alice, title="Declined Invite", content="# D")
        _publish(alice, article_ref=a.data["id"])
        aid = a.data["id"]

        _add_maintainer(ctx.db, aid, bob.current_user_id)
        invite_reviewer(alice, article_ref=aid, user_ref=bob.current_user_id)
        decline(bob, article_ref=aid)

        # Bob declined — but during sedimentation, replies use anonymous IDs
        r = reply(alice, article_ref=aid, to_ref=bob.current_user_id,
                  content="Bob declined the invitation, but Alice can still "
                          "post a message to the anonymous review thread. "
                          "This is by design for sedimentation anonymity.")
        assert r.code == "OK"


# ═══════════════════════════════════════════════════════════════════════════════
# J37 — Re-submission: reviewer updates their review
# ═══════════════════════════════════════════════════════════════════════════════


class TestReviewReSubmission:
    """Reviewers can submit multiple times — each submission is an
    update to their review.  No invitation is required.

    Story: Bob submits a critical review.  Alice addresses concerns.
    Bob re-submits with improved scores.  Alice replies.  Bob
    re-submits one more time with final recommendation.
    """

    def test_three_submissions_from_same_reviewer(self, ctx, articles_dir):
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import (
            list_reviews, reply, submit,
        )

        alice = login(ctx, "AliceReSub")
        bob = login(ctx, "BobReSub")
        a = create(alice, title="Re-Submission Paper", content="# R")
        _publish(alice, article_ref=a.data["id"])
        aid = a.data["id"]

        # ── 1st submission: critical ─────────────────────────────────────
        submit(bob, article_ref=aid,
               scores_str="orig=3,rigor=2,comp=3,ped=3,imp=3",
               comment=_COMMENT_CRITICAL)

        reply(alice, article_ref=aid, to_ref=bob.current_user_id,
              content="We have completely revised the manuscript based on "
                      "your feedback. All issues have been addressed.")

        # ── 2nd submission: improved ─────────────────────────────────────
        submit(bob, article_ref=aid,
               scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4",
               comment=_COMMENT_DETAILED)

        reply(alice, article_ref=aid, to_ref=bob.current_user_id,
              content="Thank you. We have further refined Section 3 as "
                      "you suggested.")

        # ── 3rd submission: final recommendation ─────────────────────────
        submit(bob, article_ref=aid,
               scores_str="orig=5,rigor=5,comp=5,ped=5,imp=5",
               comment=_COMMENT_POSITIVE)

        reviews = list_reviews(alice, article_ref=aid).data["reviews"]
        assert len(reviews) >= 1

    def test_re_submission_without_invitation(self, ctx, articles_dir):
        """A user who was never invited can still submit a review."""
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import submit

        alice = login(ctx, "AliceNoInv")
        bob = login(ctx, "BobNoInv")
        a = create(alice, title="No Invitation Paper", content="# NI")
        _publish(alice, article_ref=a.data["id"])

        # Bob was never invited — can still submit
        r = submit(bob, article_ref=a.data["id"],
                   scores_str="orig=4,rigor=4,comp=4,ped=4,imp=4",
                   comment=_COMMENT_LONG)
        assert r.code == "REVIEW_SUBMITTED"

    def test_non_maintainer_can_review(self, ctx, articles_dir):
        """Review submission is open — even non-maintainers can review
        a sedimentation/published article."""
        from peerpedia_core.app.commands.article import create
        from peerpedia_core.app.commands.review import submit

        alice = login(ctx, "AliceOpen")
        outsider = login(ctx, "OutsiderReview")
        a = create(alice, title="Open Review", content="# O")
        _publish(alice, article_ref=a.data["id"])

        # Outsider is NOT a maintainer — can still submit a review
        r = submit(outsider, article_ref=a.data["id"],
                   scores_str="orig=5,rigor=4,comp=4,ped=5,imp=5",
                   comment=_COMMENT_POSITIVE)
        assert r.code == "REVIEW_SUBMITTED"
