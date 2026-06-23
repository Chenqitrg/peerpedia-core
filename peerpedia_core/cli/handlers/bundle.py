# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Bundle commands — status, push, pull."""

from __future__ import annotations

from peerpedia_core.cli.helpers import _with_db, _ok, _die
from peerpedia_core.cli.display import _print_panel, console
from peerpedia_core.cli.bundle_utils import _sync_server
from peerpedia_core.exceptions import ConflictError, ProtocolError, TransportError
from peerpedia_core.bundle.pending import list_all, remove as pop_pending
from peerpedia_core.bundle import count as pending_count, sync_article
from peerpedia_core.transport import is_online
from peerpedia_core.commands import list_articles


def _cmd_sync_status(args):
    """Check connection to a peer server and count pending sync operations.

    args: --server, --json
    """
    server = _sync_server(args)
    online = is_online(server)
    n = pending_count()
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
    synced = 0
    for op in items:
        article_id = op["id"]
        try:
            result = sync_article(db, server, article_id)
        except (TransportError, ProtocolError) as e:
            console.print(f"[warning]⚠ {article_id[:8]}: {e.detail}[/]")
            continue
        except ConflictError as e:
            console.print(f"[warning]⚠ {article_id[:8]}: {e.detail}[/]")
            continue
        if result["synced"]:
            db.commit()
            if on_success:
                on_success(op)
            synced += 1

    if synced > 0:
        _ok(f"{label} {synced} article(s)")
    else:
        _print_panel(label, "[muted]Nothing to sync.[/]")


@_with_db
def _cmd_sync_push(db, args):
    """Push all pending offline operations to a peer server.

    args: --server, --json
    """
    server = _sync_server(args)
    if not is_online(server):
        _die("Server unreachable")
    _sync_loop(db, server, list_all(), "Push", on_success=lambda op: pop_pending(op["id"]))


@_with_db
def _cmd_sync_pull(db, args):
    """Pull article updates from a peer server.

    args: --server, --json
    """
    server = _sync_server(args)
    if not is_online(server):
        _die("Server unreachable")
    _sync_loop(db, server, [{"id": a.id} for a in list_articles(db)], "Pull")
