# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""HTTP implementations of the social transport protocol.

Each function here is a callback that can be wired into the corresponding
protocol function in ``transport/social.py`` via ``functools.partial``.
"""

import json

from peerpedia_core.exceptions import ProtocolError, TransportError
from peerpedia_core.transport.auth import build_auth_header
from peerpedia_core.transport.http._core import (
    _api_path, _call, _encode_body, _get, _require_json_or_none, _post, _user_path,
    _require_ok_or_404,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Social graph callbacks
# ═══════════════════════════════════════════════════════════════════════════════


def _fetch_following(
    server: str, user_id: str, *,
    private_key_bytes: bytes | None = None, pubkey_hex: str = "",
) -> list[dict] | None:
    """GET /users/{id}/following → list of user dicts, or None."""
    return _get(
        server, _user_path(user_id, "following"), user_id,
        private_key_bytes=private_key_bytes, pubkey_hex=pubkey_hex,
        context="fetch_following",
    )


def _fetch_followers(
    server: str, user_id: str, *,
    private_key_bytes: bytes | None = None, pubkey_hex: str = "",
) -> list[dict] | None:
    """GET /users/{id}/followers → list of user dicts, or None."""
    return _get(
        server, _user_path(user_id, "followers"), user_id,
        private_key_bytes=private_key_bytes, pubkey_hex=pubkey_hex,
        context="fetch_followers",
    )


def _push_follow(
    server: str, follower_id: str, followed_id: str, *,
    private_key_bytes: bytes | None = None, pubkey_hex: str = "",
) -> bool:
    """POST /users/{follower_id}/follow → True on success, False on 404."""
    return _post(
        server, _user_path(follower_id, "follow"),
        {"followed_id": followed_id}, follower_id,
        private_key_bytes=private_key_bytes, pubkey_hex=pubkey_hex,
        context="push_follow",
    )


def _push_unfollow(
    server: str, follower_id: str, followed_id: str, *,
    private_key_bytes: bytes | None = None, pubkey_hex: str = "",
) -> bool:
    """DELETE /users/{id}/follow → True on success, False on 404."""
    path = _user_path(follower_id, "follow")
    body = _encode_body({"followed_id": followed_id})
    headers = build_auth_header("DELETE", path, follower_id,
                                private_key_bytes, pubkey_hex, body=body)
    resp = _call("DELETE", server, path, follower_id,
                 "push_unfollow", content=body, headers=headers)
    if resp.status_code == 200:
        return True
    if resp.status_code == 404:
        return False
    raise ProtocolError(
        f"push_unfollow: unexpected status {resp.status_code} from {server}")


# ═══════════════════════════════════════════════════════════════════════════════
# Key rotation callbacks
# ═══════════════════════════════════════════════════════════════════════════════


def _push_key_rotation(
    server: str, user_id: str, new_pubkey_hex: str, *,
    private_key_bytes: bytes, pubkey_hex: str = "",
) -> bool:
    """POST /api/v1/users/{user_id}/rotate-key → True on success."""
    return _post(
        server, _user_path(user_id, "rotate-key"),
        {"public_key": new_pubkey_hex}, user_id,
        private_key_bytes=private_key_bytes, pubkey_hex=pubkey_hex,
        context="push_key_rotation",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Shares callbacks
# ═══════════════════════════════════════════════════════════════════════════════


def _push_share(
    server: str, sharer_id: str, article_id: str,
    recipient_id: str | None, comment: str | None, *,
    private_key_bytes: bytes | None = None, pubkey_hex: str = "",
) -> bool:
    """POST /api/v1/users/{sharer_id}/share → True on success."""
    return _post(
        server, _user_path(sharer_id, "share"),
        {"article_id": article_id, "recipient_id": recipient_id,
         "comment": comment},
        sharer_id,
        private_key_bytes=private_key_bytes, pubkey_hex=pubkey_hex,
        context="push_share",
    )


def _push_share_remove(
    server: str, sharer_id: str, article_id: str, *,
    private_key_bytes: bytes, pubkey_hex: str = "",
) -> bool:
    """DELETE /api/v1/users/{sharer_id}/share → True on success."""
    path = _user_path(sharer_id, "share")
    body = _encode_body({"article_id": article_id})
    headers = build_auth_header("DELETE", path, sharer_id, private_key_bytes,
                                pubkey_hex, body=body)
    resp = _call("DELETE", server, path, sharer_id,
                 "push_share_remove", content=body, headers=headers)
    return _require_ok_or_404(resp, server, "push_share_remove")


def _fetch_shares(
    server: str, user_id: str, *,
    private_key_bytes: bytes | None = None, pubkey_hex: str = "",
) -> list[dict] | None:
    """GET /api/v1/users/{user_id}/shares → list of share dicts, or None."""
    return _get(
        server, _user_path(user_id, "shares"), user_id,
        private_key_bytes=private_key_bytes, pubkey_hex=pubkey_hex,
        context="fetch_shares",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Discovery callbacks — peers, users, school, notifications
# ═══════════════════════════════════════════════════════════════════════════════


def _fetch_notifications(
    server: str, user_id: str, *,
    private_key_bytes: bytes | None = None, pubkey_hex: str = "",
) -> list[dict] | None:
    """GET /api/v1/users/{user_id}/notifications → list of notification dicts."""
    return _get(
        server, _user_path(user_id, "notifications"), user_id,
        private_key_bytes=private_key_bytes, pubkey_hex=pubkey_hex,
        context="fetch_notifications",
    )


def _fetch_peers(server: str) -> list[str]:
    """GET /api/v1/peers → list of known peer URLs."""
    resp = _call("GET", server, _api_path("peers"), "", "fetch_peers")
    if resp.status_code == 200:
        try:
            return resp.json().get("peers", [])
        except json.JSONDecodeError as e:
            raise ProtocolError(f"Malformed JSON from {server}/peers") from e
    raise ProtocolError(
        f"fetch_peers: unexpected status {resp.status_code} from {server}")


def _push_peer_registration(server: str, own_url: str) -> bool:
    """POST /api/v1/peers to announce this server."""
    resp = _call("POST", server, _api_path("peers"), "",
                 "push_peer_registration", json={"url": own_url})
    return _require_ok_or_404(resp, server, "push_peer_registration")


def _fetch_user(server: str, user_id: str) -> dict | None:
    """GET /api/v1/users/{user_id} → user metadata dict, or None if 404."""
    resp = _call("GET", server, _user_path(user_id), user_id, "fetch_user")
    return _require_json_or_none(resp, server, "fetch_user")


def _fetch_school(server: str, limit: int) -> list[dict]:
    """GET /api/v1/school → top users by follower count (public, no auth)."""
    resp = _call("GET", server, _api_path("school"), "", "fetch_school",
                 params={"limit": limit})
    if resp.status_code != 200:
        raise ProtocolError(
            f"fetch_school: unexpected status {resp.status_code} from {server}")
    try:
        data = resp.json()
    except json.JSONDecodeError as e:
        raise TransportError(f"Failed to fetch school from {server}: {e}") from e
    if not isinstance(data, list):
        raise ProtocolError(
            f"Malformed school response from {server}: expected list, "
            f"got {type(data).__name__}")
    return data
