# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Bundle commands — status, push, pull."""

from __future__ import annotations

from peerpedia_core.cli.helpers import _with_db, _ok, _die, _json_out, _get_session_user, _get_session_key, _get_session_pubkey
from peerpedia_core.types import short_id
from peerpedia_core.cli.display import _print_panel, console
from peerpedia_core.cli.bundle_utils import (
    _TRANSPORT, _require_online_server, _resolve_server_url,
)
from peerpedia_core.exceptions import ConflictError, ProtocolError, TransportError
from peerpedia_core.core.sync_article import pull_new_article, sync_article
from peerpedia_core.core import get_all_article_ids, list_articles, merge_article_meta
from peerpedia_core.core.sync_social import discover_network


@_with_db
def _cmd_sync_status(db, args):
    """Check connection to a peer server.

    args: --server, --json
    """
    server = _resolve_server_url(args)
    online = _TRANSPORT.is_online(server)
    if args.json:
        _json_out({"server": server, "online": online})
        return
    status = "[success]online[/]" if online else "[error]offline[/]"
    body = f"Server:  {server} ({status})\n"
    _print_panel("Sync Status", body)


def _sync_loop(db, server, items, label):
    """Iterate *items* (each with an ``"id"`` key), sync each, commit on success."""
    synced = []
    failed = []
    for op in items:
        article_id = op["id"]
        try:
            result = sync_article(db, _TRANSPORT, server, article_id)
        except (TransportError, ProtocolError) as e:
            console.print(f"[warning]⚠ {short_id(article_id)}: {e.detail}[/]")
            failed.append((short_id(article_id), str(e.detail)))
            continue
        except ConflictError as e:
            console.print(f"[warning]⚠ {short_id(article_id)}: {e.detail}[/]")
            failed.append((short_id(article_id), "conflict"))
            continue
        if result["synced"]:
            db.commit()
            synced.append(short_id(article_id))
            head = result.get("head", "")
            console.print(f"  [success]✓[/] {short_id(article_id)} → {short_id(head)}")

    if synced:
        _ok(f"{label} {len(synced)} article(s): {', '.join(synced)}")
    else:
        _print_panel(label, "[muted]Nothing to sync.[/]")


@_with_db
def _cmd_sync_pull(db, args):
    """Pull article updates from a peer server.

    args: --server, --json
    """
    server = _require_online_server(args)

    # Discover new articles from the server.
    user_id = _get_session_user()
    key = _get_session_key()
    pubkey = _get_session_pubkey()
    server_articles = _TRANSPORT.fetch_search(
        server, user_id,
        private_key_bytes=key, pubkey_hex=pubkey,
    )
    if server_articles:
        local_ids = set(get_all_article_ids(db))
        for entry in server_articles:
            if entry["id"] not in local_ids:
                merge_article_meta(db, [entry])
                pull_new_article(db, _TRANSPORT, server, entry["id"])

    _sync_loop(db, server, [{"id": aid} for aid in get_all_article_ids(db)], "Pull")

    # Auto-discovery: walk depth=1 for followed users to pre-fetch articles.
    _auto_discover(db, server)


def _auto_discover(db, server: str) -> None:
    """Best-effort network discovery after sync — depth=1, max 50 users."""
    try:
        user_id = _get_session_user()
        key = _get_session_key()
        pubkey = _get_session_pubkey()
        result = discover_network(
            db, _TRANSPORT, server, user_id, depth=1, max_users=50,
            signing_key_bytes=key, pubkey_hex=pubkey,
        )
        if result["users_discovered"] or result["articles_discovered"]:
            console.print(
                f"[dim]✓ Auto-discovery: {result['users_discovered']} user(s), "
                f"{result['articles_discovered']} article(s).[/]"
            )
        n_errors = len(result.get("errors", []))
        if n_errors:
            import logging
            logging.getLogger(__name__).debug(
                "auto-discovery: %d error(s) during BFS", n_errors,
            )
    except (TransportError, ProtocolError) as e:
        import logging
        logging.getLogger(__name__).debug("auto-discovery failed: %s", e)
    except ValueError as e:
        import logging
        logging.getLogger(__name__).debug("auto-discovery data error: %s", e)


@_with_db
def _cmd_sync_discover(db, args):
    """Walk the follow graph to discover new users and articles.

    Starting from the current user, fetches their follows, then those
    users' follows, up to --depth N.  For each discovered user, pulls
    their article metadata.

    args: --depth, --server, --max-users, --json
    """
    server = _require_online_server(args)
    depth = getattr(args, "depth", 1) or 1
    max_users = getattr(args, "max_users", 100) or 100

    user_id = _get_session_user()
    key = _get_session_key()
    pubkey = _get_session_pubkey()

    result = discover_network(
        db, _TRANSPORT, server, user_id,
        depth=depth,
        max_users=max_users,
        signing_key_bytes=key,
        pubkey_hex=pubkey,
    )
    db.commit()

    if args.json:
        _json_out(result)
    else:
        console.print(
            f"[success]Network discovery complete:[/]\n"
            f"  Users discovered: {result['users_discovered']}\n"
            f"  Articles discovered: {result['articles_discovered']}\n"
            f"  Follows added: {result['follows_added']}\n"
            f"  Depth reached: {result['depth_reached']}"
        )
        n_errors = len(result.get("errors", []))
        if n_errors:
            console.print(
                f"  [warning]⚠ {n_errors} error(s) during discovery.[/]"
            )
