# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Alias CRUD — database only, ``session.flush()`` only."""

from sqlalchemy.orm import Session

from peerpedia_core.storage.db._validators import require_alias_nonempty, require_not_same
from peerpedia_core.storage.db.guards import require_following_for_alias
from peerpedia_core.storage.db.models import AliasStorage, UserStorage


def set_alias(session: Session, owner_id: str, target_id: str, alias: str) -> AliasStorage:
    """Set or update an alias for *target_id*.  Upsert — overwrites if exists."""
    alias = alias.strip()
    require_alias_nonempty(alias)
    require_not_same(owner_id, target_id, label="alias")
    require_following_for_alias(session, owner_id, target_id)

    a = session.query(AliasStorage).filter(
        AliasStorage.owner_id == owner_id, AliasStorage.target_id == target_id,
    ).first()
    if a:
        a.alias = alias
    else:
        a = AliasStorage(owner_id=owner_id, target_id=target_id, alias=alias)
        session.add(a)
    session.flush()
    return a


def remove_alias(session: Session, owner_id: str, target_id: str) -> None:
    """Remove the alias for *target_id*.  No-op if none set."""
    a = session.query(AliasStorage).filter(
        AliasStorage.owner_id == owner_id, AliasStorage.target_id == target_id,
    ).first()
    if a:
        session.delete(a)
        session.flush()


def get_alias_for(session: Session, owner_id: str, target_id: str) -> str | None:
    """Return the alias *owner_id* set for *target_id*, or None."""
    a = session.query(AliasStorage).filter(
        AliasStorage.owner_id == owner_id, AliasStorage.target_id == target_id,
    ).first()
    return a.alias if a else None


def list_aliases(session: Session, owner_id: str) -> list[AliasStorage]:
    """Return all aliases set by *owner_id*, sorted alphabetically."""
    return (
        session.query(AliasStorage)
        .filter(AliasStorage.owner_id == owner_id)
        .order_by(AliasStorage.alias)
        .all()
    )


def resolve_username_or_alias(
    session: Session, owner_id: str, name: str,
) -> list[UserStorage]:
    """Find users by *name*, checking username first then aliases.

    Returns all matches (may be 0, 1, or multiple).  Caller handles
    disambiguation — if multiple, prompt user to use UUID.
    """
    # Exact username match
    by_name = (
        session.query(UserStorage).filter(UserStorage.name == name).all()
    )
    if by_name:
        return by_name

    # AliasStorage match
    return (
        session.query(UserStorage)
        .join(AliasStorage, UserStorage.id == AliasStorage.target_id)
        .filter(AliasStorage.owner_id == owner_id, AliasStorage.alias == name)
        .all()
    )
