# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Account commands — register, login, whoami.

TODO(recovery): key recovery — ``account recover`` re-derives the Ed25519
key from password+salt stored in DB.  Determinstic scrypt→Ed25519 means
a user who remembers their password can recover their identity on any device.
TODO(multi-device): ``account login`` on a new device.  Currently session
is a local file; multi-device needs the recovered private key + P2P identity
sync (social graph transport, not git bundle).
"""

from __future__ import annotations

import getpass

from peerpedia_core.cli.helpers import (
    _with_db, _read_session, _write_session, _ok, _die, _json_out,
)
from peerpedia_core.cli.display import display_user as _render_user, console
from peerpedia_core.commands import (
    create_user, get_user_by_name, search_users,
    update_user_salt,
)
from peerpedia_core.crypto import derive_key_pair, new_salt


def _display_user(u) -> None:
    """Display user metadata — extract data, delegate to pure render."""
    _render_user(
        name=u.name,
        affiliation=u.affiliation or "",
        expertise=u.expertise or [],
        reputation=u.reputation or {},
        user_id=u.id,
    )


@_with_db
def _cmd_register(db, args):
    """Register a new local user with password-derived Ed25519 key pair.

    args: --name, --json
    """

    password = getpass.getpass("Password: ")
    if not password:
        _die("Password must not be empty.")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        _die("Passwords do not match.")

    salt_hex = new_salt()
    private_key_bytes, pubkey_bytes = derive_key_pair(password, salt_hex)
    pubkey_hex = pubkey_bytes.hex()

    user = create_user(db, name=args.name, public_key=pubkey_hex)
    update_user_salt(db, user.id, salt_hex)
    db.commit()

    _write_session(user.id, user.name, private_key_bytes.hex())

    if args.json:
        _json_out({"id": user.id, "name": user.name, "pubkey": pubkey_hex})
    else:
        _ok(f"Registered [accent]{user.name}[/] (id: {user.id[:8]})")


@_with_db
def _cmd_login(db, args):
    """Log in as an existing user — verify password, load key into session.

    args: --name, --json
    """

    user = get_user_by_name(db, args.name)
    if len(user) == 0:
        _die(f"User '{args.name}' not found.")
    if len(user) > 1:
        _die(f"Multiple users named '{args.name}'. "
             f"Use user ID to log in: {', '.join(u.id for u in user)}")
    user = user[0]

    if user.salt is None:
        _die(f"User '{args.name}' was registered before key derivation was supported. "
             "Please re-register: peerpedia account register --name {args.name}")

    password = getpass.getpass("Password: ")
    private_key_bytes, pubkey_bytes = derive_key_pair(password, user.salt)
    if pubkey_bytes.hex() != user.public_key:
        _die("Wrong password.")

    _write_session(user.id, user.name, private_key_bytes.hex())

    if args.json:
        _json_out({"id": user.id, "name": user.name})
    else:
        _ok(f"Logged in as [accent]{user.name}[/] (id: {user.id[:8]})")


@_with_db
def _cmd_whoami(db, args):
    """Show the currently logged-in user.

    args: --json
    """
    session = _read_session()
    if session:
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
            console.print("[muted]Not logged in. Use register or login.[/]")


@_with_db
def _cmd_account_search(db, args):
    """Fuzzy search users by name.

    args: query [positional], --json
    """
    users = search_users(db, args.query, limit=20)
    if args.json:
        _json_out([{"id": u.id, "name": u.name} for u in users])
        return
    if not users:
        console.print(f"[muted]No users match {args.query!r}[/]")
        return
    for u in users:
        _display_user(u)
