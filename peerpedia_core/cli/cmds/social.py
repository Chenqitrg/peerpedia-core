# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Social commands — follow, unfollow, following, followers, alias, bookmark, share, school."""

from __future__ import annotations

from peerpedia_core.app.commandspec import spec_for_cmd_id
from peerpedia_core.app.result import AppResult
from peerpedia_core.cli.bundle_utils import _resolve_server_url
from peerpedia_core.cli.decorators import with_context
from peerpedia_core.cli.info import console
from peerpedia_core.presentation.rich.components import no_users_msg, user_panels


# ── Follow / Unfollow ─────────────────────────────────────────────────────

@with_context
def _cmd_follow(ctx, args):
    """Follow a user."""
    return spec_for_cmd_id("follow").handler(ctx, {"user_identifier": args.user_identifier})


@with_context
def _cmd_unfollow(ctx, args):
    """Unfollow a user. Idempotent."""
    return spec_for_cmd_id("unfollow").handler(ctx, {"user_identifier": args.user_identifier})


@with_context
def _cmd_following(ctx, args):
    """List users that *user_id* follows."""
    result = spec_for_cmd_id("following").handler(ctx, {"user": args.user})
    items = result.data.get("items", [])
    if items:
        user_panels(console, items)
    return AppResult(code=result.code, data=None, params=result.params, notices=result.notices)


@with_context
def _cmd_followers(ctx, args):
    """List followers of *user_id*."""
    result = spec_for_cmd_id("followers").handler(ctx, {"user": args.user})
    items = result.data.get("items", [])
    if items:
        user_panels(console, items)
    return AppResult(code=result.code, data=None, params=result.params, notices=result.notices)


# ── Alias ─────────────────────────────────────────────────────────────────

@with_context
def _cmd_alias_set(ctx, args):
    """Set an alias for a followed user."""
    return spec_for_cmd_id("alias.set").handler(ctx, {
        "user_identifier": args.user_identifier, "alias": args.alias,
    })


@with_context
def _cmd_alias_remove(ctx, args):
    """Remove an alias for a user."""
    return spec_for_cmd_id("alias.remove").handler(ctx, {"user_identifier": args.user_identifier})


@with_context
def _cmd_alias_list(ctx, args):
    """List all aliases for the current user."""
    return spec_for_cmd_id("alias.list").handler(ctx, {})


# ── Bookmark ──────────────────────────────────────────────────────────────

@with_context
def _cmd_bookmark_add(ctx, args):
    """Bookmark an article."""
    return spec_for_cmd_id("bookmark.add").handler(ctx, {"article_id": args.article_id})


@with_context
def _cmd_bookmark_remove(ctx, args):
    """Remove a bookmark."""
    return spec_for_cmd_id("bookmark.remove").handler(ctx, {"article_id": args.article_id})


# ── Share ─────────────────────────────────────────────────────────────────

@with_context
def _cmd_share_add(ctx, args):
    """Share an article — public recommendation visible to followers."""
    return spec_for_cmd_id("share.add").handler(ctx, {
        "article_id": args.article_id,
        "to": getattr(args, "to", None),
        "comment": getattr(args, "comment", None),
    })


@with_context
def _cmd_share_list(ctx, args):
    """List shares from followed users."""
    return spec_for_cmd_id("share.list").handler(ctx, {"mine": getattr(args, "mine", False)})


@with_context
def _cmd_share_remove(ctx, args):
    """Remove a share (un-share an article)."""
    return spec_for_cmd_id("share.remove").handler(ctx, {"article_id": args.article_id})


# ── School ────────────────────────────────────────────────────────────────

@with_context
def _cmd_school(ctx, args):
    """List top users ranked by follower count — the user directory."""
    limit = getattr(args, "limit", 20) or 20
    local = getattr(args, "local", False)
    server = _resolve_server_url(args) if not local else ""
    result = spec_for_cmd_id("school").handler(ctx, {
        "limit": limit, "local": local, "server": server,
    })
    items = result.data.get("items", [])
    if not items:
        console.print(no_users_msg())
        return AppResult(code="", data=None, params=result.params, notices=result.notices)
    if hasattr(items[0], "name"):
        users = [{"name": u.name, "id": u.id,
                  "follower_count": getattr(u, "follower_count", 0)} for u in items]
    else:
        users = items
    user_panels(console, items)
    return AppResult(code="", data=None, params=result.params, notices=result.notices)
