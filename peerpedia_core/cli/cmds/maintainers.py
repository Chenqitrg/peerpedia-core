# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Maintainer commands — manage who controls an article."""

from __future__ import annotations

from peerpedia_core.app.commandspec import spec_for_cmd_id
from peerpedia_core.cli.decorators import with_context


@with_context
def _cmd_maintainer_add(ctx, args):
    """Add a user as a co-author (maintainer) of an article."""
    return spec_for_cmd_id("maintainer.add").handler(ctx, {
        "article_id": args.article_id, "target_user": args.target_user,
    })


@with_context
def _cmd_maintainer_remove(ctx, args):
    """Remove a user from maintainers."""
    return spec_for_cmd_id("maintainer.remove").handler(ctx, {
        "article_id": args.article_id, "target_user": args.target_user,
    })


@with_context
def _cmd_maintainer_list(ctx, args):
    """List all maintainers of an article."""
    return spec_for_cmd_id("maintainer.list").handler(ctx, {
        "article_id": args.article_id,
    })


@with_context
def _cmd_maintainer_consent(ctx, args):
    """Consent to publish or merge as a maintainer."""
    return spec_for_cmd_id("maintainer.consent").handler(ctx, {
        "article_id": args.article_id,
    })


@with_context
def _cmd_maintainer_revoke(ctx, args):
    """Revoke publish/merge consent."""
    return spec_for_cmd_id("maintainer.revoke").handler(ctx, {
        "article_id": args.article_id,
    })
