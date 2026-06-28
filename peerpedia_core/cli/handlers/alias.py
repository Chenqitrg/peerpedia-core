# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Alias commands — nickname users you follow."""

from __future__ import annotations

from peerpedia_core.cli.handler import with_context
import peerpedia_core.app.commands.social as _social


@with_context
def _cmd_alias_set(ctx, args):
    """Set an alias for a followed user."""
    return _social.alias_set(ctx, user_ref=args.user_identifier, alias=args.alias)


@with_context
def _cmd_alias_remove(ctx, args):
    """Remove an alias for a user."""
    return _social.alias_remove(ctx, user_ref=args.user_identifier)


@with_context
def _cmd_alias_list(ctx, args):
    """List all aliases for the current user."""
    return _social.alias_list(ctx)
