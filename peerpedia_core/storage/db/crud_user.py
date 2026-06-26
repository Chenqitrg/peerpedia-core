# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""User CRUD — database only, ``session.flush()`` only.

Functions
---------
create_user             New user with Ed25519 public key
get_user                By ID or name
get_user_by_name        Exact name match
update_user_reputation  Write reputation dict (flush only)
follow_user / unfollow_user / get_followers / get_following / get_follower_count

Reviewer's checklist
--------------------
- All functions call ``session.flush()``, not ``session.commit()``.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from peerpedia_core.exceptions import BadRequestError, NotFoundError
from peerpedia_core.storage.db.models import Follow, User


def create_user(
    session: Session,
    name: str,
    public_key: str | None = None,
    *,
    affiliation: str = "",
) -> User:
    """Create a new user with a random UUID and an anonymous display name."""
    u = User(
        id=str(uuid.uuid4()),
        name=name,
        public_key=public_key,
        affiliation=affiliation,
    )
    session.add(u)
    session.flush()
    return u


def create_user_stub(
    session: Session,
    user_id: str,
    name: str,
    public_key: str,
    salt: str,
) -> User:
    """Create a minimal user record with pre-determined id and salt.

    Idempotent — returns the existing user if *user_id* already exists.
    Used for device bootstrap and lazy discovery.  Unlike ``create_user``,
    this accepts an explicit id and salt so the user can re-derive their
    key on a new device via ``account recover``.
    """
    existing = session.get(User, user_id)
    if existing is not None:
        return existing
    u = User(
        id=user_id,
        name=name,
        public_key=public_key,
        salt=salt,
    )
    session.add(u)
    session.flush()
    return u


def get_user(session: Session, user_id: str) -> User | None:
    """Return a user by ID, or None."""
    return session.get(User, user_id)


def get_user_by_name(session: Session, name: str) -> list[User]:
    """Return all active users with the given name (may be multiple — P2P allows duplicates)."""
    return session.query(User).filter(User.name == name, User.deleted_at.is_(None)).all()


def list_users(session: Session, limit: int | None = 100) -> list[User]:
    """Return active users, newest first.  Capped at *limit* (default 100)."""
    q = session.query(User).filter(User.deleted_at.is_(None)).order_by(User.created_at.desc())
    if limit is not None:
        q = q.limit(limit)
    return q.all()


def search_users(session: Session, query: str = "", *,
                 id_prefix: str = "", limit: int | None = None,
                 offset: int = 0) -> list[User]:
    """Search active users by name (ILIKE), UUID prefix, or both."""
    q = session.query(User).filter(User.deleted_at.is_(None))
    if id_prefix:
        q = q.filter(User.id.startswith(id_prefix))
    elif query:
        q = q.filter(User.name.ilike(f"%{query}%"))
    q = q.order_by(User.created_at.desc())
    if limit is not None:
        q = q.limit(limit).offset(offset)
    return q.all()


def get_users_by_ids(session: Session, user_ids: set[str]) -> list[User]:
    """Return User records for the given IDs.

    Raises ValueError if any *user_ids* are not found — missing users
    at this point means data corruption (review from nonexistent user).
    """
    if not user_ids:
        return []
    users = session.query(User).filter(User.id.in_(user_ids)).all()
    found = {u.id for u in users}
    missing = user_ids - found
    if missing:
        raise NotFoundError(f"Users not found: {', '.join(sorted(missing))}", resource_type="user")
    return users


def update_user_public_key(session: Session, user_id: str, pubkey_hex: str) -> None:
    """Set the public_key for a user. Raises ValueError if user not found."""
    rows = session.query(User).filter(User.id == user_id).update(
        {"public_key": pubkey_hex}, synchronize_session="fetch"
    )
    if rows == 0:
        raise NotFoundError(f"User {user_id} not found", resource_type="user", resource_id=user_id)
    session.expire_all()


def update_user_salt(session: Session, user_id: str, salt_hex: str) -> None:
    """Set the scrypt salt for a user. Raises ValueError if user not found."""
    rows = session.query(User).filter(User.id == user_id).update(
        {"salt": salt_hex}, synchronize_session="fetch"
    )
    if rows == 0:
        raise NotFoundError(f"User {user_id} not found", resource_type="user", resource_id=user_id)
    session.expire_all()


def update_user_reputation(session: Session, user_id: str, reputation: dict) -> None:
    """Persist a new ReputationScores dict for *user_id*.  Raises NotFoundError if not found."""
    rows = session.query(User).filter(User.id == user_id).update(
        {"reputation": reputation}, synchronize_session="fetch"
    )
    if rows == 0:
        raise NotFoundError(f"User {user_id} not found", resource_type="user", resource_id=user_id)
    session.expire_all()


# ── Rate limiting ────────────────────────────────────────────────────────

_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


def increment_failed_login(session: Session, user_id: str) -> None:
    """Increment the failed-login counter.  Locks the account if the
    threshold is reached.

    Raises NotFoundError if the user does not exist.
    """
    from datetime import datetime, timedelta, timezone

    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found", resource_type="user", resource_id=user_id)
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= _MAX_FAILED_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=_LOCKOUT_MINUTES)
    session.flush()


