# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Extract immutable DB snapshots for workflow algorithms.

``extract_reputation_state`` builds a ``ReputationState`` from the database
— it is the single contract between the DB layer and the pure
reputation/scoring algorithms in ``workflow/``.
"""

from __future__ import annotations

from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.crud_article import get_articles_by_author, get_author_ids_batch
from peerpedia_core.storage.db.crud_review import get_reviews_for_article
from peerpedia_core.storage.db.crud_user import get_users_by_ids
from peerpedia_core.storage.db.guards import require_user
from peerpedia_core.compute.state import ReputationState
from peerpedia_core.types.entities import ArticleMetaExchange, ReviewExchange, UserExchange


def extract_reputation_state(db: Session, user_id: str) -> ReputationState:
    """Build an immutable snapshot of the data needed to compute reputation."""
    # ── Setup ──────────────────────────────────────────────────────────────
    require_user(db, user_id)

    articles = get_articles_by_author(db, user_id)
    author_map = get_author_ids_batch(db, [a.id for a in articles])

    # ── Build article + review snapshots ────────────────────────────────────
    article_map, reviews_map = _build_article_review_maps(db, articles, author_map)

    # ── Build user snapshots ────────────────────────────────────────────────
    user_map = _build_user_snapshot_map(db, user_id, reviews_map)

    # ── Assemble ────────────────────────────────────────────────────────────
    return ReputationState(articles=article_map, reviews=reviews_map, users=user_map)


def _build_article_review_maps(
    db: Session, articles, author_map: dict,
) -> tuple[dict[str, ArticleMetaExchange], dict[str, tuple[ReviewExchange, ...]]]:
    """Iterate articles, building frozen ArticleMetaExchange and ReviewExchange maps."""
    article_map: dict[str, ArticleMetaExchange] = {}
    reviews_map: dict[str, tuple[ReviewExchange, ...]] = {}

    for a in articles:
        authors = author_map.get(a.id, [])
        all_reviews = get_reviews_for_article(db, a.id)
        article_map[a.id] = ArticleMetaExchange(
            id=a.id, title=a.title, status=a.status,
            authors=tuple(authors), score=a.score,
            publish_consents=tuple(a.publish_consents) if a.publish_consents else None,
        )
        reviews_map[a.id] = tuple(
            ReviewExchange(
                reviewer_id=r.reviewer_id, scores=r.scores,
                is_self=r.reviewer_id in authors, scope=r.scope, status=r.status,
            )
            for r in all_reviews if r.status == "submitted"
        )

    return article_map, reviews_map


def _build_user_snapshot_map(
    db: Session, user_id: str, reviews_map: dict,
) -> dict[str, UserExchange]:
    """Collect all reviewer IDs from reviews, fetch users, return UserExchange map."""
    reviewer_ids: set[str] = set()
    for revs in reviews_map.values():
        for r in revs:
            reviewer_ids.add(r.reviewer_id)

    all_user_ids = {user_id} | reviewer_ids
    user_rows = get_users_by_ids(db, all_user_ids)
    return {
        u.id: UserExchange(id=u.id, name=u.name, address=u.address or "",
                           reputation=u.reputation if u.reputation else None)
        for u in user_rows
    }
