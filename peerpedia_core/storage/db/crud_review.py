# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Review score cache operations.

Review content lives in git (reviews/<reviewer_id>/scores.json,
thread.md).  The database Review table is a cache of structured
scores — synced after git writes — so scoring and reputation
workflows can query without reading git.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import Article, Review


def upsert_review(
    session: Session,
    article_id: str,
    commit_hash: str,
    reviewer_id: str,
    scores: dict,
) -> Review:
    """Create or update the scores cache for a review.

    Called AFTER review files are committed to git.  Scope is the
    article's current status.  Uses
    (article_id, reviewer_id, scope, commit_hash) as the unique key.
    """
    article = session.get(Article, article_id)
    if article is None:
        raise ValueError(f"Article {article_id} not found")

    existing = (
        session.query(Review)
        .filter(
            Review.article_id == article_id,
            Review.reviewer_id == reviewer_id,
            Review.scope == article.status,
            Review.commit_hash == commit_hash,
        )
        .first()
    )
    if existing:
        existing.scores = scores
        session.commit()
        return existing

    r = Review(
        article_id=article_id,
        commit_hash=commit_hash,
        reviewer_id=reviewer_id,
        scope=article.status,
        scores=scores,
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
