# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Notification commands — list and manage notifications."""

from __future__ import annotations

from peerpedia_core.cli.decorators import with_context
import peerpedia_core.app.commands.notification as _notify


@with_context
def _cmd_notifications(ctx, args):
    """List notifications. Shows unread by default; use --all for all."""
    unread_only = not getattr(args, "all", False)
    return _notify.list_notifications(ctx, unread_only=unread_only)


@with_context
def _cmd_notification_read(ctx, args):
    """Mark a notification as read."""
    return _notify.mark_read_notification(ctx, notification_id=args.notification_id)
