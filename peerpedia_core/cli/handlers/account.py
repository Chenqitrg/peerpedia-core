# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Account commands — search, delete, whoami."""

from __future__ import annotations

from peerpedia_core.cli.decorators import with_context
import peerpedia_core.app.commands.account as _account


@with_context
def _cmd_whoami(ctx, args):
    """Show current login status."""
    return _account.whoami(ctx)


@with_context
def _cmd_account_delete(ctx, args):
    """Soft-delete the current user account."""
    return _account.delete_account(ctx)


@with_context
def _cmd_account_search(ctx, args):
    """Search users by name (case-insensitive)."""
    return _account.search_users(ctx, query=getattr(args, "query", ""))
