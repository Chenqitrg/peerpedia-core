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
import json
import os
from pathlib import Path

import bcrypt

from peerpedia_core.cli.helpers import _with_db, _ok, _die, _json_out
from peerpedia_core.cli.display import console
from peerpedia_core.commands import (
    create_user, get_user_by_name, update_user_public_key, update_user_salt,
)
from peerpedia_core.config.paths import SESSION_FILE
from peerpedia_core.crypto import derive_key_pair, new_salt


def _write_session(user_id: str, name: str, private_key_hex: str) -> None:
    """Write session file with chmod 600."""
    _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SESSION_FILE.write_text(json.dumps({
        "user_id": user_id,
        "name": name,
        "private_key_hex": private_key_hex,
    }))
    os.chmod(_SESSION_FILE, 0o600)


def _read_session() -> dict | None:
    """Read session file, or None if not logged in."""
    if not _SESSION_FILE.exists():
        return None
    return json.loads(_SESSION_FILE.read_text())


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
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    private_key_bytes, pubkey_bytes = derive_key_pair(password, salt_hex)
    pubkey_hex = pubkey_bytes.hex()

    user = create_user(
        db,
        name=args.name,
        password_hash=password_hash,
    )
    update_user_public_key(db, user.id, pubkey_hex)
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
    if user is None:
        _die(f"User '{args.name}' not found.")

    if user.salt is None:
        _die(f"User '{args.name}' was registered before key derivation was supported. "
             "Please re-register: peerpedia account register --name {args.name}")

    password = getpass.getpass("Password: ")
    if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        _die("Wrong password.")

    private_key_bytes, _ = derive_key_pair(password, user.salt)
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
