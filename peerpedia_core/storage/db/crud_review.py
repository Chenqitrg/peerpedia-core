# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Review score/contribution cache operations.

Review content lives in git (reviews/<reviewer_id>/scores.json,
thread.md).  The database Review table is a cache of structured
scores and contributions — synced after git writes — so scoring
and reputation workflows can query without reading git.
"""

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import Review


def upsert_review(
    session: Session,
    article_id: str,
    commit_hash: str,
    reviewer_id: str,
    scope: str,
    scores: dict,
    contributions: dict | None = None,
) -> Review:
    """Create or update the scores/contributions cache for a review.

    Called AFTER review files are committed to git.  Uses
    (article_id, reviewer_id, scope, commit_hash) as the unique key.
    """
    existing = (
        session.query(Review)
        .filter(
            Review.article_id == article_id,
            Review.reviewer_id == reviewer_id,
            Review.scope == scope,
            Review.commit_hash == commit_hash,
        )
        .first()
    )
    if existing:
        existing.scores = scores
        if contributions is not None:
            existing.contributions = contributions
        session.commit()
        return existing

    r = Review(
        article_id=article_id,
        commit_hash=commit_hash,
        reviewer_id=reviewer_id,
        scope=scope,
        scores=scores,
        contributions=contributions,
    )
    session.add(r)
    session.commit()
    return r


def get_reviews_for_article(
    session: Session,
    article_id: str,
) -> list[Review]:
    """Return all cached reviews for an article, newest first."""
    return (
        session.query(Review)
        .filter(Review.article_id == article_id)
        .order_by(Review.created_at.desc())
        .all()
    )


def get_review_by_user_scope(
    session: Session,
    article_id: str,
    reviewer_id: str,
    scope: str,
    commit_hash: str,
) -> Review | None:
    """Check if a reviewer already reviewed this article+commit+scope."""
    return (
        session.query(Review)
        .filter(
            Review.article_id == article_id,
            Review.reviewer_id == reviewer_id,
            Review.scope == scope,
            Review.commit_hash == commit_hash,
        )
        .first()
    )
