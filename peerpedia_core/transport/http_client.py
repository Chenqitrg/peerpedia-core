# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""HTTP transport for sync -- the only module that imports ``httpx``.

Every HTTP call in the entire project goes through this file.  If the
transport protocol changes (e.g. WebSocket, gRPC, Unix socket), only this
file needs to be replaced.  No other module knows about HTTP.

Uses a shared ``httpx.Client`` for connection pooling — a single sync cycle
can make 14 HTTP calls; without keep-alive each pays TCP+TLS (~50ms RTT).
With pooling, all requests on the same host reuse one connection.

All public functions raise ``TransportError`` on network failure and
``ProtocolError`` on unexpected server responses.  Functions that accept
a ``private_key_bytes`` parameter also raise ``ValueError`` if it is
missing.  Callers should catch ``TransportError`` for retryable errors
and ``ProtocolError`` for non-retryable protocol mismatches.
"""

import json
import threading

import httpx

from peerpedia_core.exceptions import ConflictError, ProtocolError, TransportError
from peerpedia_core.transport.auth import sign_auth_header

_client: httpx.Client | None = None
_client_lock = threading.Lock()


def _get_client() -> httpx.Client:
    """Return a shared ``httpx.Client`` with connection pooling (thread-safe)."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = httpx.Client(
                    limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                    timeout=httpx.Timeout(30.0),
                )
    return _client


def close_client() -> None:
    """Close the shared HTTP client (call on shutdown)."""
    global _client
    with _client_lock:
        if _client is not None:
            _client.close()
            _client = None


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _api_url(server: str, article_id: str) -> str:
    """Build the REST base URL for an article on a remote server."""
    return f"{server}/api/v1/articles/{article_id}"


def _encode_body(data: dict) -> bytes:
    """Serialize a dict to JSON bytes for HTTP request bodies."""
    return json.dumps(data).encode("utf-8")


def _json_or_none(resp: httpx.Response, server: str, context: str) -> dict | list | None:
    """Parse a 200/404 response: JSON on 200, None on 404, ProtocolError otherwise."""
    if resp.status_code == 200:
        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise ProtocolError(f"Malformed JSON from {server} for {context}") from e
    if resp.status_code == 404:
        return None
    raise ProtocolError(f"{context}: unexpected status {resp.status_code} from {server}")


def _signed_post(
    server: str, path: str, body_dict: dict, user_id: str, *,
    private_key_bytes: bytes | None = None,
    pubkey_hex: str = "",
    label: str = "",
) -> bool:
    """POST to a peer with Ed25519 auth. Returns True on 200, False on 404."""
    body = _encode_body(body_dict)
    headers: dict[str, str] = {}
    if private_key_bytes:
        headers["Authorization"] = sign_auth_header(
            "POST", path, user_id, private_key_bytes, pubkey_hex=pubkey_hex, body=body,
        )
    try:
        resp = _get_client().post(f"{server}{path}", content=body, headers=headers)
    except httpx.HTTPError as e:
        raise TransportError(f"{label} failed for {user_id} at {server}: {e}") from e
    if resp.status_code == 200:
        return True
    if resp.status_code == 404:
        return False
    raise ProtocolError(f"{label}: unexpected status {resp.status_code} from {server}")


def _signed_get(
    server: str, path: str, user_id: str, *,
    private_key_bytes: bytes | None = None,
    pubkey_hex: str = "",
    label: str = "",
    params: dict | None = None,
) -> dict | list | None:
    """GET from a peer with optional Ed25519 auth. Returns JSON on 200, None on 404."""
    headers: dict[str, str] = {}
    if private_key_bytes:
        headers["Authorization"] = sign_auth_header(
            "GET", path, user_id, private_key_bytes, pubkey_hex=pubkey_hex,
        )
    try:
        resp = _get_client().get(f"{server}{path}", headers=headers, params=params)
    except httpx.HTTPError as e:
        raise TransportError(f"{label} failed for {user_id} at {server}: {e}") from e
    return _json_or_none(resp, server, label)


# ═══════════════════════════════════════════════════════════════════════════════
# Article sync
# ═══════════════════════════════════════════════════════════════════════════════


def ancestor_probe(server: str, article_id: str):
    """Return a probe callback for ``find_common_ancestor``.

    The callback asks the server ``GET /ancestor/{hash}`` and returns
    ``True`` (200), ``False`` (404), or ``None`` (network error).
    """
    client = _get_client()

    def probe(hash: str) -> bool | None:
        try:
            resp = client.get(
                f"{_api_url(server, article_id)}/ancestor/{hash}",
            )
            return resp.status_code == 200
        except httpx.HTTPError:
            return None

    return probe


def fetch_head(server: str, article_id: str) -> str | None:
    """GET /head → server's HEAD hash, or None if not found."""
    try:
        resp = _get_client().get(f"{_api_url(server, article_id)}/head")
    except httpx.HTTPError as e:
        raise TransportError(f"fetch_head failed for {article_id} at {server}: {e}") from e

    data = _json_or_none(resp, server, "fetch_head")
    if data is not None:
        return data.get("hash")
    return None


