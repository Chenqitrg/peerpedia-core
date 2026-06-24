# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Share CRUD — database only, ``session.flush()`` only."""

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import Article, Follow, Share


def add_share(
    session: Session, sharer_id: str, article_id: str, *,
    recipient_id: str | None = None, comment: str | None = None,
) -> Share:
    """Share or re-share an article.  Duplicates update the comment."""
    s = session.query(Share).filter(
        Share.sharer_id == sharer_id, Share.article_id == article_id,
    ).first()
    if s:
        s.comment = comment
        s.recipient_id = recipient_id
    else:
        s = Share(
            sharer_id=sharer_id, article_id=article_id,
            recipient_id=recipient_id, comment=comment,
        )
        session.add(s)
    session.flush()
    return s


def remove_share(session: Session, sharer_id: str, article_id: str) -> None:
    s = session.query(Share).filter(
        Share.sharer_id == sharer_id, Share.article_id == article_id,
    ).first()
    if s:
        session.delete(s)
        session.flush()


def is_shared(session: Session, sharer_id: str, article_id: str) -> bool:
    return session.query(Share).filter(
        Share.sharer_id == sharer_id, Share.article_id == article_id,
    ).first() is not None


def get_shares_for_user(
    session: Session, user_id: str, *, limit: int = 50, offset: int = 0,
) -> list[Share]:
    return (
        session.query(Share)
        .filter(Share.sharer_id == user_id)
        .order_by(Share.created_at.desc())
        .limit(limit).offset(offset)
        .all()
    )


def get_shares_by_followed(
    session: Session, viewer_id: str, *, limit: int = 20, offset: int = 0,
) -> list[Article]:
    """Return articles shared by users *viewer_id* follows, newest first.

    Uses DISTINCT to avoid duplicate rows when multiple followed users
    share the same article.  Returns Article objects — caller should join
    Share metadata separately if sharer identity/comments are needed.
    """
    return (
        session.query(Article)
        .join(Share, Article.id == Share.article_id)
        .join(Follow, Share.sharer_id == Follow.followed_id)
        .filter(
            Follow.follower_id == viewer_id,
            Follow.deleted_at.is_(None),
        )
        .distinct()
        .order_by(Share.created_at.desc())
        .limit(limit).offset(offset)
        .all()
    )
