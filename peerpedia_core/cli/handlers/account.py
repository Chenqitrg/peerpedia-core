# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Account commands — register and whoami."""

from __future__ import annotations

import json
from pathlib import Path

from peerpedia_core.cli.helpers import _with_db, _ok, _die, _json_out
from peerpedia_core.cli.display import console
from peerpedia_core.commands import create_user


@_with_db
def _cmd_register(db, args):
    """Register a new local user.

    args: --name, --json

    TODO(auth): prompt for password instead of hardcoding placeholder.
    """
    import bcrypt

    user = create_user(
        db,
        name=args.name,
        password_hash=bcrypt.hashpw(b"placeholder", bcrypt.gensalt()).decode(),
    )
    db.commit()

    # Write session so subsequent commands pick up this user automatically.
    session_file = Path.home() / ".peerpedia" / "session.json"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(json.dumps({"user_id": user.id, "name": user.name}))

    if args.json:
        _json_out({"id": user.id, "name": user.name})
    else:
        _ok(f"Registered [accent]{user.name}[/] (id: {user.id[:8]})")


@_with_db
def _cmd_whoami(db, args):
    """Show the currently logged-in user.

    args: --json
    """
    session_file = Path.home() / ".peerpedia" / "session.json"
    if session_file.exists():
        session = json.loads(session_file.read_text())
        user_id = session.get("user_id", "")
        name = session.get("name", "unknown")
        if args.json:
            _json_out({"user_id": user_id, "name": name})
        else:
            console.print(f"[accent]{name}[/] (id: {user_id[:8]})")
    else:
        if args.json:
            _json_out({"status": "not logged in"})
        else:
            console.print("[muted]Not logged in. Use register.[/]")
