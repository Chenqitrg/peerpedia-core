# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Maintainer management — add, remove, and list article maintainers.

Call graph::

    add_maintainer_to_article
      ├► policies._is_maintainer               (caller must be maintainer)
      ├► crud_maintainer.add_maintainer         (insert row)
      └► crud_maintainer.is_maintainer          (pre-check for duplicate)

    remove_maintainer_from_article
      ├► policies._is_maintainer               (caller must be maintainer)
      └► crud_maintainer.remove_maintainer      (delete row)

    list_maintainers
      └► crud_maintainer.get_maintainer_ids     (read-only)

Only existing maintainers can add or remove other maintainers.
Transfer is achieved via add(new) + remove(self), always add before remove
to ensure at least one maintainer exists at all times.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from peerpedia_core.exceptions import ConflictError, NotAuthorizedError, NotFoundError
from peerpedia_core.policies.articles import get_article_or_raise, _is_maintainer
from peerpedia_core.storage.db import crud_maintainer
from peerpedia_core.storage.db.crud_user import get_user


def add_maintainer_to_article(
    db: Session,
    article_id: str,
    user_id: str,
    caller_id: str,
) -> dict:
    """Grant maintainer status to *user_id* for *article_id*.

    Only an existing maintainer (*caller_id*) can add a new maintainer.
    """
    _assert_caller_is_maintainer(db, article_id, caller_id)

    if get_user(db, user_id) is None:
        raise NotFoundError("User not found")

    if crud_maintainer.is_maintainer(db, article_id, user_id):
        raise ConflictError("User is already a maintainer of this script")

    crud_maintainer.add_maintainer(db, article_id, user_id)
    return {"article_id": article_id, "user_id": user_id, "action": "added"}


def remove_maintainer_from_article(
    db: Session,
    article_id: str,
    user_id: str,
    caller_id: str,
) -> dict:
    """Revoke maintainer status from *user_id* for *article_id*.

    Only an existing maintainer (*caller_id*) can remove a maintainer.
    Removing the last maintainer is allowed (enables transfer via
    add-before-remove).
    """
    _assert_caller_is_maintainer(db, article_id, caller_id)

    deleted = crud_maintainer.remove_maintainer(db, article_id, user_id)
    if not deleted:
        raise NotFoundError("User is not a maintainer of this script")

    return {"article_id": article_id, "user_id": user_id, "action": "removed"}


def list_maintainers(db: Session, article_id: str) -> list[str]:
    """Return maintainer IDs for an article, ordered by created_at."""
    get_article_or_raise(db, article_id)
    return crud_maintainer.get_maintainer_ids(db, article_id)


def _assert_caller_is_maintainer(db: Session, article_id: str, caller_id: str) -> None:
    """Raise if *caller_id* is not a maintainer of *article_id*."""
    # Resolve user to check existence
    caller = get_user(db, caller_id)
    if caller is None:
        raise NotFoundError("Caller not found")
    get_article_or_raise(db, article_id)
    if not _is_maintainer(db, article_id, caller):
        raise NotAuthorizedError(
            f"User {caller_id} is not a maintainer of script {article_id}"
        )
