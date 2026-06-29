# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Application context — the "workbench" passed to every app command.

``AppContext`` bundles everything a command needs: database session,
current user identity, Ed25519 signing key, transport, and config.
CLI/REPL/server construct it; app commands consume it.

``build_context(db)`` reads the session file and environment to populate
the optional fields (user identity, keys, transport).  It never fails —
missing fields are ``None``; the command's ``require_user(ctx)`` gate
will raise ``Unauthorized`` when a logged-in user is required.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from peerpedia_core.config.params import ServerParams
from peerpedia_core.config.paths import SESSION_FILE
from peerpedia_core.crypto import _public_key_to_bytes, load_private_key
from peerpedia_core.transport import Transport

if TYPE_CHECKING:
    from peerpedia_core.storage.db import Session

_log = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Everything an app command needs — the user's workbench.

    ``db`` is the only required field (opened by the CLI/REPL entry point).
    Identity fields (``current_user_id``, ``signing_key_bytes``,
    ``pubkey_hex``) are ``None``/``""`` when not logged in.
    """
    db: Session
    transport: Transport  # always set by build_context() — non-optional
    current_user_id: str | None = None
    signing_key_bytes: bytes | None = None
    pubkey_hex: str = ""
    params: ServerParams | None = None
    experimental: bool = False


def build_context(db: Session) -> AppContext:
    """Build an ``AppContext`` from the current environment.

    Reads the session file for user identity and signing key, initialises
    the HTTP transport.  Never fails — missing identity is ``None``;
    callers gate with ``require_user(ctx)``.
    """
    session_data = read_session()
    user_id: str | None = None
    signing_key: bytes | None = None
    pubkey: str = ""

    if session_data:
        user_id = session_data.get("user_id")
        key_hex = session_data.get("private_key_hex")
        if key_hex:
            signing_key = bytes.fromhex(key_hex)
            try:
                priv = load_private_key(signing_key)
                pubkey = _public_key_to_bytes(priv.public_key()).hex()
            except Exception:
                _log.warning("Failed to derive public key from session key")

    transport = Transport.from_http()

    return AppContext(
        db=db,
        transport=transport,
        current_user_id=user_id,
        signing_key_bytes=signing_key,
        pubkey_hex=pubkey,
    )


def read_session() -> dict | None:
    """Read the session file, or None if not logged in / corrupted."""
    if not SESSION_FILE.exists():
        return None
    try:
        return json.loads(SESSION_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        _log.warning("Session file %s is corrupted", SESSION_FILE, exc_info=True)
        return None


def write_session(user_id: str, name: str, private_key_hex: str) -> None:
    """Write session file with chmod 600."""
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps({
        "user_id": user_id,
        "name": name,
        "private_key_hex": private_key_hex,
    }))
    import os
    os.chmod(SESSION_FILE, 0o600)


def _read_session() -> dict | None:
    """Backward-compat alias — delegates to ``read_session``."""
    return read_session()
