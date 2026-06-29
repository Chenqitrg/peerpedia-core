# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Maintainer commands — manage who controls an article."""

from __future__ import annotations

from peerpedia_core.cli.decorators import with_context
import peerpedia_core.app.commands.maintainer as _maint


@with_context
def _cmd_maintainer_add(ctx, args):
    """Add a user as a co-author (maintainer) of an article."""
    return _maint.add(ctx, article_ref=args.article_id, target_ref=args.target_user)


@with_context
def _cmd_maintainer_remove(ctx, args):
    """Remove a user from maintainers."""
    return _maint.remove(ctx, article_ref=args.article_id, target_ref=args.target_user)


@with_context
def _cmd_maintainer_list(ctx, args):
    """List all maintainers of an article."""
    return _maint.list_article_maintainers(ctx, article_ref=args.article_id)


@with_context
def _cmd_maintainer_consent(ctx, args):
    """Consent to publish or merge as a maintainer."""
    return _maint.consent(ctx, article_ref=args.article_id)


@with_context
def _cmd_maintainer_revoke(ctx, args):
    """Revoke publish/merge consent."""
    return _maint.revoke(ctx, article_ref=args.article_id)
