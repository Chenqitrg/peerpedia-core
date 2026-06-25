# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Notification commands — list and manage notifications."""

from peerpedia_core.cli.helpers import (
    _with_db, _get_session_user, _ok, _die, _json_out,
)
from peerpedia_core.cli.display import console
from peerpedia_core.commands import (
    count_unread, get_notifications, mark_read,
)


@_with_db
def _cmd_notifications(db, args):
    """List notifications. Shows unread by default; use --all for all."""
    user_id = _get_session_user()
    unread_only = not getattr(args, "all", False)
    notifs = get_notifications(db, user_id, unread_only=unread_only, limit=50)
    unread_count = count_unread(db, user_id)

    if args.json:
        _json_out([
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
        ])
        return

    if not notifs:
        console.print("[muted]No notifications.[/]")
        return

    if unread_only and unread_count > 0:
        console.print(f"[info]{unread_count} unread notification(s)[/]\n")

    for n in notifs:
        ts = n.created_at.strftime("%Y-%m-%d %H:%M") if n.created_at else ""
        unread_tag = "" if n.read else " [bold yellow]NEW[/]"
        console.print(f"  [accent]{n.id[:8]}[/]  {ts}  {n.message}{unread_tag}")


@_with_db
def _cmd_notification_read(db, args):
    """Mark a notification as read.

    args: notification_id [positional]
    """
    try:
        mark_read(db, args.notification_id)
        db.commit()
        _ok(f"Notification {args.notification_id[:8]} marked as read")
    except ValueError as e:
        _die(str(e), code="NOT_FOUND",
             suggestion="Check the notification ID. You can list your "
                        "notifications with 'peerpedia notifications'.",
             see_also=["notifications"])
