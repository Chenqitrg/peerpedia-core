# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Notification commands — list and mark read."""

from __future__ import annotations

from peerpedia_core.app.context import AppContext
from peerpedia_core.app.refs import require_user
from peerpedia_core.app.result import AppResult
from peerpedia_core.core import (
    count_unread_notifications, get_notifications, mark_read,
)


def list_notifications(ctx: AppContext, *, unread_only: bool = True, limit: int = 50) -> AppResult:
    """List notifications.  Shows unread by default; pass ``unread_only=False`` for all."""
    # ── Guard ──
    user_id = require_user(ctx)
    # ── Execute ──
    notifs = get_notifications(ctx.db, user_id, unread_only=unread_only, limit=limit)
    unread_count = count_unread_notifications(ctx.db, user_id)
    items = [
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
    return AppResult("", data={"items": items, "unread_count": unread_count})


def mark_read_notification(ctx: AppContext, *, notification_id: str) -> AppResult:
    """Mark a notification as read."""
    # ── Execute ──
    mark_read(ctx.db, notification_id)
    ctx.db.commit()
    return AppResult("OK", params={"msg": f"Notification {notification_id[:8]} marked as read"})
