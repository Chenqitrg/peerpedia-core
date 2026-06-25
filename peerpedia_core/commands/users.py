# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""User operations — follow/unfollow, profile queries.

Redirects to ``storage/db/crud_user.py`` via the commands facade so
CLI and routes never import storage/db directly.
"""

from __future__ import annotations

from peerpedia_core.storage.db import Session
from peerpedia_core.commands.notifications import create_notification
from peerpedia_core.storage.db.crud_user import (
    create_user as _create,
    create_user_stub as _create_stub,
    follow_user as _follow,
    get_user as _get,
    increment_failed_login as _increment_failed,
    list_users as _list_users,
    get_followers as _get_followers,
    get_following as _get_following,
    get_top_users_by_followers as _get_top_users_by_followers,
    get_user as _get,
    get_user_by_name as _get_by_name,
    reset_failed_login as _reset_failed,
    search_users as _search_users,
    soft_delete_user as _soft_delete,
    is_following as _is_following,
    unfollow_user as _unfollow,
    update_user_public_key as _update_pubkey,
    update_user_salt as _update_salt,
)


def create_user(db: Session, *, name: str, public_key: str, affiliation: str = ""):
    """Create a new user."""
    return _create(db, name=name, public_key=public_key, affiliation=affiliation)


def create_user_stub(db: Session, *, user_id: str, name: str, public_key: str, salt: str):
    """Create a minimal User record with all fields set — for device bootstrap.

    Used when setting up a new device: the user copies their user_id, name,
    public_key, and salt from their original device (via ``account whoami
    --verbose --json``) and runs ``account bootstrap`` on the new device so
    that ``account recover`` can find the User row and re-derive the key.

    Does NOT write a session file — the user still needs ``account recover``
    to verify their password and obtain a session.
    """
    return _create_stub(db, user_id=user_id, name=name, public_key=public_key, salt=salt)


def get_user(db: Session, user_ref: str):
    """Get a user by ID or name. Returns None if not found."""
    return _get(db, user_ref)


def get_user_by_name(db: Session, name: str) -> list:
    """Get users by exact name match. Returns empty list if none found."""
    return _get_by_name(db, name)


def update_user_public_key(db: Session, user_id: str, pubkey_hex: str):
    """Set the public key for a user."""
    # TODO(social-recovery): see docs/social-recovery-design.md
    return _update_pubkey(db, user_id, pubkey_hex)


def update_user_salt(db: Session, user_id: str, salt_hex: str):
    """Set the scrypt salt for a user."""
    return _update_salt(db, user_id, salt_hex)


def follow_user(db: Session, follower_id: str, followed_id: str):
    """Follow a user. Notifies followed user. Raises ValueError if self-follow."""
    result = _follow(db, follower_id, followed_id)

    follower = _get(db, follower_id)
    if follower is None:
        raise RuntimeError(
            f"Follower {follower_id} not found after follow — DB inconsistency"
        )
    follower_name = follower.name
    create_notification(
        db, user_id=followed_id, event="new_follower",
        message=f"{follower_name} started following you",
        actor_id=follower_id,
    )
    return result


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


def get_top_users_by_followers(db: Session, limit: int = 20) -> list[dict]:
    """Return users ranked by active follower count (descending).

    Each dict has ``id``, ``name``, and ``follower_count``.
    """
    return _get_top_users_by_followers(db, limit=limit)


def search_users(db: Session, query: str, limit: int | None = None, offset: int = 0) -> list:
    """Fuzzy search users by name."""
    return _search_users(db, query, limit=limit, offset=offset)


def list_users(db: Session) -> list:
    """Return all active users, newest first."""
    return _list_users(db)


def increment_failed_login(db: Session, user_id: str) -> None:
    """Increment the failed-login counter. Locks the account at threshold."""
    _increment_failed(db, user_id)


def reset_failed_login(db: Session, user_id: str) -> None:
    """Clear the failed-login counter after a successful login."""
    _reset_failed(db, user_id)


def soft_delete_user(db: Session, user_id: str) -> None:
    """Soft-delete a user account (GDPR right-to-erasure)."""
    _soft_delete(db, user_id)
