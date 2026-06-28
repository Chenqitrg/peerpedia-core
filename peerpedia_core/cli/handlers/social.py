# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Social — follow, unfollow, following, followers."""

from __future__ import annotations

import os

from peerpedia_core.cli.bundle_utils import _TRANSPORT, _resolve_server_url, _try_sync
from peerpedia_core.cli.display import console
from peerpedia_core.cli.helpers import (
    _with_db, _resolve_user, _get_session_user,
    _get_session_key, _get_session_pubkey, _ok, _json_out,
)
from peerpedia_core.core import (
    follow_user, unfollow_user,
    get_follower_views, get_followers, get_following, get_following_views,
    get_user,
)
from peerpedia_core.core.sync_social import discover_articles, discover_followers, discover_following, discover_notifications, discover_shares

_server_warned: bool = False


def _get_server_or_warn(label: str = "Social") -> str | None:
    """Read PEERPEDIA_SERVER from env, warn once per process if not set."""
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
        discover_following(db, _TRANSPORT, server, user_id, signing_key_bytes=key, pubkey_hex=pubkey)
        discover_followers(db, _TRANSPORT, server, user_id, signing_key_bytes=key, pubkey_hex=pubkey)
        discover_articles(db, _TRANSPORT, server, user_id, signing_key_bytes=key, pubkey_hex=pubkey)
        discover_shares(db, _TRANSPORT, server, user_id, signing_key_bytes=key, pubkey_hex=pubkey)
        discover_notifications(db, _TRANSPORT, server, user_id, signing_key_bytes=key, pubkey_hex=pubkey)
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
    """Push a follow/unfollow action to the peer server.  Best-effort."""
    key = _get_session_key()
    pubkey = _get_session_pubkey()
    if action == "follow":
        _push_to_peer(
            f"Social sync ({action})",
            lambda s: _TRANSPORT.push_follow(
                s, kwargs["follower_id"], kwargs["followed_id"],
                private_key_bytes=key, pubkey_hex=pubkey,
            ),
        )
    elif action == "unfollow":
        _push_to_peer(
            f"Social sync ({action})",
            lambda s: _TRANSPORT.push_unfollow(
                s, kwargs["follower_id"], kwargs["followed_id"],
                private_key_bytes=key, pubkey_hex=pubkey,
            ),
        )


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
        discover_following(db, _TRANSPORT, server, user_id)
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
        discover_followers(db, _TRANSPORT, server, user_id)
        db.commit()
    if args.json:
        _json_out(get_follower_views(db, user_id))
    else:
        users = get_followers(db, user_id)
        _ok(f"Followers {len(users)} user(s)")
