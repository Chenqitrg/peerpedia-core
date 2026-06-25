# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Social commands — fork, merge, bookmark."""

from __future__ import annotations

import os

from peerpedia_core.cli.helpers import (
    _with_db, _resolve_user, _get_session_user, _get_session_key,
    _resolve_and_display_article, _ok, _die, _json_out,
)
from peerpedia_core.cli.display import console
from peerpedia_core.cli.bundle_utils import _sync_server, _try_sync
from peerpedia_core.commands import (
    fork_article, create_merge_proposal, accept_merge, withdraw_merge_proposal,
    add_bookmark, add_share, get_feed_shares, get_shares_for_user,
    list_aliases, remove_alias, remove_bookmark, remove_share, set_alias,
    follow_user, unfollow_user,
    get_follower_views, get_followers, get_following, get_following_views,
    get_article, merge_article_meta,
)
from peerpedia_core.transport import fetch_article_meta, push_share, push_share_remove
from peerpedia_core.social import discover_articles, discover_followers, discover_following, discover_shares
from peerpedia_core.transport import push_follow, push_unfollow

def _pull_social(db, user_id: str) -> None:
    """Pull social graph + articles for *user_id* from the peer server.  Best-effort.

    Discovers who *user_id* follows, who follows *user_id*, and their
    articles — merging everything into the local DB.  Reads
    ``PEERPEDIA_SERVER`` from env.
    """
    server = os.environ.get("PEERPEDIA_SERVER")
    if not server:
        console.print("[warning]⚠ No PEERPEDIA_SERVER set — social pull skipped. Set with: export PEERPEDIA_SERVER=https://your-peer.example.com[/]")
        return
    try:
        discover_following(db, server, user_id)
        discover_followers(db, server, user_id)
        discover_articles(db, server, user_id)
        discover_shares(db, server, user_id)
    except Exception as e:
        console.print(f"[warning]⚠ Social pull from {server} failed: {e}[/]")


def _push_to_peer(label: str, push_fn) -> None:
    """Best-effort push to PEERPEDIA_SERVER.  Warns on failure.

    *push_fn* is called with ``(server)`` once the server URL and session
    key are resolved.  If PEERPEDIA_SERVER is not set, prints a warning
    and returns without calling *push_fn*.
    """
    server = os.environ.get("PEERPEDIA_SERVER")
    if not server:
        console.print(
            f"[warning]⚠ No PEERPEDIA_SERVER set — {label} push skipped. "
            "Set with: export PEERPEDIA_SERVER=https://your-peer.example.com[/]"
        )
        return
    try:
        push_fn(server)
    except Exception as e:
        console.print(f"[warning]⚠ {label} push to {server} failed: {e}[/]")


def _push_social(action: str, **kwargs) -> None:
    """Push a social action to the peer server.  Best-effort — warns on failure.

    *action* is one of ``"follow"``, ``"unfollow"``.
    """
    key = _get_session_key()
    if action == "follow":
        _push_to_peer(
            f"Social sync ({action})",
            lambda s: push_follow(
                s, kwargs["follower_id"], kwargs["followed_id"],
                private_key_bytes=key,
            ),
        )
    elif action == "unfollow":
        _push_to_peer(
            f"Social sync ({action})",
            lambda s: push_unfollow(
                s, kwargs["follower_id"], kwargs["followed_id"],
                private_key_bytes=key,
            ),
        )


def _push_share(article_id: str, sharer_id: str, recipient_id: str | None = None,
                comment: str | None = None, *, action: str = "add") -> None:
    """Push a share to the peer server.  Best-effort — warns on failure.

    *action*: ``"add"`` (default) or ``"remove"``.
    """
    key = _get_session_key()
    if action == "remove":
        _push_to_peer(
            "Share remove",
            lambda s: push_share_remove(s, sharer_id, article_id,
                                        private_key_bytes=key),
        )
    else:
        _push_to_peer(
            "Share push",
            lambda s: push_share(s, sharer_id, article_id,
                                 recipient_id=recipient_id, comment=comment,
                                 private_key_bytes=key),
        )


