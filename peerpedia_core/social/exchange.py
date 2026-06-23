# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Social discovery orchestration — fetch-then-merge.

Transport-agnostic: imports from ``transport/`` (the facade), not from
``transport/http_client`` directly.  Switching from HTTP to P2P only requires
changing ``transport/__init__.py``.
"""

from __future__ import annotations

from functools import partial
from typing import Callable

from peerpedia_core.storage.db import Session

from peerpedia_core.commands import merge_article_meta, merge_bookmarks, merge_follows, merge_users
from peerpedia_core.exceptions import ProtocolError, TransportError
from peerpedia_core.transport import (
    fetch_articles,
    fetch_bookmarks,
    fetch_followers,
    fetch_following,
)


def _fetch_or_raise(fetch_fn: Callable, server: str, user_id: str, label: str) -> list[dict]:
    """Call *fetch_fn* and return data.

    Raises ``ConnectionError`` on transport failure.  Raises
    ``ProtocolError`` if the server returned ``None`` (404 / not found).
    """
    try:
        data = fetch_fn(server, user_id)
    except TransportError as e:
        raise ConnectionError(
            f"Failed to fetch {label} from {server} for {user_id}: {e.detail}"
        ) from e
    if data is None:
        raise ProtocolError(
            f"fetch_{label}: server {server} returned None for user {user_id}"
        )
    return data


def discover_following(db: Session, server: str, user_id: str) -> int:
    """Fetch and merge the users that *user_id* follows on *server*.

    Returns count of new follows added.  Raises ConnectionError if the
    server is unreachable.  Raises ProtocolError on malformed responses.
    """
    data = _fetch_or_raise(fetch_following, server, user_id, "following")
    merge_users(db, data)
    return merge_follows(db, user_id, data)


def discover_followers(db: Session, server: str, user_id: str) -> int:
    """Fetch and merge the followers of *user_id* on *server*.

    Returns count of new users added.  Raises ConnectionError if the
    server is unreachable.  Raises ProtocolError on malformed responses.
    """
    return merge_users(db, _fetch_or_raise(fetch_followers, server, user_id, "followers"))


def discover_articles(
    db: Session, server: str, user_id: str, limit: int = 20, offset: int = 0
) -> int:
    """Fetch and merge article metadata for *user_id* from *server*.

    Returns count of new articles discovered.  Raises ConnectionError if
    the server is unreachable.  Raises ProtocolError on malformed responses.
    """
    data = _fetch_or_raise(
        partial(fetch_articles, limit=limit, offset=offset),
        server, user_id, "articles",
    )
    return merge_article_meta(db, data)


def discover_bookmarks(db: Session, server: str, user_id: str) -> int:
    """Fetch and merge the bookmarks of *user_id* from *server*.

    Creates local Bookmark records for each bookmark the remote user has.
    Returns count of new bookmarks added.  Raises ConnectionError if the
    server is unreachable.  Raises ProtocolError on malformed responses.
    """
    return merge_bookmarks(db, user_id, _fetch_or_raise(fetch_bookmarks, server, user_id, "bookmarks"))
