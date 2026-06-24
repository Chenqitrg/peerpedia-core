# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""HTTP transport for sync -- the only module that imports ``httpx``.

Every HTTP call in the entire project goes through this file.  If the
transport protocol changes (e.g. WebSocket, gRPC, Unix socket), only this
file needs to be replaced.  No other module knows about HTTP.

Functions -- each mirrors a server endpoint
-------------------------------------------

fetch_head(server, article_id) -> str | None
    GET /api/v1/articles/{id}/head -> server's HEAD hash, or None if 404.

push_bundle(server, article_id, bundle_bytes) -> None
    POST /api/v1/articles/{id}/sync with raw bundle bytes.
    Raises ConflictError on 409 (history diverged).

pull_article_repo(server, article_id) -> str | None
    GET /api/v1/articles/{id}/repo -> base64 tar.gz for first clone.

fetch_incremental_bundle(server, article_id, since_hash) -> bytes | None
    GET /api/v1/articles/{id}/bundle?since=<hash> -> incremental bundle bytes.

ancestor_probe(server, article_id) -> Callable[[str], bool]
    Returns a probe function for ``find_common_ancestor``.
    GET /api/v1/articles/{id}/ancestor/{hash} -> boolean.

fetch_article_source(server, article_id) -> (content, format) | None
    GET /api/v1/articles/{id}/source -> article text and format.

push_article_repo(server, article_id, bundle_b64) -> bool
    POST /api/v1/articles (first-time push).  Payload is base64-encoded
    tar.gz of the entire article repo.

Design -- replaceable transport
-------------------------------
This is the only file that imports ``httpx``.  To switch to a different
protocol, replace this file with one that exposes the same function
signatures.  ``bundle_client.py`` and ``bundle_server.py`` never import
``httpx`` directly.

