# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Account commands — register, login, recover, whoami, bootstrap.

TODO(multi-device): ``account login`` on a new device now has the bootstrap
flow — ``account bootstrap --from <json>`` then ``account recover``.
"""

from __future__ import annotations

import getpass

from peerpedia_core.cli.helpers import (
    _with_db, _read_session, _write_session, _ok, _die, _json_out,
)
from peerpedia_core.cli.display import display_user as _render_user, console
from peerpedia_core.commands import (
    create_user, create_user_stub, get_user, get_user_by_name, search_users,
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
def _cmd_recover(db, args):
    """Recover a user's Ed25519 key from password + stored salt.

    Re-derives the key pair deterministically (scrypt + Ed25519) and
    writes the session file.  Works on any device — the user only needs
    their password; the salt is fetched from the local DB.

    Specify the user by --name or --user-id.  If both are given, --user-id
    takes precedence.  On a new device, bootstrap first with
    ``account bootstrap`` to populate the local User record.

    args: --name, --user-id, --json
    """
    if args.user_id:
        user = get_user(db, args.user_id)
        if user is None:
            _die(f"User {args.user_id[:8]} not found locally. "
                 "Bootstrap first with: peerpedia account bootstrap --from '<json>'")
        if args.name:
            import logging
            logging.getLogger(__name__).warning(
                "Both --name and --user-id given — using --user-id"
            )
    elif args.name:
        user = get_user_by_name(db, args.name)
        if len(user) == 0:
            _die(f"User '{args.name}' not found locally. "
                 "Bootstrap first with: peerpedia account bootstrap --from '<json>'")
        if len(user) > 1:
            _die(f"Multiple users named '{args.name}'. "
                 f"Use --user-id to specify: {', '.join(u.id for u in user)}")
        user = user[0]
    else:
        _die("Specify either --name or --user-id.")

    if user.salt is None:
        _die(f"User '{user.name}' has no stored salt — key was not derived. "
             f"Please re-register: peerpedia account register --name {user.name}")

    password = getpass.getpass("Password: ")
    private_key_bytes, pubkey_bytes = derive_key_pair(password, user.salt)
    if pubkey_bytes.hex() != user.public_key:
        _die("Wrong password.")

    _write_session(user.id, user.name, private_key_bytes.hex())

    if args.json:
        _json_out({"id": user.id, "name": user.name, "pubkey": user.public_key})
    else:
        _ok(f"Recovered key for [accent]{user.name}[/] (id: {user.id[:8]})")


@_with_db
def _cmd_whoami(db, args):
    """Show the currently logged-in user.

    args: --json, --verbose
    """
    session = _read_session()
    if session:
        user_id = session.get("user_id", "")
        name = session.get("name", "unknown")

        if args.verbose:
            user = get_user(db, user_id)
            if user is None:
                _die(f"User {user_id[:8]} not found in local DB. "
                     "Run account recover first.")
            extra = {
                "user_id": user_id,
                "name": name,
                "public_key": user.public_key or "not set",
                "salt": user.salt or "not set",
            }
            if args.json:
                _json_out(extra)
            else:
                console.print(
                    f"[accent]{name}[/] (id: {user_id[:8]})\n"
                    f"Public key: {extra['public_key']}\n"
                    f"Salt:       {extra['salt']}"
                )
        else:
            if args.json:
                _json_out({"user_id": user_id, "name": name})
            else:
                console.print(f"[accent]{name}[/] (id: {user_id[:8]})")
    else:
        if args.json:
            _json_out({"status": "not logged in"})
        else:
            console.print("[muted]Not logged in. Use register or login.[/]")


def _validate_bootstrap_json(data: dict) -> None:
    """Validate the bootstrap JSON blob.  Dies with a clear message on failure."""
    import uuid as _uuid

    if not data.get("name"):
        _die("Bootstrap JSON missing 'name' field.")
    if not data.get("user_id"):
        _die("Bootstrap JSON missing 'user_id' field.")
    if not data.get("public_key"):
        _die("Bootstrap JSON missing 'public_key' field.")
    if not data.get("salt"):
        _die("Bootstrap JSON missing 'salt' field.")

    try:
        _uuid.UUID(data["user_id"])
    except (ValueError, AttributeError):
        _die(f"Invalid user_id: {data['user_id']!r} — must be a valid UUID.")

    pubkey = data["public_key"]
    if len(pubkey) != 64:
        _die(f"Invalid public_key length: {len(pubkey)} — must be 64 hex characters (32 bytes).")
    try:
        bytes.fromhex(pubkey)
    except (ValueError, AttributeError):
        _die(f"Invalid public_key: not valid hex.")

    salt = data["salt"]
    if len(salt) != 32:
        _die(f"Invalid salt length: {len(salt)} — must be 32 hex characters (16 bytes).")
    try:
        bytes.fromhex(salt)
    except (ValueError, AttributeError):
        _die(f"Invalid salt: not valid hex.")


@_with_db
def _cmd_bootstrap(db, args):
    """Create a minimal user stub on a new device for key recovery.

    Takes a JSON blob (from ``account whoami --verbose --json`` on the
    original device).  After bootstrap, run ``account recover`` to verify
    the password and obtain a session.

    args: --from, --peer, --json
    """
    import json as _json

    try:
        data = _json.loads(args.from_)
    except _json.JSONDecodeError as e:
        _die(f"Invalid JSON in --from: {e}")

    _validate_bootstrap_json(data)

    user_id = data["user_id"]
    name = data["name"]
    public_key = data["public_key"]
    salt = data["salt"]

    existing = get_user(db, user_id)
    if existing is not None:
        _die(f"User '{existing.name}' (id: {user_id[:8]}) already exists in local DB.")

    create_user_stub(
        db,
        user_id=user_id,
        name=name,
        public_key=public_key,
        salt=salt,
    )
    db.commit()

    if args.json:
        _json_out({"id": user_id, "name": name})
    else:
        _ok(f"Bootstrapped user [accent]{name}[/] (id: {user_id[:8]})")
        console.print("Now run: [accent]peerpedia account recover --user-id "
                       f"{user_id[:8]}[/] to verify your password.")

    if args.peer:
        if args.json:
            _json_out({"id": user_id, "name": name,
                       "peer_note": "Data sync not yet available — run `peerpedia sync pull` manually."})
        else:
            console.print(
                f"[muted]Peer {args.peer}: data sync not yet available. "
                "Run [accent]peerpedia sync pull <url>[/] manually.[/]"
            )


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