def reset_failed_login(session: Session, user_id: str) -> None:
    """Clear the failed-login counter and lock after a successful login.

    Idempotent — safe to call even if the counter is already zero.

    Raises NotFoundError if the user does not exist.
    """
    rows = session.query(User).filter(User.id == user_id).update(
        {"failed_login_attempts": 0, "locked_until": None},
        synchronize_session="fetch",
    )
    if rows == 0:
        raise NotFoundError(f"User {user_id} not found", resource_type="user", resource_id=user_id)
    session.expire_all()


# ── Account lifecycle ────────────────────────────────────────────────────


def soft_delete_user(session: Session, user_id: str) -> None:
    """Soft-delete a user account (GDPR right-to-erasure).

    Sets ``deleted_at`` to the current UTC timestamp.  Callers MUST clear
    the session file and commit afterward.

    Raises NotFoundError if the user does not exist.
    """
    from datetime import datetime, timezone

    rows = session.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).update(
        {"deleted_at": datetime.now(timezone.utc)}, synchronize_session="fetch"
    )
    if rows == 0:
        raise NotFoundError(f"User {user_id} not found or already deleted",
                            resource_type="user", resource_id=user_id)
    session.expire_all()


# ── Follow ───────────────────────────────────────────────────────────────


def follow_user(session: Session, follower_id: str, followed_id: str) -> Follow:
    """Create or restore a follow relationship.  Raises ValueError on self-follow.

    If a soft-deleted row exists, restores it (``deleted_at=None``).
    Otherwise inserts a new row.
    """
    if follower_id == followed_id:
        raise BadRequestError("A user cannot follow themselves")
    f = session.query(Follow).filter(
        Follow.follower_id == follower_id,
        Follow.followed_id == followed_id,
    ).first()
    if f:
        f.deleted_at = None  # restore soft-deleted row
    else:
        f = Follow(follower_id=follower_id, followed_id=followed_id)
        session.add(f)
    session.flush()
    return f


def _soft_delete_follow_row(row: Follow) -> None:
    """Mark a Follow row as soft-deleted.  Caller owns flush."""
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
        session.query(Follow)
        .filter(Follow.follower_id == follower_id, Follow.deleted_at.is_(None))
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
        session.query(Follow)
        .filter(Follow.followed_id == followed_id, Follow.deleted_at.is_(None))
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
    f = session.query(Follow).filter(
        Follow.follower_id == follower_id,
        Follow.followed_id == followed_id,
        Follow.deleted_at.is_(None),
    ).first()
    if f:
        _soft_delete_follow_row(f)
        session.flush()


def is_following(session: Session, follower_id: str, followed_id: str) -> bool:
    """Return True if *follower_id* follows *followed_id* (excludes soft-deleted)."""
    return session.query(Follow).filter(
        Follow.follower_id == follower_id,
        Follow.followed_id == followed_id,
        Follow.deleted_at.is_(None),
    ).first() is not None


def get_followers(session: Session, user_id: str) -> list[User]:
    """Return users who follow *user_id* (excludes soft-deleted, single JOIN)."""
    return (
        session.query(User)
        .join(Follow, User.id == Follow.follower_id)
        .filter(Follow.followed_id == user_id, Follow.deleted_at.is_(None))
        .all()
    )


def get_following(session: Session, user_id: str) -> list[User]:
    """Return users that *user_id* follows (excludes soft-deleted, single JOIN)."""
    return (
        session.query(User)
        .join(Follow, User.id == Follow.followed_id)
        .filter(Follow.follower_id == user_id, Follow.deleted_at.is_(None))
        .all()
    )


def get_follower_count(session: Session, user_id: str) -> int:
    """Return the number of active followers *user_id* has."""
    return (
        session.query(Follow)
        .filter(Follow.followed_id == user_id, Follow.deleted_at.is_(None))
        .count()
    )


def get_following_count(session: Session, user_id: str) -> int:
    """Return the number of active users *user_id* follows."""
    return (
        session.query(Follow)
        .filter(Follow.follower_id == user_id, Follow.deleted_at.is_(None))
        .count()
    )


def get_top_users_by_followers(session: Session, limit: int = 20) -> list[dict]:
    """Return users ranked by active follower count (descending).

    Each dict has ``id``, ``name``, and ``follower_count``.
    Includes all users — even those with 0 followers — so new users
    are discoverable via ``peerpedia school``.
    """
    from sqlalchemy import func
    rows = (
        session.query(
            User.id, User.name,
            func.count(Follow.follower_id).label("follower_count"),
        )
        .outerjoin(Follow, (Follow.followed_id == User.id)
                   & (Follow.deleted_at.is_(None)))
        .group_by(User.id, User.name)
        .order_by(func.count(Follow.follower_id).desc())
        .limit(limit)
        .all()
    )
    return [
        {"id": r.id, "name": r.name, "follower_count": r.follower_count}
        for r in rows
    ]
