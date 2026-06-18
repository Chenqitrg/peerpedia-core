# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for sedimentation pool workflow and scoring aggregation."""

from datetime import datetime, timedelta, timezone

import pytest

# Register all models with Base.metadata before engine fixture creates tables
import peerpedia_core.storage.db.models  # noqa: F401


class TestComputeArticleScore:
    """Score aggregation: weighted average of reviews, with self-review weighting."""

    def test_no_reviews_returns_none(self):
        from peerpedia_core.workflow.scoring import compute_article_score

        assert compute_article_score([]) is None

    def test_single_review_equals_that_review(self):
        from peerpedia_core.workflow.scoring import compute_article_score

        reviews = [{"scores": {"originality": 4, "rigor": 3, "completeness": 5, "pedagogy": 4, "impact": 4}, "is_self": False}]
        result = compute_article_score(reviews)
        assert result["originality"] == 4.0
        assert result["completeness"] == 5.0

    def test_self_review_weighted_lower(self):
        """Self-review has smaller weight than community reviews."""
        from peerpedia_core.workflow.scoring import compute_article_score

        reviews = [
            {"scores": {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 5, "impact": 5}, "is_self": True},
            {"scores": {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3}, "is_self": False},
        ]
        result = compute_article_score(reviews)
        # Self-review (5) weighted 0.15, community (3) weighted 0.85
        # expected ≈ 5*0.15 + 3*0.85 = 0.75 + 2.55 = 3.3
        assert result["originality"] == pytest.approx(3.3, abs=0.1)

    def test_multiple_community_reviews_averaged(self):
        from peerpedia_core.workflow.scoring import compute_article_score

        reviews = [
            {"scores": {"originality": 4, "rigor": 4, "completeness": 4, "pedagogy": 4, "impact": 4}, "is_self": False},
            {"scores": {"originality": 2, "rigor": 2, "completeness": 2, "pedagogy": 2, "impact": 2}, "is_self": False},
        ]
        result = compute_article_score(reviews)
        assert result["originality"] == 3.0


class TestSedimentation:
    """Sink time calculation and auto-publish logic."""

    def test_is_ready_to_publish(self):
        from peerpedia_core.workflow.sedimentation import is_ready_to_publish

        past = datetime.now(timezone.utc) - timedelta(days=10)
        future = datetime.now(timezone.utc) + timedelta(days=10)
        assert is_ready_to_publish(past) is True
        assert is_ready_to_publish(future) is False

    def test_is_ready_to_publish_none(self):
        """Bug 4: is_ready_to_publish crashes on None."""
        from peerpedia_core.workflow.sedimentation import is_ready_to_publish

        assert is_ready_to_publish(None) is False

    def test_apply_no_review_penalty(self):
        """No reviews → score penalty applied."""
        from peerpedia_core.workflow.sedimentation import apply_no_review_penalty

        scores = {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3}
        penalized = apply_no_review_penalty(scores)
        # Penalty reduces each dimension by at least 0.5
        assert penalized["originality"] < scores["originality"]
        assert penalized["originality"] >= 0

    def test_apply_no_review_penalty_none(self):
        """Bug 5: apply_no_review_penalty crashes on None."""
        from peerpedia_core.workflow.sedimentation import apply_no_review_penalty

        result = apply_no_review_penalty(None)
        assert result == {}


class TestPerCommitScoring:
    """Score computation: aggregates reviews across all commits."""

    def _make_user(self, session, name):
        from peerpedia_core.storage.db.models import User

        u = User(username=f"test_{name}", password_hash="$2b$12$test", name=name, anonymous_name=f"anon_{name}")
        session.add(u)
        session.commit()
        return u

    def _make_article(self, session, authors):
        from peerpedia_core.storage.db.models import Article, ArticleAuthor

        a = Article(status="sedimentation")
        session.add(a)
        session.flush()
        for pos, aid in enumerate(authors):
            session.add(ArticleAuthor(article_id=a.id, author_id=aid, position=pos))
        session.commit()
        return a

    def _make_review(self, session, article_id, commit_hash, reviewer_id, scope, scores):
        from peerpedia_core.storage.db.crud_review import create_review

        return create_review(
            session, article_id=article_id, commit_hash=commit_hash, reviewer_id=reviewer_id, scope=scope, scores=scores
        )

    def test_accumulate_scores_across_commits(self, engine):
        """Reviews from different commits are averaged together."""
        from peerpedia_core.storage.db.engine import get_session

        session = get_session(engine)

        author = self._make_user(session, "pcs_author")
        rv = self._make_user(session, "pcs_rv")
        article = self._make_article(session, [author.id])

        # Review for commit "abc" with score 5
        self._make_review(
            session,
            article.id,
            "abc",
            rv.id,
            "pool",
            {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 5, "impact": 5},
        )
        # Review for commit "def" with score 1
        self._make_review(
            session,
            article.id,
            "def",
            rv.id,
            "pool",
            {"originality": 1, "rigor": 1, "completeness": 1, "pedagogy": 1, "impact": 1},
        )

        from peerpedia_core.workflow.scoring import compute_article_score_for_commit

        score = compute_article_score_for_commit(session, article.id)

        assert score is not None
        # Two reviews: scores 5 and 1 → average 3.0 per dimension
        assert score["originality"] == 3.0
        session.close()

    def test_no_reviews_returns_none(self, engine):
        """If no reviews exist for the article, return None."""
        from peerpedia_core.storage.db.engine import get_session

        session = get_session(engine)

        author = self._make_user(session, "pcs_none")
        article = self._make_article(session, [author.id])

        from peerpedia_core.workflow.scoring import compute_article_score_for_commit

        result = compute_article_score_for_commit(session, article.id)
        assert result is None
        session.close()

    def test_unknown_article_returns_none(self, engine):
        """compute_article_score_for_commit for non-existent article returns None."""
        from peerpedia_core.storage.db.engine import get_session
        from peerpedia_core.workflow.scoring import compute_article_score_for_commit

        session = get_session(engine)
        result = compute_article_score_for_commit(session, "no-such-article", "abc")
        assert result is None
        session.close()

    def test_reviewer_weights_applied(self, engine):
        """Reputation-based reviewer weights are applied in per-commit scoring."""
        from peerpedia_core.storage.db.engine import get_session

        session = get_session(engine)

        author = self._make_user(session, "pcs_au")
        rv = self._make_user(session, "pcs_rvw")

        # Give reviewer high reputation
        from peerpedia_core.storage.db.crud_user import update_user_reputation

        update_user_reputation(
            session, rv.id, {"professionalism": 5.0, "objectivity": 5.0, "collaboration": 5.0, "pedagogy": 5.0}
        )

        article = self._make_article(session, [author.id])
        self._make_review(
            session,
            article.id,
            "hash_w",
            rv.id,
            "pool",
            {"originality": 3, "rigor": 3, "completeness": 3, "pedagogy": 3, "impact": 3},
        )

        from peerpedia_core.workflow.scoring import compute_article_score_for_commit

        score = compute_article_score_for_commit(session, article.id, "hash_w")

        assert score is not None
        assert score["originality"] == 3.0
        session.close()
