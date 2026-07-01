# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Notification commands — list and manage notifications."""

from __future__ import annotations

from peerpedia_core.app.commandspec import spec_for_cmd_id
from peerpedia_core.app.result import AppResult
from peerpedia_core.cli.decorators import with_context
from peerpedia_core.cli.display import _print_table
from peerpedia_core.cli.info import console
from peerpedia_core.messages import cached_text


@with_context
def _cmd_notifications(ctx, args):
    """List notifications. Shows unread by default; use --all for all."""
    all_flag = getattr(args, "all", False)
    result = spec_for_cmd_id("notifications").handler(ctx, {"all": all_flag})
    items = result.data.get("items", [])
    unread_count = result.data.get("unread_count", 0)
    if not items:
        console.print(cached_text("EMPTY_NOTIFICATIONS"))
        return AppResult(code="", data=None, params=result.params, notices=result.notices)
    _print_table(
        ["Event", "Message", "Read"],
        [[n["event"], n["message"], "✓" if n["read"] else "—"] for n in items],
        title=f"Notifications ({unread_count} unread)",
    )
    return AppResult(code="", data=None, params=result.params, notices=result.notices)


@with_context
def _cmd_notification_read(ctx, args):
    """Mark a notification as read."""
    return spec_for_cmd_id("notifications.read").handler(ctx, {
        "notification_id": args.notification_id,
    })
