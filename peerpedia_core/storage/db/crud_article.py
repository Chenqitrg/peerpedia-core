# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Article CRUD operations."""

from pathlib import Path

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


def replace_article_authors(session: Session, article_id: str, author_ids: set[str]) -> None:
    """Replace all author rows for an article (delete old + insert new).

    Unlike ``rebuild_article_authors`` which merges (never loses existing
    authors), this fully replaces the join table to match the given set.
    """
    from peerpedia_core.storage.db.models import User

    session.query(ArticleAuthor).filter(ArticleAuthor.article_id == article_id).delete()

    # Sort by username for stable ordering
    rows = session.query(User).filter(User.id.in_(list(author_ids))).all()
    row_map = {u.id: u for u in rows}
    sorted_ids = sorted(
        [uid for uid in author_ids if uid in row_map],
        key=lambda uid: row_map[uid].username,
    )

    for pos, author_id in enumerate(sorted_ids):
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
    session.commit()
    return a


def get_article(session: Session, article_id: str) -> Article | None:
    return session.get(Article, article_id)


def list_articles(
    session: Session,
    status: str | None = None,
    author_id: str | None = None,
    follower_id: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[Article]:
    q = session.query(Article)
    if status:
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


def count_articles(session: Session, status: str | None = None, author_id: str | None = None) -> int:
    q = session.query(Article)
    if status:
        q = q.filter(Article.status == status)
    if author_id:
        q = q.join(ArticleAuthor, Article.id == ArticleAuthor.article_id).filter(ArticleAuthor.author_id == author_id)
    return q.count()


def list_articles_multi_status(
    session: Session,
    statuses: set[str],
    author_id: str | None = None,
    follower_id: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[Article]:
    """List articles matching any of *statuses* (SQL-level IN filter).

    Used by the policy layer so visibility filtering happens before
    pagination, avoiding wrong totals / short pages.
    """
    from peerpedia_core.storage.db.models import Follow

    q = session.query(Article)
    if statuses:
        q = q.filter(Article.status.in_(list(statuses)))
    if author_id:
        q = q.join(ArticleAuthor, Article.id == ArticleAuthor.article_id).filter(ArticleAuthor.author_id == author_id)
    if follower_id:
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


def count_articles_multi_status(
    session: Session,
    statuses: set[str],
    author_id: str | None = None,
) -> int:
    """Count articles matching any of *statuses*."""
    q = session.query(Article)
    if statuses:
        q = q.filter(Article.status.in_(list(statuses)))
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
    session.commit()
    return a


def update_article_status(session: Session, article_id: str, new_status: str) -> Article:
    a = session.get(Article, article_id)
    if a is None:
        raise ValueError(f"Article {article_id} not found")
    a.status = new_status
    session.commit()
    return a


def increment_fork_count(session: Session, article_id: str) -> Article:
    a = session.get(Article, article_id)
    if a is None:
        raise ValueError(f"Article {article_id} not found")
    a.fork_count += 1
    session.commit()
    return a


def set_sink_start(session: Session, article_id: str, duration_days: int) -> Article:
    from datetime import datetime, timezone

    a = session.get(Article, article_id)
    if a is None:
        raise ValueError(f"Article {article_id} not found")
    a.status = "sedimentation"
    a.sink_start = datetime.now(timezone.utc)
    a.sink_duration_days = duration_days
    session.commit()
    return a


def delete_article(session: Session, article_id: str) -> None:
    """Delete an article from the database and remove its git repository.

    Cascades to related records: article_authors, reviews, bookmarks,
    citations, merge_proposals.
    Raises ValueError if the article does not exist.
    """
    import shutil

    from peerpedia_core.storage.db.models import (
        Bookmark,
        Citation,
        MergeProposal,
        Review,
    )
    from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR

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
    session.commit()

    repo_path = Path(DEFAULT_ARTICLES_DIR) / article_id
    if repo_path.exists():
        shutil.rmtree(str(repo_path))


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
    session.commit()
    return a


# ── Multi-author: git-derived authors ──────────────────────────────────────


def resolve_user_id_from_git_email(session: Session, email: str) -> str:
    """Resolve a user ID from a git commit email.

    Only accepts ``{UUID}@peerpedia`` format (User.id lookup).
    Raises ValueError if the email does not resolve to a known user.
    """
    from peerpedia_core.storage.db.models import User

    local = email.split("@", 1)[0].strip()
    u = session.get(User, local)
    if u is None:
        raise ValueError(f"No user found for git email: {email}")
    return u.id


def get_authors_from_git(
    repo_path,
    session: Session,
    since_hash: str | None = None,
) -> set[str]:
    """Extract unique author user IDs from git commit log.

    Scans commits reachable from HEAD. Uses git range notation
    ``since..HEAD`` for incremental scans — handles merge DAGs
    correctly without missing author chains.
    """
    import git

    repo = git.Repo(repo_path)
    if not repo.head.is_valid():
        return set()

    user_ids: set[str] = set()

    if since_hash:
        commits = repo.iter_commits(rev=f"{since_hash}..HEAD")
    else:
        commits = repo.iter_commits()

    for commit in commits:
        email = commit.author.email
        try:
            user_id = resolve_user_id_from_git_email(session, email)
            user_ids.add(user_id)
        except ValueError:
            pass

    return user_ids


def rebuild_article_authors(
    session: Session,
    article_id: str,
    new_author_ids: set[str],
) -> None:
    """Append new authors to article_authors (never delete existing ones).

    Updates ``article.last_author_rebuild_hash`` to current repo HEAD.
    """
    from peerpedia_core.storage.db.models import User
    from peerpedia_core.storage.git_backend import DEFAULT_ARTICLES_DIR

    existing = set(get_author_ids(session, article_id))
    merged = existing | new_author_ids

    # Only rebuild join table when authors actually changed
    if merged != existing:
        # Resolve usernames for lexicographic sort
        rows = session.query(User).filter(User.id.in_(list(merged))).all()
        row_map = {u.id: u for u in rows}
        sorted_ids = sorted(
            [uid for uid in merged if uid in row_map],
            key=lambda uid: row_map[uid].username,
        )
        # Add any IDs that exist in merged but not in DB (shouldn't happen)
        sorted_ids.extend(uid for uid in merged if uid not in row_map)

        # Rebuild join table
        session.query(ArticleAuthor).filter(ArticleAuthor.article_id == article_id).delete()
        add_article_authors(session, article_id, sorted_ids)

    # Update rebuild marker
    import git

    article = session.get(Article, article_id)
    if article:
        rp = DEFAULT_ARTICLES_DIR / article_id
        if rp.exists() and (rp / ".git").is_dir():
            repo = git.Repo(rp)
            if repo.head.is_valid():
                article.last_author_rebuild_hash = repo.head.commit.hexsha

    session.commit()


def validate_article_has_authors(session: Session, article_id: str) -> None:
    """Raise ValueError if an article has no authors.

    Articles must always have at least one author.  An article without
    authors indicates a bug in the creation path — never silently repair,
    always surface the error.
    """
    author_ids = get_author_ids(session, article_id)
    if not author_ids:
        raise ValueError(
            f"Article {article_id} has no authors. "
            "This is a bug — every article must have at least one author. "
            "Check the creation path (create_article, sync auto-create, or direct DB insert)."
        )


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
