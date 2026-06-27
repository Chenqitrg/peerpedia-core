# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Notification CRUD — all functions call session.flush() only."""

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import NotificationStorage


def create_notification(
    session: Session,
    *,
    user_id: str,
    event: str,
    message: str,
    article_id: str | None = None,
    actor_id: str | None = None,
) -> NotificationStorage:
    """Create a notification.  Caller must commit()."""
    n = NotificationStorage(
        user_id=user_id, event=event, message=message,
        article_id=article_id, actor_id=actor_id,
    )
    session.add(n)
    session.flush()
    return n


def ensure_notification(
    session: Session,
    *,
    user_id: str,
    event: str,
    message: str,
    article_id: str | None = None,
    actor_id: str | None = None,
    notification_id: str | None = None,
) -> NotificationStorage:
    """Idempotent notification insert — skips if an identical notification exists.

    Dedup by (user_id, event, actor_id, article_id, message).
    """
    existing = session.query(NotificationStorage).filter(
        NotificationStorage.user_id == user_id,
        NotificationStorage.event == event,
        NotificationStorage.actor_id == actor_id,
        NotificationStorage.article_id == article_id,
        NotificationStorage.message == message,
    ).first()
    if existing is not None:
        return existing
    n = NotificationStorage(
        id=notification_id,
        user_id=user_id, event=event, message=message,
        article_id=article_id, actor_id=actor_id,
    )
    session.add(n)
    session.flush()
    return n


def get_notifications(
    session: Session,
    user_id: str,
    *,
    unread_only: bool = False,
    limit: int = 50,
) -> list[NotificationStorage]:
    """Return notifications for a user, newest first."""
    q = session.query(NotificationStorage).filter(NotificationStorage.user_id == user_id)
    if unread_only:
        q = q.filter(NotificationStorage.read == 0)
    return q.order_by(NotificationStorage.created_at.desc()).limit(limit).all()


def mark_read(session: Session, notification_id: str) -> None:
    """Mark a notification as read.  Raises ValueError if not found."""
    n = session.get(NotificationStorage, notification_id)
    if n is None:
        raise ValueError(f"Notification {notification_id} not found")
    if n.read == 0:
        n.read = 1
        session.flush()


def count_unread_notifications(session: Session, user_id: str) -> int:
    """Return the number of unread notifications for a user."""
    return (
        session.query(NotificationStorage)
        .filter(NotificationStorage.user_id == user_id, NotificationStorage.read == 0)
        .count()
    )
