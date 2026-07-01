# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Tests for storage/db/state.py — reputation state extraction."""

import pytest

from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.storage.db.engine import get_session
from peerpedia_core.storage.db.models import ReviewMetaStorage

from tests.crud.conftest import default_scores, make_article, make_user


# ── Helper ───────────────────────────────────────────────────────────────────


def _make_review(session, article_id, reviewer_id, *, status="submitted", scores=None):
    """Create a ReviewMetaStorage row — caller must commit."""
    import uuid as _uuid

    r = ReviewMetaStorage(
        id=str(_uuid.uuid4()),
        article_id=article_id,
        commit_hash=_uuid.uuid4().hex[:8],
        reviewer_id=reviewer_id,
        scope="sedimentation",
        status=status,
        scores=scores or default_scores(),
    )
    session.add(r)
    session.flush()
    return r


# ═══════════════════════════════════════════════════════════════════════════════
# extract_reputation_state
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtractReputationState:
    def test_user_not_found_raises(self, engine):
        """Non-existent user_id raises NotFoundError — caller must handle gracefully."""
        from peerpedia_core.storage.db.state import extract_reputation_state

        session = get_session(engine)
        with pytest.raises(NotFoundError, match="USER_NOT_FOUND"):
            extract_reputation_state(session, "nonexistent")
        session.close()

    def test_empty_state_for_user_without_articles(self, engine):
        """User with no articles returns a valid state with empty maps."""
        from peerpedia_core.storage.db.state import extract_reputation_state

        session = get_session(engine)
        user = make_user(session, "alice")
        state = extract_reputation_state(session, user.id)
        assert len(state.articles) == 0
        assert len(state.reviews) == 0
        # The user themselves should appear in the users map
        assert user.id in state.users
        session.close()

    def test_includes_articles(self, engine):
        """User's articles appear in the ArticleMetaExchange map."""
        from peerpedia_core.storage.db.state import extract_reputation_state

        session = get_session(engine)
        user = make_user(session, "alice")
        article = make_article(session, authors=[user.id], title="My Paper", status="published")
        state = extract_reputation_state(session, user.id)
        assert article.id in state.articles
        assert state.articles[article.id].title == "My Paper"
        assert state.articles[article.id].status == "published"
        session.close()

    def test_filters_non_submitted_reviews(self, engine):
        """Only 'submitted' reviews are included — invited/accepted reviews excluded."""
        from peerpedia_core.storage.db.state import extract_reputation_state

        session = get_session(engine)
        author = make_user(session, "author")
        reviewer = make_user(session, "reviewer")
        article = make_article(session, authors=[author.id])

        # Create an invited review (not submitted) — should be excluded
        _make_review(session, article.id, reviewer.id, status="invited")
        # Create a submitted review — should be included
        _make_review(session, article.id, reviewer.id, status="submitted")

        state = extract_reputation_state(session, author.id)
        article_reviews = state.reviews.get(article.id, ())
        assert len(article_reviews) == 1
        assert article_reviews[0].reviewer_id == reviewer.id
        assert article_reviews[0].status == "submitted"
        session.close()

    def test_includes_reviewer_users(self, engine):
        """Reviewer user IDs are included in the users map —
        their reputation data is needed for scoring."""
        from peerpedia_core.storage.db.state import extract_reputation_state

        session = get_session(engine)
        author = make_user(session, "author")
        reviewer = make_user(session, "reviewer")
        article = make_article(session, authors=[author.id])
        _make_review(session, article.id, reviewer.id, status="submitted")

        state = extract_reputation_state(session, author.id)
        assert reviewer.id in state.users
        assert state.users[reviewer.id].name == "reviewer"
        session.close()

    def test_reputation_carried_through(self, engine):
        """User.reputation dict is included in UserExchange.reputation."""
        from peerpedia_core.storage.db.state import extract_reputation_state

        session = get_session(engine)
        author = make_user(session, "author")
        # Set a reputation score
        from peerpedia_core.storage.db.crud_user import get_user_by_id
        u = get_user_by_id(session, author.id)
        u.reputation = {"orig": 4.0, "rigor": 3.5}
        session.flush()

        state = extract_reputation_state(session, author.id)
        user_exchange = state.users[author.id]
        assert user_exchange.reputation == {"orig": 4.0, "rigor": 3.5}
        session.close()
