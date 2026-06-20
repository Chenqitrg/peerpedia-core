# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Bookmark operations -- thin wrappers so CLI doesn't import storage/db directly."""

from __future__ import annotations

from sqlalchemy.orm import Session


def add_bookmark(db: Session, user_id: str, article_id: str):
    """Add a bookmark. Returns the Bookmark row."""
    from peerpedia_core.storage.db.crud_bookmark import add_bookmark as _add
    return _add(db, user_id, article_id)


def get_bookmarks_for_user(db: Session, user_id: str):
    """Return all bookmarks for a user."""
    from peerpedia_core.storage.db.crud_bookmark import get_bookmarks_for_user as _get
    return _get(db, user_id)


def remove_bookmark(db: Session, user_id: str, article_id: str):
    """Remove a bookmark. Idempotent."""
    from peerpedia_core.storage.db.crud_bookmark import remove_bookmark as _rm
    _rm(db, user_id, article_id)
