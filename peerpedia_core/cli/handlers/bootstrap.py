# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Bootstrap — load a user stub on a new device for key recovery."""

from __future__ import annotations

from peerpedia_core.cli.bundle_utils import _TRANSPORT
from peerpedia_core.cli.display import console
from peerpedia_core.cli.handlers.login import _auto_sync_after_auth
from peerpedia_core.cli.helpers import _with_db, _out
from peerpedia_core.core import create_user_stub, get_user
from peerpedia_core.storage.peers import merge_peers
from peerpedia_core.types import short_id


def _validate_bootstrap_json(data: dict) -> None:
    """Validate the bootstrap JSON blob."""
    import uuid as _uuid
    for field in ("name", "user_id", "public_key", "salt"):
        if not data.get(field):
            _out(None, "INVALID_BOOTSTRAP_FIELD", field=field)
    try:
        _uuid.UUID(data["user_id"])
    except (ValueError, AttributeError):
          _out(None, "INVALID_USER_ID", value=data['user_id'])
    if len(data["public_key"]) != 64:
        _out(None, "INVALID_PUBKEY_LEN", length=len(data["public_key"]))
    if len(data["salt"]) != 32:
        _out(None, "INVALID_SALT_LEN", length=len(data["salt"]))
    try:
        bytes.fromhex(data["public_key"])
    except (ValueError, AttributeError):
        _out(None, "INVALID_PUBKEY")
    try:
        bytes.fromhex(data["salt"])
    except (ValueError, AttributeError):
        _out(None, "INVALID_SALT")


def _parse_bootstrap_json(json_str: str) -> dict:
    """Parse and validate the --from bootstrap JSON blob."""
    import json as _json
    try:
        data = _json.loads(json_str)
    except _json.JSONDecodeError as e:
        _out(None, "INVALID_JSON", error=str(e))
    _validate_bootstrap_json(data)
    return data


def _create_bootstrap_stub(db, data: dict) -> str:
    """Create a user stub from validated bootstrap data."""
    user_id = data["user_id"]
    existing = get_user(db, user_id)
    if existing is not None:
        _out(None, "DUPLICATE_USER_LOCAL", name=existing.name, id_short=short_id(user_id))
    create_user_stub(db, user_id=user_id, name=data["name"],
                     public_key=data["public_key"], salt=data["salt"])
    db.commit()
    return user_id


@_with_db
def _cmd_bootstrap(db, args):
    """Create a minimal user stub on a new device for key recovery.

    Takes a JSON blob (from ``account whoami --verbose --json``).
    After bootstrap, run ``account recover`` to verify the password.

    args: --from, --peer, --json
    """
    data = _parse_bootstrap_json(args.from_)
    _create_bootstrap_stub(db, data)
    user_id, name = data["user_id"], data["name"]

    if args.peer:
        merge_peers(_TRANSPORT, args.peer)
        _auto_sync_after_auth(db, user_id)
        console.print(f"[dim]Peer {args.peer}: registered. Syncing...[/]")

    _out(args, "BOOTSTRAPPED",
         {"id": user_id, "name": name,
          "peer_note": "Bootstrap complete" if args.peer else None},
         name=name, id_short=short_id(user_id))
