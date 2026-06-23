# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Social discovery server handlers — pure logic, no HTTP.

Called by the routing layer in ``server/app.py`` (start with
``peerpedia server start``).  Thin wrappers around ``commands/`` —
the server layer never touches DB directly.
"""

from __future__ import annotations

from peerpedia_core.commands import (
    add_bookmark as _add_bookmark,
    follow_user as _follow_user,
    get_bookmarks_for_user as _get_bookmarks,
    get_followers as _get_followers,
    get_following as _get_following,
    list_articles as _list_articles,
    unfollow_user as _unfollow_user,
)
from peerpedia_core.storage.db import Session


# ── GET handlers — read social graph ──────────────────────────────────────────


def get_following(db: Session, user_id: str) -> list:
    """Return users that *user_id* follows."""
    return _get_following(db, user_id)


def get_followers(db: Session, user_id: str) -> list:
    """Return users that follow *user_id*."""
    return _get_followers(db, user_id)


def get_articles(db: Session, user_id: str, limit: int = 20, offset: int = 0) -> list:
    """Return articles authored by *user_id*, with pagination."""
    return _list_articles(db, author_id=user_id, limit=limit, offset=offset)


def get_bookmarks(db: Session, user_id: str) -> list:
    """Return articles bookmarked by *user_id*."""
    return _get_bookmarks(db, user_id)


# ── POST handlers — write social graph ────────────────────────────────────────


def handle_follow(db: Session, follower_id: str, followed_id: str) -> None:
    """Record a follow relationship.  Idempotent — no-op if already following."""
    _follow_user(db, follower_id, followed_id)


def handle_unfollow(db: Session, follower_id: str, followed_id: str) -> None:
    """Remove a follow relationship.  Idempotent — no-op if not following."""
    _unfollow_user(db, follower_id, followed_id)


def handle_bookmark(db: Session, user_id: str, article_id: str) -> None:
    """Record a bookmark.  Idempotent — no-op if already bookmarked."""
    _add_bookmark(db, user_id, article_id)
