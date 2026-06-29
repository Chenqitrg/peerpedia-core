# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Bookmark commands."""

from __future__ import annotations

from peerpedia_core.cli.handler import with_context
import peerpedia_core.app.commands.social as _social


@with_context
def _cmd_bookmark(ctx, args):
    """Bookmark an article."""
    return _social.bookmark(ctx, article_ref=args.article_id)


@with_context
def _cmd_unbookmark(ctx, args):
    """Remove a bookmark."""
    return _social.unbookmark(ctx, article_ref=args.article_id)
