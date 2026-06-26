# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Article CRUD — database only, no git/filesystem side effects.

All functions call ``session.flush()`` only — the caller (CLI/REPL) is
responsible for ``session.commit()``.  This ensures that multiple CRUD
operations within a single command either all succeed or all roll back.

Functions
---------
Author helpers (join table)
    add_article_authors       Insert ArticleAuthor rows
    set_article_authors       Replace all authors (delete + re-insert)
    get_author_ids            Ordered author list for one article
    get_author_ids_batch      Batch version for multiple articles
    get_articles_by_author    All articles where user is an author

CRUD
    create_article            New article + author rows (flush only)
    get_article               Single article by ID, or None
    list_articles             Filtered list (status, author, follower)
    count_articles            Count with same filters
    update_article_compiled   Set compiled output cache
    update_article_status     Change status with validation (G7)
    increment_fork_count      ++fork_count
    set_sink_start            Enter sedimentation + start timer
    delete_article            Hard delete + cascade (reviews, bookmarks, etc.)
    extend_sink               Author extends sink duration
    get_article_by_fork_and_author  Find fork by (original, author)

Status validation (G7)
----------------------
``update_article_status`` only accepts ``{"draft", "sedimentation",
"published"}``.  Any other value raises ``ValueError``.

Reviewer's checklist
--------------------
- Does every function call ``session.flush()``, not ``session.commit()``?
- Are new queries indexed?  (author_id, status are the hot paths.)
- Does ``delete_article`` cascade properly?  (Check the model relations.)
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.storage.db.models import (
    Article, ArticleAuthor, Bookmark, Citation, Follow, MergeProposal,
    Review, ScriptMaintainer,
)

# ── Author helpers (join table) ───────────────────────────────────────────


def add_article_authors(session: Session, article_id: str, author_ids: list[str]) -> None:
    """Insert ArticleAuthor rows for an article."""
    for pos, author_id in enumerate(author_ids):
        session.add(
            ArticleAuthor(
                article_id=article_id,
                author_id=author_id,
                position=pos,
            )
        )


def set_article_authors(session: Session, article_id: str, author_ids: list[str]) -> None:
    """Replace all author rows for an article (delete + re-insert)."""
    session.query(ArticleAuthor).filter(ArticleAuthor.article_id == article_id).delete()
    add_article_authors(session, article_id, author_ids)


def get_author_ids(session: Session, article_id: str) -> list[str]:
    """Get all author IDs for an article (ordered by position)."""
    rows = session.query(ArticleAuthor).filter(ArticleAuthor.article_id == article_id).order_by(ArticleAuthor.position).all()
    return [r.author_id for r in rows]


def get_author_ids_batch(session: Session, article_ids: list[str]) -> dict[str, list[str]]:
    """Batch get author IDs for multiple articles.

    Returns dict mapping article_id → ordered list of author_ids.
    Articles with no authors get an empty list.
    """
    result: dict[str, list[str]] = {aid: [] for aid in article_ids}
    if not article_ids:
        return result
    rows = (
        session.query(ArticleAuthor)
        .filter(ArticleAuthor.article_id.in_(article_ids))
        .order_by(ArticleAuthor.article_id, ArticleAuthor.position)
        .all()
    )
    for r in rows:
        result[r.article_id].append(r.author_id)
    return result


def get_articles_by_author(session: Session, author_id: str) -> list[Article]:
    """Return all articles where *author_id* is an author."""
    return (
        session.query(Article)
        .join(ArticleAuthor, Article.id == ArticleAuthor.article_id)
        .filter(ArticleAuthor.author_id == author_id)
        .all()
    )


# ── CRUD ──────────────────────────────────────────────────────────────────


def create_article(
    session: Session,
    authors: list[str],
    title: str,
    status: str = "draft",
    **kwargs,
) -> Article:
    """Create a new article record with author rows in the join table."""
    a = Article(title=title, status=status, **kwargs)
    session.add(a)
    session.flush()  # ensure a.id is available
    add_article_authors(session, a.id, authors)
    session.flush()
    return a