@_with_db
def _cmd_fork(db, args):
    """Fork a published article into a new draft copy.

    args: article_id [positional], --json
    """
    result = fork_article(db, args.article_id, _get_session_user())
    db.commit()
    _try_sync(db)
    if args.json:
        _json_out(result)
    else:
        _ok(f"Forked → [accent]{result['id'][:8]}[/]")


@_with_db
def _cmd_merge_propose(db, args):
    """Propose merging a fork back into the original article.

    args: fork_id [positional], --target, --json
    """
    mp = create_merge_proposal(db, args.fork_id, args.target, _get_session_user())
    db.commit()
    if args.json:
        _json_out({"id": mp.id, "status": mp.status})
    else:
        _ok(f"Merge proposed [accent]{mp.id[:8]}[/] → target {args.target[:8]}")


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
    article_id = args.article_id
    add_bookmark(db, user_id, article_id)
    db.commit()

    # Pull article metadata + source + compile it so it's readable offline.
    existing = get_article(db, article_id)
    if existing is None:
        server = os.environ.get("PEERPEDIA_SERVER")
        if server:
            try:
                meta = fetch_article_meta(server, article_id)
                if meta:
                    merge_article_meta(db, [meta])
                    db.commit()
                    console.print(
                        f"[dim]Pulled metadata for [accent]{article_id[:8]}[/] "
                        f"from {server}[/]"
                    )
            except Exception as e:
                console.print(
                    f"[warning]⚠ Could not pull metadata for {article_id[:8]}: {e}[/]"
                )

    if args.json:
        _json_out({"bookmarked": True})
    else:
        _ok(f"Bookmarked [accent]{article_id[:8]}[/]")


@_with_db
def _cmd_bookmark_remove(db, args):
    """Remove a bookmark. Idempotent.

    args: article_id [positional], --json
    """
    remove_bookmark(db, _get_session_user(), args.article_id)
    db.commit()
    _try_sync(db)
    if args.json:
        _json_out({"removed": True})
    else:
        _ok(f"Removed bookmark for [accent]{args.article_id[:8]}[/]")


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
        _ok(f"Now following [accent]{followed_id[:8]}[/]")


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
        _ok(f"Stopped following [accent]{followed_id[:8]}[/]")


@_with_db
def _cmd_following(db, args):
    """List users that *user_id* follows. Default: pull from peer.

    args: --user, --server, --local, --json
    """
    if not args.local:
        server = _sync_server(args)
        discover_following(db, server, args.user)
        db.commit()
    if args.json:
        _json_out(get_following_views(db, args.user))
    else:
        users = get_following(db, args.user)
        _ok(f"Following {len(users)} user(s)")


@_with_db
def _cmd_followers(db, args):
    """List followers of *user_id*. Default: pull from peer.

    args: --user, --server, --local, --json
    """
    if not args.local:
        server = _sync_server(args)
        discover_followers(db, server, args.user)
        db.commit()
    if args.json:
        _json_out(get_follower_views(db, args.user))
    else:
        users = get_followers(db, args.user)
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
    recipient_id = None
    if getattr(args, "to", None):
        recipient_id = _resolve_user(db, args.to)
    result = add_share(db, user_id, args.article_id,
                       recipient_id=recipient_id, comment=args.comment)
    db.commit()
    _push_share(args.article_id, user_id, recipient_id, args.comment)
    if args.json:
        _json_out(result)
    else:
        to_str = f" → {args.to}" if getattr(args, "to", None) else ""
        _ok(f"Shared [accent]{args.article_id[:8]}[/]{to_str}")


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
    remove_share(db, user_id, args.article_id)
    db.commit()
    _push_share(args.article_id, user_id, action="remove")
    _ok(f"Unshared [accent]{args.article_id[:8]}[/]")


