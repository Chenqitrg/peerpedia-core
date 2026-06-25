# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Bundle commands — status, push, pull."""

from __future__ import annotations

from peerpedia_core.cli.helpers import _with_db, _ok, _die, _json_out, _get_session_user, _get_session_key, _get_session_pubkey
from peerpedia_core.cli.display import _print_panel, console
from peerpedia_core.cli.bundle_utils import _require_online_server, _resolve_server_url
from peerpedia_core.exceptions import ConflictError, ProtocolError, TransportError
from peerpedia_core.transport import is_online, fetch_search
from peerpedia_core.bundle.pending import list_all, remove as pop_pending
from peerpedia_core.bundle import count as pending_count, sync_article, pull_new_article
from peerpedia_core.commands import get_all_article_ids, list_articles, merge_article_meta
from peerpedia_core.social import discover_network


@_with_db
def _cmd_sync_status(db, args):
    """Check connection to a peer server and count pending sync operations.

    args: --server, --json
    """
    server = _resolve_server_url(args)
    online = is_online(server)
    n = pending_count()
    if args.json:
        _json_out({"server": server, "online": online, "pending": n})
        return
    status = "[success]online[/]" if online else "[error]offline[/]"
    body = (
        f"Server:  {server} ({status})\n"
        f"Pending: {n} ops\n"
    )
    if n > 0:
        body += f"\n[warning]⚠ {n} changes not yet synced. Run sync push.[/]"
    _print_panel("Sync Status", body)


def _sync_loop(db, server, items, label, *, on_success=None):
    """Iterate *items* (each with an ``"id"`` key), sync each, commit on success.

    *on_success* is called with ``(db, op)`` after each successful sync
    (e.g. to remove from the pending queue).
    """
    synced = []
    failed = []
    for op in items:
        article_id = op["id"]
        try:
            result = sync_article(db, server, article_id)
        except (TransportError, ProtocolError) as e:
            console.print(f"[warning]⚠ {article_id[:8]}: {e.detail}[/]")
            failed.append((article_id[:8], str(e.detail)))
            continue
        except ConflictError as e:
            console.print(f"[warning]⚠ {article_id[:8]}: {e.detail}[/]")
            failed.append((article_id[:8], "conflict"))
            continue
        if result["synced"]:
            db.commit()
            if on_success:
                on_success(op)
            synced.append(article_id[:8])
            head = result.get("head", "")
            console.print(f"  [success]✓[/] {article_id[:8]} → {head[:8]}")

    if synced:
        _ok(f"{label} {len(synced)} article(s): {', '.join(synced)}")
    else:
        _print_panel(label, "[muted]Nothing to sync.[/]")


@_with_db
def _cmd_sync_push(db, args):
    """Push all pending offline operations to a peer server.

    args: --server, --json
    """
    server = _require_online_server(args)
    _sync_loop(db, server, list_all(), "Push", on_success=lambda op: pop_pending(op["id"]))


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
    server_articles = fetch_search(
        server, user_id,
        private_key_bytes=key, pubkey_hex=pubkey,
    )
    if server_articles:
        local_ids = set(get_all_article_ids(db))
        for entry in server_articles:
            if entry["id"] not in local_ids:
                merge_article_meta(db, [entry])
                pull_new_article(db, server, entry["id"])

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
            db, server, user_id, depth=1, max_users=50,
            signing_key_bytes=key, pubkey_hex=pubkey,
        )
        if result["users_discovered"] or result["articles_discovered"]:
            console.print(
                f"[dim]✓ Auto-discovery: {result['users_discovered']} user(s), "
                f"{result['articles_discovered']} article(s).[/]"
            )
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug("auto-discovery failed: %s", e)


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
        db, server, user_id,
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
