# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""HTTP transport — social graph, discovery, key rotation, shares.

All social-layer HTTP calls: follow/unfollow, user profiles, school,
peers, shares, notifications, key rotation.
Imported by ``http_client.py`` (facade) — external code uses
``from peerpedia_core.transport import ...``.

All public functions raise ``TransportError`` on network failure and
``ProtocolError`` on unexpected server responses.  ``push_key_rotation``
and ``push_share*`` raise ``ValueError`` if ``private_key_bytes`` is missing.
"""

import json

import httpx

from peerpedia_core.exceptions import ProtocolError, TransportError
from peerpedia_core.transport import _http_core as _core
from peerpedia_core.transport._http_core import (
    _encode_body, _json_or_none, _signed_get, _signed_post,
)
from peerpedia_core.transport.auth import sign_auth_header


# ═══════════════════════════════════════════════════════════════════════════════
# Social graph
# ═══════════════════════════════════════════════════════════════════════════════


def fetch_following(server: str, user_id: str, *,
                    private_key_bytes: bytes | None = None,
                    pubkey_hex: str = "") -> list[dict] | None:
    """GET /users/{id}/following → list of user dicts, or None if not found."""
    return _signed_get(
        server, f"/api/v1/users/{user_id}/following", user_id,
        private_key_bytes=private_key_bytes, pubkey_hex=pubkey_hex,
        label="fetch_following",
    )


def fetch_followers(server: str, user_id: str, *,
                    private_key_bytes: bytes | None = None,
                    pubkey_hex: str = "") -> list[dict] | None:
    """GET /users/{id}/followers → list of user dicts, or None if not found."""
    return _signed_get(
        server, f"/api/v1/users/{user_id}/followers", user_id,
        private_key_bytes=private_key_bytes, pubkey_hex=pubkey_hex,
        label="fetch_followers",
    )


def push_follow(server: str, follower_id: str, followed_id: str, *,
                private_key_bytes: bytes | None = None,
                pubkey_hex: str = "") -> bool:
    """POST /users/{follower_id}/follow → True on success, False if not found."""
    return _signed_post(
        server, f"/api/v1/users/{follower_id}/follow",
        {"followed_id": followed_id},
        follower_id,
        private_key_bytes=private_key_bytes,
        pubkey_hex=pubkey_hex,
        label="push_follow",
    )


def push_unfollow(server: str, follower_id: str, followed_id: str, *,
                  private_key_bytes: bytes | None = None,
                  pubkey_hex: str = "") -> bool:
    """POST /users/{follower_id}/unfollow → True on success, False if not found."""
    return _signed_post(
        server, f"/api/v1/users/{follower_id}/unfollow",
        {"followed_id": followed_id},
        follower_id,
        private_key_bytes=private_key_bytes,
        pubkey_hex=pubkey_hex,
        label="push_unfollow",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Key rotation
# ═══════════════════════════════════════════════════════════════════════════════


def push_key_rotation(
    server: str, user_id: str, new_pubkey_hex: str, *,
    private_key_bytes: bytes,
    pubkey_hex: str = "",
) -> bool:
    """POST /api/v1/users/{user_id}/rotate-key → True on success.

    The request is signed with the user's current private key.
    *private_key_bytes* is required — key rotation without auth is rejected.
    The server verifies the signature and updates the stored public key.
    """
    if not private_key_bytes:
        raise ValueError("private_key_bytes is required for key rotation")
    return _signed_post(
        server, f"/api/v1/users/{user_id}/rotate-key",
        {"public_key": new_pubkey_hex},
        user_id,
        private_key_bytes=private_key_bytes,
        pubkey_hex=pubkey_hex,
        label="push_key_rotation",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Shares
# ═══════════════════════════════════════════════════════════════════════════════


def push_share(
    server: str, sharer_id: str, article_id: str, *,
    recipient_id: str | None = None, comment: str | None = None,
    private_key_bytes: bytes | None = None,
    pubkey_hex: str = "",
) -> bool:
    """POST /api/v1/users/{sharer_id}/share → True on success."""
    if not private_key_bytes:
        raise ValueError("private_key_bytes is required for share push")
    return _signed_post(
        server, f"/api/v1/users/{sharer_id}/share",
        {"article_id": article_id, "recipient_id": recipient_id, "comment": comment},
        sharer_id,
        private_key_bytes=private_key_bytes,
        pubkey_hex=pubkey_hex,
        label="push_share",
    )


def push_share_remove(
    server: str, sharer_id: str, article_id: str, *,
    private_key_bytes: bytes,
    pubkey_hex: str = "",
) -> bool:
    """DELETE /api/v1/users/{sharer_id}/share → True on success.

    Propagates share removal to peers so the social graph stays consistent.
    *private_key_bytes* is required — share removal without auth is rejected.
    """
    if not private_key_bytes:
        raise ValueError("private_key_bytes is required for share removal")
    path = f"/api/v1/users/{sharer_id}/share"
    body = _encode_body({"article_id": article_id})
    headers: dict[str, str] = {
        "Authorization": sign_auth_header(
            "DELETE", path, sharer_id, private_key_bytes, pubkey_hex=pubkey_hex, body=body,
        ),
    }
    try:
        resp = _core._get_client().request(
            "DELETE", f"{server}{path}", content=body, headers=headers,
        )
    except httpx.HTTPError as e:
        raise TransportError(
            f"push_share_remove failed for {sharer_id} at {server}: {e}"
        ) from e
    if resp.status_code == 200:
        return True
    if resp.status_code == 404:
        return False
    raise ProtocolError(
        f"push_share_remove: unexpected status {resp.status_code} from {server}"
    )


def fetch_shares(server: str, user_id: str, *,
                 private_key_bytes: bytes | None = None,
                 pubkey_hex: str = "") -> list[dict] | None:
    """GET /api/v1/users/{user_id}/shares → list of share dicts, or None."""
    return _signed_get(
        server, f"/api/v1/users/{user_id}/shares", user_id,
        private_key_bytes=private_key_bytes, pubkey_hex=pubkey_hex,
        label="fetch_shares",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Discovery — peers, users, school, notifications
# ═══════════════════════════════════════════════════════════════════════════════


def fetch_notifications(server: str, user_id: str, *,
                        private_key_bytes: bytes | None = None,
                        pubkey_hex: str = "") -> list[dict] | None:
    """GET /api/v1/users/{user_id}/notifications → list of notification dicts, or None."""
    return _signed_get(
        server, f"/api/v1/users/{user_id}/notifications", user_id,
        private_key_bytes=private_key_bytes, pubkey_hex=pubkey_hex,
        label="fetch_notifications",
    )


def fetch_peers(server: str) -> list[str]:
    """GET /api/v1/peers → list of known peer URLs for discovery."""
    try:
        resp = _core._get_client().get(f"{server}/api/v1/peers")
    except httpx.HTTPError as e:
        raise TransportError(
            f"Failed to fetch peers from {server}: {e}"
        ) from e

    if resp.status_code == 200:
        try:
            return resp.json().get("peers", [])
        except json.JSONDecodeError as e:
            raise ProtocolError(
                f"Malformed JSON from {server}/peers"
            ) from e
    raise ProtocolError(
        f"fetch_peers: unexpected status {resp.status_code} from {server}"
    )


def push_peer_registration(server: str, own_url: str) -> bool:
    """POST /api/v1/peers to announce this server to *server*.

    Returns True on success.  Idempotent — calling with an already-known
    URL is a no-op on the server.
    """
    try:
        resp = _core._get_client().post(
            f"{server}/api/v1/peers",
            json={"url": own_url},
        )
    except httpx.HTTPError as e:
        raise TransportError(
            f"Failed to register with peer {server}: {e}"
        ) from e
    if resp.status_code == 200:
        return True
    raise ProtocolError(
        f"push_peer_registration: unexpected status {resp.status_code} from {server}"
    )


def fetch_user(server: str, user_id: str) -> dict | None:
    """GET /api/v1/users/{user_id} → user metadata dict, or None if 404."""
    try:
        resp = _core._get_client().get(f"{server}/api/v1/users/{user_id}")
    except httpx.HTTPError as e:
        raise TransportError(f"fetch_user failed for {user_id} at {server}: {e}") from e
    return _json_or_none(resp, server, "fetch_user")


def fetch_school(server: str, limit: int = 20) -> list[dict]:
    """GET /api/v1/school → top users by follower count (public, no auth).

    Returns a list of ``{"id": str, "name": str, "follower_count": int}``.
    Raises ``TransportError`` on network failure, ``ProtocolError`` on
    malformed response.
    """
    import json as _json
    client = _core._get_client()
    try:
        resp = client.get(f"{server}/api/v1/school", params={"limit": limit})
        if resp.status_code != 200:
            raise ProtocolError(
                f"fetch_school: unexpected status {resp.status_code} from {server}"
            )
        data = resp.json()
        if not isinstance(data, list):
            raise ProtocolError(
                f"Malformed school response from {server}: expected list, "
                f"got {type(data).__name__}"
            )
        return data
    except (httpx.HTTPError, _json.JSONDecodeError) as e:
        raise TransportError(
            f"Failed to fetch school from {server}: {e}"
        ) from e
