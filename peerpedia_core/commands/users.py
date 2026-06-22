# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""User operations -- thin wrappers so CLI doesn't import storage/db directly."""

from __future__ import annotations

from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.crud_user import (
    create_user as _create,
    follow_user as _follow,
    get_followers as _get_followers,
    get_following as _get_following,
    get_user as _get,
    get_user_by_name as _get_by_name,
    search_users as _search_users,
    is_following as _is_following,
    unfollow_user as _unfollow,
    update_user_public_key as _update_pubkey,
    update_user_salt as _update_salt,
)


def create_user(db: Session, *, name: str, affiliation: str = "", password_hash: str = "", email: str = ""):
    """Create a new user."""
    return _create(db, name=name, affiliation=affiliation, password_hash=password_hash, email=email)


def get_user(db: Session, user_ref: str):
    """Get a user by ID or name. Returns None if not found."""
    return _get(db, user_ref)


def get_user_by_name(db: Session, name: str):
    """Get a user by exact name match. Returns None if not found."""
    return _get_by_name(db, name)


def update_user_public_key(db: Session, user_id: str, pubkey_hex: str):
    """Set the public key for a user."""
    return _update_pubkey(db, user_id, pubkey_hex)


def update_user_salt(db: Session, user_id: str, salt_hex: str):
    """Set the scrypt salt for a user."""
    return _update_salt(db, user_id, salt_hex)


def follow_user(db: Session, follower_id: str, followed_id: str):
    """Follow a user. Raises ValueError if self-follow."""
    return _follow(db, follower_id, followed_id)


def unfollow_user(db: Session, follower_id: str, followed_id: str):
    """Unfollow a user. Idempotent."""
    _unfollow(db, follower_id, followed_id)


def is_following(db: Session, follower_id: str, followed_id: str) -> bool:
    """Check if follower_id follows followed_id."""
    return _is_following(db, follower_id, followed_id)


def get_followers(db: Session, user_id: str) -> list:
    """Return users following user_id."""
    return _get_followers(db, user_id)


def get_following(db: Session, user_id: str) -> list:
    """Return users user_id follows."""
    return _get_following(db, user_id)


def search_users(db: Session, query: str, limit: int | None = None, offset: int = 0) -> list:
    """Fuzzy search users by name."""
    return _search_users(db, query, limit=limit, offset=offset)
