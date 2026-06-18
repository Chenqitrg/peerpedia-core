# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Bookmark CRUD operations."""

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import Article, Bookmark


def add_bookmark(session: Session, user_id: str, article_id: str) -> Bookmark:
    b = Bookmark(user_id=user_id, article_id=article_id)
    session.add(b)
    session.commit()
    return b


def remove_bookmark(session: Session, user_id: str, article_id: str) -> None:
    b = session.query(Bookmark).filter(Bookmark.user_id == user_id, Bookmark.article_id == article_id).first()
    if b:
        session.delete(b)
        session.commit()


def is_bookmarked(session: Session, user_id: str, article_id: str) -> bool:
    return session.query(Bookmark).filter(Bookmark.user_id == user_id, Bookmark.article_id == article_id).first() is not None


def get_bookmarks_for_user(session: Session, user_id: str) -> list[Article]:
    article_ids = (
        session.query(Bookmark.article_id).filter(Bookmark.user_id == user_id).order_by(Bookmark.created_at.desc()).all()
    )
    ids = [row[0] for row in article_ids]
    return session.query(Article).filter(Article.id.in_(ids)).all() if ids else []
