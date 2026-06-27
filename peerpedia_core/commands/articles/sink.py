# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Sink-timer processing — graduate articles from sedimentation to published/rejected."""

from __future__ import annotations

from datetime import timedelta, timezone

from peerpedia_core.storage.db import Session
from peerpedia_core.config.params import params
from peerpedia_core.storage.db.crud_article import (
    get_author_ids, list_articles, update_article_score, update_article_status,
)
from peerpedia_core.storage.db.crud_review import get_reviews_for_article
from peerpedia_core.storage.git import DEFAULT_ARTICLES_DIR, commit_status_marker
from peerpedia_core.types.scores import FiveDimScores
from peerpedia_core.compute.sedimentation import apply_no_review_penalty, is_ready_to_publish


def publish_ready_articles(db: Session) -> int:
    """Scan sedimentation pool, publish/reject articles whose sink has elapsed."""
    articles = list_articles(db, status="sedimentation")

    # ── Process each elapsed article ───────────────────────────────────────
    affected_authors: set[str] = set()
    processed = 0
    for article in articles:
        author_ids = _process_sink_article(db, article)
        if author_ids is None:          # sink has not yet elapsed
            continue
        affected_authors.update(author_ids)
        processed += 1

    if processed == 0:
        return 0

    # ── Recompute reputations for all affected authors ─────────────────────
    from peerpedia_core.commands.reconcile import reconcile_reputation
    for author_id in affected_authors:
        reconcile_reputation(db, author_id)

    return processed


def _process_sink_article(db: Session, article) -> list[str] | None:
    """Process one article whose sink may have elapsed.

    Returns the article's author IDs if processed, or None if the sink
    has not yet elapsed.
    """
    # ── Sink timer check ───────────────────────────────────────────────────
    if article.sink_start is None:
        return None

    st = article.sink_start
    if st.tzinfo is None:
        st = st.replace(tzinfo=timezone.utc)
    eta = st + timedelta(days=article.sink_duration_days)

    if not is_ready_to_publish(eta):
        return None

    # ── Count approvals ────────────────────────────────────────────────────
    authors = get_author_ids(db, article.id)
    approval_count = _count_approving_reviews(db, article.id, authors)

    # ── Decide disposition (pure — no side effects) ────────────────────────
    decision = _decide_sink_disposition(article, approval_count)

    # ── Git: write status marker ───────────────────────────────────────────
    rp = DEFAULT_ARTICLES_DIR / article.id
    if decision != "extended" and (rp / ".git").is_dir():
        commit_status_marker(rp, decision)

    # ── DB: update status + score ──────────────────────────────────────────
    if decision == "published":
        from peerpedia_core.commands.reconcile import reconcile_score
        score = reconcile_score(db, article.id)
        if score is None:
            score = apply_no_review_penalty(FiveDimScores().to_dict())
        update_article_score(db, article.id, score)
    elif decision == "extended":
        extra = params.sink.review_deficit_extend_days
        article.sink_duration_days += extra
        article.total_sink_days_accumulated += extra
        article.sink_extended_count += 1
    update_article_status(db, article.id, decision)

    return authors


def _count_approving_reviews(db: Session, article_id: str, author_ids: list[str]) -> int:
    """Count community reviews whose average score meets the approval threshold."""
    all_reviews = get_reviews_for_article(db, article_id)
    community = [r for r in all_reviews if r.reviewer_id not in author_ids]

    count = 0
    for r in community:
        if r.status != "submitted" or not isinstance(r.scores, dict):
            continue
        vals = [v for v in r.scores.values() if isinstance(v, (int, float))]
        if vals and sum(vals) / len(vals) >= params.sink.approval_score_threshold:
            count += 1
    return count


def _decide_sink_disposition(article, approval_count: int) -> str:
    """Decide the sink outcome — pure decision, no side effects.

    Returns 'published', 'extended', or 'rejected'.
    """
    if approval_count >= params.sink.min_approvals:
        return "published"

    extra = params.sink.review_deficit_extend_days
    if article.total_sink_days_accumulated + extra <= params.sink.max_total_sink_days:
        return "extended"

    return "rejected"
