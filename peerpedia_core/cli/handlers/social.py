# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Social commands — fork, merge, bookmark."""

from __future__ import annotations

import os

from peerpedia_core.cli.helpers import (
    _with_db, _resolve_article_id, _resolve_user, _get_session_user,
    _get_session_key, _get_session_pubkey,
    _resolve_and_display_article, _ok, _die, _json_out,
)
from peerpedia_core.cli.display import console
from peerpedia_core.cli.bundle_utils import _resolve_server_url, _try_sync
from peerpedia_core.commands import (
    fork_article, create_merge_proposal, accept_merge, withdraw_merge_proposal,
    add_bookmark, add_share, get_feed_shares, get_shares_for_user,
    list_aliases, remove_alias, remove_bookmark, remove_share, set_alias,
    follow_user, unfollow_user,
    get_follower_views, get_followers, get_following, get_following_views,
    create_user_stub, get_top_users_by_followers, get_user,
)
from peerpedia_core.social import discover_articles, discover_followers, discover_following, discover_notifications, discover_shares
from peerpedia_core.transport import (
    fetch_school,
    push_follow, push_share, push_share_remove, push_unfollow,
)

# Track whether the "no server configured" warning has been shown in this
# process — avoids repetitive warnings when a single command triggers
# multiple sync attempts (e.g. _try_sync + _push_social + _pull_social).
_server_warned: bool = False


def _get_server_or_warn(label: str = "Social") -> str | None:
    """Read PEERPEDIA_SERVER from env, warn and return None if not set.

    Replaces the duplicated ``os.environ.get("PEERPEDIA_SERVER")`` + warn
    pattern in ``_pull_social`` and ``_push_to_peer``.

    Only warns once per process — subsequent calls for the same missing
    server are silent.
    """
    global _server_warned
    server = os.environ.get("PEERPEDIA_SERVER")
    if not server:
        if not _server_warned:
            _server_warned = True
            console.print(
                "[warning]⚠ No PEERPEDIA_SERVER set — network sync skipped. "
                "Set with: export PEERPEDIA_SERVER=https://your-peer.example.com[/]"
            )
        return None
    return server


def _pull_social(db, user_id: str) -> None:
    """Pull social graph + articles for *user_id* from the peer server.  Best-effort."""
    server = _get_server_or_warn("social pull")
    if not server:
        return
    key = _get_session_key()
    pubkey = _get_session_pubkey()
    try:
        discover_following(db, server, user_id, signing_key_bytes=key, pubkey_hex=pubkey)
        discover_followers(db, server, user_id, signing_key_bytes=key, pubkey_hex=pubkey)
        discover_articles(db, server, user_id, signing_key_bytes=key, pubkey_hex=pubkey)
        discover_shares(db, server, user_id, signing_key_bytes=key, pubkey_hex=pubkey)
        discover_notifications(db, server, user_id, signing_key_bytes=key, pubkey_hex=pubkey)
    except Exception as e:
        console.print(f"[warning]⚠ Social pull from {server} failed: {e}[/]")


def _push_to_peer(label: str, push_fn) -> None:
    """Best-effort push to PEERPEDIA_SERVER.  Warns on failure."""
    server = _get_server_or_warn(label)
    if not server:
        return
    try:
        push_fn(server)
    except Exception as e:
        console.print(f"[warning]⚠ {label} push to {server} failed: {e}[/]")


def _push_social(action: str, **kwargs) -> None:
    """Push a social action to the peer server.  Best-effort — warns on failure.

    *action* is one of ``"follow"``, ``"unfollow"``.

    Server-side notifications are created by ``commands/users.py:follow_user``
    which the server route calls.  The followed user pulls notifications via
    ``_pull_social`` → ``discover_notifications``.
    """
    key = _get_session_key()
    pubkey = _get_session_pubkey()
    if action == "follow":
        _push_to_peer(
            f"Social sync ({action})",
            lambda s: push_follow(
                s, kwargs["follower_id"], kwargs["followed_id"],
                private_key_bytes=key, pubkey_hex=pubkey,
            ),
        )
    elif action == "unfollow":
        _push_to_peer(
            f"Social sync ({action})",
            lambda s: push_unfollow(
                s, kwargs["follower_id"], kwargs["followed_id"],
                private_key_bytes=key, pubkey_hex=pubkey,
            ),
        )


def _push_share(article_id: str, sharer_id: str, recipient_id: str | None = None,
                comment: str | None = None, *, action: str = "add") -> None:
    """Push a share to the peer server.  Best-effort — warns on failure.

    *action*: ``"add"`` (default) or ``"remove"``.
    """
    key = _get_session_key()
    pubkey = _get_session_pubkey()
    if action == "remove":
        _push_to_peer(
            "Share remove",
            lambda s: push_share_remove(s, sharer_id, article_id,
                                        private_key_bytes=key,
                                        pubkey_hex=pubkey),
        )
    else:
        _push_to_peer(
            "Share push",
            lambda s: push_share(s, sharer_id, article_id,
                                 recipient_id=recipient_id, comment=comment,
                                 private_key_bytes=key,
                                 pubkey_hex=pubkey),
        )


