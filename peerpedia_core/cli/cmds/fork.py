# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Fork and merge commands."""

from __future__ import annotations

from peerpedia_core.app.commandspec import spec_for_cmd_id
from peerpedia_core.cli.decorators import with_context


@with_context
def _cmd_fork(ctx, args):
    """Fork a published article into a new draft copy."""
    return spec_for_cmd_id("fork").handler(ctx, {"article_id": args.article_id})


@with_context
def _cmd_merge_propose(ctx, args):
    """Propose merging a fork back into the original article."""
    return spec_for_cmd_id("merge.propose").handler(ctx, {
        "fork_id": args.fork_id, "target": args.target,
    })


@with_context
def _cmd_merge_accept(ctx, args):
    """Accept a merge proposal. May report conflicts."""
    return spec_for_cmd_id("merge.accept").handler(ctx, {
        "proposal_id": args.proposal_id, "target": args.target,
    })


@with_context
def _cmd_merge_withdraw(ctx, args):
    """Withdraw a merge proposal."""
    return spec_for_cmd_id("merge.withdraw").handler(ctx, {
        "proposal_id": args.proposal_id,
    })
