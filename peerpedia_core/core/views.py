# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""View layer — returns response-ready dicts for transport and CLI callers.

Every function in this module returns plain ``dict`` or ``list[dict]``.
Callers (HTTP route handlers, CLI commands) never touch ORM objects or
call ``.to_dict()`` — they just serialize the dict to JSON or print it.

This is the ONLY place that knows how to assemble a complete article/user
response.  When the response shape changes, only this file changes.
"""

from __future__ import annotations

from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.crud_article import get_article, list_author_ids, list_author_ids_batch
from peerpedia_core.storage.db.crud_user import get_followers, get_following, get_user
from peerpedia_core.core.articles import list_articles


def get_article_view(db: Session, article_id: str) -> dict[str, object] | None:
    """Return a complete article response dict (with authors), or None."""
    article = get_article(db, article_id)
    if article is None:
        return None
    return {**article.to_dict(), "authors": list_author_ids(db, article.id)}


def list_article_views(
    db: Session,
    *,
    status: str | set[str] | None = None,
    search_query: str | None = None,
    author_id: str | None = None,
    viewer_id: str | None = None,
    bookmarked_by: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    """Return a list of complete article response dicts (with authors)."""
    articles = list_articles(
        db,
        status=status,
        search_query=search_query,
        author_id=author_id,
        viewer_id=viewer_id,
        bookmarked_by=bookmarked_by,
        limit=limit,
        offset=offset,
    )
    if not articles:
        return []
    # Batch-load author IDs to avoid N+1.
    author_map = _batch_author_ids(db, [a.id for a in articles])
    return [{**a.to_dict(), "authors": author_map.get(a.id, [])} for a in articles]


def get_user_view(db: Session, user_id: str) -> dict[str, object] | None:
    """Return a complete user response dict, or None."""
    user = get_user(db, user_id)
    if user is None:
        return None
    return user.to_dict()


def get_following_views(db: Session, user_id: str) -> list[dict]:
    """Return list of user dicts that *user_id* follows."""
    return [u.to_dict() for u in get_following(db, user_id)]


def get_follower_views(db: Session, user_id: str) -> list[dict]:
    """Return list of user dicts that follow *user_id*."""
    return [u.to_dict() for u in get_followers(db, user_id)]


def list_user_article_views(
    db: Session,
    user_id: str,
    *,
    status: str | set[str] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    """Return articles authored by *user_id* as complete response dicts."""
    articles = list_articles(
        db, author_id=user_id, status=status, limit=limit, offset=offset,
    )
    if not articles:
        return []
    author_map = _batch_author_ids(db, [a.id for a in articles])
    return [{**a.to_dict(), "authors": author_map.get(a.id, [])} for a in articles]


# ── Helpers ──────────────────────────────────────────────────────────────────


def _batch_author_ids(db: Session, article_ids: list[str]) -> dict[str, list[str]]:
    """Return ``{article_id: [author_id, ...]}`` for a list of article IDs."""
    return list_author_ids_batch(db, article_ids)
