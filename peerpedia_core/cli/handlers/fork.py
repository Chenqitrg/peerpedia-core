# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Fork and merge commands."""

from __future__ import annotations

from peerpedia_core.cli.handler import with_context
import peerpedia_core.app.commands.fork as _fork


@with_context
def _cmd_fork(ctx, args):
    """Fork a published article into a new draft copy."""
    return _fork.fork(ctx, article_ref=args.article_id)


@with_context
def _cmd_merge_propose(ctx, args):
    """Propose merging a fork back into the original article."""
    return _fork.merge_propose(ctx, fork_ref=args.fork_id, target_ref=args.target)


@with_context
def _cmd_merge_accept(ctx, args):
    """Accept a merge proposal. May report conflicts."""
    return _fork.merge_accept(ctx, proposal_ref=args.proposal_id, target_ref=args.target)


@with_context
def _cmd_merge_withdraw(ctx, args):
    """Withdraw a merge proposal."""
    return _fork.merge_withdraw(ctx, proposal_ref=args.proposal_id)
