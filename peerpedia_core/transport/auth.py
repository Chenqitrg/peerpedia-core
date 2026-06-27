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

    Peerpedia <user_id>:<pubkey_hex>:<unix_timestamp>:<bodysha256_hex>:<signature_hex>

The signature covers ``<method>:<path>:<user_id>:<ts>:<body_hash>``.
Timestamp must be within ±30s of server time (replay window).
Body hash is SHA-256 hex, or "" for GET/empty requests.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from peerpedia_core.crypto import sha256_hex, sign_detached, validate_pubkey_hex, validate_sig_hex, verify_signature
from peerpedia_core.time import validate_timestamp


@dataclass
class AuthResult:
    """Result of ``verify_auth_header`` — check ``.ok``, read ``.reason`` on failure."""
    ok: bool
    user_id: str = ""
    pubkey_hex: str = ""
    reason: str = ""


@dataclass
class _ParsedHeader:
    """5 colon-separated fields extracted from the Authorization header."""
    user_id: str
    pubkey_hex: str
    ts: str
    body_hash: str
    sig_hex: str


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
    body_hash = sha256_hex(body)
    message = f"{method}:{path}:{user_id}:{ts}:{body_hash}".encode("utf-8")
    sig = sign_detached(private_key_bytes, message)
    return f"Peerpedia {user_id}:{pubkey_hex}:{ts}:{body_hash}:{sig.hex()}"


def verify_auth_header(
    header_value: str, method: str, path: str, *, body: bytes = b"",
) -> AuthResult:
    """Verify a ``Peerpedia`` auth header — pubkey is embedded, no DB needed."""
    parsed = _parse_auth_header(header_value)
    if isinstance(parsed, AuthResult):
        return parsed

    # ── Validate pubkey ──────────────────────────────────────────────────────
    try:
        pubkey_bytes = validate_pubkey_hex(parsed.pubkey_hex)
    except ValueError as e:
        return AuthResult(ok=False, reason=str(e))

    ts = validate_timestamp(parsed.ts)
    if isinstance(ts, str):
        return AuthResult(ok=False, reason=ts)

    try:
        sig_bytes = validate_sig_hex(parsed.sig_hex)
    except ValueError as e:
        return AuthResult(ok=False, reason=str(e))

    # ── Body hash ────────────────────────────────────────────────────────────
    actual_hash = sha256_hex(body)
    if parsed.body_hash != actual_hash:
        return AuthResult(ok=False,
            reason=f"Body hash mismatch (expected {actual_hash[:16]}..., "
                   f"got {parsed.body_hash[:16]}...)")

    # ── Verify signature ─────────────────────────────────────────────────────
    message = f"{method}:{path}:{parsed.user_id}:{parsed.ts}:{parsed.body_hash}".encode("utf-8")
    if not verify_signature(pubkey_bytes, message, sig_bytes):
        return AuthResult(ok=False, reason="Signature verification failed")

    return AuthResult(ok=True, user_id=parsed.user_id, pubkey_hex=parsed.pubkey_hex)


def _parse_auth_header(header_value: str) -> _ParsedHeader | AuthResult:
    """Extract the 5 colon-separated fields, or return an AuthResult failure."""
    try:
        scheme, payload = header_value.split(" ", 1)
        if scheme != "Peerpedia":
            return AuthResult(ok=False, reason="Authorization scheme must be 'Peerpedia'")
        parts = payload.split(":")
        if len(parts) != 5:
            return AuthResult(ok=False,
                reason=f"Expected 5 colon-separated fields, got {len(parts)}")
        return _ParsedHeader(user_id=parts[0], pubkey_hex=parts[1],
                              ts=parts[2], body_hash=parts[3], sig_hex=parts[4])
    except ValueError as e:
        return AuthResult(ok=False, reason=f"Malformed header: {e}")
