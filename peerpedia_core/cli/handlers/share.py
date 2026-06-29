# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Share commands — public recommendations for followers."""

from __future__ import annotations

from peerpedia_core.cli.decorators import with_context
import peerpedia_core.app.commands.social as _social


@with_context
def _cmd_share(ctx, args):
    """Share an article — public recommendation visible to followers."""
    return _social.share(ctx, article_ref=args.article_id,
        to_ref=getattr(args, "to", None),
        comment=getattr(args, "comment", None))


@with_context
def _cmd_share_list(ctx, args):
    """List shares from followed users."""
    return _social.share_list(ctx, mine=getattr(args, "mine", False))


@with_context
def _cmd_unshare(ctx, args):
    """Remove a share (un-share an article)."""
    return _social.unshare(ctx, article_ref=args.article_id)