def push_bundle(server: str, article_id: str, bundle_bytes: bytes) -> None:
    """POST /sync with raw bundle bytes → None on success.
    Raises ConflictError on history divergence."""
    try:
        resp = _get_client().post(
            f"{_api_url(server, article_id)}/sync",
            content=bundle_bytes,
            headers={"Content-Type": "application/octet-stream"},
            timeout=60,
        )
    except httpx.HTTPError as e:
        raise TransportError(f"push_bundle failed for {article_id} at {server}: {e}") from e

    if resp.status_code == 200:
        return
    if resp.status_code == 409:
        raise ConflictError(f"push_bundle: history diverged for {article_id} at {server}")
    raise ProtocolError(f"push_bundle: unexpected status {resp.status_code} from {server}")


def fetch_incremental_bundle(server: str, article_id: str, since_hash: str | None) -> bytes | None:
    """GET /bundle?since= → bundle bytes, or None if not found."""
    try:
        resp = _get_client().get(
            f"{_api_url(server, article_id)}/bundle",
            params={"since": since_hash} if since_hash else None,
            timeout=60,
        )
    except httpx.HTTPError as e:
        raise TransportError(f"fetch_incremental_bundle failed for {article_id} at {server}: {e}") from e

    if resp.status_code == 200 and resp.content:
        return resp.content
    if resp.status_code == 404:
        return None
    raise ProtocolError(f"fetch_incremental_bundle: unexpected status {resp.status_code} from {server}")


def fetch_article_repo(server: str, article_id: str) -> str | None:
    """GET /api/v1/articles/{id}/repo → base64 tar.gz string, or None if 404."""
    try:
        resp = _get_client().get(f"{_api_url(server, article_id)}/repo", timeout=60)
    except httpx.HTTPError as e:
        raise TransportError(f"fetch_article_repo failed for {article_id} at {server}: {e}") from e

    data = _json_or_none(resp, server, "fetch_article_repo")
    if data is not None:
        return data.get("repo_bundle")
    return None


def push_article_repo(server: str, article_id: str, bundle_b64: str) -> bool:
    """POST /api/v1/articles with base64 tar.gz → True on success."""
    try:
        resp = _get_client().post(
            f"{server}/api/v1/articles",
            json={"id": article_id, "repo_bundle": bundle_b64},
            timeout=60,
        )
    except httpx.HTTPError as e:
        raise TransportError(f"push_article_repo failed for {article_id} at {server}: {e}") from e

    if resp.status_code in (200, 201):
        return True
    if resp.status_code == 409:
        return False
    raise ProtocolError(f"push_article_repo: unexpected status {resp.status_code} from {server}")


def fetch_article_source(server: str, article_id: str) -> tuple[str, str] | None:
    """GET /api/v1/articles/{id}/source → (content, format) or None if 404."""
    try:
        resp = _get_client().get(f"{_api_url(server, article_id)}/source")
    except httpx.HTTPError as e:
        raise TransportError(f"fetch_article_source failed for {article_id} at {server}: {e}") from e

    data = _json_or_none(resp, server, "fetch_article_source")
    if data is not None:
        return data.get("content"), data.get("format", "markdown")
    return None


def fetch_search(
    server: str, q: str | None = None, status: str | None = None,
    limit: int = 20, offset: int = 0,
) -> list[dict] | None:
    """GET /api/v1/search?q=&status=&limit=&offset= → article list."""
    try:
        resp = _get_client().get(
            f"{server}/api/v1/search",
            params={"q": q, "status": status, "limit": limit, "offset": offset},
        )
    except httpx.HTTPError as e:
        raise TransportError(f"fetch_search failed at {server}: {e}") from e

    if resp.status_code == 200:
        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise ProtocolError(f"Malformed JSON from {server}/search") from e
    raise ProtocolError(f"fetch_search: unexpected status {resp.status_code} from {server}")


# ═══════════════════════════════════════════════════════════════════════════════
# Social discovery
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


def fetch_article_meta(server: str, article_id: str) -> dict | None:
    """GET /api/v1/articles/{id} → article metadata dict, or None if 404."""
    try:
        resp = _get_client().get(f"{_api_url(server, article_id)}")
    except httpx.HTTPError as e:
        raise TransportError(f"fetch_article_meta failed for {article_id} at {server}: {e}") from e
    data = _json_or_none(resp, server, "fetch_article_meta")
    if data is not None:
        return data
    return None


def fetch_user_articles(server: str, user_id: str, limit: int = 20, offset: int = 0, *,
                        private_key_bytes: bytes | None = None,
                        pubkey_hex: str = "") -> list[dict] | None:
    """GET /users/{id}/articles?limit=&offset= → list of article dicts, or None if not found."""
    return _signed_get(
        server, f"/api/v1/users/{user_id}/articles", user_id,
        private_key_bytes=private_key_bytes, pubkey_hex=pubkey_hex,
        label="fetch_user_articles",
        params={"limit": limit, "offset": offset},
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
# Share
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
        resp = _get_client().request(
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
        resp = _get_client().get(f"{server}/api/v1/peers")
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
        resp = _get_client().post(
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
        resp = _get_client().get(f"{server}/api/v1/users/{user_id}")
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
    client = _get_client()
    try:
        resp = client.get(f"{server}/api/v1/school", params={"limit": limit})
        resp.raise_for_status()
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
