# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Transport-level guards — validate HTTP/P2P auth headers and responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from peerpedia_core.crypto import validate_pubkey_hex, validate_sig_hex, verify_body_hash, verify_signature
from peerpedia_core.exceptions import ProtocolError, TransportError
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
    except ValueError as e:
        return AuthResult(ok=False, reason=f"Malformed header: {e}")


def require_private_key(private_key_bytes: bytes | None, label: str) -> bytes:
    """Return *private_key_bytes*, or raise ValueError if None."""
    if not private_key_bytes:
        raise ValueError(f"private_key_bytes is required for {label}")
    return private_key_bytes


def require_fetch_response(
    fetch_fn: Callable, server: str, user_id: str, label: str, **auth_kwargs,
) -> list[dict]:
    """Call *fetch_fn*, raise on failure or None response. Returns data."""
    try:
        data = fetch_fn(server, user_id, **auth_kwargs)
    except TransportError as e:
        raise ConnectionError(
            f"Failed to fetch {label} from {server} for {user_id}: {e.detail}"
        ) from e
    if data is None:
        raise ProtocolError(
            f"fetch_{label}: server {server} returned None for user {user_id}"
        )
    return data


def fetch_with_auth_fallback(
    fetch_fn: Callable, server: str, user_id: str, **auth_kwargs,
) -> list[dict] | None:
    """Try unauth first; on 401/403, retry with Ed25519 signing."""
    # ── First attempt ────────────────────────────────────────────────────────
    data, retry = try_fetch(fetch_fn, server, user_id)
    if data is not None:
        return data
    if not retry or not auth_kwargs:
        return None

    # ── Auth retry ──────────────────────────────────────────────────────────
    return try_fetch(fetch_fn, server, user_id, **auth_kwargs)[0]


def try_fetch(fetch_fn, server, user_id, **kwargs) -> tuple[list[dict] | None, bool]:
    """Call *fetch_fn*, swallowing errors. Returns ``(data, should_retry)``.

    ``should_retry`` is True on 401/403 — the caller should retry with auth.
    """
    try:
        return fetch_fn(server, user_id, **kwargs), False
    except TransportError:
        return None, False
    except ProtocolError as e:
        return None, _is_auth_required(e)


def _is_auth_required(error: ProtocolError) -> bool:
    """Return True if *error* is an auth-related HTTP status (401/403)."""
    return getattr(error, "status_code", None) in (401, 403)


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
    try:
        verify_body_hash(body, parsed.body_hash)
    except ValueError as e:
        return AuthResult(ok=False, reason=str(e))

    # ── Verify signature ─────────────────────────────────────────────────────
    message = f"{method}:{path}:{parsed.user_id}:{parsed.ts}:{parsed.body_hash}".encode("utf-8")
    if not verify_signature(pubkey_bytes, message, sig_bytes):
        return AuthResult(ok=False, reason="Signature verification failed")

    return AuthResult(ok=True, user_id=parsed.user_id, pubkey_hex=parsed.pubkey_hex)