Reviewer's checklist
--------------------
- Is every function using ``httpx`` via this module, not directly?
- Are timeouts set on every request?
- Are error responses (4xx, 5xx) handled distinctly from transport errors?
"""

import json

import httpx

from peerpedia_core.exceptions import ConflictError, ProtocolError, TransportError

# TODO(perf): every function uses standalone httpx.get/post() — no connection
# pooling.  Each sync_article cycle makes up to 14 HTTP calls, each paying
# TCP+TLS handshake (~50ms RTT × 14 = 700ms vs ~150ms with keep-alive).
# Fix: create a shared httpx.Client() instance and reuse it across all calls.


def _api_url(server: str, article_id: str) -> str:
    """Build the REST base URL for an article on a remote server."""
    return f"{server}/api/v1/articles/{article_id}"


def ancestor_probe(server: str, article_id: str):
    """Return a probe callback for ``find_common_ancestor``.

    The callback asks the server ``GET /ancestor/{hash}`` and returns
    ``True`` (200), ``False`` (404), or ``None`` (network error).
    """
    def probe(hash: str) -> bool | None:
        try:
            resp = httpx.get(
                f"{_api_url(server, article_id)}/ancestor/{hash}",
                timeout=30,
            )
            return resp.status_code == 200
        except httpx.HTTPError:
            return None

    return probe


def fetch_head(server: str, article_id: str) -> str | None:
    """GET /head → server's HEAD hash, or None if not found.

    Raises ``TransportError`` on network failure.
    Raises ``ProtocolError`` on malformed JSON response.
    """
    try:
        resp = httpx.get(f"{_api_url(server, article_id)}/head", timeout=30)
    except httpx.HTTPError as e:
        raise TransportError(
            f"fetch_head failed for {article_id} at {server}: {e}"
        ) from e

    if resp.status_code == 200:
        try:
            return resp.json().get("hash")
        except json.JSONDecodeError as e:
            raise ProtocolError(
                f"Malformed JSON from {server} for {article_id}/head"
            ) from e

    if resp.status_code == 404:
        return None

    raise ProtocolError(
        f"fetch_head: unexpected status {resp.status_code} from {server}"
    )


def push_bundle(server: str, article_id: str, bundle_bytes: bytes) -> None:
    """POST /sync with raw bundle bytes → None on success.

    Raises ``ConflictError`` on 409 (history diverged — pull first).
    Raises ``TransportError`` on network failure.
    Raises ``ProtocolError`` on unexpected status codes.
    """
    try:
        resp = httpx.post(
            f"{_api_url(server, article_id)}/sync",
            content=bundle_bytes,
            headers={"Content-Type": "application/octet-stream"},
            timeout=60,
        )
    except httpx.HTTPError as e:
        raise TransportError(
            f"push_bundle failed for {article_id} at {server}: {e}"
        ) from e

    if resp.status_code == 200:
        return

    if resp.status_code == 409:
        raise ConflictError(
            f"push_bundle: history diverged for {article_id} at {server}"
        )

    raise ProtocolError(
        f"push_bundle: unexpected status {resp.status_code} from {server}"
    )


def fetch_incremental_bundle(server: str, article_id: str, since_hash: str | None) -> bytes | None:
    """GET /bundle?since= → bundle bytes, or None if not found.

    Raises ``TransportError`` on network failure.
    Raises ``ProtocolError`` on unexpected status codes.
    """
    try:
        resp = httpx.get(
            f"{_api_url(server, article_id)}/bundle",
            params={"since": since_hash} if since_hash else None,
            timeout=60,
        )
    except httpx.HTTPError as e:
        raise TransportError(
            f"fetch_incremental_bundle failed for {article_id} at {server}: {e}"
        ) from e

    if resp.status_code == 200 and resp.content:
        return resp.content

    if resp.status_code == 404:
        return None

    raise ProtocolError(
        f"fetch_incremental_bundle: unexpected status {resp.status_code} from {server}"
    )


def pull_article_repo(server: str, article_id: str) -> str | None:
    """GET /api/v1/articles/{id}/repo → base64 tar.gz string, or None if 404.

    First-time clone — downloads the full article repo in the same format
    sent by ``push_article_repo``.  The caller unpacks with
    ``bundle/server.ingest_article`` semantics.
    """
    try:
        resp = httpx.get(
            f"{_api_url(server, article_id)}/repo",
            timeout=60,
        )
    except httpx.HTTPError as e:
        raise TransportError(
            f"pull_article_repo failed for {article_id} at {server}: {e}"
        ) from e

    if resp.status_code == 200:
        try:
            return resp.json().get("repo_bundle")
        except json.JSONDecodeError as e:
            raise ProtocolError(
                f"Malformed JSON from {server} for {article_id}/repo"
            ) from e

    if resp.status_code == 404:
        return None

    raise ProtocolError(
        f"pull_article_repo: unexpected status {resp.status_code} from {server}"
    )


def push_article_repo(server: str, article_id: str, bundle_b64: str) -> bool:
    """POST /api/v1/articles with base64 tar.gz → True on success.

    Only sends ``id`` and ``repo_bundle`` — the server unpacks the tar.gz
    to create the article repo and reads everything else from git history.

    Raises ``TransportError`` on network failure.
    """
    try:
        resp = httpx.post(
            f"{server}/api/v1/articles",
            json={
                "id": article_id,
                "repo_bundle": bundle_b64,
            },
            timeout=60,
        )
    except httpx.HTTPError as e:
        raise TransportError(
            f"push_article_repo failed for {article_id} at {server}: {e}"
        ) from e

    if resp.status_code in (200, 201):
        return True

    if resp.status_code == 409:
        return False

    raise ProtocolError(
        f"push_article_repo: unexpected status {resp.status_code} from {server}"
    )


def fetch_article_source(server: str, article_id: str) -> tuple[str, str] | None:
    """GET /api/v1/articles/{id}/source → (content, format) or None if 404.

    Returns the article's source text and format without requiring a full sync.
    """
    try:
        resp = httpx.get(
            f"{_api_url(server, article_id)}/source",
            timeout=30,
        )
    except httpx.HTTPError as e:
        raise TransportError(
            f"fetch_article_source failed for {article_id} at {server}: {e}"
        ) from e

    if resp.status_code == 200:
        try:
            data = resp.json()
            return data.get("content"), data.get("format", "markdown")
        except json.JSONDecodeError as e:
            raise ProtocolError(
                f"Malformed JSON from {server} for {article_id}/source"
            ) from e

    if resp.status_code == 404:
        return None

    raise ProtocolError(
        f"fetch_article_source: unexpected status {resp.status_code} from {server}"
    )


def fetch_search(
    server: str,
    q: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict] | None:
    """GET /api/v1/search?q=&status=&limit=&offset= → article list.

    Returns list of article dicts, or None if not found.
    """
    try:
        resp = httpx.get(
            f"{server}/api/v1/search",
            params={"q": q, "status": status, "limit": limit, "offset": offset},
            timeout=30,
        )
    except httpx.HTTPError as e:
        raise TransportError(f"fetch_search failed at {server}: {e}") from e

    if resp.status_code == 200:
        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise ProtocolError(f"Malformed JSON from {server}/search") from e

    raise ProtocolError(
        f"fetch_search: unexpected status {resp.status_code} from {server}"
    )


# ── Social discovery fetches ─────────────────────────────────────────────────


def fetch_following(server: str, user_id: str) -> list[dict] | None:
    """GET /users/{id}/following → list of user dicts, or None if not found.

    Raises ``TransportError`` on network failure.
    Raises ``ProtocolError`` on malformed JSON or unexpected status.
    """
    try:
        resp = httpx.get(
            f"{server}/api/v1/users/{user_id}/following",
            timeout=30,
        )
    except httpx.HTTPError as e:
        raise TransportError(
            f"fetch_following failed for {user_id} at {server}: {e}"
        ) from e

    if resp.status_code == 200:
        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise ProtocolError(
                f"Malformed JSON from {server} for users/{user_id}/following"
            ) from e

    if resp.status_code == 404:
        return None

    raise ProtocolError(
        f"fetch_following: unexpected status {resp.status_code} from {server}"
    )


def fetch_followers(server: str, user_id: str) -> list[dict] | None:
    """GET /users/{id}/followers → list of user dicts, or None if not found.

    Raises ``TransportError`` on network failure.
    Raises ``ProtocolError`` on malformed JSON or unexpected status.
    """
    try:
        resp = httpx.get(
            f"{server}/api/v1/users/{user_id}/followers",
            timeout=30,
        )
    except httpx.HTTPError as e:
        raise TransportError(
            f"fetch_followers failed for {user_id} at {server}: {e}"
        ) from e

    if resp.status_code == 200:
        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise ProtocolError(
                f"Malformed JSON from {server} for users/{user_id}/followers"
            ) from e

    if resp.status_code == 404:
        return None

    raise ProtocolError(
        f"fetch_followers: unexpected status {resp.status_code} from {server}"
    )


def push_follow(server: str, follower_id: str, followed_id: str) -> bool:
    """POST /users/{follower_id}/follow → True on success, False if not found.

    Raises ``TransportError`` on network failure.
    Raises ``ProtocolError`` on unexpected status codes.
    """
    try:
        resp = httpx.post(
            f"{server}/api/v1/users/{follower_id}/follow",
            json={"followed_id": followed_id},
            timeout=30,
        )
    except httpx.HTTPError as e:
        raise TransportError(
            f"push_follow failed for {follower_id} at {server}: {e}"
        ) from e

    if resp.status_code == 200:
        return True

    if resp.status_code == 404:
        return False

    raise ProtocolError(
        f"push_follow: unexpected status {resp.status_code} from {server}"
    )


def push_unfollow(server: str, follower_id: str, followed_id: str) -> bool:
    """POST /users/{follower_id}/unfollow → True on success, False if not found.

    Raises ``TransportError`` on network failure.
    Raises ``ProtocolError`` on unexpected status codes.
    """
    try:
        resp = httpx.post(
            f"{server}/api/v1/users/{follower_id}/unfollow",
            json={"followed_id": followed_id},
            timeout=30,
        )
    except httpx.HTTPError as e:
        raise TransportError(
            f"push_unfollow failed for {follower_id} at {server}: {e}"
        ) from e

    if resp.status_code == 200:
        return True

    if resp.status_code == 404:
        return False

    raise ProtocolError(
        f"push_unfollow: unexpected status {resp.status_code} from {server}"
    )


def fetch_user_articles(server: str, user_id: str, limit: int = 20, offset: int = 0) -> list[dict] | None:
    """GET /users/{id}/articles?limit=&offset= → list of article dicts, or None if not found.

    Raises ``TransportError`` on network failure.
    Raises ``ProtocolError`` on malformed JSON or unexpected status.
    """
    try:
        resp = httpx.get(
            f"{server}/api/v1/users/{user_id}/articles",
            params={"limit": limit, "offset": offset},
            timeout=30,
        )
    except httpx.HTTPError as e:
        raise TransportError(
            f"fetch_user_articles failed for {user_id} at {server}: {e}"
        ) from e

    if resp.status_code == 200:
        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise ProtocolError(
                f"Malformed JSON from {server} for users/{user_id}/articles"
            ) from e

    if resp.status_code == 404:
        return None

    raise ProtocolError(
        f"fetch_user_articles: unexpected status {resp.status_code} from {server}"
    )
