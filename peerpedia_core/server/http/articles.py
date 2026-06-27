# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""HTTP implementations of the article transport protocol.

Each function here is a callback that can be wired into the corresponding
protocol function in ``transport/articles.py`` via ``functools.partial``.

All HTTP details — status codes, paths, methods, serialization — are
confined to this module.
"""

from peerpedia_core.exceptions import ConflictError, ProtocolError, TransportError
from peerpedia_core.server.http._core import (
    _api_path, _article_path, _call, _get, _require_json_or_none, _user_path,
)
from peerpedia_core.time import SYNC_TIMEOUT_SECONDS


# ═══════════════════════════════════════════════════════════════════════════════
# Sync protocol callbacks
# ═══════════════════════════════════════════════════════════════════════════════


def _ancestor_probe(server: str, article_id: str, hash: str) -> bool | None:
    """GET /api/v1/articles/{id}/ancestor/{hash} → True/False/None on error."""
    try:
        resp = _call("GET", server,
                     _article_path(article_id, f"ancestor/{hash}"),
                     article_id, "ancestor_probe")
        return resp.status_code == 200
    except TransportError:
        return None


def _fetch_head(server: str, article_id: str) -> str | None:
    """GET /api/v1/articles/{id}/head → HEAD hash or None (404)."""
    resp = _call("GET", server, _article_path(article_id, "head"),
                 article_id, "fetch_head")
    data = _require_json_or_none(resp, server, "fetch_head")
    return data.get("hash") if data else None


def _push_bundle(server: str, article_id: str, bundle_bytes: bytes) -> None:
    """POST /api/v1/articles/{id}/sync → None on success, raises on failure."""
    resp = _call("POST", server, _article_path(article_id, "sync"), article_id,
                 "push_bundle", content=bundle_bytes,
                 headers={"Content-Type": "application/octet-stream"},
                 timeout=SYNC_TIMEOUT_SECONDS)
    if resp.status_code == 200:
        return
    if resp.status_code == 409:
        raise ConflictError(
            f"push_bundle: history diverged for {article_id} at {server}")
    raise ProtocolError(
        f"push_bundle: unexpected status {resp.status_code} from {server}")


def _fetch_incremental_bundle(
    server: str, article_id: str, since_hash: str | None,
) -> bytes | None:
    """GET /api/v1/articles/{id}/bundle?since= → bytes, None (404), or raises."""
    resp = _call("GET", server, _article_path(article_id, "bundle"), article_id,
                 "fetch_incremental_bundle",
                 params={"since": since_hash} if since_hash else None,
                 timeout=SYNC_TIMEOUT_SECONDS)
    if resp.status_code == 200 and resp.content:
        return resp.content
    if resp.status_code == 404:
        return None
    raise ProtocolError(
        f"fetch_incremental_bundle: unexpected status {resp.status_code} "
        f"from {server}")


def _fetch_article_repo(server: str, article_id: str) -> str | None:
    """GET /api/v1/articles/{id}/repo → base64 tar.gz string or None (404)."""
    resp = _call("GET", server, _article_path(article_id, "repo"), article_id,
                 "fetch_article_repo", timeout=SYNC_TIMEOUT_SECONDS)
    data = _require_json_or_none(resp, server, "fetch_article_repo")
    return data.get("repo_bundle") if data else None


def _push_article_repo(server: str, article_id: str, bundle_b64: str) -> bool:
    """POST /api/v1/articles → True (200/201), False (409), or raises."""
    resp = _call("POST", server, _api_path("articles"), article_id,
                 "push_article_repo",
                 json={"id": article_id, "repo_bundle": bundle_b64},
                 timeout=SYNC_TIMEOUT_SECONDS)
    if resp.status_code in (200, 201):
        return True
    if resp.status_code == 409:
        return False
    raise ProtocolError(
        f"push_article_repo: unexpected status {resp.status_code} "
        f"from {server}")


def _fetch_article_source(server: str, article_id: str) -> tuple[str, str] | None:
    """GET /api/v1/articles/{id}/source → (content, format) or None (404)."""
    resp = _call("GET", server, _article_path(article_id, "source"), article_id,
                 "fetch_article_source")
    data = _require_json_or_none(resp, server, "fetch_article_source")
    return (data.get("content"), data.get("format", "markdown")) if data else None


# ═══════════════════════════════════════════════════════════════════════════════
# Search + metadata callbacks
# ═══════════════════════════════════════════════════════════════════════════════


def _fetch_search(
    server: str, user_id: str, q: str | None, status: str | None,
    limit: int, offset: int, *,
    private_key_bytes: bytes | None = None, pubkey_hex: str = "",
) -> list[dict] | None:
    """GET /api/v1/search?q=&status=&limit=&offset= → article list or None."""
    params: dict[str, str | int | None] = {
        "q": q, "status": status, "limit": limit, "offset": offset,
    }
    return _get(
        server, _api_path("search"), user_id,
        private_key_bytes=private_key_bytes, pubkey_hex=pubkey_hex,
        context="fetch_search", params=params,
    )


def _fetch_article_meta(server: str, article_id: str) -> dict | None:
    """GET /api/v1/articles/{id} → article metadata or None (404)."""
    resp = _call("GET", server, _article_path(article_id), article_id,
                 "fetch_article_meta")
    return _require_json_or_none(resp, server, "fetch_article_meta")


def _fetch_user_articles(
    server: str, user_id: str, limit: int, offset: int, *,
    private_key_bytes: bytes | None = None, pubkey_hex: str = "",
) -> list[dict] | None:
    """GET /users/{id}/articles?limit=&offset= → article list or None."""
    return _get(
        server, _user_path(user_id, "articles"), user_id,
        private_key_bytes=private_key_bytes, pubkey_hex=pubkey_hex,
        context="fetch_user_articles",
        params={"limit": limit, "offset": offset},
    )
