# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Social discovery orchestration — fetch-then-merge.

Each ``discover_*`` function: fetch from peer → convert JSON → ingest.
"""

from __future__ import annotations

import logging
import os

from peerpedia_core.storage.db import Session

from peerpedia_core.storage.db.crawler import _bfs_walk
from peerpedia_core.storage.db.ingest import (
    ingest_articles, ingest_followers, ingest_following, ingest_notifications,
    ingest_shares, ingest_users, sync_followers, sync_following,
)
from peerpedia_core.transport import (
    fetch_followers,
    fetch_following,
    fetch_notifications,
    fetch_shares,
    fetch_user_articles,
)
from peerpedia_core.transport import require_fetch_response
from peerpedia_core.transport._http_core import _fetch_with_auth_fallback
from peerpedia_core.types.entities import (
    ArticleMetaExchange, FollowExchange, NotificationExchange, ShareExchange, UserExchange,
)

logger = logging.getLogger(__name__)


def discover_following(db: Session, server: str, user_id: str, *,
                       signing_key_bytes: bytes | None = None,
                       pubkey_hex: str = "") -> int:
    """Fetch and ingest the users that *user_id* follows on *server*."""
    data = require_fetch_response(
        fetch_following, server, user_id, "following",
        private_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
    )
    return _ingest_follow_data(db, server, user_id, data,
                               sync_fn=sync_following, ingest_fn=ingest_following)


def discover_followers(db: Session, server: str, user_id: str, *,
                       signing_key_bytes: bytes | None = None,
                       pubkey_hex: str = "") -> int:
    """Fetch and merge the followers of *user_id* on *server*."""
    data = require_fetch_response(
        fetch_followers, server, user_id, "followers",
        private_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
    )
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
    db: Session, server: str, user_id: str, limit: int = 20, offset: int = 0, *,
    signing_key_bytes: bytes | None = None,
    pubkey_hex: str = "",
) -> int:
    """Fetch and merge article metadata for *user_id* from *server*."""
    data = require_fetch_response(
        fetch_user_articles, server, user_id, "articles",
        limit=limit, offset=offset,
        private_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
    )
    stubs = [ArticleMetaExchange.from_json(e) for e in data]
    return ingest_articles(db, stubs)


def discover_shares(db: Session, server: str, user_id: str, *,
                    signing_key_bytes: bytes | None = None,
                    pubkey_hex: str = "") -> int:
    """Fetch and merge shares from *user_id* on *server*."""
    data = require_fetch_response(
        fetch_shares, server, user_id, "shares",
        private_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
    )
    shares = [ShareExchange.from_json(e) for e in data]
    return ingest_shares(db, user_id, shares)


def discover_notifications(db: Session, server: str, user_id: str, *,
                           signing_key_bytes: bytes | None = None,
                           pubkey_hex: str = "") -> int:
    """Fetch and merge notifications for *user_id* from *server*."""
    data = require_fetch_response(
        fetch_notifications, server, user_id, "notifications",
        private_key_bytes=signing_key_bytes, pubkey_hex=pubkey_hex,
    )
    notifs = [NotificationExchange.from_json(e) for e in data]
    return ingest_notifications(db, user_id, notifs)


def discover_network(
    db: Session,
    server: str,
    start_user_id: str,
    depth: int = 1,
    max_users: int = 100,
    *,
    signing_key_bytes: bytes | None = None,
    pubkey_hex: str = "",
) -> dict:
    """BFS walk of the follow graph from *start_user_id* on *server*."""
    auth_kwargs = {"private_key_bytes": signing_key_bytes, "pubkey_hex": pubkey_hex}

    def _fetch_following_with_fallback(server: str, user_id: str):
        return _fetch_with_auth_fallback(
            fetch_following, server, user_id, **auth_kwargs,
        )

    return _bfs_walk(
        db, server, start_user_id,
        depth=depth,
        max_users=max_users,
        fetch_following_fn=_fetch_following_with_fallback,
        discover_articles_fn=discover_articles,
    )
