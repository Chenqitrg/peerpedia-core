# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""HTTP transport for sync — the only module that imports ``httpx``.

When PeerPedia switches to a different transport (WebSocket, direct TCP, file
exchange), replace this module without touching ``bundle_client`` or
``bundle_server``.
"""

import httpx


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
