# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Peerpedia auth protocol — types and signing.

Verification lives in ``transport/guards.py``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from peerpedia_core.crypto import sha256_hex, sign_detached


# ── Protocol constants ───────────────────────────────────────────────────────

_SCHEME = "Peerpedia"
"""Auth scheme name in the ``Authorization`` header."""

_FIELD_COUNT = 5
"""Header format: ``Peerpedia <uid>:<pubkey>:<ts>:<body_hash>:<sig>``.

The signature covers ``<method>:<path>:<uid>:<ts>:<body_hash>``.
"""


@dataclass
class AuthResult:
    """Result of auth verification — check ``.ok``, read ``.reason`` on failure."""
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
    """
    ts = str(int(time.time()))
    body_hash = sha256_hex(body)
    message = f"{method}:{path}:{user_id}:{ts}:{body_hash}".encode("utf-8")
    sig = sign_detached(private_key_bytes, message)
    return f"{_SCHEME} {user_id}:{pubkey_hex}:{ts}:{body_hash}:{sig.hex()}"


def build_auth_header(
    method: str, path: str, user_id: str,
    private_key_bytes: bytes | None, pubkey_hex: str,
    *, body: bytes = b"",
) -> dict[str, str]:
    """Return an ``Authorization`` header dict, or ``{}`` if no credentials."""
    if not private_key_bytes:
        return {}
    return {"Authorization": sign_auth_header(
        method, path, user_id, private_key_bytes, pubkey_hex=pubkey_hex, body=body,
    )}
