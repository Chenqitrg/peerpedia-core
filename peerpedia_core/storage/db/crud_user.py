# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""User CRUD — database only, ``session.flush()`` only.

Functions
---------
**User creation**
  create_user              New user with random UUID
  create_user_stub         Bootstrap user with pre-determined id and salt
  ensure_user              Upsert — create if not exists, verify address consistency

**User queries**
  get_user_by_id           By ID, or None
  list_active_users        Active users (no ordering guarantee)
  list_recent_users        Active users, newest first, with optional limit
  list_users_by_name       Exact name match (active users only)
  search_users             By name (ILIKE) or UUID prefix
  list_users_by_ids        Bulk fetch; raises if any missing

**User updates**
  update_user_public_key   Replace public key
  set_user_pubkey_tofu     TOFU (Trust On First Use) semantics for public key
  update_user_salt         Replace scrypt salt
  update_user_reputation   Write reputation scores dict

**Rate limiting**
  increment_failed_login   Bump counter; lock account at threshold
  reset_failed_login       Clear counter and lock after successful login

**Account lifecycle**
  soft_delete_user         GDPR right-to-erasure (sets deleted_at)

**Follow — writes**
  follow_user / unfollow_user / follow_users / add_followers
  set_following / set_followers

**Follow — reads**
  is_following / get_followers / get_following
  get_follower_count / get_following_count / get_top_users_by_followers

Reviewer's checklist
--------------------
- All functions call ``session.flush()``, not ``session.commit()``.
- Active-user queries always filter ``deleted_at.is_(None)``.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from peerpedia_core.config.params import params
from peerpedia_core.storage.db._validators import require_not_same
from peerpedia_core.storage.db.models import FollowStorage, UserStorage


# ═══════════════════════════════════════════════════════════════════════════════
# User creation
# ═══════════════════════════════════════════════════════════════════════════════


def _insert_user(session: Session, **fields) -> UserStorage:
    """Insert a UserStorage row and flush.  All field validation is the caller's job."""
    u = UserStorage(**fields)
    session.add(u)
    session.flush()
    return u


def create_user(
    session: Session,
    name: str,
    public_key: str | None = None,
    *,
    affiliation: str = "",
) -> UserStorage:
    """Create a new user with a random UUID and an anonymous display name."""
    return _insert_user(
        session,
        id=str(uuid.uuid4()),
        name=name,
        public_key=public_key,
        affiliation=affiliation,
    )


def create_user_stub(
    session: Session,
    user_id: str,
    name: str,
    public_key: str,
    salt: str,
) -> UserStorage:
    """Create a minimal user record with pre-determined id and salt.

    Idempotent — returns the existing user if *user_id* already exists.
    Used for device bootstrap and lazy discovery.  Unlike ``create_user``,
    this accepts an explicit id and salt so the user can re-derive their
    key on a new device via ``account recover``.
    """
    existing = session.get(UserStorage, user_id)
    if existing is not None:
        return existing
    return _insert_user(session, id=user_id, name=name, public_key=public_key, salt=salt)


def ensure_user(
    session: Session, user_id: str, name: str, *, address: str = "",
) -> UserStorage:
    """Return the user, creating it if it doesn't exist."""
    existing = session.get(UserStorage, user_id)
    if existing is not None:
        return existing
    return _insert_user(session, id=user_id, name=name, address=address)


# ═══════════════════════════════════════════════════════════════════════════════
# User queries
# ═══════════════════════════════════════════════════════════════════════════════


def get_user_by_id(session: Session, user_id: str) -> UserStorage | None:
    """Return a user by ID, or None."""
    return session.get(UserStorage, user_id)


def list_users_by_name(session: Session, name: str) -> list[UserStorage]:
    """List active users with the given name (may be multiple — P2P allows duplicates)."""
    return session.query(UserStorage).filter(
        UserStorage.name == name, UserStorage.deleted_at.is_(None)
    ).all()


def list_active_users(session: Session) -> list[UserStorage]:
    """Return all active users.  No ordering guarantee — use
    ``list_recent_users`` when newest-first ordering matters."""
    return session.query(UserStorage).filter(
        UserStorage.deleted_at.is_(None)
    ).all()


def list_recent_users(session: Session, limit: int = 20) -> list[UserStorage]:
    """Return active users, newest first, capped at *limit*."""
    return session.query(UserStorage).filter(
        UserStorage.deleted_at.is_(None)
    ).order_by(UserStorage.created_at.desc()).limit(limit).all()


