# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Sync commands — status and push."""

from __future__ import annotations

from peerpedia_core.cli.helpers import _with_db, _ok, _die
from peerpedia_core.cli.display import _print_panel
from peerpedia_core.cli.sync_utils import _sync_server
from peerpedia_core.sync import is_online, count as pending_count, client_sync as sync_push


def _cmd_sync_status(args):
    """Check connection to a peer server and count pending sync operations.

    args: --server, --user, --json
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


@_with_db
def _cmd_sync_push(db, args):
    """Push all pending offline operations to a peer server.

    args: --server, --user, --json
    """
    from peerpedia_core.sync.pending_queue import list_all, remove as pop_pending

    server = _sync_server(args)
    if not is_online(server):
        _die("Server unreachable")

    pushed = 0
    for op in list_all():
        result = sync_push(db, server, op["id"])
        if result["synced"]:
            pop_pending(op["id"])
            pushed += 1
    if pushed > 0:
        db.commit()
        _ok(f"Pushed {pushed} article(s)")
    else:
        _print_panel("Push", "[muted]Nothing to push.[/]")
