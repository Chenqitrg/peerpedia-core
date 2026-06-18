# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article CRUD operations — database only, no git/filesystem side effects."""

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import Article, ArticleAuthor

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
    status: str = "draft",
    **kwargs,
) -> Article:
    """Create a new article record with author rows in the join table."""
    a = Article(status=status, **kwargs)
    session.add(a)
    session.flush()  # ensure a.id is available
    add_article_authors(session, a.id, authors)
    session.commit()  # DB commit, not git
    return a


def get_article(session: Session, article_id: str) -> Article | None:
    return session.get(Article, article_id)


def list_articles(
    session: Session,
    status: str | set[str] | None = None,
    author_id: str | None = None,
    follower_id: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[Article]:
    """List articles with optional filters, ordered by created_at desc.

    Args:
        status: Filter by Article.status. Pass a ``str`` for single status
            (e.g. ``"published"``), a ``set[str]`` for multiple (e.g.
            ``{"draft", "sedimentation"}``), or ``None`` for no filter.
        author_id: Filter by author. None = no filter.
        follower_id: Filter by follower of the author. None = no filter.
        limit: Max results. None = unlimited.
        offset: Pagination offset.
    """
    q = session.query(Article)
    if isinstance(status, set):
        if status:
            q = q.filter(Article.status.in_(list(status)))
    elif status:
        q = q.filter(Article.status == status)
    if author_id:
        q = q.join(ArticleAuthor, Article.id == ArticleAuthor.article_id).filter(ArticleAuthor.author_id == author_id)
    if follower_id:
        from peerpedia_core.storage.db.models import Follow

        q = (
            q.join(ArticleAuthor, Article.id == ArticleAuthor.article_id)
            .join(Follow, ArticleAuthor.author_id == Follow.followed_id)
            .filter(Follow.follower_id == follower_id)
            .distinct()
        )
    q = q.order_by(Article.created_at.desc())
    if limit is not None:
        q = q.limit(limit).offset(offset)
    return q.all()


def count_articles(session: Session, status: str | set[str] | None = None, author_id: str | None = None) -> int:
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
) -> Article:
    a = session.get(Article, article_id)
    if a is None:
        raise ValueError(f"Article {article_id} not found")
    a.compiled_format = html_format
    a.compiled_output = output
    a.compiled_pages = pages
    session.commit()  # DB commit, not git
    return a


def update_article_status(session: Session, article_id: str, new_status: str) -> Article:
    a = session.get(Article, article_id)
    if a is None:
        raise ValueError(f"Article {article_id} not found")
    a.status = new_status
    session.commit()  # DB commit, not git
    return a


def increment_fork_count(session: Session, article_id: str) -> Article:
    a = session.get(Article, article_id)
    if a is None:
        raise ValueError(f"Article {article_id} not found")
    a.fork_count += 1
    session.commit()  # DB commit, not git
    return a


def set_sink_start(session: Session, article_id: str, duration_days: int) -> Article:
    from datetime import datetime, timezone

    a = session.get(Article, article_id)
    if a is None:
        raise ValueError(f"Article {article_id} not found")
    a.status = "sedimentation"
    a.sink_start = datetime.now(timezone.utc)
    a.sink_duration_days = duration_days
    session.commit()  # DB commit, not git
    return a


def delete_article(session: Session, article_id: str) -> None:
    """Delete an article and its related records from the database.

    Cascades to: article_authors, reviews, bookmarks, citations,
    merge_proposals.  Does NOT touch the git repository — callers
    should clean up the article's git directory separately via
    ``git_backend.delete_article_repo()``.

    Raises ValueError if the article does not exist.
    """
    from peerpedia_core.storage.db.models import (
        Bookmark,
        Citation,
        MergeProposal,
        Review,
    )

    a = session.get(Article, article_id)
    if a is None:
        raise ValueError(f"Article {article_id} not found")

    # Delete related records
    session.query(ArticleAuthor).filter(ArticleAuthor.article_id == article_id).delete()
    session.query(Review).filter(Review.article_id == article_id).delete()
    session.query(Bookmark).filter(Bookmark.article_id == article_id).delete()
    session.query(Citation).filter((Citation.from_article_id == article_id) | (Citation.to_article_id == article_id)).delete()
    session.query(MergeProposal).filter(
        (MergeProposal.fork_article_id == article_id) | (MergeProposal.target_article_id == article_id)
    ).delete()

    session.delete(a)
    session.commit()  # DB commit, not git


def extend_sink(session: Session, article_id: str, extra_days: int, max_days: int = 180) -> Article:
    """Author extends sink time. Can be called repeatedly up to max_days.

    Raises ValueError if extra_days <= 0.
    Only increments sink_extended_count when the duration actually increases.
    """
    if extra_days <= 0:
        raise ValueError(f"extra_days must be positive, got {extra_days}")
    a = session.get(Article, article_id)
    if a is None:
        raise ValueError(f"Article {article_id} not found")
    old_total = a.sink_duration_days
    new_total = a.sink_duration_days + extra_days
    if new_total > max_days:
        new_total = max_days
    a.sink_duration_days = new_total
    if new_total > old_total:
        a.sink_extended_count += 1
    session.commit()  # DB commit, not git
    return a


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


