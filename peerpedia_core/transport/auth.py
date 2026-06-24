# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Ed25519 request signing — challenge-free auth matching commit signing.

Every authenticated request carries an ``Authorization: Peerpedia`` header::

    Peerpedia <user_id>:<timestamp>:<signature_hex>

The signature covers ``<method>:<path>:<user_id>:<timestamp>``.  The server
looks up the user's public key and verifies with Ed25519.  Timestamp must
be within ±60s of server time to prevent replay.

This is the same Ed25519 key pair used for git commit signing — no separate
password or JWT needed.
"""

from __future__ import annotations

import time
import warnings

from peerpedia_core.crypto import _load_public_key, verify_signature


def sign_auth_header(
    method: str,
    path: str,
    user_id: str,
    private_key_bytes: bytes,
) -> str:
    """Build an ``Authorization: Peerpedia ...`` header value.

    The signature covers ``method:path:user_id:timestamp``, binding the
    request to a specific user and time window.
    """
    ts = str(int(time.time()))
    message = f"{method}:{path}:{user_id}:{ts}".encode("utf-8")
    sig = _sign_detached(private_key_bytes, message)
    return f"Peerpedia {user_id}:{ts}:{sig.hex()}"


def verify_auth_header(
    header_value: str,
    method: str,
    path: str,
    public_key_hex: str,
) -> str | None:
    """Verify a ``Peerpedia`` auth header.  Returns user_id if valid, None otherwise.

    Args:
        header_value: The full ``Authorization`` header value.
        method: HTTP method (GET, POST, ...).
        path: Request path (e.g. ``/api/v1/users/alice/following``).
        public_key_hex: The user's Ed25519 public key as a hex string.
    """
    try:
        scheme, payload = header_value.split(" ", 1)
        if scheme != "Peerpedia":
            return None
        parts = payload.split(":")
        if len(parts) != 3:
            return None
        user_id, ts_str, sig_hex = parts
    except ValueError:
        return None

    # Replay window — clock skew + short-term replay protection
    try:
        ts = int(ts_str)
        now = int(time.time())
        if abs(now - ts) > 60:
            return None
    except ValueError:
        return None

    try:
        sig_bytes = bytes.fromhex(sig_hex)
    except ValueError:
        return None

    message = f"{method}:{path}:{user_id}:{ts_str}".encode("utf-8")
    pubkey_bytes = bytes.fromhex(public_key_hex)
    if not verify_signature(pubkey_bytes, message, sig_bytes):
        return None

    return user_id


# ── Internal (wrap crypto.py functions) ──────────────────────────────────

from peerpedia_core.crypto import sign_detached as _sign_detached
