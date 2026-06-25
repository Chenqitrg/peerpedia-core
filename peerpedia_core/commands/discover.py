# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Merge functions for P2P social graph exchange.

Called by ``social/exchange.py`` (fetch-then-merge orchestration).
Each function takes a list of dicts from a remote peer and merges them
into the local DB — inserting new rows, skipping duplicates::

    merge_users             — create User rows for newly discovered peers
    merge_follows           — insert Follow rows for a user's social graph
    merge_article_meta      — insert Article rows for discovered articles
    merge_bookmarks         — insert Bookmark rows (deprecated, kept for compat)
    merge_script_maintainers— insert maintainer rows from sync

""""""Social discovery merge — DB writes for metadata pulled from peers.

Pure DB operations — no HTTP, no git.  Only imports from ``storage/db/``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.crud_article import create_article_from_orm, get_article
from peerpedia_core.storage.db.crud_bookmark import add_bookmark, is_bookmarked
from peerpedia_core.storage.db.crud_maintainer import add_maintainer, is_maintainer
from peerpedia_core.storage.db.crud_share import add_share as _add_share, is_shared
from peerpedia_core.storage.db.crud_user import (
    create_user_stub, follow_user, get_user, is_following,
)
from peerpedia_core.storage.db.models import Article, Follow, Notification, User

logger = logging.getLogger(__name__)


def _require_keys(entries: list[dict], *keys: str, label: str) -> None:
    """Fail fast if any entry is missing a required key.  Does not touch DB."""
    for e in entries:
        for k in keys:
            if not e.get(k):
                raise ValueError(
                    f"merge_{label}: missing '{k}' in entry {e}"
                )


def merge_users(db: Session, entries: list[dict]) -> int:
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
                f"merge_users: address conflict for {e['id']}: "
                f"local={u.address!r}, peer={e['address']!r}"
            )
    db.flush()
    return added


def merge_follows(
    db: Session, follower_id: str, entries: list[dict], *,
    authoritative: bool = False,
) -> int:
    """Merge follows discovered from a peer — lazy social discovery.

    Creates or restores ``follow`` rows for users in *entries*.

    When *authoritative* is True (home-server pull), the remote list is
    treated as the complete following set: local follows not in *entries*
    are soft-deleted.  When False (peer discovery), only adds/restores,
    never deletes.

    Raises ValueError if any entry is missing *id*, or if a self-follow
    is detected.
    """
    _require_keys(entries, "id", label="follows")

    remote_ids = {e["id"] for e in entries}
    for followed_id in remote_ids:
        if followed_id == follower_id:
            raise ValueError(
                f"merge_follows: self-follow detected for user {follower_id}"
            )

    added = 0
    for followed_id in remote_ids:
        if is_following(db, follower_id, followed_id):
            continue
        follow_user(db, follower_id=follower_id, followed_id=followed_id)
        added += 1

    if authoritative:
        if remote_ids:
            # Soft-delete local follows not present in the authoritative list.
            local_follows = (
                db.query(Follow)
                .filter(
                    Follow.follower_id == follower_id,
                    Follow.deleted_at.is_(None),
                )
                .all()
            )
            removed = 0
            for f in local_follows:
                if f.followed_id not in remote_ids:
                    f.deleted_at = datetime.now(timezone.utc)
                    removed += 1
            if removed:
                logger.info(
                    "merge_follows: authoritative — soft-deleted %d follow(s) for %s",
                    removed, follower_id,
                )
        else:
            logger.warning(
                "merge_follows: authoritative server returned empty following "
                "list for %s — soft-deletes skipped to prevent data loss.",
                follower_id,
            )

    return added


def merge_article_meta(db: Session, entries: list[dict]) -> int:
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
        # Ensure authors exist locally before inserting FK rows.
        for aid in author_ids:
            if get_user(db, aid) is None:
                create_user_stub(db, user_id=aid, name=aid[:8],
                                 public_key="", salt="")
        article = Article(**{k: v for k, v in e.items() if k != "authors"})
        create_article_from_orm(db, article, author_ids)
        added += 1
    db.flush()
    return added


def merge_bookmarks(db: Session, user_id: str, entries: list[dict]) -> int:
    """Insert bookmarks discovered from a peer — lazy social discovery.

    Creates ``bookmark`` rows for articles that *user_id* has bookmarked
    on the peer.  Duplicates (already bookmarked) are logged as warnings
    and skipped.

    Raises ValueError if any entry is missing *article_id*.
    """
    _require_keys(entries, "article_id", label="bookmarks")

    added = 0
    for e in entries:
        article_id = e["article_id"]
        if is_bookmarked(db, user_id, article_id):
            logger.warning(
                "merge_bookmarks: %s already bookmarked %s — skipping duplicate",
                user_id,
                article_id,
            )
            continue
        add_bookmark(db, user_id, article_id)
        added += 1
    db.flush()
    return added


def merge_script_maintainers(db: Session, article_id: str, entries: list[dict]) -> int:
    """Insert maintainers discovered from a peer — lazy social discovery.

    Creates ``script_maintainer`` rows for *article_id*.  Duplicates
    (already a maintainer) are logged as warnings and skipped.

    Raises ValueError if any entry is missing *user_id*.
    """
    _require_keys(entries, "user_id", label="script_maintainers")

    added = 0
    for e in entries:
        user_id = e["user_id"]
        if is_maintainer(db, article_id, user_id):
            logger.warning(
                "merge_script_maintainers: %s is already a maintainer of %s — skipping duplicate",
                user_id,
                article_id,
            )
            continue
        add_maintainer(db, article_id, user_id)
        added += 1
    db.flush()
    return added


def merge_shares(db: Session, user_id: str, entries: list[dict]) -> int:
    """Merge shares discovered from a peer — lazy social discovery.

    Each entry must have ``article_id``.  Duplicates are skipped.
    """
    _require_keys(entries, "article_id", label="shares")

    added = 0
    for e in entries:
        article_id = e["article_id"]
        if is_shared(db, user_id, article_id):
            continue
        _add_share(
            db, user_id, article_id,
            recipient_id=e.get("recipient_id"),
            comment=e.get("comment"),
        )
        added += 1
    return added


def merge_notifications(db: Session, user_id: str, entries: list[dict]) -> int:
    """Insert new notifications from peer data.

    Dedup by (user_id, event, actor_id, article_id, message) — if a
    notification with the same fields already exists, skip it.
    Returns count of new notifications inserted.
    """
    _require_keys(entries, "event", "message", label="notifications")

    added = 0
    for entry in entries:
        existing = db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.event == entry.get("event"),
            Notification.actor_id == entry.get("actor_id"),
            Notification.article_id == entry.get("article_id"),
            Notification.message == entry.get("message"),
        ).first()
        if existing:
            continue
        n = Notification(
            id=entry.get("id"),
            user_id=user_id,
            event=entry["event"],
            message=entry["message"],
            article_id=entry.get("article_id"),
            actor_id=entry.get("actor_id"),
            read=1 if entry.get("read") else 0,
        )
        db.add(n)
        added += 1
    if added:
        db.flush()
    return added
