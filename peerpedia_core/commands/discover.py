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

from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.crud_article import get_article, insert_article
from peerpedia_core.storage.db.crud_bookmark import add_bookmark, is_bookmarked
from peerpedia_core.storage.db.crud_maintainer import add_maintainer, is_maintainer
from peerpedia_core.storage.db.crud_user import follow_user, get_user, is_following
from peerpedia_core.storage.db.models import Article, User

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

    Only writes users that do not already exist locally.  Existing users
    with a missing address raise ``ValueError`` (data inconsistency —
    the local record should have been created with an address).

    Raises ValueError if any entry is missing *id*, *name*, or *address*.
    """
    _require_keys(entries, "id", "name", "address", label="users")

    added = 0
    for e in entries:
        u = get_user(db, e["id"])
        if u is None:
            u = User(id=e["id"], name=e["name"], address=e["address"])
            db.add(u)
            added += 1
        elif not u.address:
            raise ValueError(
                f"merge_users: existing user {e['id']} has no address; "
                f"peer data has address={e['address']!r}. Data inconsistency."
            )
    db.flush()
    return added


def merge_follows(db: Session, follower_id: str, entries: list[dict]) -> int:
    """Insert follows discovered from a peer — lazy social discovery.

    Creates ``follow`` rows for users that *follower_id* follows on the
    peer.  Duplicates (already following) are logged as warnings and
    skipped.  Self-follows raise ``ValueError`` — they indicate corrupt
    peer data.

    Raises ValueError if any entry is missing *id*, or if a self-follow
    is detected.
    """
    _require_keys(entries, "id", label="follows")

    added = 0
    for e in entries:
        followed_id = e["id"]
        if followed_id == follower_id:
            raise ValueError(
                f"merge_follows: self-follow detected for user {follower_id}"
            )
        if is_following(db, follower_id, followed_id):
            logger.warning(
                "merge_follows: %s already follows %s — skipping duplicate",
                follower_id,
                followed_id,
            )
            continue
        follow_user(db, follower_id=follower_id, followed_id=followed_id)
        added += 1
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

    Raises ValueError if any entry is missing *id*, *title*, or *status*.
    """
    _require_keys(entries, "id", "title", "status", label="article_meta")

    added = 0
    for e in entries:
        if get_article(db, e["id"]) is not None:
            logger.warning(
                "merge_article_meta: article %s already exists — skipping duplicate",
                e["id"],
            )
            continue
        author_ids = e.get("authors", [])
        article = Article(**{k: v for k, v in e.items() if k != "authors"})
        insert_article(db, article, author_ids)
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
