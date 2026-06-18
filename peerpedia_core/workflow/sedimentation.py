# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Sedimentation pool logic — sink time calculation and auto-publish."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from peerpedia_core.config.params import params
from peerpedia_core.storage.db.models import Article


def is_ready_to_publish(sink_eta: datetime | None) -> bool:
    """Check if the sink time has elapsed. Returns False if sink_eta is None."""
    if sink_eta is None:
        return False
    now = datetime.now(timezone.utc)
    if sink_eta.tzinfo is None:
        sink_eta = sink_eta.replace(tzinfo=timezone.utc)
    return now >= sink_eta


def apply_no_review_penalty(scores: dict | None) -> dict:
    """Apply penalty when an article receives zero reviews in the pool.

    Returns a new scores dict with penalty applied (each dimension reduced).
    Returns empty dict if scores is None.
    """
    if scores is None:
        return {}
    penalty = params.score.no_review_penalty()
    return {dim: max(0.0, value - penalty) for dim, value in scores.items()}


def publish_ready_articles(session: Session) -> int:
    """Scan all articles in sedimentation, publish those whose sink time has elapsed.

    Uses a two-phase transaction: (1) batch all article status changes in one
    commit, then (2) recompute reputations for all affected authors in a second
    commit. This prevents data loss where the last article's reputation updates
    were never committed under the old per-article commit pattern.

    Returns the number of articles published in this call.
    """
    from peerpedia_core.storage.db.crud_article import get_author_ids
    from peerpedia_core.storage.db.crud_review import get_reviews_for_article
    from peerpedia_core.workflow.reputation import compute_author_reputation
    from peerpedia_core.workflow.scoring import compute_article_score_for_commit

    articles = session.query(Article).filter(Article.status == "sedimentation").all()

    published_count = 0
    all_author_ids: set[str] = set()

    # Phase 1: mark ready articles and collect affected authors
    for article in articles:
        if article.sink_start is None:
            continue

        st = article.sink_start
        if st.tzinfo is None:
            st = st.replace(tzinfo=timezone.utc)
        eta = st + timedelta(days=article.sink_duration_days)

        if not is_ready_to_publish(eta):
            continue

        # Compute score by aggregating all reviews across all commits
        score = compute_article_score_for_commit(session, article.id)

        # Check for community reviews and apply penalty if none
        all_reviews = get_reviews_for_article(session, article.id)
        authors = get_author_ids(session, article.id)
        community_reviews = [r for r in all_reviews if r.reviewer_id not in authors]
        if len(community_reviews) == 0:
            score = apply_no_review_penalty(score)

        # Mark article (committed in batch below)
        article.status = "published"
        if score:
            article.score = score

        for author_id in authors:
            all_author_ids.add(author_id)

        published_count += 1

    if published_count == 0:
        return 0

    # Commit all article status changes at once
    session.commit()

    # Phase 2: recompute reputations for all affected authors
    for author_id in all_author_ids:
        compute_author_reputation(session, author_id)
    session.commit()

    return published_count