@_with_db
def _cmd_fork(db, args):
    """Fork a published article into a new draft copy.

    args: article_id [positional], --json
    """
    article = _resolve_article_id(db, args.article_id)
    result = fork_article(db, article.id, _get_session_user())
    db.commit()
    _try_sync(db)
    if args.json:
        _json_out(result)
    else:
        _ok(f"Forked → [accent]{result['id'][:8]}[/] ({result['title']})")


@_with_db
def _cmd_merge_propose(db, args):
    """Propose merging a fork back into the original article.

    args: fork_id [positional], --target, --json
    """
    target = _resolve_article_id(db, args.target)
    mp = create_merge_proposal(db, args.fork_id, target.id, _get_session_user())
    db.commit()
    if args.json:
        _json_out({"id": mp.id, "status": mp.status})
    else:
        _ok(f"Merge proposed [accent]{mp.id[:8]}[/] → target {target.id[:8]}")


@_with_db
def _cmd_merge_accept(db, args):
    """Accept a merge proposal. May report conflicts.

    args: proposal_id [positional], --target, --json
    """
    result = accept_merge(db, args.target, args.proposal_id, _get_session_user())
    db.commit()
    _try_sync(db)
    if args.json:
        _json_out(result)
    elif result.get("status") == "conflict":
        console.print(f"[warning]⚠ {result['message']}[/]")
    else:
        _ok(f"Merge accepted — [accent]{result['id'][:8]}[/]")


@_with_db
def _cmd_merge_withdraw(db, args):
    """Withdraw a merge proposal (proposer only).

    args: proposal_id [positional], --json
    """
    result = withdraw_merge_proposal(db, args.proposal_id, _get_session_user())
    db.commit()
    if args.json:
        _json_out(result)
    else:
        _ok(f"Proposal [accent]{args.proposal_id[:8]}[/] withdrawn")


@_with_db
def _cmd_bookmark_add(db, args):
    """Bookmark an article for the given user.

    args: article_id [positional], --json
    """
    user_id = _get_session_user()
    article = _resolve_article_id(db, args.article_id)
    article_id = article.id
    add_bookmark(db, user_id, article_id)
    db.commit()

    if args.json:
        _json_out({"bookmarked": True})
    else:
        _ok(f"Bookmarked [accent]{args.article_id}[/]")


@_with_db
def _cmd_bookmark_remove(db, args):
    """Remove a bookmark. Idempotent.

    args: article_id [positional], --json
    """
    article = _resolve_article_id(db, args.article_id)
    remove_bookmark(db, _get_session_user(), article.id)
    db.commit()
    _try_sync(db)
    if args.json:
        _json_out({"removed": True})
    else:
        _ok(f"Removed bookmark for [accent]{article.id[:8]}[/]")


@_with_db
def _cmd_follow_user(db, args):
    """Follow a user.

    args: user_identifier [positional], --json
    """
    follower_id = _get_session_user()
    followed_id = _resolve_user(db, args.user_identifier)
    follow_user(db, follower_id, followed_id)
    db.commit()
    _try_sync(db)
    _push_social("follow", follower_id=follower_id, followed_id=followed_id)
    _pull_social(db, followed_id)
    if args.json:
        _json_out({"following": True})
    else:
        followed_user = get_user(db, followed_id)
        followed_name = followed_user.name if followed_user else args.user_identifier
        _ok(f"Now following [accent]{followed_name}[/]")


@_with_db
def _cmd_unfollow_user(db, args):
    """Unfollow a user. Idempotent.

    args: user_identifier [positional], --json
    """
    follower_id = _get_session_user()
    followed_id = _resolve_user(db, args.user_identifier)
    unfollow_user(db, follower_id, followed_id)
    db.commit()
    _try_sync(db)
    _push_social("unfollow", follower_id=follower_id, followed_id=followed_id)
    if args.json:
        _json_out({"following": False})
    else:
        followed_user = get_user(db, followed_id)
        followed_name = followed_user.name if followed_user else args.user_identifier
        _ok(f"Stopped following [accent]{followed_name}[/]")


@_with_db
def _cmd_following(db, args):
    """List users that *user_id* follows. Default: pull from peer.

    args: --user, --server, --local, --json
    """
    user_id = _resolve_user(db, args.user)
    if not args.local:
        server = _resolve_server_url(args)
        discover_following(db, server, user_id)
        db.commit()
    if args.json:
        _json_out(get_following_views(db, user_id))
    else:
        users = get_following(db, user_id)
        _ok(f"Following {len(users)} user(s)")


@_with_db
def _cmd_followers(db, args):
    """List followers of *user_id*. Default: pull from peer.

    args: --user, --server, --local, --json
    """
    user_id = _resolve_user(db, args.user)
    if not args.local:
        server = _resolve_server_url(args)
        discover_followers(db, server, user_id)
        db.commit()
    if args.json:
        _json_out(get_follower_views(db, user_id))
    else:
        users = get_followers(db, user_id)
        _ok(f"Followers {len(users)} user(s)")


