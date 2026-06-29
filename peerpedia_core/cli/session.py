# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Session file I/O — read, write, key derivation.

Imports from ``output`` (Layer 1) and ``crypto`` (external).
"""

from __future__ import annotations

import json
import logging
import os

from peerpedia_core.cli.info import _out
from peerpedia_core.config.paths import SESSION_FILE
from peerpedia_core.crypto import load_private_key, _public_key_to_bytes


def _read_session() -> dict | None:
    """Read the session file, or None if not logged in or file is corrupted."""
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            logging.getLogger(__name__).warning(
                "Session file %s is corrupted — treating as not logged in",
                SESSION_FILE, exc_info=True,
            )
            return None
    return None


def _write_session(user_id: str, name: str, private_key_hex: str) -> None:
    """Write session file with chmod 600."""
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps({
        "user_id": user_id,
        "name": name,
        "private_key_hex": private_key_hex,
    }))
    os.chmod(SESSION_FILE, 0o600)


def _get_session_user_id() -> str:
    """Return the current user ID from session, or '' if not logged in.

    Unlike ``_get_session_user()``, this never exits — callers must
    handle the empty-string case themselves.
    """
    s = _read_session()
    return s["user_id"] if s else ""


def _get_session_user() -> str:
    """Return the current user ID, or exit if not logged in."""
    s = _read_session()
    if s:
        return s["user_id"]
    _out(None, "USER_NOT_REGISTERED")


def _get_session_key() -> bytes | None:
    """Return the current user's private key from the session file, or None."""
    s = _read_session()
    if s:
        key_hex = s.get("private_key_hex")
        if key_hex:
            return bytes.fromhex(key_hex)
    return None


def _get_session_pubkey() -> str:
    """Return the current user's Ed25519 public key (hex), or '' if not logged in."""
    key = _get_session_key()
    if key:
        priv = load_private_key(key)
        pub = priv.public_key()
        return _public_key_to_bytes(pub).hex()
    return ""
