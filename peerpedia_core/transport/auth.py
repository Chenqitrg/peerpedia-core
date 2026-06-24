# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Ed25519 request signing — the same key pair used for git commit signing.

No passwords, no JWT, no separate registration.  A user's Ed25519 identity
is derived once from password+salt at registration, stored as ``public_key``
in the DB, and used for both commit signing AND HTTP request signing.

API
---
Client side (called by CLI before each network request)::

    sign_auth_header(method, path, user_id, private_key_bytes, *, body=b"")
        → "Peerpedia <uid>:<ts>:<body_hash>:<sig_hex>"

Server side (called by AuthMiddleware)::

    verify_auth_header(header, method, path, public_key_hex, *, body=b"")
        → user_id (str) if valid, None if invalid

Format
------
The ``Authorization`` header value has 4 colon-separated fields::

    Peerpedia <user_id>:<unix_timestamp>:<body_sha256_hex>:<signature_hex>

The signature covers ``<method>:<path>:<user_id>:<ts>:<body_hash>``.
Timestamp must be within ±30s of server time (replay window).
Body hash is SHA-256 hex, or "" for GET/empty requests.

Backward-compatible with the 3-field format (no body hash) for GET requests.
"""

from __future__ import annotations

import hashlib
import time
import warnings

from peerpedia_core.crypto import sign_detached, verify_signature


def sign_auth_header(
    method: str,
    path: str,
    user_id: str,
    private_key_bytes: bytes,
    *,
    body: bytes = b"",
) -> str:
    """Build an ``Authorization: Peerpedia ...`` header value.

    The signature covers ``method:path:user_id:ts:body_hash``, binding the
    request to a specific user, time window, and body content.
    """
    ts = str(int(time.time()))
    body_hash = _sha256_hex(body)
    message = f"{method}:{path}:{user_id}:{ts}:{body_hash}".encode("utf-8")
    sig = sign_detached(private_key_bytes, message)
    return f"Peerpedia {user_id}:{ts}:{body_hash}:{sig.hex()}"


def verify_auth_header(
    header_value: str,
    method: str,
    path: str,
    public_key_hex: str,
    *,
    body: bytes = b"",
) -> str | None:
    """Verify a ``Peerpedia`` auth header.  Returns user_id if valid, None otherwise.

    Args:
        header_value: The full ``Authorization`` header value.
        method: HTTP method (GET, POST, ...).
        path: Request path (e.g. ``/api/v1/users/alice/following``).
        public_key_hex: The user's Ed25519 public key as a hex string.
        body: The request body bytes (empty for GET).
    """
    try:
        scheme, payload = header_value.split(" ", 1)
        if scheme != "Peerpedia":
            return None
        parts = payload.split(":")
        if len(parts) == 4:
            user_id, ts_str, body_hash, sig_hex = parts
        elif len(parts) == 3:
            # Backward-compat: old format without body hash (no body)
            user_id, ts_str, sig_hex = parts
            body_hash = ""
        else:
            return None
    except ValueError:
        return None

    # Replay window — tight to limit replay, loose enough for clock skew
    try:
        ts = int(ts_str)
        now = int(time.time())
        if abs(now - ts) > 30:
            return None
    except ValueError:
        return None

    try:
        sig_bytes = bytes.fromhex(sig_hex)
    except ValueError:
        return None

    actual_body_hash = _sha256_hex(body)
    if body_hash != actual_body_hash:
        return None

    message = f"{method}:{path}:{user_id}:{ts_str}:{body_hash}".encode("utf-8")
    pubkey_bytes = bytes.fromhex(public_key_hex)
    if not verify_signature(pubkey_bytes, message, sig_bytes):
        return None

    return user_id


def _sha256_hex(data: bytes) -> str:
    if not data:
        return ""
    return hashlib.sha256(data).hexdigest()
