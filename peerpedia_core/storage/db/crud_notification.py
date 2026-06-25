# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Notification CRUD — all functions call session.flush() only."""

from sqlalchemy.orm import Session

from peerpedia_core.storage.db.models import Notification


def create_notification(
    session: Session,
    *,
    user_id: str,
    event: str,
    message: str,
    article_id: str | None = None,
    actor_id: str | None = None,
) -> Notification:
    """Create a notification.  Caller must commit()."""
    n = Notification(
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
) -> list[Notification]:
    """Return notifications for a user, newest first."""
    q = session.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        q = q.filter(Notification.read == 0)
    return q.order_by(Notification.created_at.desc()).limit(limit).all()


def mark_read(session: Session, notification_id: str) -> None:
    """Mark a notification as read.  Raises ValueError if not found."""
    n = session.get(Notification, notification_id)
    if n is None:
        raise ValueError(f"Notification {notification_id} not found")
    if n.read == 0:
        n.read = 1
        session.flush()


def count_unread(session: Session, user_id: str) -> int:
    """Return the number of unread notifications for a user."""
    return (
        session.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read == 0)
        .count()
    )