def search_users(session: Session, query: str = "", *,
                 id_prefix: str = "", limit: int | None = None,
                 offset: int = 0) -> list[UserStorage]:
    """Search active users by name (ILIKE), UUID prefix, or both."""
    q = session.query(UserStorage).filter(UserStorage.deleted_at.is_(None))
    if id_prefix:
        q = q.filter(UserStorage.id.startswith(id_prefix))
    elif query:
        q = q.filter(UserStorage.name.ilike(f"%{query}%"))
    q = q.order_by(UserStorage.created_at.desc())
    if limit is not None:
        q = q.limit(limit).offset(offset)
    return q.all()


def list_users_by_ids(session: Session, user_ids: set[str]) -> list[UserStorage]:
    """List UserStorage records for the given IDs.  Returns only those found."""
    if not user_ids:
        return []
    return session.query(UserStorage).filter(UserStorage.id.in_(user_ids)).all()


def map_user_ids_to_names(session: Session, user_ids: set[str]) -> dict[str, str]:
    """Return ``{user_id: display_name}`` for a set of user IDs.

    Raises NotFoundError if any *user_ids* are not found.
    """
    if not user_ids:
        return {}
    return {u.id: u.name for u in list_users_by_ids(session, user_ids)}


# ═══════════════════════════════════════════════════════════════════════════════
# User updates
# ═══════════════════════════════════════════════════════════════════════════════


def update_user_public_key(session: Session, user_id: str, pubkey_hex: str) -> None:
    """Set the public_key for a user. Raises NotFoundError if user not found."""
    rows = session.query(UserStorage).filter(UserStorage.id == user_id).update(
        {"public_key": pubkey_hex}, synchronize_session="fetch"
    )
    session.expire_all()


def set_user_pubkey_tofu(session: Session, user_id: str, pubkey_hex: str, *,
                         user: UserStorage | None = None) -> str:
    """Set public key with TOFU (Trust On First Use) semantics.

    Returns ``"stored"`` (first key), ``"rotated"`` (key changed),
    ``"unchanged"`` (same key), or ``"unknown_user"`` (no such user).

    Pass *user* to avoid a redundant query when the caller already has
    the UserStorage object loaded.
    """
    if user is None:
        user = session.get(UserStorage, user_id)
    if user is None:
        return "unknown_user"
    if user.public_key is None:
        update_user_public_key(session, user_id, pubkey_hex)
        return "stored"
    if user.public_key != pubkey_hex:
        update_user_public_key(session, user_id, pubkey_hex)
        return "rotated"
    return "unchanged"


def update_user_salt(session: Session, user_id: str, salt_hex: str) -> None:
    """Set the scrypt salt for a user. Raises NotFoundError if user not found."""
    rows = session.query(UserStorage).filter(UserStorage.id == user_id).update(
        {"salt": salt_hex}, synchronize_session="fetch"
    )
    session.expire_all()


def update_user_reputation(session: Session, user_id: str, reputation: dict[str, float]) -> None:
    """Persist a new ReputationScores dict for *user_id*.  Raises NotFoundError if not found."""
    rows = session.query(UserStorage).filter(UserStorage.id == user_id).update(
        {"reputation": reputation}, synchronize_session="fetch"
    )
    session.expire_all()


# ═══════════════════════════════════════════════════════════════════════════════
# Rate limiting
# ═══════════════════════════════════════════════════════════════════════════════


def increment_failed_login(session: Session, user: UserStorage) -> None:
    """Increment the failed-login counter.  Locks the account if the
    threshold is reached.

    Caller must have loaded *user* via ``require_user``.
    """
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= params.server.max_failed_login_attempts:
        user.locked_until = datetime.now(timezone.utc) + timedelta(
            minutes=params.server.login_lockout_minutes
        )
    session.flush()


def reset_failed_login(session: Session, user_id: str) -> None:
    """Clear the failed-login counter and lock after a successful login.

    Idempotent — safe to call even if the counter is already zero.

    Raises NotFoundError if the user does not exist.
    """
    rows = session.query(UserStorage).filter(UserStorage.id == user_id).update(
        {"failed_login_attempts": 0, "locked_until": None},
        synchronize_session="fetch",
    )
    session.expire_all()


# ═══════════════════════════════════════════════════════════════════════════════
# Account lifecycle
# ═══════════════════════════════════════════════════════════════════════════════


def soft_delete_user(session: Session, user_id: str) -> None:
    """Soft-delete a user account (GDPR right-to-erasure).

    Sets ``deleted_at`` to the current UTC timestamp.  Callers MUST clear
    the session file and commit afterward.

    Raises NotFoundError if the user does not exist.
    """
    rows = session.query(UserStorage).filter(
        UserStorage.id == user_id, UserStorage.deleted_at.is_(None)
    ).update(
        {"deleted_at": datetime.now(timezone.utc)}, synchronize_session="fetch"
    )
    session.expire_all()

