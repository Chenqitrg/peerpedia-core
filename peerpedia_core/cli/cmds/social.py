# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Social commands — follow, unfollow, following, followers, alias, bookmark, share, school."""

from __future__ import annotations

from peerpedia_core.app.result import AppResult
from peerpedia_core.cli.bundle_utils import _resolve_server_url
from peerpedia_core.cli.decorators import with_context
from peerpedia_core.cli.display import display_user
from peerpedia_core.cli.info import console
import peerpedia_core.app.commands.social as _social


# ── Follow / Unfollow ─────────────────────────────────────────────────────

@with_context
def _cmd_follow(ctx, args):
    """Follow a user."""
    return _social.follow(ctx, target_ref=args.user_identifier)


@with_context
def _cmd_unfollow(ctx, args):
    """Unfollow a user. Idempotent."""
    return _social.unfollow(ctx, target_ref=args.user_identifier)


def _render_user_panels(items: list[dict]) -> None:
    """Render a list of user dicts as individual Rich panels."""
    for u in items:
        display_user(
            u.get("name", "?"),
            u.get("id") or u.get("user_id", "?"),
            affiliation=u.get("affiliation", ""),
            expertise=u.get("expertise"),
            reputation=u.get("reputation"),
            follower_count=u.get("follower_count"),
            public_key=u.get("public_key"),
            created_at=u.get("created_at"),
        )


@with_context
def _cmd_following(ctx, args):
    """List users that *user_id* follows."""
    result = _social.list_following(ctx, user_ref=args.user)
    items = result.data.get("items", [])
    if items:
        _render_user_panels(items)
    return AppResult(code=result.code, data=None, params=result.params, notices=result.notices)


@with_context
def _cmd_followers(ctx, args):
    """List followers of *user_id*."""
    result = _social.list_followers(ctx, user_ref=args.user)
    items = result.data.get("items", [])
    if items:
        _render_user_panels(items)
    return AppResult(code=result.code, data=None, params=result.params, notices=result.notices)


# ── Alias ─────────────────────────────────────────────────────────────────

@with_context
def _cmd_alias_set(ctx, args):
    """Set an alias for a followed user."""
    return _social.alias(ctx, user_ref=args.user_identifier, alias=args.alias)


@with_context
def _cmd_alias_remove(ctx, args):
    """Remove an alias for a user."""
    return _social.unalias(ctx, user_ref=args.user_identifier)


@with_context
def _cmd_alias_list(ctx, args):
    """List all aliases for the current user."""
    return _social.alias_list(ctx)


# ── Bookmark ──────────────────────────────────────────────────────────────

@with_context
def _cmd_bookmark_add(ctx, args):
    """Bookmark an article."""
    return _social.bookmark(ctx, article_ref=args.article_id)


@with_context
def _cmd_bookmark_remove(ctx, args):
    """Remove a bookmark."""
    return _social.unbookmark(ctx, article_ref=args.article_id)


# ── Share ─────────────────────────────────────────────────────────────────

@with_context
def _cmd_share_add(ctx, args):
    """Share an article — public recommendation visible to followers."""
    return _social.share(ctx, article_ref=args.article_id,
        to_ref=getattr(args, "to", None),
        comment=getattr(args, "comment", None))


@with_context
def _cmd_share_list(ctx, args):
    """List shares from followed users."""
    return _social.share_list(ctx, mine=getattr(args, "mine", False))


@with_context
def _cmd_share_remove(ctx, args):
    """Remove a share (un-share an article)."""
    return _social.unshare(ctx, article_ref=args.article_id)


# ── School ────────────────────────────────────────────────────────────────

@with_context
def _cmd_school(ctx, args):
    """List top users ranked by follower count — the user directory."""
    limit = getattr(args, "limit", 20) or 20
    local = getattr(args, "local", False)
    server = _resolve_server_url(args) if not local else ""
    result = _social.school(ctx, limit=limit, local=local, server=server)
    items = result.data.get("items", [])
    if not items:
        console.print("[muted]No users found.[/]")
        return AppResult(code="", data=None, params=result.params, notices=result.notices)
    # items are ORM objects (local) or dicts (remote) — normalize to dicts
    if hasattr(items[0], "name"):
        users = [{"name": u.name, "id": u.id,
                  "follower_count": getattr(u, "follower_count", 0)} for u in items]
    else:
        users = items
    _render_user_panels(users)
    return AppResult(code="", data=None, params=result.params, notices=result.notices)
