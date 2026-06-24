# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Review score cache — synced from git, queried by scoring.

Review content lives in git (``reviews/<reviewer_id>/scores.json`` +
``threads/*.md``).  The database ``Review`` table is a read cache of
structured scores — populated after every git write — so that
``recompute_article_score`` and ``compute_author_reputation`` can query
without touching the filesystem.

Functions
---------
upsert_review(session, article_id, commit_hash, reviewer_id, scores) → Review
    Create or update the score cache for one review.  Keyed by
    (article_id, reviewer_id, scope, commit_hash).  Called AFTER review
    files are committed to git — from ``submit_review`` (local) and
    ``sync_reviews_from_worktree`` (sync).

    Scope is set to ``article.status`` at the time of the call — so
    reviews written during sedimentation are tagged ``scope="sedimentation"``
    and reviews written after publish are tagged ``scope="published"``.

get_reviews_for_article(session, article_id) → list[Review]
    All cached reviews for an article, newest first.  Used by
    ``recompute_article_score`` to gather input for scoring.

Reviewer's checklist
--------------------
- Is ``upsert_review`` called AFTER the git commit succeeds?  (git-first)
- Is the ``scope`` field correctly derived from the article's current status?
- Remember: this is a CACHE.  The real data is in git.  If there's a
  disagreement, git wins.
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
    from sqlalchemy.orm import load_only  # noqa: PLC0415

    article = session.get(
        Article, article_id,
        options=[load_only(Article.status)],
    )
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
        session.flush()
        return existing

    r = Review(
        article_id=article_id,
        commit_hash=commit_hash,
        reviewer_id=reviewer_id,
        scope=article.status,
        scores=scores,
    )
    session.add(r)
    session.flush()
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


def get_review(
    session: Session,
    article_id: str,
    reviewer_id: str,
    scope: str,
    commit_hash: str,
) -> Review | None:
    """Return a specific review by composite key, or None."""
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
