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

from datetime import datetime, timezone

from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.crud_article import create_article_from_orm, get_article
from peerpedia_core.storage.db.crud_bookmark import add_bookmark
from peerpedia_core.storage.db.crud_maintainer import add_maintainer
from peerpedia_core.storage.db.crud_share import add_share as _add_share
from peerpedia_core.storage.db.crud_user import (
    add_followers, create_user_stub, follow_users, get_user,
    set_followers, set_following,
)
from peerpedia_core.types import short_id
from peerpedia_core.storage.db.models import Article, User

def _require_keys(entries: list[dict], *keys: str, label: str) -> None:
    """Fail fast if any entry is missing a required key.  Does not touch DB."""
    for e in entries:
        for k in keys:
            if not e.get(k):
                raise ValueError(
                    f"ingest_{label}: missing '{k}' in entry {e}"
                )


def ingest_users(db: Session, entries: list[dict]) -> int:
    """Insert new users discovered from a peer — lazy social discovery.

    Only writes users that do not already exist locally.  The *address*
    field (peer URL) is optional — not all users run their own server.
    Raises only when two peers disagree on a user's address.
    """
    _require_keys(entries, "id", "name", label="users")

    added = 0
    for e in entries:
        u = get_user(db, e["id"])
        if u is None:
            u = User(id=e["id"], name=e["name"],
                     address=e.get("address", ""))
            db.add(u)
            added += 1
        elif u.address and e.get("address") and u.address != e["address"]:
            raise ValueError(
                f"ingest_users: address conflict for {e['id']}: "
                f"local={u.address!r}, peer={e['address']!r}"
            )
    db.flush()
    return added


def _upsert_follow_edges(
    db: Session,
    source_id: str,
    entries: list[dict],
    *,
    direction: str,
    cleanup: bool,
) -> int:
    """Insert follow edges; optionally soft-delete stale ones.

    *direction* is ``"following"`` (source_id follows the users in entries)
    or ``"followers"`` (the users in entries follow source_id).

    When *cleanup* is True, local Follow rows not in *entries* are
    soft-deleted (home-server sync).  When False, only inserts — never
    deletes (peer discovery).
    """
    label = "following" if direction == "following" else "followers"
    _require_keys(entries, "id", label=label)

    remote_ids = {e["id"] for e in entries}
    if source_id in remote_ids:
        raise ValueError(
            f"{label}: self-follow detected for user {source_id}"
        )

    if direction == "following":
        added = follow_users(db, source_id, remote_ids)
    else:
        added = add_followers(db, source_id, remote_ids)

    if cleanup:
        if direction == "following":
            set_following(db, source_id, remote_ids)
        else:
            set_followers(db, source_id, remote_ids)

    return added


def ingest_following(db: Session, follower_id: str, entries: list[dict]) -> int:
    """Insert Follow rows discovered from a peer — never deletes.

    Raises ValueError if any entry is missing *id*, or if a self-follow
    is detected.
    """
    return _upsert_follow_edges(
        db, follower_id, entries,
        direction="following", cleanup=False,
    )


def sync_following(db: Session, follower_id: str, entries: list[dict]) -> int:
    """Insert Follow rows and soft-delete local follows not in *entries*.

    Treats *entries* as the authoritative following set from the user's
    home server.  Returns count of new rows inserted (not counting deletions).

    Raises ValueError if any entry is missing *id*, or if a self-follow
    is detected.
    """
    return _upsert_follow_edges(
        db, follower_id, entries,
        direction="following", cleanup=True,
    )


def ingest_followers(db: Session, followed_id: str, entries: list[dict]) -> int:
    """Insert Follow rows for users who follow *followed_id* — never deletes.

    Raises ValueError if any entry is missing *id*, or if a self-follow
    is detected.
    """
    return _upsert_follow_edges(
        db, followed_id, entries,
        direction="followers", cleanup=False,
    )


def sync_followers(db: Session, followed_id: str, entries: list[dict]) -> int:
    """Insert Follow rows and soft-delete local followers not in *entries*.

    Treats *entries* as the authoritative followers set from the user's
    home server.  Returns count of new rows inserted (not counting deletions).

    Raises ValueError if any entry is missing *id*, or if a self-follow
    is detected.
    """
    return _upsert_follow_edges(
        db, followed_id, entries,
        direction="followers", cleanup=True,
    )


def ingest_articles(db: Session, entries: list[dict]) -> int:
    """Insert article metadata discovered from a peer — lazy discovery.

    This is a **lightweight stub**: the article record arrives before its
    git content.  It lets users know the article exists on the peer (title,
    status, authors) without pulling the full git bundle.  The actual git
    content is fetched later, on-demand, by ``article show`` or ``sync``.

    Only writes if the article does not already exist locally.  Existing
    articles are skipped — full reconciliation (authors, status, reviews,
    scores) happens in ``apply_sync_bundle`` when the git content is pulled.

    **Side effect:** Creates User stubs via ``create_user_stub`` for any
    author IDs not already present in the local DB, ensuring FK integrity.

    Raises ValueError if any entry is missing *id*, *title*, or *status*.
    """
    _require_keys(entries, "id", "title", "status", label="article_meta")

    # Datetime fields that may arrive as ISO strings from JSON.
    _dt_fields = {"sink_start", "created_at", "witnessed_at", "updated_at"}

    added = 0
    for e in entries:
        if get_article(db, e["id"]) is not None:
            continue
        # Convert ISO datetime strings to Python datetime objects.
        for field in _dt_fields:
            val = e.get(field)
            if isinstance(val, str):
                e[field] = datetime.fromisoformat(val)
        author_ids = e.get("authors", [])
        # Ensure authors exist locally (create_user_stub is idempotent).
        for aid in author_ids:
            create_user_stub(db, user_id=aid, name=short_id(aid),
                             public_key="", salt="")
        article = Article(**{k: v for k, v in e.items() if k != "authors"})
        create_article_from_orm(db, article, author_ids)
        added += 1
    db.flush()
    return added


def ingest_bookmarks(db: Session, user_id: str, entries: list[dict]) -> int:
    """Insert bookmarks discovered from a peer — lazy social discovery.

    ``add_bookmark`` is idempotent — duplicates are silently skipped.
    Raises ValueError if any entry is missing *article_id*.
    """
    _require_keys(entries, "article_id", label="bookmarks")
    for e in entries:
        add_bookmark(db, user_id, e["article_id"])
    return len(entries)


def ingest_maintainers(db: Session, article_id: str, entries: list[dict]) -> int:
    """Insert maintainers discovered from a peer — lazy social discovery.

    ``add_maintainer`` is idempotent — duplicates are silently skipped.
    Raises ValueError if any entry is missing *user_id*.
    """
    _require_keys(entries, "user_id", label="script_maintainers")
    for e in entries:
        add_maintainer(db, article_id, e["user_id"])
    return len(entries)


def ingest_shares(db: Session, user_id: str, entries: list[dict]) -> int:
    """Insert shares discovered from a peer — lazy social discovery.

    ``add_share`` is an upsert — duplicates update the existing row.
    Raises ValueError if any entry is missing *article_id*.
    """
    _require_keys(entries, "article_id", label="shares")
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
    _require_keys(entries, "event", "message", label="notifications")
    from peerpedia_core.storage.db.crud_notification import ensure_notification

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
