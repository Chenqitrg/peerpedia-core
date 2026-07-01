# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Ingest and sync functions for P2P social graph exchange.

Each function takes typed entity lists and writes rows into the local DB.
Callers deserialize JSON at the boundary — these functions never see dicts.
"""

from __future__ import annotations

from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.crud_article import ensure_article_stub
from peerpedia_core.storage.db.crud_bookmark import add_bookmark
from peerpedia_core.storage.db.crud_maintainer import add_maintainer
from peerpedia_core.storage.db.crud_share import add_share as _add_share
from peerpedia_core.storage.db.crud_notification import ensure_notification
from peerpedia_core.storage.db.crud_follow import (
    add_followers, follow_users, set_followers, set_following,
)
from peerpedia_core.storage.db.crud_user import ensure_user
from peerpedia_core.storage.db.models import (
    ArticleMetaStorage, NotificationStorage, ShareStorage, UserStorage,
)
from peerpedia_core.types.entities import (
    ArticleMetaExchange, BookmarkExchange, FollowExchange, MaintainerExchange,
    NotificationExchange, UserExchange, ShareExchange,
)


def ingest_users(db: Session, entries: list[UserExchange]) -> int:
    """Insert new users discovered from a peer — lazy social discovery."""
    for e in entries:
        ensure_user(db, e.id, e.name, address=e.address)
    return len(entries)


def ingest_following(db: Session, follower_id: str, entries: list[FollowExchange]) -> int:
    """Insert FollowStorage rows discovered from a peer — never deletes."""
    ids = {e.id for e in entries}
    return follow_users(db, follower_id, ids)


def sync_following(db: Session, follower_id: str, entries: list[FollowExchange]) -> int:
    """Insert FollowStorage rows and soft-delete stale follows (home-server sync)."""
    ids = {e.id for e in entries}
    added = follow_users(db, follower_id, ids)
    set_following(db, follower_id, ids)
    return added


def ingest_followers(db: Session, followed_id: str, entries: list[FollowExchange]) -> int:
    """Insert FollowStorage rows for users who follow *followed_id* — never deletes."""
    ids = {e.id for e in entries}
    return add_followers(db, followed_id, ids)


def sync_followers(db: Session, followed_id: str, entries: list[FollowExchange]) -> int:
    """Insert FollowStorage rows and soft-delete stale followers (home-server sync)."""
    ids = {e.id for e in entries}
    added = add_followers(db, followed_id, ids)
    set_followers(db, followed_id, ids)
    return added


def ingest_articles(db: Session, entries: list[ArticleMetaExchange]) -> int:
    """Insert article stubs discovered from a peer — lazy discovery."""
    added = 0
    for e in entries:
        if ensure_article_stub(db, ArticleMetaStorage.from_exchange(e), author_ids=list(e.authors)) is not None:
            added += 1
    return added


def ingest_articles_from_json(db: Session, entries: list[dict]) -> int:
    """Insert article stubs from peer JSON dicts."""
    return ingest_articles(db, [ArticleMetaExchange.from_json(e) for e in entries])


def ingest_bookmarks(db: Session, user_id: str, entries: list[BookmarkExchange]) -> int:
    """Insert bookmarks discovered from a peer — lazy discovery."""
    for e in entries:
        add_bookmark(db, user_id, e.article_id)
    return len(entries)


def ingest_maintainers(db: Session, article_id: str, entries: list[MaintainerExchange]) -> int:
    """Insert maintainers discovered from a peer — lazy discovery."""
    for e in entries:
        add_maintainer(db, article_id, e.user_id)
    return len(entries)


def ingest_shares(db: Session, user_id: str, entries: list[ShareExchange]) -> int:
    """Insert shares discovered from a peer — lazy discovery."""
    for e in entries:
        _add_share(db, user_id, e.article_id,
                   recipient_id=e.recipient_id or None,
                   comment=e.comment or None)
    return len(entries)


def ingest_notifications(db: Session, user_id: str, entries: list[NotificationExchange]) -> int:
    """Insert notifications from peer data — dedup via ensure_notification."""
    for entry in entries:
        n = ensure_notification(
            db,
            user_id=user_id,
            event=entry.event,
            message=entry.message,
            article_id=entry.article_id or None,
            actor_id=entry.actor_id or None,
            notification_id=entry.id or None,
        )
        if entry.read:
            n.read = 1
    return len(entries)
