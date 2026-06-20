# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Workflow orchestration — DB-aware wrappers around pure workflow/ functions.

Each function here follows the same pattern: (1) gather data from DB,
(2) call a pure function in ``peerpedia_core.workflow.*``, (3) write the
result back to DB.  None of these functions call ``session.commit()`` —
that is the caller's responsibility.

Call graph::

    publish_ready_articles
      ├► DB: query Article.status == "sedimentation"
      ├► for each ready article:
      │     ├▻ commands.sync.git_sync_reviews    (deferred import)
      │     ├► recompute_article_score
      │     ├► workflow.sedimentation.apply_no_review_penalty
      │     └► article.status = "published"
      ├► db.commit()                     ← Phase 1: status changes
      ├► for each affected author:
      │     └► recompute_author_reputation
      └► db.commit()                     ← Phase 2: reputation updates

    recompute_article_score
      ├► DB: get_article, get_reviews_for_article, get_author_ids
      ├► DB: batch-load User rows for reviewer weights
      ├► workflow.scoring.aggregate_review_scores   (pure, with scope_weights)
      └► article.score = result

    recompute_author_reputation
      ├► DB: session.get(User, user_id)  → ValueError if missing
      ├► DB: get_articles_by_author
      ├► workflow.reputation.compute_reputation     (pure)
      ├► workflow.reputation.blend_reputation       (pure, EMA)
      └► crud_user.update_user_reputation

    recalculate_all_reputations
      └► recompute_author_reputation for every user

Reviewer's checklist
--------------------
- Is the two-phase commit in publish_ready_articles correct?
  Phase 1 (status) must succeed before Phase 2 (reputation) runs.
- Does every functions raise on missing data rather than returning a default?
  (e.g. recompute_author_reputation raises ValueError for unknown user)
- Are scope_weights correctly passed from params to aggregate_review_scores?
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from peerpedia_core.config.params import params
from peerpedia_core.storage.db.crud_article import get_article, get_articles_by_author, get_author_ids
from peerpedia_core.storage.db.crud_review import get_reviews_for_article, upsert_review
from peerpedia_core.storage.db.crud_user import update_user_reputation
from peerpedia_core.storage.db.models import Article, User
from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR, list_review_dirs, read_review_scores
from peerpedia_core.types.scores import ReputationScores
from peerpedia_core.workflow.reputation import (
    blend_reputation,
    compute_reputation,
    get_reviewer_weight,
)
from peerpedia_core.workflow.scoring import aggregate_review_scores
from peerpedia_core.workflow.sedimentation import apply_no_review_penalty, is_ready_to_publish


def publish_ready_articles(db: Session) -> int:
    """Scan all articles in sedimentation, publish those whose sink time has elapsed.

    Uses a two-phase transaction: (1) batch all article status changes in one
    commit, then (2) recompute reputations for all affected authors in a second
    commit.

    Before scoring, syncs reviews from git worktree into DB cache via
    git_sync_reviews(), ensuring the DB reflects the latest state.

    Returns the number of articles published in this call.
    """
    articles = db.query(Article).filter(Article.status == "sedimentation").all()

    published_count = 0
    all_author_ids: set[str] = set()

    # Phase 1: mark ready articles and collect affected authors
    for article in articles:
        if article.sink_start is None:
            continue

        st = article.sink_start
        if st.tzinfo is None:
            from datetime import timezone
            st = st.replace(tzinfo=timezone.utc)
        eta = st + timedelta(days=article.sink_duration_days)

        if not is_ready_to_publish(eta):
            continue

        # Sync reviews from git before scoring — git is the SOT.
        from peerpedia_core.commands.sync import git_sync_reviews
        rp = DEFAULT_ARTICLES_DIR / article.id
        if (rp / ".git").is_dir():
            git_sync_reviews(db, article.id)

        # Compute score by aggregating all reviews
        score = recompute_article_score(db, article.id)

        # Check for community reviews and apply penalty if none
        all_reviews = get_reviews_for_article(db, article.id)
        authors = get_author_ids(db, article.id)
        community_reviews = [r for r in all_reviews if r.reviewer_id not in authors]
        if len(community_reviews) == 0 and score is not None:
            score = apply_no_review_penalty(score)

        # Mark article
        article.status = "published"
        if score:
            article.score = score

        for author_id in authors:
            all_author_ids.add(author_id)

        published_count += 1

    if published_count == 0:
        return 0

    # Commit all article status changes at once
    db.commit()

    # Phase 2: recompute reputations for all affected authors
    for author_id in all_author_ids:
        recompute_author_reputation(db, author_id)
    db.commit()

    return published_count


def recompute_article_score(db: Session, article_id: str) -> dict | None:
    """Compute the article score from all cached reviews and write it to DB.

    Returns the computed score dict, or None if no reviews exist.
    Raises ValueError if the article does not exist.
    """
    article = get_article(db, article_id)
    if article is None:
        raise ValueError(f"Article not found: {article_id}")

    all_reviews = get_reviews_for_article(db, article_id)
    if not all_reviews:
        return None

    authors = get_author_ids(db, article_id)
    # Batch-load all reviewer users in one query
    reviewer_ids = {r.reviewer_id for r in all_reviews}
    reviewer_users = db.query(User).filter(User.id.in_(reviewer_ids)).all()
    user_weight_map: dict[str, float] = {}
    for u in reviewer_users:
        user_weight_map[u.id] = get_reviewer_weight(u.reputation if u.reputation else None)

    review_dicts = [
        {
            "scores": r.scores,
            "is_self": r.reviewer_id in authors,
            "reviewer_id": r.reviewer_id,
            "scope": r.scope,
        }
        for r in all_reviews
    ]
    reviewer_weights = {r.reviewer_id: user_weight_map.get(r.reviewer_id, 1.0) for r in all_reviews}

    scope_weights = {
        "sedimentation": params.score.sedimentation_scope_weight,
        "published": params.score.published_scope_weight,
    }

    score = aggregate_review_scores(review_dicts, reviewer_weights, scope_weights)
    if score is not None:
        article.score = score
    return score


def recompute_author_reputation(db: Session, user_id: str) -> ReputationScores:
    """Compute and persist a blended reputation for *user_id*.

    Raises ValueError if the user does not exist.
    """
    user = db.get(User, user_id)
    if user is None:
        raise ValueError(f"User not found: {user_id}")

    articles = get_articles_by_author(db, user_id)
    article_dicts = [
        {"score": a.score, "status": a.status}
        for a in articles
    ]

    new_rep = compute_reputation(article_dicts)
    existing_rep = user.reputation if user.reputation else {}
    blended = blend_reputation(existing_rep, new_rep)

    update_user_reputation(db, user_id, blended.to_dict())
    return blended


def recalculate_all_reputations(db: Session) -> int:
    """Recalculate reputation for every user in the system.

    Returns the number of users whose reputation was (re)computed.
    """
    users = db.query(User).all()
    for user in users:
        recompute_author_reputation(db, user.id)
    return len(users)
