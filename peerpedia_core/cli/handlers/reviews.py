# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Review commands — submit and list."""

from __future__ import annotations

from peerpedia_core.cli.handler import with_context
from peerpedia_core.cli.helpers import _open_editor
from peerpedia_core.cli.output import _out
import peerpedia_core.app.commands.review as _review


@with_context
def _cmd_review_submit(ctx, args):
    """Submit a review with 5-dim scores + optional comment."""
    return _review.submit(ctx, article_ref=args.article_id,
        scores_str=args.scores, comment=args.comment or "")


@with_context
def _cmd_review_list(ctx, args):
    """List all reviews for an article."""
    return _review.list_reviews(ctx, article_ref=args.article_id)


@with_context
def _cmd_review_reply(ctx, args):
    """Reply to a reviewer on an article.  Opens $EDITOR for the reply."""
    reply = _edit_reply(args.to)
    if not reply:
        _out(args, "EMPTY_REPLY")
    return _review.reply(ctx, article_ref=args.article_id,
        to_ref=args.to, content=reply)


@with_context
def _cmd_review_invite(ctx, args):
    """Invite a user to review an article."""
    return _review.invite_reviewer(ctx, article_ref=args.article_id,
        user_ref=args.user)


@with_context
def _cmd_review_accept(ctx, args):
    """Accept a pending review invitation."""
    return _review.accept(ctx, article_ref=args.article_id)


@with_context
def _cmd_review_decline(ctx, args):
    """Decline a pending review invitation."""
    return _review.decline(ctx, article_ref=args.article_id)


@with_context
def _cmd_review_rate(ctx, args):
    """Rate a review's helpfulness."""
    return _review.rate(ctx, article_ref=args.article_id,
        reviewer_ref=args.reviewer, helpfulness=args.helpfulness)


def _edit_reply(to_user: str) -> str:
    """Open $EDITOR with a reply template, return the non-comment text."""
    template = (
        f"# Author Reply\n"
        f"# Replying to: {to_user}\n"
        "# Write your reply below. Lines starting with # are ignored.\n"
        "# An empty reply aborts.\n\n"
    )
    content = _open_editor(template)
    lines = [l for l in content.splitlines() if not l.strip().startswith("#")]
    return "\n".join(lines).strip()
