# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Review commands — submit, list, reply, invite, accept, decline, rate."""

from __future__ import annotations

from peerpedia_core.app.context import AppContext
from peerpedia_core.app.parsers import parse_scores
from peerpedia_core.app.refs import require_article, require_user, require_user_by_ref
from peerpedia_core.app.result import AppNotice, AppResult
from peerpedia_core.core import (
    accept_invitation, decline_invitation,
    get_reviews_for_article, get_user, list_users_by_ids,
    invite_reviewer as _invite_reviewer, rate_review_helpfulness,
    submit_reply, submit_review,
)


def submit(ctx: AppContext, *, article_ref: str, scores_str: str, comment: str) -> AppResult:
    """Submit a review with 5-dim scores + comment."""
    # ── Resolve ──
    reviewer_id = require_user(ctx)
    article = require_article(ctx.db, article_ref)
    scores = parse_scores(scores_str)
    # ── Execute ──
    user = get_user(ctx.db, reviewer_id)
    result = submit_review(
        ctx.db, article_id=article.id, reviewer_id=reviewer_id,
        scores=scores, comment=comment,
        signing_key_bytes=ctx.signing_key_bytes,
        pubkey_hex=user.public_key if user else None,
    )
    ctx.db.commit()
    return AppResult("REVIEW_SUBMITTED", data=result)


def list_reviews(ctx: AppContext, *, article_ref: str) -> AppResult:
    """List all reviews for an article."""
    # ── Resolve ──
    article = require_article(ctx.db, article_ref)
    # ── Execute ──
    reviews = get_reviews_for_article(ctx.db, article.id)
    reviewer_ids = {r.reviewer_id for r in reviews if hasattr(r, 'reviewer_id')}
    users_by_id = {u.id: u for u in list_users_by_ids(ctx.db, reviewer_ids)} if reviewer_ids else {}
    items = []
    for r in reviews:
        rid = r.reviewer_id if hasattr(r, 'reviewer_id') else ""
        user = users_by_id.get(rid)
        items.append({
            "id": r.id,
            "reviewer_id": rid,
            "reviewer_name": user.name if user else rid,
            "scores": getattr(r, 'scores', {}),
            "status": getattr(r, 'status', ''),
            "created_at": str(r.created_at) if r.created_at else None,
        })
    return AppResult("", data={"reviews": items, "article_id": article.id})


def reply(ctx: AppContext, *, article_ref: str, to_ref: str, content: str) -> AppResult:
    """Reply to a reviewer on an article."""
    # ── Resolve ──
    user_id = require_user(ctx)
    article = require_article(ctx.db, article_ref)
    reviewer_ref = require_user_by_ref(ctx.db, to_ref).id
    # ── Execute ──
    user = get_user(ctx.db, user_id)
    result = submit_reply(
        ctx.db, article_id=article.id, user_id=user_id,
        reviewer_ref=reviewer_ref, content=content,
        signing_key_bytes=ctx.signing_key_bytes,
        pubkey_hex=user.public_key if user else None,
    )
    ctx.db.commit()
    return AppResult("OK", data=result, params={"msg": "Reply posted to review thread"})


def invite_reviewer(ctx: AppContext, *, article_ref: str, user_ref: str) -> AppResult:
    """Invite a user to review an article."""
    # ── Resolve ──
    user_id = require_user(ctx)
    article = require_article(ctx.db, article_ref)
    target = require_user_by_ref(ctx.db, user_ref)
    # ── Execute ──
    result = _invite_reviewer(ctx.db, article.id, user_id, target.id)
    ctx.db.commit()
    return AppResult("REVIEW_INVITED", data=result,
        params={"name": target.name, "id": article.id})


def accept(ctx: AppContext, *, article_ref: str) -> AppResult:
    """Accept a pending review invitation."""
    # ── Resolve ──
    user_id = require_user(ctx)
    article = require_article(ctx.db, article_ref)
    # ── Execute ──
    result = accept_invitation(ctx.db, article.id, user_id)
    ctx.db.commit()
    return AppResult("INVITATION_ACCEPTED", data=result)


def decline(ctx: AppContext, *, article_ref: str) -> AppResult:
    """Decline a pending review invitation."""
    # ── Resolve ──
    user_id = require_user(ctx)
    article = require_article(ctx.db, article_ref)
    # ── Execute ──
    result = decline_invitation(ctx.db, article.id, user_id)
    ctx.db.commit()
    return AppResult("INVITATION_DECLINED", data=result)


def rate(ctx: AppContext, *, article_ref: str, reviewer_ref: str, helpfulness: int) -> AppResult:
    """Rate a review's helpfulness."""
    # ── Resolve ──
    user_id = require_user(ctx)
    article = require_article(ctx.db, article_ref)
    reviewer = require_user_by_ref(ctx.db, reviewer_ref)
    # ── Execute ──
    result = rate_review_helpfulness(
        ctx.db, article.id, reviewer.id, user_id, helpfulness,
    )
    ctx.db.commit()
    return AppResult("HELPFULNESS_RATED", data=result,
        params={"score": str(helpfulness)})
