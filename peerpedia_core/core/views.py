# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""View layer — returns storage-independent exchange objects.

Every function returns ``ArticleMetaExchange``, ``UserExchange``, or lists
thereof.  Callers (HTTP route handlers, CLI, REPL) never touch ORM objects
or call ``.to_dict()``.  Transport serializes via ``dataclasses.asdict()``.

This is the ONLY place that assembles exchange objects from storage.  When
the response shape changes, only the exchange types and this file change.
"""

from __future__ import annotations

from peerpedia_core.core.articles import list_articles
from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.crud_article import get_article
from peerpedia_core.storage.db.crud_follow import get_followers, get_following
from peerpedia_core.storage.db.crud_user import get_user_by_id
from peerpedia_core.types.entities import ArticleMetaExchange, UserExchange


# ── Public view functions ────────────────────────────────────────────────


def get_article_view(db: Session, article_id: str) -> ArticleMetaExchange | None:
    """Return an article exchange, or None."""
    article = get_article(db, article_id)
    if article is None:
        return None
    return article.to_exchange()


def list_article_views(
    db: Session,
    *,
    status: str | set[str] | None = None,
    search_query: str | None = None,
    author_id: str | None = None,
    maintainer_id: str | None = None,
    viewer_id: str | None = None,
    bookmarked_by: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[ArticleMetaExchange]:
    """Return articles as exchange objects."""
    articles = list_articles(
        db, status=status, search_query=search_query,
        author_id=author_id, maintainer_id=maintainer_id,
        viewer_id=viewer_id, bookmarked_by=bookmarked_by,
        limit=limit, offset=offset,
    )
    return [a.to_exchange() for a in articles]


def get_user_view(db: Session, user_id: str) -> UserExchange | None:
    """Return a user exchange, or None."""
    user = get_user_by_id(db, user_id)
    if user is None:
        return None
    return user.to_exchange()


def get_following_views(db: Session, user_id: str) -> list[UserExchange]:
    """Return list of users that *user_id* follows."""
    return [u.to_exchange() for u in get_following(db, user_id)]


def get_follower_views(db: Session, user_id: str) -> list[UserExchange]:
    """Return list of users that follow *user_id*."""
    return [u.to_exchange() for u in get_followers(db, user_id)]
