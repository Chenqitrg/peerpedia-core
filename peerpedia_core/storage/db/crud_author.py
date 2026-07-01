# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Article author CRUD — join table management, ``session.flush()`` only.

Functions
---------
  add_article_authors       Insert ArticleAuthorStorage rows
  reset_article_authors     Delete all authors + re-insert
  list_author_ids           Ordered author list for one article
  list_author_ids_batch     Batch version for multiple articles
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import ArticleAuthorStorage


def add_article_authors(session: Session, article_id: str, author_ids: list[str]) -> None:
    """Append author rows for *article_id*, starting after the current max position.

    Idempotent at the DB level — the unique constraint on
    ``(article_id, author_id)`` prevents duplicates, so an author already
    in the join table will raise ``IntegrityError``.  Callers that might
    re-insert existing authors should deduplicate first (see
    ``reconcile_authors`` in ``core/reconcile/mirror.py``).
    """
    max_pos = session.query(func.max(ArticleAuthorStorage.position)).filter(
        ArticleAuthorStorage.article_id == article_id
    ).scalar()
    start = 0 if max_pos is None else max_pos + 1
    for i, author_id in enumerate(author_ids):
        session.add(
            ArticleAuthorStorage(
                article_id=article_id,
                author_id=author_id,
                position=start + i,
            )
        )


def reset_article_authors(session: Session, article_id: str, author_ids: list[str]) -> None:
    """Delete all author rows for *article_id* and re-insert *author_ids*."""
    session.query(ArticleAuthorStorage).filter(ArticleAuthorStorage.article_id == article_id).delete()
    add_article_authors(session, article_id, author_ids)


def list_author_ids(session: Session, article_id: str) -> list[str]:
    """List all author IDs for an article (ordered by position)."""
    rows = session.query(ArticleAuthorStorage).filter(ArticleAuthorStorage.article_id == article_id).order_by(ArticleAuthorStorage.position).all()
    return [r.author_id for r in rows]


def list_author_ids_batch(session: Session, article_ids: list[str]) -> dict[str, list[str]]:
    """Batch list author IDs for multiple articles.

    Returns dict mapping article_id → ordered list of author_ids.
    Articles with no authors get an empty list.
    """
    result: dict[str, list[str]] = {aid: [] for aid in article_ids}
    if not article_ids:
        return result
    rows = (
        session.query(ArticleAuthorStorage)
        .filter(ArticleAuthorStorage.article_id.in_(article_ids))
        .order_by(ArticleAuthorStorage.article_id, ArticleAuthorStorage.position)
        .all()
    )
    for r in rows:
        result[r.article_id].append(r.author_id)
    return result
