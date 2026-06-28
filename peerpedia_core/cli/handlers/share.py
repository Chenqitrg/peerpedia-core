# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Share commands — public recommendations for followers."""

from __future__ import annotations

from peerpedia_core.cli.bundle_utils import _TRANSPORT, _resolve_server_url
from peerpedia_core.cli.display import console
from peerpedia_core.cli.helpers import (
    _with_db, _resolve_user, _get_session_user,
    _get_session_key, _get_session_pubkey, _ok, _die, _json_out,
    search_articles,
)
from peerpedia_core.core import (
    add_share, get_feed_shares, get_shares_for_user, remove_share,
)
from peerpedia_core.types import short_id


def _push_share(article_id: str, sharer_id: str, recipient_id: str | None = None,
                comment: str | None = None, *, action: str = "add") -> None:
    """Push a share to the peer server.  Best-effort — warns on failure."""
    key = _get_session_key()
    pubkey = _get_session_pubkey()
    try:
        server = _resolve_server_url(None)
        if action == "remove":
            _TRANSPORT.push_share_remove(server, sharer_id, article_id,
                                         private_key_bytes=key, pubkey_hex=pubkey)
        else:
            _TRANSPORT.push_share(server, sharer_id, article_id,
                                  recipient_id=recipient_id, comment=comment,
                                  private_key_bytes=key, pubkey_hex=pubkey)
    except Exception as e:
        console.print(f"[warning]⚠ Share {action} push failed: {e}[/]")


@_with_db
def _cmd_share_add(db, args):
    """Share an article — public recommendation visible to followers.

    args: article_id [positional], --to, --comment, --json
    """
    user_id = _get_session_user()
    results = search_articles(db, args.article_id)
    if len(results) != 1:
        _out(args, "ARTICLE_NOT_FOUND", article_id=args.article_id)
    article = results[0]
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
                table.add_row(short_id(s["article_id"]), s.get("comment") or "")
        else:
            table = Table(title="Shares")
            table.add_column("Article", style="dim")
            table.add_column("Title")
            for s in shares:
                table.add_row(short_id(s["id"]), s["title"])
        console.print(table)


@_with_db
def _cmd_share_remove(db, args):
    """Remove a share (un-share an article).

    args: article_id [positional]
    """
    user_id = _get_session_user()
    results = search_articles(db, args.article_id)
    if len(results) != 1:
        _out(args, "ARTICLE_NOT_FOUND", article_id=args.article_id)
    article = results[0]
    remove_share(db, user_id, article.id)
    db.commit()
    _push_share(args.article_id, user_id, action="remove")
    _ok(f"Unshared [accent]{short_id(args.article_id)}[/]")
