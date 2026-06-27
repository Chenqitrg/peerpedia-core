# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Shared HTTP transport infrastructure — client pool, auth, helpers.

Internal module — not part of the public transport facade.  Imported
by ``http_articles.py`` and ``http_social.py``.
"""

import json
import threading

import httpx

from peerpedia_core.exceptions import ProtocolError, TransportError
from peerpedia_core.transport.auth import build_auth_header

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


def _article_path(article_id: str, action: str = "") -> str:
    """Build an article REST path: ``/api/v1/articles/{id}/{action}``."""
    base = f"/api/v1/articles/{article_id}"
    return f"{base}/{action}" if action else base


def _user_path(user_id: str, action: str = "") -> str:
    """Build a user REST path: ``/api/v1/users/{id}/{action}``."""
    base = f"/api/v1/users/{user_id}"
    return f"{base}/{action}" if action else base


def _api_path(action: str) -> str:
    """Build an API root path: ``/api/v1/{action}`` (peers, school, search)."""
    return f"/api/v1/{action}"


def _encode_body(data: dict) -> bytes:
    """Serialize a dict to JSON bytes for HTTP request bodies."""
    return json.dumps(data).encode("utf-8")


def _require_json_or_none(resp: httpx.Response, server: str, context: str) -> dict | list | None:
    """Parse a 200/404 response: JSON on 200, None on 404, ProtocolError otherwise."""
    if resp.status_code == 200:
        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise ProtocolError(
                f"Malformed JSON from {server} for {context}",
                server=server, status_code=resp.status_code,
            ) from e
    if resp.status_code == 404:
        return None
    raise ProtocolError(
        f"{context}: unexpected status {resp.status_code} from {server}",
        server=server, status_code=resp.status_code,
    )


def _post(
    server: str, path: str, body_dict: dict, user_id: str, *,
    private_key_bytes: bytes | None = None,
    pubkey_hex: str = "",
    context: str = "",
) -> bool:
    """POST to a peer. Returns True on 200, False on 404."""
    body = _encode_body(body_dict)
    headers = build_auth_header("POST", path, user_id, private_key_bytes,
                                  pubkey_hex, body=body)
    resp = _call("POST", server, path, user_id, context,
                  content=body, headers=headers)
    return _require_ok_or_404(resp, server, context)


def _get(
    server: str, path: str, user_id: str, *,
    private_key_bytes: bytes | None = None,
    pubkey_hex: str = "",
    context: str = "",
    params: dict | None = None,
) -> dict | list | None:
    """GET from a peer. Returns JSON on 200, None on 404."""
    headers = build_auth_header("GET", path, user_id, private_key_bytes, pubkey_hex)
    resp = _call("GET", server, path, user_id, context,
                  headers=headers, params=params)
    return _require_json_or_none(resp, server, context)


def _call(
    method: str, server: str, path: str, user_id: str, context: str, **kwargs,
) -> httpx.Response:
    """Execute an HTTP request, converting ``httpx.HTTPError`` → ``TransportError``."""
    try:
        return _get_client().request(method, f"{server}{path}", **kwargs)
    except httpx.HTTPError as e:
        raise TransportError(f"{context} failed for {user_id} at {server}: {e}") from e


def _require_ok_or_404(resp: httpx.Response, server: str, context: str) -> bool:
    """Return True on 200, False on 404, raise ProtocolError otherwise."""
    if resp.status_code == 200:
        return True
    if resp.status_code == 404:
        return False
    raise ProtocolError(
        f"{context}: unexpected status {resp.status_code} from {server}",
        server=server, status_code=resp.status_code,
    )
