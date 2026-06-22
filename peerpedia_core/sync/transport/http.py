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

push_bundle(server, article_id, bundle_bytes) -> str
    POST /api/v1/articles/{id}/sync with raw bundle bytes.
    Returns "ok", "conflict", or "error".

fetch_bundle(server, article_id, since_hash) -> bytes | None
    GET /api/v1/articles/{id}/bundle?since=<hash> -> raw bundle bytes.

ancestor_probe(server, article_id) -> Callable[[str], bool]
    Returns a probe function for ``find_common_ancestor``.
    GET /api/v1/articles/{id}/ancestor/{hash} -> boolean.

post_article(server, article_id, bundle_b64) -> bool
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

import httpx

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
        except Exception:
            return None

    return probe


def fetch_head(server: str, article_id: str) -> str | None:
    """GET /head → server's HEAD hash, or None if not found / unreachable."""
    try:
        resp = httpx.get(f"{_api_url(server, article_id)}/head", timeout=30)
        if resp.status_code == 200:
            # TODO(perf): resp.json() parses full JSON for a single field.
            # Use resp.text and simple extraction for the "hash" value.
            return resp.json().get("hash")
    except Exception:
        pass
    return None


def push_bundle(server: str, article_id: str, bundle_bytes: bytes) -> str:
    """POST /sync → "ok" | "conflict" | "error"."""
    try:
        resp = httpx.post(
            f"{_api_url(server, article_id)}/sync",
            content=bundle_bytes,
            headers={"Content-Type": "application/octet-stream"},
            timeout=60,
        )
        if resp.status_code == 200:
            return "ok"
        if resp.status_code == 409:
            return "conflict"
    except Exception:
        pass
    return "error"


def fetch_bundle(server: str, article_id: str, since_hash: str | None) -> bytes | None:
    """GET /bundle?since= → bundle bytes, or None."""
    try:
        resp = httpx.get(
            f"{_api_url(server, article_id)}/bundle",
            params={"since": since_hash} if since_hash else None,
            timeout=60,
        )
        if resp.status_code == 200 and resp.content:
            return resp.content
    except Exception:
        pass
    return None


def post_article(server: str, article_id: str, bundle_b64: str) -> bool:
    """POST /articles with base64 tar.gz → True on success."""
    try:
        resp = httpx.post(
            f"{_api_url(server, '')}s",
            json={
                "id": article_id,
                "title": "",
                "content": "",
                "format": "markdown",
                "commit_message": "Initial push",
                "repo_bundle": bundle_b64,
            },
            timeout=60,
        )
        return resp.status_code in (200, 201)
    except Exception:
        return False
