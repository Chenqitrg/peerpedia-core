# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Account commands -- register, login, recover, whoami, bootstrap, delete.

``account login --peer <url> --user-id <uuid>`` bootstraps a new device by
fetching user metadata from a peer, then verifies the password locally.
"""

from __future__ import annotations

import getpass

from peerpedia_core.cli.helpers import (
    _with_db, _read_session, _write_session, _ok, _die, _json_out,
    _empty_state,
)
from peerpedia_core.config.paths import SESSION_FILE
from peerpedia_core.cli.display import display_user as _render_user, console
from peerpedia_core.commands import (
    create_user, create_user_stub, get_user, get_user_by_name,
    increment_failed_login, reset_failed_login, search_users,
    soft_delete_user, update_user_salt,
)
from peerpedia_core.crypto import derive_key_pair, new_salt
from peerpedia_core.transport import fetch_user


def _display_user(u) -> None:
    """Display user metadata — extract data, delegate to pure render."""
    _render_user(
        name=u.name,
        affiliation=u.affiliation or "",
        expertise=u.expertise or [],
        reputation=u.reputation or {},
        user_id=u.id,
    )


import os as _os


def _get_password(args, confirm: bool = False) -> str:
    """Get password from --password flag, env var, or interactive prompt."""
    pw = getattr(args, "password", None)
    if pw is not None:
        return pw
    pw = _os.environ.get("PEERPEDIA_PASSWORD")
    if pw is not None:
        return pw
    password = getpass.getpass("Password: ")
    if not password:
        _die("Password must not be empty.",
             suggestion="Passwords protect your Ed25519 signing key. "
                        "Choose a strong, memorable password.")
    if confirm:
        c = getpass.getpass("Confirm password: ")
        if password != c:
            _die("Passwords do not match.",
                 suggestion="The two password entries must be identical. "
                            "Try again.")
    return password


@_with_db
def _cmd_register(db, args):
    """Register a new local user with password-derived Ed25519 key pair.

    args: --name, --password (optional), --json
    """

    password = _get_password(args, confirm=True)

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

    With ``--peer`` and ``--user-id``, bootstraps a new device by fetching the
    user record from a peer server first, then verifies the password locally.

    args: --name, --password (optional), --json, --peer (optional), --user-id (optional)
    """

    user = get_user_by_name(db, args.name)
    if len(user) == 0:
        # Try remote bootstrap if --peer or PEERPEDIA_SERVER is set
        peer = getattr(args, "peer", None) or _os.environ.get("PEERPEDIA_SERVER")
        user_id = getattr(args, "user_id", None)
        if peer and user_id:
            data = fetch_user(peer, user_id)
            if data:
                create_user_stub(
                    db,
                    user_id=data["id"], name=data["name"],
                    public_key=data["public_key"], salt=data["salt"],
                )
                db.commit()
                u = get_user(db, data["id"])
                if u is None:
                    _die(f"Failed to bootstrap user {data['id']} from {peer}")
                user = [u]
            else:
                _die(f"User '{args.name}' not found on {peer}.",
                     suggestion="Check the --user-id or try a different peer server.")
        else:
            _die(f"User '{args.name}' not found.",
                 suggestion="Check the spelling, or register first: "
                            "peerpedia account register --name <your-name>",
                 see_also=["account register", "account search"])
    if len(user) > 1:
        _die(f"Multiple users named '{args.name}'.",
             suggestion=f"Use a user ID to specify which one: "
                        f"{', '.join(u.id[:8] for u in user)}",
             see_also=["account whoami"])
    user = user[0]

    if user.salt is None:
        _die(f"User '{args.name}' was registered before key derivation was supported.",
             suggestion=f"Re-register: peerpedia account register --name {args.name}")

    # Rate-limit: reject if account is locked
    if user.locked_until is not None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if user.locked_until > now:
            remaining = int((user.locked_until - now).total_seconds())
            minutes = max(1, remaining // 60)
            _die(f"Account locked — too many failed attempts. Try again in {minutes} minute(s).",
                 suggestion="Wait for the lockout to expire, or use account recover "
                            "if you forgot your password.",
                 see_also=["account recover"])

    password = _get_password(args)
    private_key_bytes, pubkey_bytes = derive_key_pair(password, user.salt)
    if pubkey_bytes.hex() != user.public_key:
        increment_failed_login(db, user.id)
        _die("Wrong password.",
             suggestion="If you forgot your password, run: peerpedia account recover "
                        "--name <your-name>. If this is a new device, bootstrap first.",
             see_also=["account recover", "account bootstrap"])

    reset_failed_login(db, user.id)
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
        _die("Specify either --name or --user-id.",
             suggestion="Use --name to look up by display name, "
                        "or --user-id to look up by UUID.",
             see_also=["account whoami --verbose"])

    if user.salt is None:
        _die(f"User '{user.name}' has no stored salt — key was not derived.",
             suggestion=f"Re-register: peerpedia account register --name {user.name}")

    # Rate-limit: reject if account is locked
    if user.locked_until is not None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if user.locked_until > now:
            remaining = int((user.locked_until - now).total_seconds())
            minutes = max(1, remaining // 60)
            _die(f"Account locked — too many failed attempts. Try again in {minutes} minute(s).",
                 suggestion="Wait for the lockout to expire before attempting recovery.",
                 see_also=["account login"])

    password = _get_password(args)
    private_key_bytes, pubkey_bytes = derive_key_pair(password, user.salt)
    if pubkey_bytes.hex() != user.public_key:
        increment_failed_login(db, user.id)
        _die("Wrong password.",
             suggestion="If you forgot your password, you'll need to re-register. "
                        "The salt+password derive your key — there is no reset.",
             see_also=["account register"])

    reset_failed_login(db, user.id)

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
        _empty_state(f"No users match {args.query!r}")
        return
    for u in users:
        _display_user(u)


@_with_db
def _cmd_account_delete(db, args):
    """Delete your account (soft-delete).  Requires password confirmation.

    args: --json
    """

    session = _read_session()
    if not session:
        _die("Not logged in. Run 'peerpedia account login' first.")

    user_id = session["user_id"]
    user = get_user(db, user_id)
    if user is None:
        _die("User not found in local database.",
             suggestion="Your session references a user that no longer exists.")

    if user.salt is None:
        _die("Cannot verify identity — no salt stored. Re-register to enable password verification.")

    password = _get_password(args)
    _, pubkey_bytes = derive_key_pair(password, user.salt)
    if pubkey_bytes.hex() != user.public_key:
        _die("Wrong password — account deletion cancelled.")

    soft_delete_user(db, user_id)
    db.commit()

    # Clear session file
    try:
        SESSION_FILE.unlink(missing_ok=True)
    except OSError:
        pass  # file already gone — nothing to clean up

    if args.json:
        _json_out({"status": "deleted", "user_id": user_id})
    else:
        _ok(f"Account [accent]{user.name}[/] deleted. Goodbye.")
