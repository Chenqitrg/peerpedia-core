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

from peerpedia_core.config.paths import article_repo_path
from peerpedia_core.core.articles import list_articles
from peerpedia_core.frontmatter import parse_frontmatter as _parse_frontmatter
from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.crud_article import get_article
from peerpedia_core.storage.db.crud_author import list_author_ids, list_author_ids_batch
from peerpedia_core.storage.db.crud_follow import get_followers, get_following
from peerpedia_core.storage.db.crud_user import get_user, list_users_by_ids
from peerpedia_core.storage.db.models import ArticleMetaStorage
from peerpedia_core.types.entities import ArticleMetaExchange, UserExchange


# ── Article resolution ───────────────────────────────────────────────────


def resolve_article_meta(db: Session, article, *,
                         author_ids: list[str] | None = None) -> ArticleMetaExchange:
    """Resolve article metadata into a frozen exchange object."""
    ids = author_ids or list_author_ids(db, article.id)
    fm = _article_frontmatter(article.id)
    return ArticleMetaExchange(
        id=article.id,
        title=fm.get("title", article.title),
        status=article.status,
        authors=tuple(_author_names(db, ids)),
        abstract=fm.get("abstract", article.abstract),
        score=article.score,
    )


def resolve_article_meta_batch(db: Session,
                               article_ids: list[str]) -> list[ArticleMetaExchange]:
    """Resolve metadata for a batch of articles — single DB round-trip."""
    author_map = list_author_ids_batch(db, article_ids)
    all_author_ids = {aid for ids in author_map.values() for aid in ids}
    users = {u.id: u for u in list_users_by_ids(db, all_author_ids)} if all_author_ids else {}

    articles = db.query(ArticleMetaStorage).filter(ArticleMetaStorage.id.in_(article_ids)).all()
    article_by_id = {a.id: a for a in articles}
    result: list[ArticleMetaExchange] = []
    for aid in article_ids:
        a = article_by_id.get(aid)
        if a is None:
            continue
        ids = author_map.get(aid, [])
        fm = _article_frontmatter(aid)
        result.append(ArticleMetaExchange(
            id=aid,
            title=fm.get("title", a.title),
            status=a.status,
            authors=tuple(users[uid].name if uid in users else uid for uid in ids),
            abstract=fm.get("abstract", a.abstract),
            score=a.score,
        ))
    return result


# ── Helpers ───────────────────────────────────────────────────────────────


def _author_names(db: Session, author_ids: list[str]) -> list[str]:
    """Resolve author UUIDs to display names."""
    if not author_ids:
        return []
    users = {u.id: u for u in list_users_by_ids(db, set(author_ids))}
    return [users[uid].name if uid in users else uid for uid in author_ids]


def _article_frontmatter(article_id: str) -> dict:
    """Read frontmatter from an article's source file, or {}."""
    source = article_repo_path(article_id) / "article.md"
    return _parse_frontmatter(source.read_text()) if source.exists() else {}


# ── Public view functions ────────────────────────────────────────────────


def get_article_view(db: Session, article_id: str) -> ArticleMetaExchange | None:
    """Return a resolved article exchange, or None."""
    article = get_article(db, article_id)
    if article is None:
        return None
    return resolve_article_meta(db, article)


def _list_raw_articles(
    db: Session,
    *,
    status: str | set[str] | None = None,
    author_id: str | None = None,
    viewer_id: str | None = None,
    bookmarked_by: str | None = None,
    search_query: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[ArticleMetaExchange]:
    """Raw query + batch resolution — internal helper."""
    articles = list_articles(
        db, status=status, author_id=author_id,
        viewer_id=viewer_id, bookmarked_by=bookmarked_by,
        search_query=search_query, limit=limit, offset=offset,
    )
    if not articles:
        return []
    return resolve_article_meta_batch(db, [a.id for a in articles])


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
) -> list[ArticleMetaExchange]:
    """Return resolved article exchanges."""
    return _list_raw_articles(
        db, status=status, search_query=search_query,
        author_id=author_id, viewer_id=viewer_id,
        bookmarked_by=bookmarked_by, limit=limit, offset=offset,
    )


def list_user_article_views(
    db: Session,
    user_id: str,
    *,
    status: str | set[str] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[ArticleMetaExchange]:
    """Return resolved article exchanges for a specific user."""
    return _list_raw_articles(
        db, author_id=user_id, status=status,
        limit=limit, offset=offset,
    )


def get_user_view(db: Session, user_id: str) -> UserExchange | None:
    """Return a user exchange, or None."""
    user = get_user(db, user_id)
    if user is None:
        return None
    return user.to_exchange()


def get_following_views(db: Session, user_id: str) -> list[UserExchange]:
    """Return list of users that *user_id* follows."""
    return [u.to_exchange() for u in get_following(db, user_id)]


def get_follower_views(db: Session, user_id: str) -> list[UserExchange]:
    """Return list of users that follow *user_id*."""
    return [u.to_exchange() for u in get_followers(db, user_id)]


def merge_article_meta(db: Session, entries: list[dict]) -> int:
    """Merge article metadata from peer JSON into the local DB."""
    from peerpedia_core.storage.db.ingest import ingest_articles
    return ingest_articles(db, [ArticleMetaExchange.from_json(e) for e in entries])
