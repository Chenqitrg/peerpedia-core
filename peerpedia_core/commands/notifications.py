# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Notification commands — thin facade over CRUD."""

from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.models import Notification
from peerpedia_core.storage.db.crud_notification import (
    count_unread as _count_unread,
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
    return _create(db, user_id=user_id, event=event, message=message,
                   article_id=article_id, actor_id=actor_id)


def get_notifications(
    db: Session, user_id: str, *, unread_only: bool = False, limit: int = 50,
):
    return _get(db, user_id, unread_only=unread_only, limit=limit)


def mark_read(db: Session, notification_id: str):
    return _mark_read(db, notification_id)


def count_unread(db: Session, user_id: str) -> int:
    return _count_unread(db, user_id)


def create_notifications_batch(
    db: Session,
    entries: list[dict],
) -> list[Notification]:
    """Create multiple notifications in one batch flush.

    Each entry dict must have keys matching ``create_notification`` kwargs:
    user_id, event, message, plus optional article_id and actor_id.
    Returns the list of created Notification ORM objects.
    """
    notifications = [
        Notification(
            user_id=e["user_id"],
            event=e["event"],
            message=e["message"],
            article_id=e.get("article_id"),
            actor_id=e.get("actor_id"),
        )
        for e in entries
    ]
    db.add_all(notifications)
    db.flush()
    return notifications
