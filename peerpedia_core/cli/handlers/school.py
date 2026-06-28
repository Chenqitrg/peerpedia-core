# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""School command — top users ranked by follower count."""

from __future__ import annotations

from peerpedia_core.cli.bundle_utils import _TRANSPORT, _resolve_server_url
from peerpedia_core.cli.display import console
from peerpedia_core.cli.helpers import _with_db, _json_out
from peerpedia_core.core import create_user_stub, get_top_users_by_followers, get_user


@_with_db
def _cmd_school(db, args):
    """List top users ranked by follower count — the user directory.

    args: --server, --local, --limit, --json
    """
    limit = getattr(args, "limit", 20) or 20

    if getattr(args, "local", False):
        users = get_top_users_by_followers(db, limit=limit)
    else:
        server = _resolve_server_url(args)
        try:
            users = _TRANSPORT.fetch_school(server, limit=limit)
            for u in users:
                existing = get_user(db, u["id"])
                if existing is None:
                    create_user_stub(db, user_id=u["id"], name=u["name"],
                                     public_key="", salt="")
                    db.commit()
        except Exception as e:
            console.print(f"[dim]Remote school unavailable ({e}) — showing local.[/]")
            users = get_top_users_by_followers(db, limit=limit)

    if args.json:
        _json_out(users)
        return

    if not users:
        console.print("[muted]No users with followers yet.[/]")
        return

    from rich.table import Table
    table = Table(title="School — Top Users by Followers")
    table.add_column("Rank", style="dim", justify="right")
    table.add_column("Name")
    table.add_column("Followers", justify="right")
    for i, u in enumerate(users, 1):
        table.add_row(str(i), u["name"], str(u["follower_count"]))
    console.print(table)
