# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Register a new local user."""

from __future__ import annotations

from peerpedia_core.cli.display import console
from peerpedia_core.cli.helpers import (
    _with_db, _read_session, _write_session, _out, _get_password,
)
from peerpedia_core.core import create_user, get_user_by_name
from peerpedia_core.crypto import derive_key_pair, new_salt
from peerpedia_core.storage.db.crud_user import update_user_salt
from peerpedia_core.types import short_id


@_with_db
def _cmd_register(db, args):
    """Register a new local user.  args: --name, --password, --json"""
    same_name = get_user_by_name(db, args.name)
    if same_name:
        _out(args, "DUPLICATE_NAME",
             ids=", ".join(short_id(u.id) for u in same_name), name=args.name)

    existing = _read_session()
    if existing:
        _out(args, "W_REGISTER_SWITCH",
             name=existing.get("name", "?"),
             id_short=short_id(existing.get("user_id", "?")))

    password = _get_password(args, confirm=True)
    salt_hex = new_salt()
    private_key_bytes, pubkey_bytes = derive_key_pair(password, salt_hex)
    pubkey_hex = pubkey_bytes.hex()

    user = create_user(db, name=args.name, public_key=pubkey_hex)
    update_user_salt(db, user.id, salt_hex)
    db.commit()

    _write_session(user.id, user.name, private_key_bytes.hex())
    _out(args, "REGISTERED", {"id": user.id, "name": user.name, "pubkey": pubkey_hex},
         name=user.name, id_short=short_id(user.id))
