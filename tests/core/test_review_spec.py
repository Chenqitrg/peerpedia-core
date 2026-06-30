# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Spec: Review workflow — invite → accept → submit.

STATUS: LOCKED — these define product behavior.
"""

import pytest

from peerpedia_core.exceptions import NotAuthorizedError
from tests.core.conftest import make_signing_key, make_user


def _article(db, author, *, status="draft"):
    from peerpedia_core.core import create_article_with_content
    key, pubkey = make_signing_key(f"{author.id}@peerpedia")
    result = create_article_with_content(
        db, title="Test", content="# X",
        author_ids=[author.id], signing_key_bytes=key, pubkey_hex=pubkey,
    )
    db.flush()
    return result


def _build_scores(orig=4, rig=4, comp=4, ped=4, imp=4):
    return {"originality": orig, "rigor": rig, "completeness": comp, "pedagogy": ped, "impact": imp}


# ═══════════════════════════════════════════════════════════════════════════════
# SR1 — Invite → accept → submit review
# ═══════════════════════════════════════════════════════════════════════════════


class TestReviewWorkflow:
    def test_invite_accept_submit(self, db, articles_dir):
        """Invite a reviewer, they accept, then submit a review."""
        from peerpedia_core.core import publish_article
        from peerpedia_core.core.reviews import invite_reviewer, accept_invitation, submit_review
        from peerpedia_core.storage.db.crud_review import get_reviews_for_article
        from peerpedia_core.storage.db.crud_maintainer import add_maintainer

        author = make_user(db, "Author")
        reviewer = make_user(db, "Reviewer")
        a = _article(db, author)
        key, pubkey = make_signing_key("author@peerpedia")

        # Publish → sedimentation (review only allowed in sedimentation)
        publish_article(db, a["id"], user_id=author.id,
                        self_review=_build_scores(),
                        signing_key_bytes=key, pubkey_hex=pubkey)
        # Add reviewer as maintainer so they can be invited
        add_maintainer(db, a["id"], reviewer.id)
        db.flush()

        # Invite reviewer
        invite_reviewer(db, article_id=a["id"], inviter_id=author.id, invited_id=reviewer.id)

        # Reviewer accepts
        accept_invitation(db, a["id"], reviewer.id)

        # Reviewer submits (comment must be ≥200 chars)
        key2, pubkey2 = make_signing_key("reviewer@peerpedia")
        comment = (
            "This paper makes a significant contribution to the field. "
            "The methodology is sound, the results are clearly presented, "
            "and the discussion addresses all relevant limitations. "
            "I recommend acceptance with minor revisions. " * 3
        )
        submit_review(db, a["id"], reviewer.id, _build_scores(5, 5, 5, 5, 5),
                      comment=comment,
                      signing_key_bytes=key2, pubkey_hex=pubkey2)

        reviews = get_reviews_for_article(db, a["id"])
        assert len(reviews) >= 1
        assert any(r.reviewer_id == reviewer.id for r in reviews)

    def test_anyone_can_submit_review(self, db, articles_dir):
        """Reviews don't require invitation — any user can submit."""
        from peerpedia_core.core import publish_article
        from peerpedia_core.core.reviews import submit_review

        author = make_user(db, "Author")
        stranger = make_user(db, "Stranger")
        a = _article(db, author)
        key, pubkey = make_signing_key("author@peerpedia")

        publish_article(db, a["id"], user_id=author.id,
                        self_review=_build_scores(),
                        signing_key_bytes=key, pubkey_hex=pubkey)

        key2, pubkey2 = make_signing_key("stranger@peerpedia")
        comment = ("This is an unsolicited review from a stranger. "
                   "Reviews do not require invitation — anyone can "
                   "submit a review on a sedimentation article. " * 2)
        result = submit_review(db, a["id"], stranger.id, _build_scores(),
                               comment=comment,
                               signing_key_bytes=key2, pubkey_hex=pubkey2)
        assert result is not None
