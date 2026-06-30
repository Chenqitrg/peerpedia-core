# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Pure compute functions — scoring, reputation, sedimentation, monotonic search.

All functions in ``compute/`` are zero-IO, zero-DB.  Tests construct
inputs directly — fast, deterministic, no fixtures needed.
"""

import pytest
from datetime import datetime, timezone, timedelta

from peerpedia_core.compute.scoring import aggregate_review_scores
from peerpedia_core.compute.sedimentation import (
    apply_no_review_penalty,
    is_ready_to_publish,
)
from peerpedia_core.compute.monotonic import search_monotonic_boundary
from peerpedia_core.compute.state import ReputationState, _to_primitive
from peerpedia_core.compute.reputation import (
    blend_reputation,
    compute_reputation,
    get_reviewer_weight,
)
from peerpedia_core.types.entities import ArticleMetaExchange, UserExchange
from peerpedia_core.types.scores import ReputationScores


# ═══════════════════════════════════════════════════════════════════════════════
# Scoring — aggregate_review_scores
# ═══════════════════════════════════════════════════════════════════════════════


class TestAggregateReviewScores:
    """Weighted average of 5-dim scores across reviews."""

    def test_empty_reviews_returns_none(self):
        assert aggregate_review_scores([]) is None

    def test_single_self_review(self):
        r = aggregate_review_scores([
            {"scores": {"originality": 5, "rigor": 5, "completeness": 5,
                        "pedagogy": 4, "impact": 5},
             "is_self": True},
        ])
        assert r is not None
        # Self-review weighted at self_review_weight
        assert 0 < r["originality"] <= 5

    def test_single_community_review(self):
        r = aggregate_review_scores([
            {"scores": {"originality": 4, "rigor": 4, "completeness": 4,
                        "pedagogy": 4, "impact": 4},
             "is_self": False},
        ])
        assert r is not None
        assert r["originality"] == 4.0

    def test_mixed_self_and_community(self):
        """Community review has larger weight than self-review."""
        r = aggregate_review_scores([
            {"scores": {"originality": 5, "rigor": 5, "completeness": 5,
                        "pedagogy": 5, "impact": 5},
             "is_self": True},
            {"scores": {"originality": 2, "rigor": 2, "completeness": 2,
                        "pedagogy": 2, "impact": 2},
             "is_self": False},
        ])
        assert r is not None
        # Community weight (0.85) > self weight (0.15) → closer to 2
        assert r["originality"] < 4.0

    def test_invalid_scores_raises(self):
        with pytest.raises(ValueError, match="empty or invalid scores"):
            aggregate_review_scores([
                {"scores": {}, "is_self": False},
            ])
        with pytest.raises(ValueError, match="empty or invalid scores"):
            aggregate_review_scores([
                {"scores": None, "is_self": False},
            ])

    def test_reviewer_weights_applied(self):
        """High-reputation reviewer → higher weight."""
        r = aggregate_review_scores([
            {"scores": {"originality": 5, "rigor": 5, "completeness": 5,
                        "pedagogy": 5, "impact": 5},
             "is_self": False, "reviewer_id": "expert"},
            {"scores": {"originality": 2, "rigor": 2, "completeness": 2,
                        "pedagogy": 2, "impact": 2},
             "is_self": False, "reviewer_id": "novice"},
        ], reviewer_weights={"expert": 2.0, "novice": 0.5})
        assert r is not None
        # Expert with weight 2.0 on score 5 dominates novice with 0.5 on 2
        assert r["originality"] > 4.0

    def test_scope_weights_applied(self):
        """Sedimentation reviews weigh more than published."""
        r = aggregate_review_scores([
            {"scores": {"originality": 5, "rigor": 5, "completeness": 5,
                        "pedagogy": 5, "impact": 5},
             "is_self": False, "scope": "sedimentation"},
            {"scores": {"originality": 2, "rigor": 2, "completeness": 2,
                        "pedagogy": 2, "impact": 2},
             "is_self": False, "scope": "published"},
        ], scope_weights={"sedimentation": 1.0, "published": 0.5})
        assert r is not None
        assert r["originality"] > 3.5  # closer to 5 than 2

    def test_all_zero_scores(self):
        """All zero scores → result is zero."""
        r = aggregate_review_scores([
            {"scores": {"originality": 0, "rigor": 0, "completeness": 0,
                        "pedagogy": 0, "impact": 0},
             "is_self": False},
        ])
        assert r is not None
        assert r["originality"] == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Sedimentation
# ═══════════════════════════════════════════════════════════════════════════════


class TestSedimentation:
    def test_is_ready_to_publish_none(self):
        assert is_ready_to_publish(None) is False

    def test_is_ready_to_publish_past(self):
        past = datetime.now(timezone.utc) - timedelta(days=7)
        assert is_ready_to_publish(past) is True

    def test_is_ready_to_publish_future(self):
        future = datetime.now(timezone.utc) + timedelta(days=7)
        assert is_ready_to_publish(future) is False

    def test_is_ready_to_publish_naive_treated_as_utc(self):
        """Naive datetime is treated as UTC."""
        past = datetime.now() - timedelta(days=7)  # naive
        assert is_ready_to_publish(past) is True

    def test_apply_no_review_penalty_reduces_scores(self):
        scores = {"originality": 4.0, "rigor": 3.0, "completeness": 5.0}
        result = apply_no_review_penalty(scores)
        assert result["originality"] < 4.0
        assert result["rigor"] < 3.0
        assert result["completeness"] < 5.0

    def test_apply_no_review_penalty_floors_at_zero(self):
        scores = {"originality": 0.1, "rigor": 0.0}
        result = apply_no_review_penalty(scores)
        assert result["originality"] >= 0.0
        assert result["rigor"] >= 0.0

    def test_apply_no_review_penalty_none_raises(self):
        with pytest.raises(TypeError, match="scores must not be None"):
            apply_no_review_penalty(None)


# ═══════════════════════════════════════════════════════════════════════════════
# Monotonic search
# ═══════════════════════════════════════════════════════════════════════════════


class TestMonotonicSearch:
    def test_all_false_returns_none(self):
        def probe(i):
            return False
        assert search_monotonic_boundary(probe, 100) is None

    def test_all_true_returns_zero(self):
        def probe(i):
            return True
        assert search_monotonic_boundary(probe, 100) == 0

    def test_first_true_at_boundary(self):
        """True starts at index 42."""
        def probe(i):
            return i >= 42
        assert search_monotonic_boundary(probe, 100) == 42

    def test_first_true_at_end(self):
        """Only the very last element is True."""
        def probe(i):
            return i >= 99
        assert search_monotonic_boundary(probe, 99) == 99

    def test_small_range(self):
        """Range of 5 elements, True starts at 2."""
        def probe(i):
            return i >= 2
        assert search_monotonic_boundary(probe, 4) == 2

    def test_none_probe_aborts(self):
        """Any probe returning None aborts the search."""
        call_count = 0

        def probe(i):
            nonlocal call_count
            call_count += 1
            if i >= 5:
                return None
            return False

        assert search_monotonic_boundary(probe, 100) is None
        # Should abort early, not continue probing
        assert call_count <= 10

    def test_k_less_than_2_raises(self):
        with pytest.raises(ValueError, match="k must be >= 2"):
            search_monotonic_boundary(lambda i: True, 10, k=1)

    def test_single_element_range(self):
        """Range of 1 element."""
        assert search_monotonic_boundary(lambda i: i >= 0, 0) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Reputation
# ═══════════════════════════════════════════════════════════════════════════════


class TestReputation:
    def _article(self, id_, authors, score, status="published"):
        return id_, ArticleMetaExchange(
            id=id_, title="T", status=status, authors=tuple(authors),
            score=score, publish_consents=None,
        )

    def _user(self, id_, name="U"):
        return id_, UserExchange(id=id_, name=name)

    def _state(self, articles, users):
        return ReputationState(
            articles={a[0]: a[1] for a in articles},
            reviews={},
            users={u[0]: u[1] for u in users},
        )

    def test_no_articles_returns_zeros(self):
        u = self._user("u1", "Alice")
        state = self._state([], [u])
        rep = compute_reputation(state, "u1")
        assert rep.professionalism == 0.0
        assert rep.objectivity == 0.0

    def test_single_article(self):
        u = self._user("u1")
        a = self._article("a1", ["u1"], {"originality": 5, "rigor": 5,
                           "completeness": 5, "pedagogy": 5, "impact": 5})
        state = self._state([a], [u])
        rep = compute_reputation(state, "u1")
        # professionalism ← avg(originality=5, rigor=5) = 5.0
        assert rep.professionalism == 5.0
        assert rep.pedagogy == 5.0

    def test_user_not_author_returns_zeros(self):
        u1 = self._user("u1")
        u2 = self._user("u2")
        a = self._article("a1", ["u2"], {"originality": 5, "rigor": 5,
                           "completeness": 5, "pedagogy": 5, "impact": 5})
        state = self._state([a], [u1, u2])
        rep = compute_reputation(state, "u1")
        assert rep.professionalism == 0.0

    def test_blend_reputation_ema(self):
        existing = {"professionalism": 3.0, "objectivity": 3.0,
                    "collaboration": 3.0, "pedagogy": 3.0}
        new = ReputationScores(professionalism=5.0, objectivity=5.0,
                                collaboration=5.0, pedagogy=5.0)
        blended = blend_reputation(existing, new)
        # EMA with default weight → closer to new but not equal
        assert 3.0 < blended.professionalism < 5.0

    def test_blend_empty_existing(self):
        blended = blend_reputation({}, ReputationScores(
            professionalism=4.0, objectivity=4.0, collaboration=4.0, pedagogy=4.0))
        # Starting from 0 → blended toward 4
        assert 0.0 < blended.professionalism <= 4.0

    def test_get_reviewer_weight_none(self):
        assert get_reviewer_weight(None) == 1.0

    def test_get_reviewer_weight_empty(self):
        assert get_reviewer_weight({}) == 1.0

    def test_get_reviewer_weight_high_reputation(self):
        high_rep = {"professionalism": 5.0, "objectivity": 5.0,
                    "collaboration": 5.0, "pedagogy": 5.0}
        assert get_reviewer_weight(high_rep) > 1.0

    def test_get_reviewer_weight_low_reputation(self):
        low_rep = {"professionalism": 1.0, "objectivity": 1.0,
                   "collaboration": 1.0, "pedagogy": 1.0}
        w = get_reviewer_weight(low_rep)
        assert w >= 0.0  # floors at zero, but could be < 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# State serialization
# ═══════════════════════════════════════════════════════════════════════════════


class TestStateSerialization:
    def test_to_primitive_scalars(self):
        assert _to_primitive("hello") == "hello"
        assert _to_primitive(42) == 42
        assert _to_primitive(3.14) == 3.14
        assert _to_primitive(True) is True
        assert _to_primitive(None) is None

    def test_to_primitive_tuple(self):
        assert _to_primitive((1, "a", True)) == [1, "a", True]

    def test_to_primitive_dict(self):
        assert _to_primitive({"key": (1, 2)}) == {"key": [1, 2]}

    def test_to_primitive_unknown_type_raises(self):
        with pytest.raises(TypeError, match="Cannot serialize"):
            _to_primitive(object())
