# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Social discovery orchestration — fetch-then-merge.

Each ``discover_*`` function: fetch from peer → convert JSON → ingest.
Symmetric with ``core/sync_article.py`` — both take a ``Transport`` instance.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from peerpedia_core.storage.db import Session

from peerpedia_core.storage.db.crawler import _bfs_walk
from peerpedia_core.exceptions import ProtocolError
from peerpedia_core.storage.db.ingest import (
    ingest_articles, ingest_followers, ingest_following, ingest_notifications,
    ingest_shares, ingest_users, sync_followers, sync_following,
)
from peerpedia_core.types.entities import (
    ArticleMetaExchange, FollowExchange, NotificationExchange, ShareExchange, UserExchange,
)

if TYPE_CHECKING:
    from peerpedia_core.transport import Transport

logger = logging.getLogger(__name__)


def discover_following(db: Session, transport: Transport, server: str, user_id: str, *,
                       signing_key_bytes: bytes | None = None,
                       pubkey_hex: str = "") -> int:
    """Fetch and ingest the users that *user_id* follows on *server*."""
    data = transport.fetch_following(
        server, user_id,
        private_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
    )
    if data is None:
        raise ProtocolError(
            f"fetch_following: server {server} returned None for user {user_id}")
    return _ingest_follow_data(db, server, user_id, data,
                               sync_fn=sync_following, ingest_fn=ingest_following)


def discover_followers(db: Session, transport: Transport, server: str, user_id: str, *,
                       signing_key_bytes: bytes | None = None,
                       pubkey_hex: str = "") -> int:
    """Fetch and merge the followers of *user_id* on *server*."""
    data = transport.fetch_followers(
        server, user_id,
        private_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
    )
    if data is None:
        raise ProtocolError(
            f"fetch_followers: server {server} returned None for user {user_id}")
    return _ingest_follow_data(db, server, user_id, data,
                               sync_fn=sync_followers, ingest_fn=ingest_followers)


def _ingest_follow_data(db, server, user_id, data, *, sync_fn, ingest_fn) -> int:
    """Convert JSON → users + follows, ingest users, then sync or ingest follows."""
    users = [UserExchange.from_json(e) for e in data]
    follows = [FollowExchange.from_json(e) for e in data]
    ingest_users(db, users)
    home_server = os.environ.get("PEERPEDIA_SERVER")
    if home_server is not None and server == home_server:
        return sync_fn(db, user_id, follows)
    return ingest_fn(db, user_id, follows)


def discover_articles(
    db: Session, transport: Transport, server: str, user_id: str,
    limit: int = 20, offset: int = 0, *,
    signing_key_bytes: bytes | None = None,
    pubkey_hex: str = "",
) -> int:
    """Fetch and merge article metadata for *user_id* from *server*."""
    data = transport.fetch_user_articles(
        server, user_id, limit, offset,
        private_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
    )
    if data is None:
        raise ProtocolError(
            f"fetch_user_articles: server {server} returned None for user {user_id}")
    stubs = [ArticleMetaExchange.from_json(e) for e in data]
    return ingest_articles(db, stubs)


def discover_shares(db: Session, transport: Transport, server: str, user_id: str, *,
                    signing_key_bytes: bytes | None = None,
                    pubkey_hex: str = "") -> int:
    """Fetch and merge shares from *user_id* on *server*."""
    data = transport.fetch_shares(
        server, user_id,
        private_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
    )
    if data is None:
        raise ProtocolError(
            f"fetch_shares: server {server} returned None for user {user_id}")
    shares = [ShareExchange.from_json(e) for e in data]
    return ingest_shares(db, user_id, shares)


def discover_notifications(db: Session, transport: Transport, server: str, user_id: str, *,
                           signing_key_bytes: bytes | None = None,
                           pubkey_hex: str = "") -> int:
    """Fetch and merge notifications for *user_id* from *server*."""
    data = transport.fetch_notifications(
        server, user_id,
        private_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
    )
    if data is None:
        raise ProtocolError(
            f"fetch_notifications: server {server} returned None for user {user_id}")
    notifs = [NotificationExchange.from_json(e) for e in data]
    return ingest_notifications(db, user_id, notifs)


def discover_network(
    db: Session,
    transport: Transport,
    server: str,
    start_user_id: str,
    depth: int = 1,
    max_users: int = 100,
    *,
    signing_key_bytes: bytes | None = None,
    pubkey_hex: str = "",
) -> dict:
    """BFS walk of the follow graph from *start_user_id* on *server*."""
    auth_kw = {"private_key_bytes": signing_key_bytes, "pubkey_hex": pubkey_hex}

    def _fetch_with_retry(server: str, user_id: str) -> list[dict] | None:
        # Try unauth first; retry with auth on 401/403.
        data = transport.fetch_following(server, user_id)
        if data is not None:
            return data
        return transport.fetch_following(server, user_id, **auth_kw)

    def _discover_articles_fn(db, srv, uid, **kw):
        return discover_articles(db, transport, srv, uid, **kw)

    return _bfs_walk(
        db, server, start_user_id,
        depth=depth,
        max_users=max_users,
        fetch_following_fn=_fetch_with_retry,
        discover_articles_fn=_discover_articles_fn,
    )
