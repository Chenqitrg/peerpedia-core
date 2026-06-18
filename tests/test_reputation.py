# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for the reputation mechanism (core calculation logic)."""

import pytest

from peerpedia_core.storage.db.crud_article import create_article
from peerpedia_core.storage.db.crud_user import create_user, update_user_reputation
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import User
from peerpedia_core.types.scores import ReputationScores
from peerpedia_core.workflow.reputation import (
    compute_author_reputation,
    get_reviewer_weight,
    recalculate_all_reputations,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_score(originality=3.0, rigor=3.0, completeness=3.0, pedagogy=3.0, impact=3.0) -> dict:
    return {
        "originality": originality,
        "rigor": rigor,
        "completeness": completeness,
        "pedagogy": pedagogy,
        "impact": impact,
    }


# ── compute_author_reputation ─────────────────────────────────────────────────


class TestComputeAuthorReputation:
    """Reputation derived from article scores."""

    @pytest.fixture
    def session(self, engine):
        s = get_session(engine)
        yield s
        s.close()

    def test_no_articles_returns_defaults(self, session):
        """A user with no articles gets all-zero reputation."""
        user = create_user(session, "alice")
        rep = compute_author_reputation(session, user.id)

        assert isinstance(rep, ReputationScores)
        assert rep.professionalism == 0.0
        assert rep.objectivity == 0.0
        assert rep.collaboration == 0.0
        assert rep.pedagogy == 0.0

    def test_single_article_blends_with_default_rep(self, session):
        """A single published article builds reputation through blending.

        Dimension mapping:
          professionalism <- avg(originality=4, rigor=3) = 3.5
          objectivity    <- completeness=5             = 5.0
          collaboration  <- avg(originality=4, impact=4) = 4.0
          pedagogy       <- pedagogy=4                  = 4.0

        Blending weight = article_to_author_weight = 0.3.
        Old rep is all zeros, so blended = 0.3 * article_avg.
        """
        user = create_user(session, "bob")
        create_article(
            session,
            authors=[user.id],
            status="published",
            score=_build_score(originality=4, rigor=3, completeness=5, pedagogy=4, impact=4),
        )

        rep = compute_author_reputation(session, user.id)

        assert rep.professionalism == pytest.approx(0.3 * 3.5, abs=0.01)
        assert rep.objectivity == pytest.approx(0.3 * 5.0, abs=0.01)
        assert rep.collaboration == pytest.approx(0.3 * 4.0, abs=0.01)
        assert rep.pedagogy == pytest.approx(0.3 * 4.0, abs=0.01)

    def test_multiple_articles_averaged_and_blended(self, session):
        """Multiple articles are averaged (weighted by status) then blended."""
        user = create_user(session, "carol")

        # published article with perfect scores
        create_article(
            session,
            authors=[user.id],
            status="published",
            score=_build_score(originality=5, rigor=5, completeness=5, pedagogy=5, impact=5),
        )
        # sedimentation article with moderate scores
        create_article(
            session,
            authors=[user.id],
            status="sedimentation",
            score=_build_score(originality=1, rigor=1, completeness=1, pedagogy=1, impact=1),
        )

        rep = compute_author_reputation(session, user.id)

        # Status weights: published = 1.0, sedimentation = 0.7
        # Article reputation averages (all 5 dims map the same for each article):
        #   published: professionalism=5, objectivity=5, collaboration=5, pedagogy=5
        #   sedimentation: professionalism=1, objectivity=1, collaboration=1, pedagogy=1
        # Weighted average:
        #   professionalism = (5*1.0 + 1*0.7) / (1.0 + 0.7) = 5.7/1.7 = 3.3529...
        #   Then blend with weight 0.3: 0.3 * 3.3529 = 1.0059
        assert rep.professionalism == pytest.approx(0.3 * (5.0 + 0.7) / 1.7, abs=0.02)
        assert rep.objectivity == pytest.approx(0.3 * (5.0 + 0.7) / 1.7, abs=0.02)
        assert rep.collaboration == pytest.approx(0.3 * (5.0 + 0.7) / 1.7, abs=0.02)
        assert rep.pedagogy == pytest.approx(0.3 * (5.0 + 0.7) / 1.7, abs=0.02)

    def test_blends_with_existing_reputation(self, session):
        """Existing reputation is blended with the new article-derived value."""
        user = create_user(session, "dave")

        # First computation (no existing rep) -- sets reputation to blended value
        create_article(
            session,
            authors=[user.id],
            status="published",
            score=_build_score(originality=4, rigor=4, completeness=4, pedagogy=4, impact=4),
        )
        rep1 = compute_author_reputation(session, user.id)

        # Article avg: professionalism = avg(4,4)=4, objectivity = 4, etc.
        # rep1 = 0.3 * 4 = 1.2 for all dimensions
        assert rep1.professionalism == pytest.approx(1.2, abs=0.01)

        # Add a second article. Now blending uses the existing reputation (1.2).
        create_article(
            session,
            authors=[user.id],
            status="published",
            score=_build_score(originality=5, rigor=5, completeness=5, pedagogy=5, impact=5),
        )
        rep2 = compute_author_reputation(session, user.id)

        # New article average from both articles:
        #   first: all 4, second: all 5
        #   Article average: professionalism = avg(4,5)=4.5, etc.
        # Blended: (1-0.3)*1.2 + 0.3*4.5 = 0.7*1.2 + 0.3*4.5 = 0.84 + 1.35 = 2.19
        assert rep2.professionalism == pytest.approx(2.19, abs=0.02)
        assert rep2.objectivity == pytest.approx(2.19, abs=0.02)

    def test_article_without_score_skipped(self, session):
        """Articles missing a score dict are skipped in the calculation."""
        user = create_user(session, "eve")
        create_article(
            session,
            authors=[user.id],
            status="published",
            score=None,  # no score set yet
        )
        rep = compute_author_reputation(session, user.id)
        assert rep.professionalism == 0.0
        assert rep.objectivity == 0.0
        assert rep.collaboration == 0.0
        assert rep.pedagogy == 0.0

    def test_persisted_in_db(self, session):
        """After compute_author_reputation, the DB record is updated."""
        user = create_user(session, "frank")
        create_article(
            session,
            authors=[user.id],
            status="published",
            score=_build_score(originality=5, rigor=5, completeness=5, pedagogy=5, impact=5),
        )
        compute_author_reputation(session, user.id)

        session.expire_all()
        updated = session.get(User, user.id)
        assert updated is not None
        assert updated.reputation is not None
        assert updated.reputation.get("professionalism", 0) > 0


# ---- get_reviewer_weight ----------------------------------------------------


class TestGetReviewerWeight:
    """Weight factor derived from reviewer reputation."""

    @pytest.fixture
    def session(self, engine):
        s = get_session(engine)
        yield s
        s.close()

    def test_unknown_user_returns_default(self, session):
        """A user who doesn't exist gets weight 1.0."""
        rep = get_reviewer_weight(session, "nonexistent-id")
        assert rep == 1.0

    def test_user_without_reputation_returns_default(self, session):
        """A user who has no reputation data gets weight 1.0."""
        user = create_user(session, "grace")
        rep = get_reviewer_weight(session, user.id)
        assert rep == 1.0

    def test_user_with_high_rep_gets_weight_above_one(self, session):
        """Avg reputation > 3.0 gives weight > 1.0."""
        user = create_user(session, "heidi")
        update_user_reputation(
            session,
            user.id,
            {"professionalism": 5.0, "objectivity": 5.0, "collaboration": 5.0, "pedagogy": 5.0},
        )
        rep = get_reviewer_weight(session, user.id)
        # avg_rep = 5.0 -> weight = 1.0 + 0.2 * (5.0 - 3.0) / 2.0 = 1.2
        assert rep == pytest.approx(1.2, abs=0.01)

    def test_user_with_low_rep_gets_weight_below_one(self, session):
        """Avg reputation < 3.0 gives weight < 1.0."""
        user = create_user(session, "ivan")
        update_user_reputation(
            session,
            user.id,
            {"professionalism": 1.0, "objectivity": 1.0, "collaboration": 1.0, "pedagogy": 1.0},
        )
        rep = get_reviewer_weight(session, user.id)
        # avg_rep = 1.0 -> weight = 1.0 + 0.2 * (1.0 - 3.0) / 2.0 = 0.8
        assert rep == pytest.approx(0.8, abs=0.01)


# ---- recalculate_all_reputations ---------------------------------------------


class TestRecalculateAllReputations:
    """Bulk recalculation for all users."""

    @pytest.fixture
    def session(self, engine):
        s = get_session(engine)
        yield s
        s.close()

    def test_recalculates_all_users(self, session):
        """Every user in the system gets their reputation updated."""
        u1 = create_user(session, "jill")
        u2 = create_user(session, "jack")
        create_article(
            session,
            authors=[u1.id, u2.id],
            status="published",
            score=_build_score(originality=5, rigor=5, completeness=5, pedagogy=5, impact=5),
        )

        count = recalculate_all_reputations(session)
        assert count == 2

        session.expire_all()
        for u in (u1, u2):
            updated = session.get(User, u.id)
            assert updated is not None
            assert updated.reputation is not None
            assert updated.reputation.get("professionalism", 0) > 0

    def test_returns_count_of_updated_users(self, session):
        """The function returns the number of users processed."""
        create_user(session, "ken")
        create_user(session, "laura")
        count = recalculate_all_reputations(session)
        assert count == 2

    def test_empty_db_returns_zero(self, session):
        """No users -> returns 0 (idempotent)."""
        count = recalculate_all_reputations(session)
        assert count == 0


# ---- Weighted article scoring ------------------------------------------------


class TestWeightedArticleScoring:
    """compute_article_score with optional reviewer_weights."""

    def test_no_reviewer_weights_unchanged(self):
        """Without reviewer_weights, behaves exactly as before."""
        from peerpedia_core.workflow.scoring import compute_article_score

        reviews = [
            {
                "scores": {"originality": 4, "rigor": 3, "completeness": 5, "pedagogy": 4, "impact": 4},
                "is_self": False,
                "reviewer_id": "u1",
            },
        ]
        result = compute_article_score(reviews)
        assert result["originality"] == 4.0
        assert result["completeness"] == 5.0

    def test_reviewer_weights_applied(self):
        """Reviewer weights multiply the contribution of each review."""
        from peerpedia_core.workflow.scoring import compute_article_score

        reviews = [
            {
                "scores": {"originality": 4, "rigor": 4, "completeness": 4, "pedagogy": 4, "impact": 4},
                "is_self": False,
                "reviewer_id": "trusted",
            },
            {
                "scores": {"originality": 2, "rigor": 2, "completeness": 2, "pedagogy": 2, "impact": 2},
                "is_self": False,
                "reviewer_id": "low_rep",
            },
        ]
        weights = {"trusted": 2.0, "low_rep": 0.5}
        result = compute_article_score(reviews, reviewer_weights=weights)

        # Both are community reviews (weight = 0.85).
        # With reviewer weights:
        #   trusted: 0.85 * 2.0 = 1.7
        #   low_rep: 0.85 * 0.5 = 0.425
        # Weighted avg = (4*1.7 + 2*0.425) / (1.7 + 0.425)
        #             = (6.8 + 0.85) / 2.125 = 7.65 / 2.125 = 3.6
        assert result["originality"] == pytest.approx(3.6, abs=0.01)

    def test_missing_reviewer_id_falls_back_to_one(self):
        """A review without a matching weight entry defaults to 1.0."""
        from peerpedia_core.workflow.scoring import compute_article_score

        reviews = [
            {
                "scores": {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
                "is_self": False,
                "reviewer_id": "unknown",
            },
        ]
        weights = {}
        result = compute_article_score(reviews, reviewer_weights=weights)
        assert result["originality"] == 3.0

    def test_weights_multiply_with_self_review_weight(self):
        """Reviewer weights also affect self-reviews."""
        from peerpedia_core.workflow.scoring import compute_article_score

        reviews = [
            {
                "scores": {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 5, "impact": 5},
                "is_self": True,
                "reviewer_id": "author",
            },
        ]
        # Self-review base weight = 0.15, boosted by 2.0 = 0.30
        weights = {"author": 2.0}
        result = compute_article_score(reviews, reviewer_weights=weights)
        # Only one review, weight doesn't change the computed value
        assert result["originality"] == 5.0
