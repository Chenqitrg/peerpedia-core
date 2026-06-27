# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Ingest and sync functions for P2P social graph exchange.

Called by ``social/exchange.py`` (fetch-then-ingest orchestration).
Each function takes a list of dicts from a remote peer and writes new rows
into the local DB, skipping duplicates::

    ingest_users             — create User rows for newly discovered peers
    ingest_following         — insert Follow rows (I follow them), no cleanup
    sync_following           — insert Follow rows + soft-delete stale follows
    ingest_followers         — insert Follow rows (they follow me), no cleanup
    sync_followers           — insert Follow rows + soft-delete stale followers
    ingest_articles          — insert Article stubs for discovered articles
    ingest_bookmarks         — insert Bookmark rows (deprecated, kept for compat)
    ingest_maintainers       — insert maintainer rows from sync
    ingest_shares            — insert share rows
    ingest_notifications     — insert notification rows

Pure DB operations — no HTTP, no git.  Only imports from ``storage/db/``.
"""

from __future__ import annotations

from peerpedia_core.storage.db import Session
from peerpedia_core.core.guards import require_keys, validate_follow_entries
from peerpedia_core.storage.db.crud_article import ensure_article_stub
from peerpedia_core.storage.db.crud_bookmark import add_bookmark
from peerpedia_core.storage.db.crud_maintainer import add_maintainer
from peerpedia_core.storage.db.crud_share import add_share as _add_share
from peerpedia_core.storage.db.crud_notification import ensure_notification
from peerpedia_core.storage.db.crud_user import (
    add_followers, ensure_user, follow_users, set_followers, set_following,
)

def ingest_users(db: Session, entries: list[dict]) -> int:
    """Insert new users discovered from a peer — lazy social discovery.

    ``ensure_user`` is idempotent and checks for address conflicts.
    """
    require_keys(entries, "id", "name", label="users")
    for e in entries:
        ensure_user(db, e["id"], e["name"], address=e.get("address", ""))
    return len(entries)


def ingest_following(db: Session, follower_id: str, entries: list[dict]) -> int:
    """Insert Follow rows discovered from a peer — never deletes."""
    ids = validate_follow_entries(entries, follower_id, "following")
    return follow_users(db, follower_id, ids)


def sync_following(db: Session, follower_id: str, entries: list[dict]) -> int:
    """Insert Follow rows and soft-delete stale follows (home-server sync)."""
    ids = validate_follow_entries(entries, follower_id, "following")
    added = follow_users(db, follower_id, ids)
    set_following(db, follower_id, ids)
    return added


def ingest_followers(db: Session, followed_id: str, entries: list[dict]) -> int:
    """Insert Follow rows for users who follow *followed_id* — never deletes."""
    ids = validate_follow_entries(entries, followed_id, "followers")
    return add_followers(db, followed_id, ids)


def sync_followers(db: Session, followed_id: str, entries: list[dict]) -> int:
    """Insert Follow rows and soft-delete stale followers (home-server sync)."""
    ids = validate_follow_entries(entries, followed_id, "followers")
    added = add_followers(db, followed_id, ids)
    set_followers(db, followed_id, ids)
    return added


def ingest_articles(db: Session, entries: list[dict]) -> int:
    """Insert article stubs discovered from a peer — lazy discovery.

    ``ensure_article_stub`` is idempotent: existing articles are skipped.
    Raises ValueError if any entry is missing *id*, *title*, or *status*.
    """
    require_keys(entries, "id", "title", "status", label="article_meta")
    added = 0
    for e in entries:
        if ensure_article_stub(db, e, author_ids=e.get("authors", [])) is not None:
            added += 1
    return added


def ingest_bookmarks(db: Session, user_id: str, entries: list[dict]) -> int:
    """Insert bookmarks discovered from a peer — lazy social discovery.

    ``add_bookmark`` is idempotent — duplicates are silently skipped.
    Raises ValueError if any entry is missing *article_id*.
    """
    require_keys(entries, "article_id", label="bookmarks")
    for e in entries:
        add_bookmark(db, user_id, e["article_id"])
    return len(entries)


def ingest_maintainers(db: Session, article_id: str, entries: list[dict]) -> int:
    """Insert maintainers discovered from a peer — lazy social discovery.

    ``add_maintainer`` is idempotent — duplicates are silently skipped.
    Raises ValueError if any entry is missing *user_id*.
    """
    require_keys(entries, "user_id", label="script_maintainers")
    for e in entries:
        add_maintainer(db, article_id, e["user_id"])
    return len(entries)


def ingest_shares(db: Session, user_id: str, entries: list[dict]) -> int:
    """Insert shares discovered from a peer — lazy social discovery.

    ``add_share`` is an upsert — duplicates update the existing row.
    Raises ValueError if any entry is missing *article_id*.
    """
    require_keys(entries, "article_id", label="shares")
    for e in entries:
        _add_share(
            db, user_id, e["article_id"],
            recipient_id=e.get("recipient_id"),
            comment=e.get("comment"),
        )
    return len(entries)


def ingest_notifications(db: Session, user_id: str, entries: list[dict]) -> int:
    """Insert notifications from peer data.

    Dedup via ``crud_notification.ensure_notification``.
    Raises ValueError if any entry is missing *event* or *message*.
    """
    require_keys(entries, "event", "message", label="notifications")
    for entry in entries:
        n = ensure_notification(
            db,
            user_id=user_id,
            event=entry["event"],
            message=entry["message"],
            article_id=entry.get("article_id"),
            actor_id=entry.get("actor_id"),
            notification_id=entry.get("id"),
        )
        if entry.get("read"):
            n.read = 1
    return len(entries)
