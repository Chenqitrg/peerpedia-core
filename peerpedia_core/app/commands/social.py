# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Social commands — follow, unfollow, following, followers, bookmark, share, alias, school."""

from __future__ import annotations

from peerpedia_core.app.context import AppContext
from peerpedia_core.app.refs import require_article, require_user, require_user_by_ref
from peerpedia_core.app.result import AppNotice, AppResult
from peerpedia_core.core import (
    add_bookmark, add_share,
    follow_user, get_follower_views, get_following_views,
    get_shares_for_user, get_feed_shares,
    get_top_users_by_followers, get_user, list_users_by_ids,
    remove_bookmark, remove_share,
    set_alias, list_aliases, remove_alias,
    unfollow_user,
)
from peerpedia_core.types import short_id


# ── Follow / Unfollow ────────────────────────────────────────────────────


def follow(ctx: AppContext, *, target_ref: str) -> AppResult:
    """Follow a user."""
    # ── Resolve ──
    follower_id = require_user(ctx)
    target = require_user_by_ref(ctx.db, target_ref)
    # ── Execute ──
    follow_user(ctx.db, follower_id, target.id)
    ctx.db.commit()
    return AppResult("FOLLOWING", params={"name": target.name})


def unfollow(ctx: AppContext, *, target_ref: str) -> AppResult:
    """Unfollow a user.  Idempotent."""
    # ── Resolve ──
    follower_id = require_user(ctx)
    target = require_user_by_ref(ctx.db, target_ref)
    # ── Execute ──
    unfollow_user(ctx.db, follower_id, target.id)
    ctx.db.commit()
    return AppResult("UNFOLLOWED", params={"name": target.name})


def list_following(ctx: AppContext, *, user_ref: str) -> AppResult:
    """List users that *user_ref* follows."""
    # ── Resolve ──
    user = require_user_by_ref(ctx.db, user_ref)
    # ── Execute ──
    views = get_following_views(ctx.db, user.id)
    return AppResult("FOLLOWING_COUNT", data={"items": views},
        params={"count": len(views)})


def list_followers(ctx: AppContext, *, user_ref: str) -> AppResult:
    """List followers of *user_ref*."""
    # ── Resolve ──
    user = require_user_by_ref(ctx.db, user_ref)
    # ── Execute ──
    views = get_follower_views(ctx.db, user.id)
    return AppResult("FOLLOWERS_COUNT", data={"items": views},
        params={"count": len(views)})


# ── Bookmark ─────────────────────────────────────────────────────────────


def bookmark_add(ctx: AppContext, *, article_ref: str) -> AppResult:
    """Bookmark an article."""
    # ── Resolve ──
    user_id = require_user(ctx)
    article = require_article(ctx.db, article_ref)
    # ── Execute ──
    add_bookmark(ctx.db, user_id, article.id)
    ctx.db.commit()
    return AppResult("BOOKMARKED", params={"name": article.title})


def bookmark_remove(ctx: AppContext, *, article_ref: str) -> AppResult:
    """Remove a bookmark."""
    # ── Resolve ──
    user_id = require_user(ctx)
    article = require_article(ctx.db, article_ref)
    # ── Execute ──
    remove_bookmark(ctx.db, user_id, article.id)
    ctx.db.commit()
    return AppResult("BOOKMARK_REMOVED", params={"id_short": short_id(article.id)})


# ── Share ────────────────────────────────────────────────────────────────


def share_add(ctx: AppContext, *, article_ref: str, to_ref: str | None = None,
              comment: str | None = None) -> AppResult:
    """Share an article — public recommendation visible to followers."""
    # ── Resolve ──
    user_id = require_user(ctx)
    article = require_article(ctx.db, article_ref)
    recipient_id = require_user_by_ref(ctx.db, to_ref).id if to_ref else None
    # ── Execute ──
    result = add_share(ctx.db, user_id, article.id,
                       recipient_id=recipient_id, comment=comment)
    ctx.db.commit()
    to_str = f" → {to_ref}" if to_ref else ""
    return AppResult("SHARED", data=result, params={"name": article.title, "to_str": to_str})


def share_list(ctx: AppContext, *, mine: bool = False) -> AppResult:
    """List shares from followed users (or my shares if *mine*)."""
    # ── Resolve ──
    user_id = require_user(ctx)
    # ── Execute ──
    shares = get_shares_for_user(ctx.db, user_id) if mine else get_feed_shares(ctx.db, user_id)
    return AppResult("", data={"items": shares})


def share_remove(ctx: AppContext, *, article_ref: str) -> AppResult:
    """Remove a share (un-share an article)."""
    # ── Resolve ──
    user_id = require_user(ctx)
    article = require_article(ctx.db, article_ref)
    # ── Execute ──
    remove_share(ctx.db, user_id, article.id)
    ctx.db.commit()
    return AppResult("UNSHARED", params={"name": article.title})


# ── Alias ────────────────────────────────────────────────────────────────


def alias_set(ctx: AppContext, *, user_ref: str, alias: str) -> AppResult:
    """Set an alias for a followed user."""
    # ── Resolve ──
    user_id = require_user(ctx)
    target = require_user_by_ref(ctx.db, user_ref)
    # ── Execute ──
    set_alias(ctx.db, user_id, target.id, alias)
    ctx.db.commit()
    return AppResult("ALIAS_SET", params={"alias": alias, "target_id": short_id(target.id)})


def alias_list(ctx: AppContext) -> AppResult:
    """List all aliases for the current user."""
    # ── Resolve ──
    user_id = require_user(ctx)
    # ── Execute ──
    aliases = list_aliases(ctx.db, user_id)
    return AppResult("", data={"items": [{"user_id": a.user_id, "alias": a.alias} for a in aliases]})


def alias_remove(ctx: AppContext, *, user_ref: str) -> AppResult:
    """Remove an alias for a user."""
    # ── Resolve ──
    user_id = require_user(ctx)
    target = require_user_by_ref(ctx.db, user_ref)
    # ── Execute ──
    remove_alias(ctx.db, user_id, target.id)
    ctx.db.commit()
    return AppResult("ALIAS_REMOVED", params={"target_id": short_id(target.id)})


# ── School ───────────────────────────────────────────────────────────────


def school(ctx: AppContext, *, limit: int = 20, local: bool = False,
           server: str = "") -> AppResult:
    """List top users ranked by follower count.

    Uses *server* for remote fetch when *local* is False and *server*
    is provided.  Falls back to local DB on remote failure.
    """
    # ── Local-only path ──
    if local or not server:
        users = get_top_users_by_followers(ctx.db, limit=limit)
        return AppResult("", data={"items": users})
    # ── Remote path ──
    from peerpedia_core.core import create_user_stub, get_user
    try:
        users = ctx.transport.fetch_school(server, limit=limit)
        for u in users:
            existing = get_user(ctx.db, u["id"])
            if existing is None:
                create_user_stub(ctx.db, user_id=u["id"], name=u["name"],
                                 public_key="", salt="")
                ctx.db.commit()
        return AppResult("", data={"items": users})
    except Exception:
        users = get_top_users_by_followers(ctx.db, limit=limit)
        return AppResult("", data={"items": users})
