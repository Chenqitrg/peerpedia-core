# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Social discovery orchestration — fetch-then-merge.

Each ``discover_*`` function: (1) fetches data from a peer server via the
``transport/`` facade, (2) merges it into the local DB via ``commands/discover``.
Transport-agnostic — switching from HTTP to P2P only requires changing
``transport/__init__.py``::

    discover_following   → fetch_following  → merge_follows
    discover_followers   → fetch_followers  → merge_users + merge_followers
    discover_articles    → fetch_user_articles  → merge_article_meta

``discover_bookmarks`` was removed — bookmarks are private, not social graph data.
"""

from __future__ import annotations

import logging
import os
from collections import deque
from functools import partial
from typing import Callable

from peerpedia_core.storage.db import Session

from peerpedia_core.commands import merge_article_meta, merge_followers, merge_follows, merge_notifications, merge_shares, merge_users

logger = logging.getLogger(__name__)
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

    Creates User stubs via ``merge_users``, then reconciles Follow rows
    via ``merge_followers``.  When *server* is the user's home server
    (PEERPEDIA_SERVER), the remote followers list is treated as
    authoritative — local Follow rows for *user_id* not in the remote
    list are soft-deleted (unfollow detection).

    Returns count of new followers added.  Raises ConnectionError if the
    server is unreachable.  Raises ProtocolError on malformed responses.
    """
    data = _fetch_or_raise(
        fetch_followers, server, user_id, "followers",
        **_auth_args(signing_key_bytes, pubkey_hex),
    )
    merge_users(db, data)
    home_server = os.environ.get("PEERPEDIA_SERVER")
    authoritative = (home_server is not None and server == home_server)
    return merge_followers(db, user_id, data, authoritative=authoritative)


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
    """BFS walk of the follow graph from *start_user_id* on *server*.

    At each depth:
      1. Fetch following list for each discovered user.
      2. Merge users and follows locally (non-authoritative).
      3. Discover articles for each discovered user.

    Uses auth fallback: tries unauthenticated fetch first; on 401/403,
    retries with Ed25519 signing.

    Returns ``{"users_discovered": int, "articles_discovered": int,
              "follows_added": int, "depth_reached": int}``.

    Dedup by user_id — never revisits a user.  Caps at *max_users*.
    """
    users_discovered = 0
    articles_discovered = 0
    follows_added = 0
    depth_reached = 0

    visited: set[str] = {start_user_id}
    # BFS queue: (user_id, current_depth)
    queue: deque[tuple[str, int]] = deque()
    queue.append((start_user_id, 0))

    auth_kwargs = _auth_args(signing_key_bytes, pubkey_hex)

    while queue:
        user_id, current_depth = queue.popleft()
        depth_reached = max(depth_reached, current_depth)

        if current_depth >= depth:
            continue

        if users_discovered >= max_users:
            break

        # Fetch following list for this user.
        try:
            data = _try_fetch_with_fallback(
                fetch_following, server, user_id, "following", **auth_kwargs,
            )
        except (ConnectionError, ProtocolError):
            logger.debug("discover_network: fetch_following failed for %s, skipping", user_id)
            continue

        if not data:
            continue

        # Merge discovered users.
        merge_users(db, data)

        # Merge follows (non-authoritative — we're discovering, not reconciling).
        n = merge_follows(db, user_id, data, authoritative=False)
        follows_added += n

        # Discover articles for each followed user.
        for entry in data:
            followed_id = entry["id"]
            if followed_id in visited:
                continue
            visited.add(followed_id)
            users_discovered += 1

            if users_discovered >= max_users:
                break

            try:
                n_articles = discover_articles(
                    db, server, followed_id,
                    signing_key_bytes=signing_key_bytes,
                    pubkey_hex=pubkey_hex,
                )
                articles_discovered += n_articles
            except (ConnectionError, ProtocolError):
                logger.debug(
                    "discover_network: discover_articles failed for %s, skipping",
                    followed_id,
                )

            # Enqueue for next depth level.
            if current_depth + 1 < depth:
                queue.append((followed_id, current_depth + 1))

    return {
        "users_discovered": users_discovered,
        "articles_discovered": articles_discovered,
        "follows_added": follows_added,
        "depth_reached": depth_reached,
    }


def _try_fetch_with_fallback(
    fetch_fn: Callable,
    server: str,
    user_id: str,
    label: str,
    **auth_kwargs,
) -> list[dict] | None:
    """Try unauthenticated fetch first; on 401/403, retry with auth.

    Foreign peers serve public data without auth.  Home server requires
    Ed25519 signing for private data (following, followers, notifications).
    This fallback avoids sending signatures to peers that don't need them.
    """
    # Try without auth first.
    try:
        data = fetch_fn(server, user_id)
        if data is not None:
            return data
    except TransportError as e:
        # 401/403 → retry with auth.  Other errors: log and fall through.
        status = getattr(e, "status_code", None)
        if status not in (401, 403):
            logger.debug(
                "_try_fetch_with_fallback: fetch failed with status %s for %s: %s",
                status, user_id, e,
            )
    except ProtocolError as e:
        logger.debug("_try_fetch_with_fallback: protocol error for %s: %s", user_id, e)

    # Retry with Ed25519 signing.
    result = None
    if auth_kwargs:
        try:
            result = fetch_fn(server, user_id, **auth_kwargs)
        except (TransportError, ProtocolError) as e:
            logger.debug("_try_fetch_with_fallback: auth fetch also failed: %s", e)

    return result
