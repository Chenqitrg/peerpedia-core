# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Review commands — submit and list."""

from __future__ import annotations

from peerpedia_core.app.commandspec import spec_for_cmd_id
from peerpedia_core.cli.decorators import with_context
from peerpedia_core.editor import open_editor as _open_editor
from peerpedia_core.cli.info import _out


@with_context
def _cmd_review_submit(ctx, args):
    """Submit a review with 5-dim scores + optional comment."""
    return spec_for_cmd_id("review.submit").handler(ctx, {
        "article_id": args.article_id, "scores": args.scores,
        "comment": args.comment or "",
    })


@with_context
def _cmd_review_list(ctx, args):
    """List all reviews for an article."""
    return spec_for_cmd_id("review.list").handler(ctx, {
        "article_id": args.article_id,
    })


@with_context
def _cmd_review_reply(ctx, args):
    """Reply to a reviewer on an article.  Opens $EDITOR for the reply."""
    reply = _edit_reply(args.to)
    if not reply:
        _out(args, "EMPTY_REPLY")
    return spec_for_cmd_id("review.reply").handler(ctx, {
        "article_id": args.article_id, "to": args.to, "content": reply,
    })


@with_context
def _cmd_review_invite(ctx, args):
    """Invite a user to review an article."""
    return spec_for_cmd_id("review.invite").handler(ctx, {
        "article_id": args.article_id, "user": args.user,
    })


@with_context
def _cmd_review_accept(ctx, args):
    """Accept a pending review invitation."""
    return spec_for_cmd_id("review.accept").handler(ctx, {
        "article_id": args.article_id,
    })


@with_context
def _cmd_review_decline(ctx, args):
    """Decline a pending review invitation."""
    return spec_for_cmd_id("review.decline").handler(ctx, {
        "article_id": args.article_id,
    })


@with_context
def _cmd_review_rate(ctx, args):
    """Rate a review's helpfulness."""
    return spec_for_cmd_id("review.rate").handler(ctx, {
        "article_id": args.article_id, "reviewer": args.reviewer,
        "helpfulness": args.helpfulness,
    })


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
