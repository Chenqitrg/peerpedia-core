# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Alias CRUD — database only, ``session.flush()`` only."""

from sqlalchemy.orm import Session

from peerpedia_core.exceptions import BadRequestError
from peerpedia_core.storage.db.crud_user import is_following
from peerpedia_core.storage.db.models import Alias, User


def set_alias(session: Session, owner_id: str, target_id: str, alias: str) -> Alias:
    """Set or update an alias for *target_id*.  Upsert — overwrites if exists.

    Raises ``BadRequestError`` if *owner_id* does not follow *target_id*,
    or ``ValueError`` if *alias* is empty.
    """
    alias = alias.strip()
    if not alias:
        raise ValueError("Alias must not be empty")
    if not is_following(session, owner_id, target_id):
        raise BadRequestError(f"You must follow {target_id} to set an alias")

    a = session.query(Alias).filter(
        Alias.owner_id == owner_id, Alias.target_id == target_id,
    ).first()
    if a:
        a.alias = alias
    else:
        a = Alias(owner_id=owner_id, target_id=target_id, alias=alias)
        session.add(a)
    session.flush()
    return a


def remove_alias(session: Session, owner_id: str, target_id: str) -> None:
    """Remove the alias for *target_id*.  No-op if none set."""
    a = session.query(Alias).filter(
        Alias.owner_id == owner_id, Alias.target_id == target_id,
    ).first()
    if a:
        session.delete(a)
        session.flush()


def get_alias_for(session: Session, owner_id: str, target_id: str) -> str | None:
    """Return the alias *owner_id* set for *target_id*, or None."""
    a = session.query(Alias).filter(
        Alias.owner_id == owner_id, Alias.target_id == target_id,
    ).first()
    return a.alias if a else None


def list_aliases(session: Session, owner_id: str) -> list[Alias]:
    """Return all aliases set by *owner_id*, sorted alphabetically."""
    return (
        session.query(Alias)
        .filter(Alias.owner_id == owner_id)
        .order_by(Alias.alias)
        .all()
    )


def resolve_username_or_alias(
    session: Session, owner_id: str, name: str,
) -> list[User]:
    """Find users by *name*, checking username first then aliases.

    Returns all matches (may be 0, 1, or multiple).  Caller handles
    disambiguation — if multiple, prompt user to use UUID.
    """
    # Exact username match
    by_name = (
        session.query(User).filter(User.name == name).all()
    )
    if by_name:
        return by_name

    # Alias match
    return (
        session.query(User)
        .join(Alias, User.id == Alias.target_id)
        .filter(Alias.owner_id == owner_id, Alias.alias == name)
        .all()
    )