def create_article_from_orm(
    session: Session,
    article: Article,
    author_ids: list[str],
) -> Article:
    """Create an Article row from a pre-built ORM object with author join rows.

    Unlike ``create_article`` which constructs the Article from keyword
    parameters, this takes an already-built Article object. Use when the
    caller has deserialized article metadata from a peer or otherwise
    constructed the ORM object externally.
    """
    session.add(article)
    session.flush()
    add_article_authors(session, article.id, author_ids)
    session.flush()
    return article


def get_article(session: Session, article_id: str) -> Article | None:
    """Return an article by ID, or None if not found."""
    return session.get(Article, article_id)


def list_articles(
    session: Session,
    status: str | set[str] | None = None,
    search_query: str | None = None,
    id_prefix: str | None = None,
    author_ids: str | list[str] | None = None,
    viewer_id: str | None = None,
    bookmarked_by: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[Article]:
    """List articles with optional SQL-level AND filters, ordered by created_at desc.

    Args:
        status: Filter by Article.status.
        search_query: Fuzzy title match (case-insensitive ILIKE).
        id_prefix: UUID prefix match (``Article.id.startswith``).
        author_id: Only articles authored by this user (JOIN on article_authors).
        bookmarked_by: Only articles bookmarked by this user (JOIN on bookmarks).
        limit: Max results. None = unlimited.
        offset: Pagination offset.
    """
    q = session.query(Article)
    joined = False
    if isinstance(status, set):
        if status:
            q = q.filter(Article.status.in_(list(status)))
    elif status:
        q = q.filter(Article.status == status)
    if id_prefix:
        q = q.filter(Article.id.startswith(id_prefix))
    if search_query:
        q = q.filter(Article.title.ilike(f"%{search_query}%"))
    if author_ids:
        q = q.join(ArticleAuthor, ArticleAuthor.article_id == Article.id)
        joined = True
        if isinstance(author_ids, list):
            q = q.filter(ArticleAuthor.author_id.in_(author_ids))
        else:
            q = q.filter(ArticleAuthor.author_id == author_ids)
    elif viewer_id:
        followed_sub = (
            select(Follow.followed_id)
            .where(Follow.follower_id == viewer_id, Follow.deleted_at.is_(None))
        )
        q = q.join(ArticleAuthor, ArticleAuthor.article_id == Article.id)\
             .filter(ArticleAuthor.author_id.in_(followed_sub))
        joined = True
    if bookmarked_by:
        q = q.join(Bookmark, Bookmark.article_id == Article.id)\
             .filter(Bookmark.user_id == bookmarked_by)
        joined = True
    if joined:
        q = q.distinct()
    q = q.order_by(Article.created_at.desc())
    if limit is not None:
        q = q.limit(limit).offset(offset)
    return q.all()


def get_all_article_ids(session: Session) -> list[str]:
    """Return every article ID.  Lightweight — only fetches the ``id`` column."""
    return [row[0] for row in session.query(Article.id).all()]

def count_articles(session: Session, status: str | set[str] | None = None, author_id: str | None = None) -> int:
    """Count articles matching optional status and author filters."""
    q = session.query(Article)
    if isinstance(status, set):
        if status:
            q = q.filter(Article.status.in_(list(status)))
    elif status:
        q = q.filter(Article.status == status)
    if author_id:
        q = q.join(ArticleAuthor, Article.id == ArticleAuthor.article_id).filter(ArticleAuthor.author_id == author_id)
    return q.count()


def update_article_compiled(
    session: Session,
    article_id: str,
    html_format: str,
    output: str | None,
    pages: list[str] | None,
) -> None:
    """Cache compiled output (HTML/PDF/etc.) for an article.

    Uses targeted UPDATE to avoid loading ``compiled_output`` (which may
    be 100KB+).  Called by the compiler pipeline after rendering.  Not yet
    wired into the production compiler path — currently only exercised in
    tests.

    Raises NotFoundError if the article does not exist.
    """
    rows = session.query(Article).filter(Article.id == article_id).update(
        {"compiled_format": html_format, "compiled_output": output, "compiled_pages": pages},
        synchronize_session="fetch",
    )
    if rows == 0:
        raise NotFoundError("Article not found", resource_type="article", resource_id=article_id)
    session.expire_all()


def update_article_status(session: Session, article_id: str, new_status: str) -> None:
    """Transition *article_id* to *new_status*.  Raises NotFoundError if not found.

    Uses targeted UPDATE to avoid loading ``compiled_output`` (which may
    be 100KB+).  Expires the session afterward so subsequent ``get()``
    calls reload from DB.
    """
    _VALID_STATUSES = {"draft", "sedimentation", "published", "rejected"}
    if new_status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status {new_status!r}, must be one of {_VALID_STATUSES}")
    rows = session.query(Article).filter(Article.id == article_id).update(
        {"status": new_status}, synchronize_session="fetch"
    )
    if rows == 0:
        raise NotFoundError("Article not found", resource_type="article", resource_id=article_id)
    session.expire_all()


def update_article_score(session: Session, article_id: str, score: dict) -> None:
    """Set the computed score for an article. Raises NotFoundError if not found."""
    rows = session.query(Article).filter(Article.id == article_id).update(
        {"score": score}, synchronize_session="fetch"
    )
    if rows == 0:
        raise NotFoundError("Article not found", resource_type="article", resource_id=article_id)
    session.expire_all()


def increment_fork_count(session: Session, article_id: str) -> None:
    """Atomically increment ``fork_count`` by 1. Raises NotFoundError if not found."""
    rows = session.query(Article).filter(Article.id == article_id).update(
        {"fork_count": Article.fork_count + 1}, synchronize_session="fetch"
    )
    if rows == 0:
        raise NotFoundError("Article not found", resource_type="article", resource_id=article_id)
    session.expire_all()


def decrement_fork_count(session: Session, article_id: str) -> None:
    """Atomically decrement ``fork_count`` by 1 (floor at 0). Raises NotFoundError if not found."""
    from sqlalchemy import case
    rows = session.query(Article).filter(Article.id == article_id).update(
        {"fork_count": case((Article.fork_count > 0, Article.fork_count - 1), else_=0)},
        synchronize_session="fetch",
    )
    if rows == 0:
        raise NotFoundError("Article not found", resource_type="article", resource_id=article_id)
    session.expire_all()


def set_sink_start(session: Session, article_id: str, duration_days: int) -> None:
    """Enter sedimentation and start the sink timer (targeted UPDATE).

    Raises NotFoundError if the article does not exist.
    """
    from datetime import datetime, timezone

    rows = session.query(Article).filter(Article.id == article_id).update(
        {"status": "sedimentation", "sink_start": datetime.now(timezone.utc),
         "sink_duration_days": duration_days},
        synchronize_session="fetch",
    )
    if rows == 0:
        raise NotFoundError("Article not found", resource_type="article", resource_id=article_id)
    session.expire_all()


def delete_article(session: Session, article_id: str) -> None:
    """Delete an article and its related records from the database.

    Cascades to: article_authors, reviews, bookmarks, citations,
    merge_proposals.  Does NOT touch the git repository — callers
    should clean up the article's git directory separately via
    ``git_backend.delete_article_repo()``.

    Raises NotFoundError if the article does not exist.
    """
    # Delete related records
    session.query(ArticleAuthor).filter(ArticleAuthor.article_id == article_id).delete()
    session.query(ScriptMaintainer).filter(ScriptMaintainer.article_id == article_id).delete()
    session.query(Review).filter(Review.article_id == article_id).delete()
    session.query(Bookmark).filter(Bookmark.article_id == article_id).delete()
    session.query(Citation).filter((Citation.from_article_id == article_id) | (Citation.to_article_id == article_id)).delete()
    session.query(MergeProposal).filter(
        (MergeProposal.fork_article_id == article_id) | (MergeProposal.target_article_id == article_id)
    ).delete()

    rows = session.query(Article).filter(Article.id == article_id).delete()
    if rows == 0:
        raise NotFoundError("Article not found", resource_type="article", resource_id=article_id)
    session.flush()
    session.expire_all()


def extend_sink(session: Session, article_id: str, extra_days: int, max_days: int = 180) -> None:
    """Author extends sink time. Can be called repeatedly up to max_days.

    Raises ValueError if extra_days <= 0.
    Only increments sink_extended_count when the duration actually increases.
    """
    if extra_days <= 0:
        raise ValueError(f"extra_days must be positive, got {extra_days}")
    row = session.query(Article.sink_duration_days, Article.sink_extended_count).filter(
        Article.id == article_id
    ).first()
    if row is None:
        raise NotFoundError("Article not found", resource_type="article", resource_id=article_id)
    old_total, old_count = row
    new_total = min(old_total + extra_days, max_days)
    extended_count = old_count + 1 if new_total > old_total else old_count
    session.query(Article).filter(Article.id == article_id).update(
        {"sink_duration_days": new_total, "sink_extended_count": extended_count},
        synchronize_session="fetch",
    )
    session.expire_all()


def get_article_by_fork_and_author(
    session: Session,
    forked_from: str,
    author_id: str,
) -> Article | None:
    """Find an article forked from *forked_from* by *author_id*."""
    return (
        session.query(Article)
        .join(ArticleAuthor, Article.id == ArticleAuthor.article_id)
        .filter(Article.forked_from == forked_from)
        .filter(ArticleAuthor.author_id == author_id)
        .first()
    )


def update_witnessed_at(session: Session, article_id: str) -> None:
    """Record the current UTC time as the witness timestamp for *article_id*.

    Called when the server receives new commits via sync — the server clock
    proves "this article had this commit by this time," defending against
    local clock manipulation for priority claims.

    Raises ``NotFoundError`` if *article_id* does not exist.
    """
    from datetime import datetime, timezone

    rows = session.query(Article).filter(Article.id == article_id).update(
        {"witnessed_at": datetime.now(timezone.utc)},
        synchronize_session="fetch",
    )
    if rows == 0:
        raise NotFoundError("Article not found", resource_type="article", resource_id=article_id)
    session.expire_all()


# ── Publish consent ─────────────────────────────────────────────────────


def _get_article_or_raise(session: Session, article_id: str) -> Article:
    """Return an article or raise NotFoundError."""
    article = session.get(Article, article_id)
    if article is None:
        raise NotFoundError("Article not found", resource_type="article", resource_id=article_id)
    return article


def add_publish_consent(session: Session, article_id: str, user_id: str) -> None:
    """Record a maintainer's consent to publish/merge.

    Appends *user_id* to ``publish_consents`` if not already present.
    Raises NotFoundError if article not found.
    """
    article = _get_article_or_raise(session, article_id)
    consents = list(article.publish_consents or [])
    if user_id not in consents:
        consents.append(user_id)
        article.publish_consents = consents
    session.flush()


def remove_publish_consent(session: Session, article_id: str, user_id: str) -> None:
    """Remove a single maintainer's consent to publish/merge.

    No-op if the consent was not recorded.  Raises NotFoundError if article not found.
    """
    article = _get_article_or_raise(session, article_id)
    consents = list(article.publish_consents or [])
    if user_id in consents:
        consents.remove(user_id)
        article.publish_consents = consents if consents else None
    session.flush()


def clear_publish_consents(session: Session, article_id: str) -> None:
    """Clear all publish consents (e.g. after content edit or publish).

    Raises NotFoundError if article not found.
    """
    article = _get_article_or_raise(session, article_id)
    article.publish_consents = None
    session.flush()


