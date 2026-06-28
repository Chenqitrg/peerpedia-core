# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Fork and merge commands — fork, merge propose/accept/withdraw."""

from __future__ import annotations

from peerpedia_core.app.context import AppContext
from peerpedia_core.app.refs import require_article, require_user
from peerpedia_core.app.result import AppResult
from peerpedia_core.core import (
    accept_merge, create_merge_proposal, fork_article, withdraw_merge_proposal,
)
from peerpedia_core.types import short_id


def fork(ctx: AppContext, *, article_ref: str) -> AppResult:
    """Fork a published article into a new draft copy."""
    # ── Resolve ──
    user_id = require_user(ctx)
    article = require_article(ctx.db, article_ref)
    # ── Execute ──
    result = fork_article(ctx.db, article.id, user_id)
    ctx.db.commit()
    return AppResult("FORKED", data=result,
        params={"id_short": short_id(result["id"]), "title": result["title"]})


def merge_propose(ctx: AppContext, *, fork_ref: str, target_ref: str) -> AppResult:
    """Propose merging a fork back into the original article."""
    # ── Resolve ──
    user_id = require_user(ctx)
    target = require_article(ctx.db, target_ref)
    # ── Execute ──
    mp = create_merge_proposal(ctx.db, fork_ref, target.id, user_id)
    ctx.db.commit()
    return AppResult("MERGE_PROPOSED", data={"id": mp.id, "status": mp.status},
        params={"id_short": short_id(mp.id), "target_id": short_id(target.id)})


def merge_accept(ctx: AppContext, *, proposal_ref: str, target_ref: str) -> AppResult:
    """Accept a merge proposal.  May report conflicts."""
    # ── Resolve ──
    user_id = require_user(ctx)
    # ── Execute ──
    result = accept_merge(ctx.db, target_ref, proposal_ref, user_id)
    ctx.db.commit()
    if result.get("status") == "conflict":
        return AppResult("MERGE_ACCEPTED", data=result,
            params={"id_short": short_id(result["id"])},
            notices=[AppResult.__new__(AppResult)])  # conflict notice
    return AppResult("MERGE_ACCEPTED", data=result,
        params={"id_short": short_id(result["id"])})


def merge_withdraw(ctx: AppContext, *, proposal_ref: str) -> AppResult:
    """Withdraw a merge proposal."""
    # ── Resolve ──
    user_id = require_user(ctx)
    # ── Execute ──
    result = withdraw_merge_proposal(ctx.db, proposal_ref, user_id)
    ctx.db.commit()
    return AppResult("MERGE_WITHDRAWN", data=result,
        params={"id_short": short_id(proposal_ref)})
