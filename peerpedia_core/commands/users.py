# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""User operations -- thin wrappers so CLI doesn't import storage/db directly."""

from __future__ import annotations

from peerpedia_core.storage.db import Session


def create_user(db: Session, *, name: str, affiliation: str = "", password_hash: str = "", email: str = ""):
    """Create a new user."""
    from peerpedia_core.storage.db.crud_user import create_user as _create
    return _create(db, name=name, affiliation=affiliation, password_hash=password_hash, email=email)


def get_user(db: Session, user_ref: str):
    """Get a user by ID or name. Returns None if not found."""
    from peerpedia_core.storage.db.crud_user import get_user as _get
    return _get(db, user_ref)


def get_user_by_name(db: Session, name: str):
    """Get a user by exact name match. Returns None if not found."""
    from peerpedia_core.storage.db.crud_user import get_user_by_name as _get
    return _get(db, name)
