# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article lifecycle — create, fork, publish, rollback, update, delete, query."""

from peerpedia_core.storage.git import DEFAULT_ARTICLES_DIR  # noqa: F401 — re-exported for test mocks
from peerpedia_core.core.articles.create import create_article_with_content
from peerpedia_core.core.articles.delete import delete_article
from peerpedia_core.core.articles.fork import fork_article
from peerpedia_core.core.articles.publish import publish_article
from peerpedia_core.core.articles.sink import publish_ready_articles
from peerpedia_core.core.articles.rollback import rollback_article
from peerpedia_core.core.articles.update import update_article_content
from peerpedia_core.core.articles.diff import diff_article

# ── Read wrappers — thin pass-through to crud ────────────────────────────

from peerpedia_core.config.paths import article_repo_path
from peerpedia_core.frontmatter import parse_frontmatter as _parse_frontmatter
from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.models import ArticleMetaStorage
from peerpedia_core.storage.db.crud_article import (
    count_articles as _count,
    list_all_article_ids as _get_all_ids,
    get_article as _get_article,
    list_articles as _list,
)
from peerpedia_core.storage.db.crud_author import list_author_ids as _get_author_ids
from peerpedia_core.storage.db.crud_user import list_users_by_ids as _list_users_by_ids
from peerpedia_core.core.reconcile import reconcile_integrity


def get_article(db: Session, article_id: str) -> ArticleMetaStorage | None:
    """Return an article by ID, or None.

    Runs a lightweight integrity check (latest commit signature) before
    returning the article.
    """
    article = _get_article(db, article_id)
    if article is not None:
        reconcile_integrity(db, article_id, level="light")
    return article


def list_articles(
    db: Session,
    status: str | set[str] | None = None,
    search_query: str | None = None,
    author_id: str | None = None,
    viewer_id: str | None = None,
    bookmarked_by: str | None = None,
    id_prefix: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list:
    """List articles with AND filters — all pushed to SQL via JOINs/subqueries."""
    statuses = _to_set(status)
    author_ids = _to_set(author_id)
    return _list(
        db, statuses=statuses, search_query=search_query,
        author_ids=author_ids, viewer_id=viewer_id,
        bookmarked_by=bookmarked_by, id_prefix=id_prefix,
        limit=limit, offset=offset,
    )


def count_articles(db: Session, **kwargs) -> int:
    """Count articles with optional filters."""
    if "status" in kwargs:
        kwargs["statuses"] = _to_set(kwargs.pop("status"))
    return _count(db, **kwargs)


def _to_set(value: str | set[str] | None) -> set[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return {value}
    return value


def list_all_article_ids(db: Session) -> list[str]:
    """Return every local article ID.  Lightweight — id column only."""
    return _get_all_ids(db)

def list_author_ids(db: Session, article_id: str) -> list[str]:
    """Return ordered author IDs for an article."""
    return _get_author_ids(db, article_id)


def _author_names(db: Session, author_ids: list[str]) -> list[str]:
    """Resolve author UUIDs to display names."""
    if not author_ids:
        return []
    users = {u.id: u for u in _list_users_by_ids(db, set(author_ids))}
    return [users[uid].name if uid in users else uid for uid in author_ids]


def _article_frontmatter(article_id: str) -> dict:
    """Read frontmatter from an article's source file, or {}."""
    source = article_repo_path(article_id) / "article.md"
    return _parse_frontmatter(source.read_text()) if source.exists() else {}


def resolve_article_meta(db: Session, article,
                         *, author_ids: list[str] | None = None) -> dict:
    """Resolve article metadata from DB + source file with fallbacks."""
    ids = author_ids or _get_author_ids(db, article.id)
    fm = _article_frontmatter(article.id)
    return {
        "title": fm.get("title", article.title),
        "status": article.status,
        "authors": _author_names(db, ids),
        "score": article.score,
        "abstract": fm.get("abstract", article.abstract),
    }


def resolve_article_meta_batch(db: Session,
                               article_ids: list[str]) -> list[dict]:
    """Resolve metadata for a batch of articles — single DB round-trip."""
    from peerpedia_core.storage.db.crud_author import list_author_ids_batch

    author_map = list_author_ids_batch(db, article_ids)
    all_author_ids = {aid for ids in author_map.values() for aid in ids}
    users = {u.id: u for u in _list_users_by_ids(db, all_author_ids)} if all_author_ids else {}

    articles = _list(db, limit=len(article_ids))
    article_by_id = {a.id: a for a in articles}
    result: list[dict] = []
    for aid in article_ids:
        a = article_by_id.get(aid)
        if a is None:
            continue
        ids = author_map.get(aid, [])
        fm = _article_frontmatter(aid)
        result.append({
            "id": aid,
            "title": fm.get("title", a.title),
            "status": a.status,
            "authors": [users[uid].name if uid in users else uid for uid in ids],
            "score": a.score,
            "abstract": fm.get("abstract", a.abstract),
        })
    return result
