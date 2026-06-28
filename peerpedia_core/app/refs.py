# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""Fuzzy reference resolution — turn ambiguous user input into canonical IDs.

This module is the ONLY place that resolves fuzzy input (short IDs, @names,
title keywords).  Once a canonical ID is found, existence checks are
delegated to the lower-level guards in ``storage/db/guards.py``.

Ambiguity (N > 1 matches) is the one genuinely app-level error — lower
layers can't tell you "your query matched 3 users, be more specific."
"""

from __future__ import annotations

from peerpedia_core.app.context import AppContext
from peerpedia_core.core import find_users, resolve_username_or_alias, search_articles
from peerpedia_core.exceptions import BadRequestError, NotAuthorizedError
from peerpedia_core.storage.db.guards import require_article as _lower_require_article
from peerpedia_core.storage.db.guards import require_user as _lower_require_user
from peerpedia_core.types import short_id


def require_user(ctx: AppContext) -> str:
    """Return the current user ID from session, or raise NotAuthorizedError."""
    if not ctx.current_user_id:
        raise NotAuthorizedError(code="UNAUTHORIZED")
    return ctx.current_user_id


def require_article(db, ref: str):
    """Resolve a fuzzy article reference → ORM object via lower guard.

    Delegates existence check to ``storage/db/guards.require_article``.
    Raises ``ValidationFailed`` on ambiguous input (the one app-only error).
    """
    results = search_articles(db, ref)
    if len(results) == 1:
        return _lower_require_article(db, results[0].id)
    if len(results) > 1:
        names = ", ".join(f"{short_id(a.id)} ({a.title})" for a in results)
        raise BadRequestError(code="AMBIGUOUS_NAME", ids=names)
    # Zero results — let lower guard produce the proper NotFoundError
    return _lower_require_article(db, ref)


def require_user_by_ref(db, ref: str):
    """Resolve a user reference → ORM object via lower guard.

    ``@name`` → username/alias → canonical ID → lower guard.
    Plain string → prefix/name search → canonical ID → lower guard.

    Delegates existence check to ``storage/db/guards.require_user``.
    """
    if ref.startswith("@"):
        return _resolve_by_atname(db, ref[1:])
    results = find_users(db, ref)
    if len(results) == 1:
        return _lower_require_user(db, results[0].id)
    if len(results) > 1:
        names = ", ".join(f"{short_id(u.id)} ({u.name})" for u in results)
        raise BadRequestError(code="AMBIGUOUS_NAME", ids=names)
    return _lower_require_user(db, ref)


def _resolve_by_atname(db, name: str):
    """Resolve ``@name`` → canonical ID → lower guard."""
    users = resolve_username_or_alias(db, "", name)
    if len(users) == 1:
        return _lower_require_user(db, users[0].id)
    if len(users) > 1:
        candidates = "\n".join(f"  {u.id}  {u.name}" for u in users)
        raise BadRequestError(code="AMBIGUOUS_NAME", ids=candidates)
    return _lower_require_user(db, name)
