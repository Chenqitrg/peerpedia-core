# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Spec: Pure rule functions — article and review authorization.

All functions in ``rules/`` are zero-IO.  Tests construct inputs directly.
"""

import pytest

from peerpedia_core.exceptions import BadRequestError, ConflictError, NotAuthorizedError
from peerpedia_core.rules.articles import (
    FORKABLE_STATUSES,
    PUBLIC_READABLE_STATUSES,
    assert_can_edit_article,
    assert_can_fork_article,
    assert_can_publish_article,
    assert_can_reply_to_review,
    assert_can_submit_review,
    assert_not_folded,
    visible_statuses_for_user,
)
from peerpedia_core.rules.reviews import (
    assert_valid_review,
    guard_proposal_owner,
    require_integrity_level,
    require_signing_key_not_none,
)
from peerpedia_core.types.entities import ArticleMetaExchange, UserExchange


# ── Helpers ────────────────────────────────────────────────────────────────

_GOOD_SCORES = {"originality": 4, "rigor": 4, "completeness": 4,
                "pedagogy": 4, "impact": 4}


def _article(status="draft", score=None, authors=None, publish_consents=None,
             id="a1", title="T"):
    return ArticleMetaExchange(
        id=id, title=title, status=status, authors=tuple(authors or ["u1"]),
        score=score, publish_consents=tuple(publish_consents or []),
    )


def _user(id="u1", name="Alice"):
    return UserExchange(id=id, name=name)


# ═══════════════════════════════════════════════════════════════════════════════
# Article rules
# ═══════════════════════════════════════════════════════════════════════════════


class TestArticleStatusGates:
    def test_submit_review_requires_sedimentation_or_published(self):
        draft = _article("draft")
        with pytest.raises(NotAuthorizedError, match="CANNOT_REVIEW_DRAFT"):
            assert_can_submit_review(draft)

        assert_can_submit_review(_article("sedimentation", score=_GOOD_SCORES)) is not None
        assert_can_submit_review(_article("published", score=_GOOD_SCORES)) is not None

    def test_reply_requires_sedimentation_or_published(self):
        draft = _article("draft")
        with pytest.raises(NotAuthorizedError, match="CANNOT_REPLY_DRAFT"):
            assert_can_reply_to_review(draft, ["u1"], _user("u1"))

    def test_reply_requires_maintainer(self):
        pub = _article("sedimentation", score=_GOOD_SCORES)
        with pytest.raises(NotAuthorizedError, match="NOT_ARTICLE_AUTHOR"):
            assert_can_reply_to_review(pub, ["u1"], _user("u2"))

        # Author is maintainer → ok
        assert_can_reply_to_review(pub, ["u1"], _user("u1")) is not None

    def test_publish_requires_unanimous_consent(self):
        a = _article("draft", authors=["u1", "u2"], publish_consents=["u1"])
        with pytest.raises(NotAuthorizedError, match="Unanimous consent"):
            assert_can_publish_article(a, ["u1", "u2"], _user("u1"))

    def test_publish_single_author_no_consent_needed(self):
        a = _article("draft", authors=["u1"])
        assert_can_publish_article(a, ["u1"], _user("u1")) is not None

    def test_edit_writable_status(self):
        a = _article("rejected")
        with pytest.raises(NotAuthorizedError):
            assert_can_edit_article(a, ["u1"], _user("u1"))

    def test_forkable_statuses(self):
        assert "draft" in FORKABLE_STATUSES
        assert "published" in FORKABLE_STATUSES
        assert "rejected" in FORKABLE_STATUSES
        assert "sedimentation" not in FORKABLE_STATUSES

    def test_fork_draft_requires_maintainer(self):
        a = _article("draft")
        with pytest.raises(NotAuthorizedError):
            assert_can_fork_article(a, user=_user("u2"), maintainer_ids=["u1"])

    def test_fork_already_forked_raises(self):
        a = _article("published")
        with pytest.raises(ConflictError, match="ALREADY_FORKED"):
            assert_can_fork_article(a, already_forked=True)

    def test_folded_article_blocks_edit(self):
        a = _article("sedimentation", score={"originality": 0.5, "rigor": 0.5,
                         "completeness": 0.5, "pedagogy": 0.5, "impact": 0.5})
        with pytest.raises(NotAuthorizedError):
            assert_not_folded(a, threshold=1.0)
            assert_can_edit_article(a, ["u1"], _user("u1"))


class TestVisibility:
    def test_anonymous_sees_public_only(self):
        visible = visible_statuses_for_user(None)
        assert "draft" not in visible
        assert "sedimentation" in visible
        assert "published" in visible

    def test_logged_in_sees_all(self):
        visible = visible_statuses_for_user(_user())
        assert "draft" in visible
        assert "sedimentation" in visible
        assert "published" in visible
        assert "rejected" in visible

    def test_public_readable(self):
        assert "sedimentation" in PUBLIC_READABLE_STATUSES
        assert "published" in PUBLIC_READABLE_STATUSES
        assert "draft" not in PUBLIC_READABLE_STATUSES


# ═══════════════════════════════════════════════════════════════════════════════
# Review rules
# ═══════════════════════════════════════════════════════════════════════════════


class TestReviewValidation:
    def test_valid_scores_pass(self):
        scores = {"originality": 4, "rigor": 4, "completeness": 4,
                  "pedagogy": 4, "impact": 4}
        assert_valid_review(scores, comment="x" * 200)

    def test_missing_dimension_fails(self):
        scores = {"originality": 4, "rigor": 4}
        with pytest.raises(BadRequestError, match="INVALID_REVIEW"):
            assert_valid_review(scores, comment="x" * 200)

    def test_score_out_of_range_fails(self):
        scores = {"originality": 6, "rigor": 4, "completeness": 4,
                  "pedagogy": 4, "impact": 4}
        with pytest.raises(BadRequestError, match="INVALID_REVIEW"):
            assert_valid_review(scores, comment="x" * 200)

    def test_comment_too_short_fails(self):
        scores = {"originality": 4, "rigor": 4, "completeness": 4,
                  "pedagogy": 4, "impact": 4}
        with pytest.raises(BadRequestError, match="INVALID_REVIEW"):
            assert_valid_review(scores, comment="too short")

    def test_comment_none_fails(self):
        scores = {"originality": 4, "rigor": 4, "completeness": 4,
                  "pedagogy": 4, "impact": 4}
        with pytest.raises(BadRequestError, match="INVALID_REVIEW"):
            assert_valid_review(scores, comment=None)

    def test_skip_comment_check(self):
        """With check_comment=False, comment is not validated."""
        scores = {"originality": 4, "rigor": 4, "completeness": 4,
                  "pedagogy": 4, "impact": 4}
        assert_valid_review(scores, comment=None, check_comment=False)

    def test_abbreviated_dimension_keys_accepted(self):
        """Both 'orig' (abbreviated) and 'originality' (full) are accepted."""
        scores = {"orig": 4, "rigor": 4, "comp": 4, "ped": 4, "imp": 4}
        assert_valid_review(scores, comment="x" * 200)


class TestReviewUtilityGuards:
    def test_proposal_owner_mismatch(self):
        mp = type("MP", (), {"proposer_id": "u1"})()
        guard_proposal_owner(mp, "u1")  # no error
        with pytest.raises(NotAuthorizedError, match="NOT_PROPOSAL_CREATOR"):
            guard_proposal_owner(mp, "u2")

    def test_require_signing_key_not_none(self):
        with pytest.raises(BadRequestError, match="MISSING_SIGNING_KEY"):
            require_signing_key_not_none(None)
        require_signing_key_not_none(b"some-key")  # no error

    def test_require_integrity_level(self):
        require_integrity_level("light")
        require_integrity_level("full")
        with pytest.raises(ValueError, match="INVALID_INTEGRITY_LEVEL"):
            require_integrity_level("medium")
