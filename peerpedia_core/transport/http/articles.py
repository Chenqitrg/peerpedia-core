# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""HTTP transport — article sync, bundle protocol, search, metadata.

All article-level HTTP calls: head, bundle, repo, source, search, meta.
Imported by ``http_client.py`` (facade) — external code uses
``from peerpedia_core.transport import ...``.

All public functions raise ``TransportError`` on network failure and
``ProtocolError`` on unexpected server responses.
"""

from peerpedia_core.exceptions import ConflictError, ProtocolError, TransportError
from peerpedia_core.time import SYNC_TIMEOUT_SECONDS
from peerpedia_core.transport.http._core import (
    _api_path, _article_path, _call, _get, _require_json_or_none, _user_path,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Sync protocol
# ═══════════════════════════════════════════════════════════════════════════════


def ancestor_probe(server: str, article_id: str):
    """Return a callback for ``find_common_ancestor`` — returns True/False/None."""

    def probe(hash: str) -> bool | None:
        try:
            resp = _call("GET", server, _article_path(article_id, f"ancestor/{hash}"),
                          article_id, "ancestor_probe")
            return resp.status_code == 200
        except TransportError:
            return None

    return probe


def fetch_head(server: str, article_id: str) -> str | None:
    """GET /head → server's HEAD hash, or None if not found."""
    resp = _call("GET", server, _article_path(article_id, "head"), article_id, "fetch_head")
    data = _require_json_or_none(resp, server, "fetch_head")
    if data is not None:
        return data.get("hash")
    return None


def push_bundle(server: str, article_id: str, bundle_bytes: bytes) -> None:
    """POST /sync with raw bundle bytes → None on success.
    Raises ConflictError on history divergence."""
    resp = _call("POST", server, _article_path(article_id, "sync"), article_id,
                  "push_bundle", content=bundle_bytes,
                  headers={"Content-Type": "application/octet-stream"},
                  timeout=SYNC_TIMEOUT_SECONDS)
    if resp.status_code == 200:
        return
    if resp.status_code == 409:
        raise ConflictError(f"push_bundle: history diverged for {article_id} at {server}")
    raise ProtocolError(f"push_bundle: unexpected status {resp.status_code} from {server}")


def fetch_incremental_bundle(server: str, article_id: str, since_hash: str | None) -> bytes | None:
    """GET /bundle?since= → bundle bytes, or None if not found."""
    resp = _call("GET", server, _article_path(article_id, "bundle"), article_id,
                  "fetch_incremental_bundle",
                  params={"since": since_hash} if since_hash else None,
                  timeout=SYNC_TIMEOUT_SECONDS)
    if resp.status_code == 200 and resp.content:
        return resp.content
    if resp.status_code == 404:
        return None
    raise ProtocolError(f"fetch_incremental_bundle: unexpected status {resp.status_code} from {server}")


def fetch_article_repo(server: str, article_id: str) -> str | None:
    """GET /api/v1/articles/{id}/repo → base64 tar.gz string, or None if 404."""
    resp = _call("GET", server, _article_path(article_id, "repo"), article_id,
                  "fetch_article_repo", timeout=SYNC_TIMEOUT_SECONDS)
    data = _require_json_or_none(resp, server, "fetch_article_repo")
    if data is not None:
        return data.get("repo_bundle")
    return None


def push_article_repo(server: str, article_id: str, bundle_b64: str) -> bool:
    """POST /api/v1/articles with base64 tar.gz → True on success."""
    resp = _call("POST", server, _api_path("articles"), article_id,
                  "push_article_repo", json={"id": article_id, "repo_bundle": bundle_b64},
                  timeout=SYNC_TIMEOUT_SECONDS)
    if resp.status_code in (200, 201):
        return True
    if resp.status_code == 409:
        return False
    raise ProtocolError(f"push_article_repo: unexpected status {resp.status_code} from {server}")


def fetch_article_source(server: str, article_id: str) -> tuple[str, str] | None:
    """GET /api/v1/articles/{id}/source → (content, format) or None if 404."""
    resp = _call("GET", server, _article_path(article_id, "source"), article_id,
                  "fetch_article_source")
    data = _require_json_or_none(resp, server, "fetch_article_source")
    if data is not None:
        return data.get("content"), data.get("format", "markdown")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Search + metadata
# ═══════════════════════════════════════════════════════════════════════════════


def fetch_search(
    server: str, user_id: str = "", q: str | None = None, status: str | None = None,
    limit: int = 20, offset: int = 0, *,
    private_key_bytes: bytes | None = None, pubkey_hex: str = "",
) -> list[dict] | None:
    """GET /api/v1/search?q=&status=&limit=&offset= → article list.

    When *private_key_bytes* is provided, signs the request with Ed25519.
    Without auth, the server returns 401 — callers should pass session
    credentials when available.
    """
    params: dict[str, str | int | None] = {
        "q": q, "status": status, "limit": limit, "offset": offset,
    }
    return _get(
        server, _api_path("search"), user_id,
        private_key_bytes=private_key_bytes, pubkey_hex=pubkey_hex,
        context="fetch_search", params=params,
    )


def fetch_article_meta(server: str, article_id: str) -> dict | None:
    """GET /api/v1/articles/{id} → article metadata dict, or None if 404."""
    resp = _call("GET", server, _article_path(article_id), article_id,
                  "fetch_article_meta")
    data = _require_json_or_none(resp, server, "fetch_article_meta")
    if data is not None:
        return data
    return None


def fetch_user_articles(server: str, user_id: str, limit: int = 20, offset: int = 0, *,
                        private_key_bytes: bytes | None = None,
                        pubkey_hex: str = "") -> list[dict] | None:
    """GET /users/{id}/articles?limit=&offset= → list of article dicts, or None if not found."""
    return _get(
        server, _user_path(user_id, "articles"), user_id,
        private_key_bytes=private_key_bytes, pubkey_hex=pubkey_hex,
        context="fetch_user_articles",
        params={"limit": limit, "offset": offset},
    )
