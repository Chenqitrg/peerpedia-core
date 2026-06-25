# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Notification commands — thin facade over CRUD."""

from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.models import Notification
from peerpedia_core.storage.db.crud_notification import (
    count_unread_notifications as _count_unread_notifications,
    create_notification as _create,
    get_notifications as _get,
    mark_read as _mark_read,
)


def create_notification(
    db: Session,
    *,
    user_id: str,
    event: str,
    message: str,
    article_id: str | None = None,
    actor_id: str | None = None,
):
    """Create a notification for *user_id*.  Returns the Notification ORM object."""
    return _create(db, user_id=user_id, event=event, message=message,
                   article_id=article_id, actor_id=actor_id)


def get_notifications(
    db: Session, user_id: str, *, unread_only: bool = False, limit: int = 50,
):
    """Return notifications for *user_id*, newest first."""
    return _get(db, user_id, unread_only=unread_only, limit=limit)


def mark_read(db: Session, notification_id: str):
    """Mark a single notification as read."""
    return _mark_read(db, notification_id)


def count_unread_notifications(db: Session, user_id: str) -> int:
    """Return the count of unread notifications for *user_id*."""
    return _count_unread_notifications(db, user_id)


def get_notifications_for_user(db: Session, user_id: str) -> list[dict]:
    """Return notifications for a user as dicts, newest first."""
    notifs = _get(db, user_id)
    return [
        {
            "id": n.id,
            "event": n.event,
            "message": n.message,
            "article_id": n.article_id,
            "actor_id": n.actor_id,
            "read": bool(n.read),
            "created_at": str(n.created_at) if n.created_at else None,
        }
        for n in notifs
    ]


def merge_notifications(
    db: Session,
    entries: list[dict],
) -> int:
    """Merge notifications from a P2P sync — dedup on (user_id, event, article_id, actor_id, created_at).

    Returns count of new notifications inserted.
    """
    count = 0
    for entry in entries:
        existing = _get(db, entry.get("user_id"), limit=200)
        dup = False
        for n in existing:
            if (
                n.event == entry.get("event")
                and n.article_id == entry.get("article_id")
                and n.actor_id == entry.get("actor_id")
                and str(n.created_at) == entry.get("created_at")
            ):
                # Update read status if newer
                if entry.get("read", 0) and not n.read:
                    n.read = 1
                dup = True
                break
        if not dup:
            create_notification(
                db,
                user_id=entry["user_id"],
                event=entry["event"],
                message=entry["message"],
                article_id=entry.get("article_id"),
                actor_id=entry.get("actor_id"),
            )
            count += 1
    db.flush()
    return count


def create_notifications_batch(
    db: Session,
    entries: list[dict],
) -> list[Notification]:
    """Create multiple notifications in one batch flush.

    Each entry dict must have keys matching ``create_notification`` kwargs:
    user_id, event, message, plus optional article_id and actor_id.
    Returns the list of created Notification ORM objects.

    Delegates to ``create_notification`` for consistency with the single
    notification path — any future validation or side effects added there
    will be applied to batch-created notifications as well.
    """
    notifications = []
    for e in entries:
        n = create_notification(
            db,
            user_id=e["user_id"],
            event=e["event"],
            message=e["message"],
            article_id=e.get("article_id"),
            actor_id=e.get("actor_id"),
        )
        notifications.append(n)
    return notifications
