# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Share CRUD — database only, ``session.flush()`` only."""

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import ArticleMetaStorage, FollowStorage, ShareStorage


def add_share(
    session: Session, sharer_id: str, article_id: str, *,
    recipient_id: str | None = None, comment: str | None = None,
) -> ShareStorage:
    """Share or re-share an article.  Duplicates update the comment."""
    s = session.query(ShareStorage).filter(
        ShareStorage.sharer_id == sharer_id, ShareStorage.article_id == article_id,
    ).first()
    if s:
        s.comment = comment
        s.recipient_id = recipient_id
    else:
        s = ShareStorage(
            sharer_id=sharer_id, article_id=article_id,
            recipient_id=recipient_id, comment=comment,
        )
        session.add(s)
    session.flush()
    return s


def remove_share(session: Session, sharer_id: str, article_id: str) -> None:
    """Remove a share.  No-op if not shared."""
    s = session.query(ShareStorage).filter(
        ShareStorage.sharer_id == sharer_id, ShareStorage.article_id == article_id,
    ).first()
    if s:
        session.delete(s)
        session.flush()


def is_shared(session: Session, sharer_id: str, article_id: str) -> bool:
    """Return True if *sharer_id* has shared *article_id*."""
    return session.query(ShareStorage).filter(
        ShareStorage.sharer_id == sharer_id, ShareStorage.article_id == article_id,
    ).first() is not None


def get_shares_for_user(
    session: Session, user_id: str, *, limit: int = 50, offset: int = 0,
) -> list[ShareStorage]:
    """Return all shares by *user_id*, newest first."""
    return (
        session.query(ShareStorage)
        .filter(Share.sharer_id == user_id)
        .order_by(Share.created_at.desc())
        .limit(limit).offset(offset)
        .all()
    )


def get_shares_by_followed(
    session: Session, viewer_id: str, *, limit: int = 20, offset: int = 0,
) -> list[ArticleMetaStorage]:
    """Return articles shared by users *viewer_id* follows, newest first.

    Uses DISTINCT to avoid duplicate rows when multiple followed users
    share the same article.  Returns ArticleMetaStorage objects — caller should join
    ShareStorage metadata separately if sharer identity/comments are needed.
    """
    return (
        session.query(ArticleMetaStorage)
        .join(ShareStorage, ArticleMetaStorage.id == ShareStorage.article_id)
        .join(FollowStorage, ShareStorage.sharer_id == FollowStorage.followed_id)
        .filter(
            FollowStorage.follower_id == viewer_id,
            FollowStorage.deleted_at.is_(None),
        )
        .distinct()
        .order_by(Share.created_at.desc())
        .limit(limit).offset(offset)
        .all()
    )
