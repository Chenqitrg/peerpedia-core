# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Bookmark CRUD operations."""

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import ArticleMetaStorage, BookmarkStorage


def add_bookmark(session: Session, user_id: str, article_id: str) -> BookmarkStorage:
    """Bookmark an article.  Idempotent — duplicates silently succeed."""
    existing = session.query(BookmarkStorage).filter(
        BookmarkStorage.user_id == user_id, BookmarkStorage.article_id == article_id,
    ).first()
    if existing:
        return existing
    b = BookmarkStorage(user_id=user_id, article_id=article_id)
    session.add(b)
    session.flush()
    return b


def remove_bookmark(session: Session, user_id: str, article_id: str) -> None:
    """Remove a bookmark.  No-op if not bookmarked."""
    b = session.query(BookmarkStorage).filter(Bookmark.user_id == user_id, BookmarkStorage.article_id == article_id).first()
    if b:
        session.delete(b)
        session.flush()


def is_bookmarked(session: Session, user_id: str, article_id: str) -> bool:
    """Return True if *user_id* has bookmarked *article_id*."""
    return session.query(BookmarkStorage).filter(Bookmark.user_id == user_id, BookmarkStorage.article_id == article_id).first() is not None


def get_bookmarks_for_user(session: Session, user_id: str) -> list[ArticleMetaStorage]:
    """Return all articles bookmarked by *user_id*, newest first."""
    return (
        session.query(ArticleMetaStorage)
        .join(BookmarkStorage, BookmarkStorage.article_id == ArticleMetaStorage.id)
        .filter(Bookmark.user_id == user_id)
        .order_by(Bookmark.created_at.desc())
        .all()
    )
