# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Social discovery orchestration — fetch-then-merge.

Each ``discover_*`` function: (1) fetches data from a peer server via the
``transport/`` facade, (2) merges it into the local DB via ``commands/discover``.
Transport-agnostic — switching from HTTP to P2P only requires changing
``transport/__init__.py``::

    discover_following   → fetch_following  → merge_follows
    discover_followers   → fetch_followers  → merge_follows
    discover_articles    → fetch_user_articles  → merge_article_meta

``discover_bookmarks`` was removed — bookmarks are private, not social graph data.
"""

from __future__ import annotations

import os
from functools import partial
from typing import Callable

from peerpedia_core.storage.db import Session

from peerpedia_core.commands import merge_article_meta, merge_follows, merge_notifications, merge_shares, merge_users
from peerpedia_core.exceptions import ProtocolError, TransportError
from peerpedia_core.transport import (
    fetch_followers,
    fetch_following,
    fetch_notifications,
    fetch_shares,
    fetch_user_articles,
)


def _fetch_or_raise(fetch_fn: Callable, server: str, user_id: str, label: str,
                    **auth_kwargs) -> list[dict]:
    """Call *fetch_fn* and return data.  Passes *auth_kwargs* for Ed25519 signing.

    Raises ``ConnectionError`` on transport failure.  Raises
    ``ProtocolError`` if the server returned ``None`` (404 / not found).
    """
    try:
        data = fetch_fn(server, user_id, **auth_kwargs)
    except TransportError as e:
        raise ConnectionError(
            f"Failed to fetch {label} from {server} for {user_id}: {e.detail}"
        ) from e
    if data is None:
        raise ProtocolError(
            f"fetch_{label}: server {server} returned None for user {user_id}"
        )
    return data


def _auth_args(signing_key_bytes, pubkey_hex):
    """Build keyword arguments for signed fetch functions."""
    kwargs: dict = {}
    if signing_key_bytes:
        kwargs["private_key_bytes"] = signing_key_bytes
    if pubkey_hex:
        kwargs["pubkey_hex"] = pubkey_hex
    return kwargs


def discover_following(db: Session, server: str, user_id: str, *,
                       signing_key_bytes: bytes | None = None,
                       pubkey_hex: str = "") -> int:
    """Fetch and merge the users that *user_id* follows on *server*.

    Returns count of new follows added.  Raises ConnectionError if the
    server is unreachable.  Raises ProtocolError on malformed responses.

    When *server* is the user's home server (PEERPEDIA_SERVER), the remote
    following list is treated as authoritative — local follows not in the
    remote list are soft-deleted.
    """
    data = _fetch_or_raise(fetch_following, server, user_id, "following",
                           **_auth_args(signing_key_bytes, pubkey_hex))
    merge_users(db, data)
    home_server = os.environ.get("PEERPEDIA_SERVER")
    authoritative = (home_server is not None and server == home_server)
    return merge_follows(db, user_id, data, authoritative=authoritative)


def discover_followers(db: Session, server: str, user_id: str, *,
                       signing_key_bytes: bytes | None = None,
                       pubkey_hex: str = "") -> int:
    """Fetch and merge the followers of *user_id* on *server*.

    Returns count of new users added.  Raises ConnectionError if the
    server is unreachable.  Raises ProtocolError on malformed responses.
    """
    return merge_users(db, _fetch_or_raise(
        fetch_followers, server, user_id, "followers",
        **_auth_args(signing_key_bytes, pubkey_hex),
    ))


def discover_articles(
    db: Session, server: str, user_id: str, limit: int = 20, offset: int = 0, *,
    signing_key_bytes: bytes | None = None,
    pubkey_hex: str = "",
) -> int:
    """Fetch and merge article metadata for *user_id* from *server*.

    Returns count of new articles discovered.  Raises ConnectionError if
    the server is unreachable.  Raises ProtocolError on malformed responses.
    """
    data = _fetch_or_raise(
        fetch_user_articles, server, user_id, "articles",
        limit=limit, offset=offset,
        **_auth_args(signing_key_bytes, pubkey_hex),
    )
    return merge_article_meta(db, data)


def discover_shares(db: Session, server: str, user_id: str, *,
                    signing_key_bytes: bytes | None = None,
                    pubkey_hex: str = "") -> int:
    """Fetch and merge shares from *user_id* on *server*.

    Returns count of new shares discovered.  Raises ConnectionError if
    the server is unreachable.  Raises ProtocolError on malformed responses.
    """
    data = _fetch_or_raise(
        fetch_shares, server, user_id, "shares",
        **_auth_args(signing_key_bytes, pubkey_hex),
    )
    return merge_shares(db, user_id, data)


def discover_notifications(db: Session, server: str, user_id: str, *,
                           signing_key_bytes: bytes | None = None,
                           pubkey_hex: str = "") -> int:
    """Fetch and merge notifications for *user_id* from *server*.

    Returns count of new notifications discovered.  Raises ConnectionError
    if the server is unreachable.  Raises ProtocolError on malformed responses.
    """
    data = _fetch_or_raise(
        fetch_notifications, server, user_id, "notifications",
        **_auth_args(signing_key_bytes, pubkey_hex),
    )
    return merge_notifications(db, user_id, data)
