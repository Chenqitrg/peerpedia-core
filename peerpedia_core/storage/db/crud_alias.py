# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Alias CRUD — database only, ``session.flush()`` only."""

from sqlalchemy.orm import Session

from peerpedia_core.storage.db._validators import require_alias_nonempty, require_not_same
from peerpedia_core.storage.db.models import AliasStorage, UserStorage


def set_alias(session: Session, owner_id: str, target_id: str, alias: str) -> AliasStorage:
    """Set or update an alias for *target_id*.  Upsert — overwrites if exists.

    Caller must validate via ``require_following_for_alias`` first.
    """
    alias = alias.strip()
    require_alias_nonempty(alias)
    require_not_same(owner_id, target_id, label="alias")

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


def search_users_by_name_or_alias(
    session: Session,
    *,
    name: str | None = None,
    alias: str | None = None,
    owner_id: str | None = None,
) -> list[UserStorage]:
    """Search users by name and/or alias.

    - If only *name* is given, returns users with that exact name.
    - If only *alias* is given, returns users with that alias (scoped to
      *owner_id* if provided, otherwise across all owners).
    - If both are given, returns users matching both (intersection).
    - If neither is given, returns an empty list.
    """
    if name is None and alias is None:
        return []

    q = session.query(UserStorage)

    if name is not None:
        q = q.filter(UserStorage.name == name)

    if alias is not None:
        q = q.join(AliasStorage, UserStorage.id == AliasStorage.target_id)
        q = q.filter(AliasStorage.alias == alias)
        if owner_id is not None:
            q = q.filter(AliasStorage.owner_id == owner_id)

    return q.all()
