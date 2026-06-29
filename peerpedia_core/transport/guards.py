# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Transport-level guards — pure validation, no IO, no fetch_fn calls."""

from __future__ import annotations

from dataclasses import dataclass

from peerpedia_core.exceptions import BadRequestError
from peerpedia_core.crypto import (
    validate_pubkey_hex, validate_sig_hex, verify_body_hash, verify_signature,
)
from peerpedia_core.time import validate_timestamp
from peerpedia_core.transport.auth import _FIELD_COUNT, _SCHEME, AuthResult


@dataclass
class _ParsedHeader:
    """5 colon-separated fields extracted from the Authorization header."""
    user_id: str
    pubkey_hex: str
    ts: str
    body_hash: str
    sig_hex: str


def _parse_auth_header(header_value: str) -> _ParsedHeader | AuthResult:
    """Extract the 5 colon-separated fields, or return an AuthResult failure."""
    try:
        scheme, payload = header_value.split(" ", 1)
        if scheme != _SCHEME:
            return AuthResult(ok=False,
                reason=f"Authorization scheme must be '{_SCHEME}'")
        parts = payload.split(":")
        if len(parts) != _FIELD_COUNT:
            return AuthResult(ok=False,
                reason=f"Expected {_FIELD_COUNT} colon-separated fields, got {len(parts)}")
        return _ParsedHeader(user_id=parts[0], pubkey_hex=parts[1],
                              ts=parts[2], body_hash=parts[3], sig_hex=parts[4])
    except (BadRequestError, ValueError) as e:
        return AuthResult(ok=False, reason=f"Malformed header: {e}")


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
    except (BadRequestError, ValueError) as e:
        return AuthResult(ok=False, reason=str(e))

    ts = validate_timestamp(parsed.ts)
    if isinstance(ts, str):
        return AuthResult(ok=False, reason=ts)

    try:
        sig_bytes = validate_sig_hex(parsed.sig_hex)
    except (BadRequestError, ValueError) as e:
        return AuthResult(ok=False, reason=str(e))

    # ── Body hash ────────────────────────────────────────────────────────────
    try:
        verify_body_hash(body, parsed.body_hash)
    except (BadRequestError, ValueError) as e:
        return AuthResult(ok=False, reason=str(e))

    # ── Verify signature ─────────────────────────────────────────────────────
    message = f"{method}:{path}:{parsed.user_id}:{parsed.ts}:{parsed.body_hash}".encode("utf-8")
    if not verify_signature(pubkey_bytes, message, sig_bytes):
        return AuthResult(ok=False, reason="Signature verification failed")

    return AuthResult(ok=True, user_id=parsed.user_id, pubkey_hex=parsed.pubkey_hex)
