# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Follow CRUD — social graph edges, ``session.flush()`` only.

Functions
---------
**Follow — writes**
  follow_user / unfollow_user / follow_users / add_followers
  set_following / set_followers

**Follow — reads**
  is_following / get_followers / get_following
  get_follower_count / get_following_count / get_top_users_by_followers

Reviewer's checklist
--------------------
- All functions call ``session.flush()``, not ``session.commit()``.
- Follow queries always filter ``deleted_at.is_(None)`` on FollowStorage.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from peerpedia_core.storage.db._validators import require_not_same
from peerpedia_core.storage.db.models import FollowStorage, UserStorage


# ═══════════════════════════════════════════════════════════════════════════════
# Follow — writes
# ═══════════════════════════════════════════════════════════════════════════════


def follow_user(session: Session, follower_id: str, followed_id: str) -> FollowStorage:
    """Create or restore a follow relationship.  Raises ValueError on self-follow.

    If a soft-deleted row exists, restores it (``deleted_at=None``).
    Otherwise inserts a new row.
    """
    require_not_same(follower_id, followed_id, label="follow")
    f = session.query(FollowStorage).filter(
        FollowStorage.follower_id == follower_id,
        FollowStorage.followed_id == followed_id,
    ).first()
    if f:
        f.deleted_at = None  # restore soft-deleted row
    else:
        f = FollowStorage(follower_id=follower_id, followed_id=followed_id)
        session.add(f)
    session.flush()
    return f


def _soft_delete_follow_row(row: FollowStorage) -> None:
    """Mark a FollowStorage row as soft-deleted.  Caller owns flush."""
    row.deleted_at = datetime.now(timezone.utc)


def follow_users(session: Session, follower_id: str, followed_ids: set[str]) -> int:
    """*follower_id* follows everyone in *followed_ids* (idempotent).

    Skips pairs that already exist.  Returns count of new rows inserted.
    """
    added = 0
    for other_id in followed_ids:
        if is_following(session, follower_id, other_id):
            continue
        follow_user(session, follower_id=follower_id, followed_id=other_id)
        added += 1
    return added


def add_followers(session: Session, followed_id: str, follower_ids: set[str]) -> int:
    """Everyone in *follower_ids* follows *followed_id* (idempotent).

    Skips pairs that already exist.  Returns count of new rows inserted.
    """
    added = 0
    for other_id in follower_ids:
        if is_following(session, other_id, followed_id):
            continue
        follow_user(session, follower_id=other_id, followed_id=followed_id)
        added += 1
    return added


def set_following(session: Session, follower_id: str, followed_ids: set[str]) -> int:
    """Soft-delete any ``follower_id → *`` rows whose target is not in *followed_ids*.

    After this call, *follower_id* follows exactly the users in *followed_ids*
    (plus any follows not managed by this peer).  An empty *followed_ids* is a
    no-op — returns 0.  Returns count removed.
    """
    if not followed_ids:
        return 0
    rows = (
        session.query(FollowStorage)
        .filter(FollowStorage.follower_id == follower_id, FollowStorage.deleted_at.is_(None))
        .all()
    )
    removed = 0
    for row in rows:
        if row.followed_id not in followed_ids:
            _soft_delete_follow_row(row)
            removed += 1
    if removed:
        session.flush()
    return removed


def set_followers(session: Session, followed_id: str, follower_ids: set[str]) -> int:
    """Soft-delete any ``* → followed_id`` rows whose source is not in *follower_ids*.

    After this call, exactly the users in *follower_ids* follow *followed_id*
    (plus any followers not managed by this peer).  An empty *follower_ids* is a
    no-op — returns 0.  Returns count removed.
    """
    if not follower_ids:
        return 0
    rows = (
        session.query(FollowStorage)
        .filter(FollowStorage.followed_id == followed_id, FollowStorage.deleted_at.is_(None))
        .all()
    )
    removed = 0
    for row in rows:
        if row.follower_id not in follower_ids:
            _soft_delete_follow_row(row)
            removed += 1
    if removed:
        session.flush()
    return removed


def unfollow_user(session: Session, follower_id: str, followed_id: str) -> None:
    """Soft-delete a follow relationship.  Idempotent — no-op if not following."""
    f = session.query(FollowStorage).filter(
        FollowStorage.follower_id == follower_id,
        FollowStorage.followed_id == followed_id,
        FollowStorage.deleted_at.is_(None),
    ).first()
    if f:
        _soft_delete_follow_row(f)
        session.flush()


# ═══════════════════════════════════════════════════════════════════════════════
# Follow — reads
# ═══════════════════════════════════════════════════════════════════════════════


def is_following(session: Session, follower_id: str, followed_id: str) -> bool:
    """Return True if *follower_id* follows *followed_id* (excludes soft-deleted)."""
    return session.query(FollowStorage).filter(
        FollowStorage.follower_id == follower_id,
        FollowStorage.followed_id == followed_id,
        FollowStorage.deleted_at.is_(None),
    ).first() is not None


def get_followers(session: Session, user_id: str) -> list[UserStorage]:
    """Return users who follow *user_id* (excludes soft-deleted, single JOIN)."""
    return (
        session.query(UserStorage)
        .join(FollowStorage, UserStorage.id == FollowStorage.follower_id)
        .filter(FollowStorage.followed_id == user_id, FollowStorage.deleted_at.is_(None))
        .all()
    )


def get_following(session: Session, user_id: str) -> list[UserStorage]:
    """Return users that *user_id* follows (excludes soft-deleted, single JOIN)."""
    return (
        session.query(UserStorage)
        .join(FollowStorage, UserStorage.id == FollowStorage.followed_id)
        .filter(FollowStorage.follower_id == user_id, FollowStorage.deleted_at.is_(None))
        .all()
    )


def get_follower_count(session: Session, user_id: str) -> int:
    """Return the number of active followers *user_id* has."""
    return (
        session.query(FollowStorage)
        .filter(FollowStorage.followed_id == user_id, FollowStorage.deleted_at.is_(None))
        .count()
    )


def get_following_count(session: Session, user_id: str) -> int:
    """Return the number of active users *user_id* follows."""
    return (
        session.query(FollowStorage)
        .filter(FollowStorage.follower_id == user_id, FollowStorage.deleted_at.is_(None))
        .count()
    )


def get_top_users_by_followers(session: Session, limit: int = 20) -> list[dict]:
    """Return users ranked by active follower count (descending).

    Each dict has ``id``, ``name``, and ``follower_count``.
    Includes all users — even those with 0 followers — so new users
    are discoverable via ``peerpedia school``.
    """
    rows = (
        session.query(
            UserStorage.id, UserStorage.name,
            func.count(FollowStorage.follower_id).label("follower_count"),
        )
        .outerjoin(FollowStorage, (FollowStorage.followed_id == UserStorage.id)
                   & (FollowStorage.deleted_at.is_(None)))
        .group_by(UserStorage.id, UserStorage.name)
        .order_by(func.count(FollowStorage.follower_id).desc())
        .limit(limit)
        .all()
    )
    return [
        {"id": r.id, "name": r.name, "follower_count": r.follower_count}
        for r in rows
    ]
