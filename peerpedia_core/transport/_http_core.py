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
from peerpedia_core.transport.auth import sign_auth_header

_SYNC_TIMEOUT = 60  # seconds — bundle upload/download can be large

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
