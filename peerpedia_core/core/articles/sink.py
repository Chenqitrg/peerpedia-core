# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Sink-timer processing — graduate articles from sedimentation to published/rejected."""

from __future__ import annotations

from datetime import timedelta, timezone

from peerpedia_core.storage.db import Session
from peerpedia_core.config.params import params
from peerpedia_core.storage.db.crud_article import (
    list_articles, update_article_score, update_article_status,
)
from peerpedia_core.storage.db.crud_author import list_author_ids
from peerpedia_core.storage.db.crud_review import get_reviews_for_article
from peerpedia_core.storage.git import DEFAULT_ARTICLES_DIR, commit_status_marker
from peerpedia_core.types.scores import FiveDimScores
from peerpedia_core.compute.sedimentation import apply_no_review_penalty, is_ready_to_publish
from peerpedia_core.core.reconcile import reconcile_many_reputations, reconcile_score


def publish_ready_articles(db: Session) -> int:
    """Scan sedimentation pool, publish/reject articles whose sink has elapsed."""
    articles = list_articles(db, statuses={"sedimentation"})

    affected_authors: set[str] = set()
    processed = 0
    for article in articles:
        author_ids = _process_sink_article(db, article)
        if author_ids is None:
            continue
        affected_authors.update(author_ids)
        processed += 1

    if processed == 0:
        return 0

    reconcile_many_reputations(db, affected_authors)
    return processed


# ── Per-article processing ──────────────────────────────────────────────────


def _process_sink_article(db: Session, article) -> list[str] | None:
    """Process one article whose sink may have elapsed.

    Returns the article's author IDs if processed, or None if the sink
    has not yet elapsed.
    """
    if not _sink_has_elapsed(article):
        return None

    authors = list_author_ids(db, article.id)
    approval_count = _count_approving_reviews(db, article.id, authors)

    approved = _review_verdict(approval_count)
    _resolve_sink(db, article, approved)
    return authors


# ── Review verdict ──────────────────────────────────────────────────────────


def _review_verdict(approval_count: int) -> bool:
    """Return True if community reviews approve this article for publication."""
    return approval_count >= params.sink.min_approvals


def _resolve_sink(db: Session, article, approved: bool) -> None:
    """Resolve the sink outcome.

    If *approved*, publish the article.
    Otherwise, extend the sink if still within limits, else reject.
    """
    if approved:
        _publish(db, article)
    elif _can_extend(article):
        _extend(article)
    else:
        _reject(db, article)


# ── Timer ───────────────────────────────────────────────────────────────────


def _sink_has_elapsed(article) -> bool:
    """Return True if the article's sink timer has expired."""
    if article.sink_start is None:
        return False
    st = article.sink_start
    if st.tzinfo is None:
        st = st.replace(tzinfo=timezone.utc)
    eta = st + timedelta(days=article.sink_duration_days)
    return is_ready_to_publish(eta)


# ── Disposition branches ────────────────────────────────────────────────────


def _publish(db: Session, article) -> None:
    """Graduate article to published — write git marker, compute score, update DB."""
    rp = DEFAULT_ARTICLES_DIR / article.id
    if (rp / ".git").is_dir():
        commit_status_marker(rp, "published")
    score = reconcile_score(db, article.id)
    if score is None:
        score = apply_no_review_penalty(FiveDimScores().to_dict())
    update_article_score(db, article.id, score)
    update_article_status(db, article.id, "published")


def _can_extend(article) -> bool:
    """Return True if the article can be extended (still within max total days)."""
    extra = params.sink.review_deficit_extend_days
    return article.total_sink_days_accumulated + extra <= params.sink.max_total_sink_days


def _extend(article) -> None:
    """Extend the sink timer — keep article in sedimentation, grant more days."""
    extra = params.sink.review_deficit_extend_days
    article.sink_duration_days += extra
    article.total_sink_days_accumulated += extra
    article.sink_extended_count += 1


def _reject(db: Session, article) -> None:
    """Reject the article — write git marker, update DB status."""
    rp = DEFAULT_ARTICLES_DIR / article.id
    if (rp / ".git").is_dir():
        commit_status_marker(rp, "rejected")
    update_article_status(db, article.id, "rejected")


# ── Review counting ─────────────────────────────────────────────────────────


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
