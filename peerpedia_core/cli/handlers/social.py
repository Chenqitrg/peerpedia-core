# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Social — follow, unfollow, following, followers."""

from __future__ import annotations

from peerpedia_core.cli.decorators import with_context
import peerpedia_core.app.commands.social as _social


@with_context
def _cmd_follow_user(ctx, args):
    """Follow a user."""
    return _social.follow(ctx, target_ref=args.user_identifier)


@with_context
def _cmd_unfollow_user(ctx, args):
    """Unfollow a user. Idempotent."""
    return _social.unfollow(ctx, target_ref=args.user_identifier)


@with_context
def _cmd_following(ctx, args):
    """List users that *user_id* follows."""
    return _social.list_following(ctx, user_ref=args.user)


@with_context
def _cmd_followers(ctx, args):
    """List followers of *user_id*."""
    return _social.list_followers(ctx, user_ref=args.user)
