# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Notification commands — thin facade over CRUD."""

from peerpedia_core.storage.db import Session
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
