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

get_reviews_for_article(session, article_id) → list[ReviewMetaStorage]
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

from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.storage.db.models import ArticleMetaStorage, ReviewMetaStorage


def upsert_review(
    session: Session,
    article_id: str,
    commit_hash: str,
    reviewer_id: str,
    scores: dict[str, float],
) -> ReviewMetaStorage:
    """Create or update the scores cache for a review.

    Called AFTER review files are committed to git.  Scope is the
    article's current status.  Uses
    (article_id, reviewer_id, scope, commit_hash) as the unique key.

    Raises ValueError if the article is not found.
    """
    from sqlalchemy.orm import load_only  # noqa: PLC0415

    article = session.get(
        ArticleMetaStorage, article_id,
        options=[load_only(ArticleMetaStorage.status)],
    )
    if article is None:
        raise NotFoundError(code="ARTICLE_NOT_FOUND", resource_type="article", resource_id=article_id)

    existing = (
        session.query(ReviewMetaStorage)
        .filter(
            ReviewMetaStorage.article_id == article_id,
            ReviewMetaStorage.reviewer_id == reviewer_id,
            ReviewMetaStorage.scope == article.status,
            ReviewMetaStorage.commit_hash == commit_hash,
        )
        .first()
    )
    if existing:
        existing.scores = scores
        session.flush()
        return existing

    r = ReviewMetaStorage(
        article_id=article_id,
        commit_hash=commit_hash,
        reviewer_id=reviewer_id,
        scope=article.status,
        status="submitted",
        scores=scores,
    )
    session.add(r)
    session.flush()
    return r


def get_reviews_for_article(
    session: Session,
    article_id: str,
) -> list[ReviewMetaStorage]:
    """Return all cached reviews for an article, newest first."""
    return (
        session.query(ReviewMetaStorage)
        .filter(ReviewMetaStorage.article_id == article_id)
        .order_by(ReviewMetaStorage.created_at.desc())
        .all()
    )


def get_pending_invitation(
    session: Session,
    article_id: str,
    reviewer_id: str,
) -> ReviewMetaStorage | None:
    """Return the pending invitation for (article, reviewer), or None."""
    return (
        session.query(ReviewMetaStorage)
        .filter(
            ReviewMetaStorage.article_id == article_id,
            ReviewMetaStorage.reviewer_id == reviewer_id,
            ReviewMetaStorage.status == "invited",
        )
        .first()
    )


def get_accepted_invitation(
    session: Session,
    article_id: str,
    reviewer_id: str,
) -> ReviewMetaStorage | None:
    """Return the accepted invitation for (article, reviewer), or None."""
    return (
        session.query(ReviewMetaStorage)
        .filter(
            ReviewMetaStorage.article_id == article_id,
            ReviewMetaStorage.reviewer_id == reviewer_id,
            ReviewMetaStorage.status == "accepted",
        )
        .first()
    )


def update_review_status(
    session: Session,
    review: ReviewMetaStorage,
    status: str,
) -> None:
    """Update the status of a ReviewMetaStorage row and flush.

    Used by accept_invitation, decline_invitation, and submit_review
    to transition reviews through the invitation lifecycle state machine.
    """
    review.status = status
    session.flush()


def get_review(
    session: Session,
    article_id: str,
    reviewer_id: str,
    scope: str,
    commit_hash: str,
) -> ReviewMetaStorage | None:
    """Return a specific review by composite key, or None."""
    return (
        session.query(ReviewMetaStorage)
        .filter(
            ReviewMetaStorage.article_id == article_id,
            ReviewMetaStorage.reviewer_id == reviewer_id,
            ReviewMetaStorage.scope == scope,
            ReviewMetaStorage.commit_hash == commit_hash,
        )
        .first()
    )
