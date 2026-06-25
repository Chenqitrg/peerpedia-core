# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article lifecycle — create, fork, publish, rollback, update, delete, query."""

from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR  # noqa: F401 — re-exported for test mocks
from peerpedia_core.commands.articles._helpers import rebuild_article_authors
from peerpedia_core.commands.articles.create import create_article_with_content
from peerpedia_core.commands.articles.delete import delete_article
from peerpedia_core.commands.articles.fork import fork_article
from peerpedia_core.commands.articles.publish import publish_article
from peerpedia_core.commands.articles.rollback import rollback_article
from peerpedia_core.commands.articles.update import update_article_content
from peerpedia_core.commands.articles.diff import diff_article

# ── Read wrappers — thin pass-through to crud ────────────────────────────

from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.crud_article import (
    count_articles as _count,
    get_article as _get_article,
    get_author_ids as _get_author_ids,
    list_articles as _list,
)
from peerpedia_core.storage.db.crud_bookmark import is_bookmarked as _is_bookmarked
from peerpedia_core.storage.db.crud_user import get_following as _get_following
from peerpedia_core.commands.integrity import assert_article_integrity


def get_article(db: Session, article_id: str):
    """Return an article by ID, or None.

    Runs a lightweight integrity check (latest commit signature) before
    returning the article.
    """
    article = _get_article(db, article_id)
    if article is not None:
        assert_article_integrity(db, article_id, level="light")
    return article


def list_articles(
    db: Session,
    status: str | set[str] | None = None,
    search_query: str | None = None,
    author_id: str | None = None,
    viewer_id: str | None = None,
    bookmarked_by: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list:
    """List articles with AND filters — all pushed to SQL via JOINs.

    *viewer_id* (feed) looks up followed users first, then passes their
    IDs as an ``author_ids`` SQL filter.
    """
    # Resolve author filter: explicit --user, or --feed (followed users).
    ids: str | list[str] | None = author_id
    if viewer_id:
        followed = [u.id for u in _get_following(db, viewer_id)]
        if not followed:
            return []
        if author_id and author_id not in followed:
            return []
        ids = followed

    return _list(
        db, status=status, search_query=search_query,
        author_ids=ids, bookmarked_by=bookmarked_by,
        limit=limit, offset=offset,
    )


def count_articles(db: Session, **kwargs) -> int:
    """Count articles with optional filters."""
    return _count(db, **kwargs)


def get_author_ids(db: Session, article_id: str) -> list[str]:
    """Return ordered author IDs for an article."""
    return _get_author_ids(db, article_id)