# ── Alias ────────────────────────────────────────────────────────────────────


@_with_db
def _cmd_alias_set(db, args):
    """Set or update an alias for a user you follow.

    args: user_identifier [positional], alias [positional]
    """
    owner_id = _get_session_user()
    target_id = _resolve_user(db, args.user_identifier)
    set_alias(db, owner_id, target_id, args.alias)
    db.commit()
    _ok(f"Alias [accent]{args.alias}[/] → {target_id[:8]}")


@_with_db
def _cmd_alias_remove(db, args):
    """Remove an alias.

    args: user_identifier [positional]
    """
    owner_id = _get_session_user()
    target_id = _resolve_user(db, args.user_identifier)
    remove_alias(db, owner_id, target_id)
    db.commit()
    _ok(f"Alias removed for {target_id[:8]}")


@_with_db
def _cmd_alias_list(db, args):
    """List all aliases you have set.

    args: --json
    """
    aliases = list_aliases(db, _get_session_user())
    if args.json:
        _json_out([{"target": a.target_id, "alias": a.alias} for a in aliases])
    elif not aliases:
        console.print("[muted]No aliases set.[/]")
    else:
        for a in aliases:
            console.print(f"  [accent]{a.alias}[/] → {a.target_id[:8]}")


# ── Share ────────────────────────────────────────────────────────────────────


@_with_db
def _cmd_share_add(db, args):
    """Share an article — public recommendation visible to followers.

    args: article_id [positional], --to, --comment, --json
    """
    user_id = _get_session_user()
    article = _resolve_article_id(db, args.article_id)
    recipient_id = None
    if getattr(args, "to", None):
        recipient_id = _resolve_user(db, args.to)
    result = add_share(db, user_id, article.id,
                       recipient_id=recipient_id, comment=args.comment)
    db.commit()
    _push_share(args.article_id, user_id, recipient_id, args.comment)
    if args.json:
        _json_out(result)
    else:
        to_str = f" → {args.to}" if getattr(args, "to", None) else ""
        _ok(f"Shared [accent]{args.article_id}[/]{to_str}")


@_with_db
def _cmd_share_list(db, args):
    """List shares from followed users.

    args: --mine, --json
    """
    if getattr(args, "mine", False):
        shares = get_shares_for_user(db, _get_session_user())
    else:
        shares = get_feed_shares(db, _get_session_user())
    if args.json:
        _json_out(shares)
    elif not shares:
        console.print("[muted]No shares in feed.[/]")
    else:
        from rich.table import Table

        is_mine = getattr(args, "mine", False)
        if is_mine:
            table = Table(title="My Shares")
            table.add_column("Article ID", style="dim")
            table.add_column("Comment")
            for s in shares:
                table.add_row(s["article_id"][:8], s.get("comment") or "")
        else:
            table = Table(title="Shares")
            table.add_column("Article", style="dim")
            table.add_column("Title")
            for s in shares:
                table.add_row(s["id"][:8], s["title"])
        console.print(table)


@_with_db
def _cmd_share_remove(db, args):
    """Remove a share (un-share an article).

    args: article_id [positional]
    """

    user_id = _get_session_user()
    article = _resolve_article_id(db, args.article_id)
    remove_share(db, user_id, article.id)
    db.commit()
    _push_share(args.article_id, user_id, action="remove")
    _ok(f"Unshared [accent]{args.article_id[:8]}[/]")


# ── School ────────────────────────────────────────────────────────────────────


@_with_db
def _cmd_school(db, args):
    """List top users ranked by follower count — the user directory.

    args: --server, --local, --limit, --json

    Default: fetches from the peer server (network is the primary source).
    With --local: queries the local DB only.
    """
    limit = getattr(args, "limit", 20) or 20

    users: list[dict] = []
    if not getattr(args, "local", False):
        # Default: fetch from peer server.
        server = _resolve_server_url(args)
        try:
            users = fetch_school(server, limit=limit)
            # Merge fetched users into local DB so they appear in future
            # local queries (school --local, follow, etc.).
            for u in users:
                existing = get_user(db, u["id"])
                if existing is None:
                    create_user_stub(
                        db, user_id=u["id"], name=u["name"],
                        public_key="", salt="",
                    )
                    db.commit()
        except Exception as e:
            console.print(f"[dim]Remote school unavailable ({e}) — showing local.[/]")
            users = []

    if not users:
        users = get_top_users_by_followers(db, limit=limit)
        db.commit()

    if args.json:
        _json_out(users)
        return

    if not users:
        console.print("[muted]No users with followers yet. "
                      "Follow some people to build the school.[/]")
        return

    from rich.table import Table
    table = Table(title="School — Top Users by Followers")
    table.add_column("Rank", style="dim", justify="right")
    table.add_column("Name")
    table.add_column("Followers", justify="right")
    for i, u in enumerate(users, 1):
        table.add_row(str(i), u["name"], str(u["follower_count"]))
    console.print(table)


