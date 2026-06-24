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
    fork_article, create_merge_proposal, accept_merge,
    add_bookmark, remove_bookmark,
    follow_user, unfollow_user,
    get_followers, get_following,
    get_article, merge_article_meta,
)
from peerpedia_core.transport import fetch_article_meta
from peerpedia_core.social import discover_followers, discover_following
from peerpedia_core.transport import push_follow, push_unfollow

def _pull_social(db, user_id: str) -> None:
    """Pull social graph for *user_id* from the peer server.  Best-effort.

    Discovers who *user_id* follows and who follows *user_id*, merging
    new users and follows into the local DB.  Reads ``PEERPEDIA_SERVER``
    from env.  Warns on each invocation if the server is unreachable.
    """
    server = os.environ.get("PEERPEDIA_SERVER")
    if not server:
        console.print("[dim]⚠ No PEERPEDIA_SERVER set — social pull skipped.[/]")
        return
    try:
        discover_following(db, server, user_id)
        discover_followers(db, server, user_id)
    except Exception as e:
        console.print(f"[dim]⚠ Social pull from {server} failed: {e}[/]")


def _push_social(action: str, **kwargs) -> None:
    """Push a social action to the peer server.  Best-effort — warns on failure.

    *action* is one of ``"follow"``, ``"unfollow"``, ``"bookmark"``.
    Reads the server URL from ``PEERPEDIA_SERVER`` env var.  Warns on
    each invocation if the server is unreachable.
    """
    server = os.environ.get("PEERPEDIA_SERVER")
    if not server:
        console.print("[dim]⚠ No PEERPEDIA_SERVER set — social push skipped.[/]")
        return
    try:
        key = _get_session_key()
        if action == "follow":
            push_follow(server, kwargs["follower_id"], kwargs["followed_id"],
                        private_key_bytes=key)
        elif action == "unfollow":
            push_unfollow(server, kwargs["follower_id"], kwargs["followed_id"],
                          private_key_bytes=key)
    except Exception as e:
        console.print(f"[dim]⚠ Social sync ({action}) to {server} failed: {e}[/]")


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
                    f"[dim]⚠ Could not pull metadata for {article_id[:8]}: {e}[/]"
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
    if args.local:
        users = get_following(db, args.user)
    else:
        server = _sync_server(args)
        discover_following(db, server, args.user)
        db.commit()
        users = get_following(db, args.user)
    if args.json:
        _json_out([u.to_dict() for u in users])
    else:
        _ok(f"Following {len(users)} user(s)")


@_with_db
def _cmd_followers(db, args):
    """List followers of *user_id*. Default: pull from peer.

    args: --user, --server, --local, --json
    """
    if args.local:
        users = get_followers(db, args.user)
    else:
        server = _sync_server(args)
        discover_followers(db, server, args.user)
        db.commit()
        users = get_followers(db, args.user)
    if args.json:
        _json_out([u.to_dict() for u in users])
    else:
        _ok(f"Followers {len(users)} user(s)")
