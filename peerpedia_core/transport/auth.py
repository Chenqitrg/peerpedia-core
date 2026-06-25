# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Ed25519 request signing — the same key pair used for git commit signing.

No passwords, no JWT, no separate registration.  A user's Ed25519 identity
is derived once from password+salt at registration, stored as ``public_key``
in the DB, and used for both commit signing AND HTTP request signing.

API
---
Client side (called by CLI before each network request)::

    sign_auth_header(method, path, user_id, private_key_bytes, pubkey_hex, *, body=b"")
        → "Peerpedia <uid>:<pubkey>:<ts>:<body_hash>:<sig>"

Server side (called by AuthMiddleware)::

    verify_auth_header(header, method, path, *, body=b"")
        → AuthResult(ok=True, user_id=..., pubkey_hex=...)
        → AuthResult(ok=False, reason="...")

Format
------
The ``Authorization`` header value has 5 colon-separated fields::

    Peerpedia <user_id>:<pubkey_hex>:<unix_timestamp>:<body_sha256_hex>:<signature_hex>

The signature covers ``<method>:<path>:<user_id>:<ts>:<body_hash>``.
Timestamp must be within ±30s of server time (replay window).
Body hash is SHA-256 hex, or "" for GET/empty requests.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from peerpedia_core.crypto import sign_detached, verify_signature


@dataclass
class AuthResult:
    """Result of ``verify_auth_header``.  ``ok=True`` on success; on failure
    ``ok=False`` and ``reason`` explains why."""
    ok: bool
    user_id: str = ""
    pubkey_hex: str = ""
    reason: str = ""


def sign_auth_header(
    method: str,
    path: str,
    user_id: str,
    private_key_bytes: bytes,
    pubkey_hex: str,
    *,
    body: bytes = b"",
) -> str:
    """Build an ``Authorization: Peerpedia ...`` header value.

    Includes the public key so the server can verify the signature without
    a DB lookup — enabling TOFU (Trust On First Use) for new peers.

    Format: ``Peerpedia <uid>:<pubkey>:<ts>:<body_hash>:<sig>``
    """
    ts = str(int(time.time()))
    body_hash = _sha256_hex(body)
    message = f"{method}:{path}:{user_id}:{ts}:{body_hash}".encode("utf-8")
    sig = sign_detached(private_key_bytes, message)
    return f"Peerpedia {user_id}:{pubkey_hex}:{ts}:{body_hash}:{sig.hex()}"


def verify_auth_header(
    header_value: str,
    method: str,
    path: str,
    *,
    body: bytes = b"",
) -> AuthResult:
    """Verify a ``Peerpedia`` auth header.  Self-contained — pubkey is in the header.

    Returns ``AuthResult`` — check ``.ok``, read ``.reason`` on failure.
    """
    try:
        scheme, payload = header_value.split(" ", 1)
        if scheme != "Peerpedia":
            return AuthResult(ok=False, reason="Authorization scheme must be 'Peerpedia'")
        parts = payload.split(":")
        if len(parts) == 5:
            user_id, pubkey_hex, ts_str, body_hash, sig_hex = parts
        elif len(parts) == 4:
            return AuthResult(ok=False,
                reason="Old auth format (no public key) — update your client")
        else:
            return AuthResult(ok=False,
                reason=f"Expected 5 colon-separated fields, got {len(parts)}")
    except ValueError as e:
        return AuthResult(ok=False, reason=f"Malformed header: {e}")

    # Validate pubkey format
    if len(pubkey_hex) != 64:
        return AuthResult(ok=False,
            reason=f"Public key must be 64 hex chars, got {len(pubkey_hex)}")
    try:
        pubkey_bytes = bytes.fromhex(pubkey_hex)
    except ValueError:
        return AuthResult(ok=False, reason="Public key is not valid hex")

    # Replay window
    try:
        ts = int(ts_str)
        now = int(time.time())
        if abs(now - ts) > 30:
            return AuthResult(ok=False,
                reason=f"Timestamp {ts} is outside ±30s window (server time: {now})")
    except ValueError:
        return AuthResult(ok=False, reason=f"Timestamp '{ts_str}' is not an integer")

    try:
        sig_bytes = bytes.fromhex(sig_hex)
    except ValueError:
        return AuthResult(ok=False, reason="Signature is not valid hex")

    actual_hash = _sha256_hex(body)
    if body_hash != actual_hash:
        return AuthResult(ok=False,
            reason=f"Body hash mismatch (expected {actual_hash[:16]}..., "
                   f"got {body_hash[:16]}...)")

    message = f"{method}:{path}:{user_id}:{ts_str}:{body_hash}".encode("utf-8")
    if not verify_signature(pubkey_bytes, message, sig_bytes):
        return AuthResult(ok=False, reason="Signature verification failed")

    return AuthResult(ok=True, user_id=user_id, pubkey_hex=pubkey_hex)


def _sha256_hex(data: bytes) -> str:
    if not data:
        return ""
    return hashlib.sha256(data).hexdigest()
