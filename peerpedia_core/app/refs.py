# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

r"""App-level reference resolution and ownership guards.

Fuzzy input (short IDs, @names, title keywords) is resolved here because
only the app layer knows about ambiguity.  Once a canonical ID is found,
existence checks delegate to ``storage/db/guards.py``.

Ownership checks (is this your notification? your session?) also live here
— they are app-level concerns, not storage-layer business rules.
"""

from __future__ import annotations

from peerpedia_core.app.context import AppContext
from peerpedia_core.core import (
    find_users, get_user as _get_user, list_users_by_name,
    search_users_by_name_or_alias, search_articles,
)
from peerpedia_core.exceptions import BadRequestError, NotFoundError, NotAuthorizedError
from peerpedia_core.storage.db import Session
from peerpedia_core.storage.db.guards import require_article as _lower_require_article
from peerpedia_core.storage.db.guards import require_user as _lower_require_user
from peerpedia_core.storage.db.models import ArticleMetaStorage, NotificationStorage, UserStorage


def require_user(ctx: AppContext) -> str:
    """Return the current user ID from session, or raise NotAuthorizedError."""
    if not ctx.current_user_id:
        raise NotAuthorizedError(code="UNAUTHORIZED")
    return ctx.current_user_id


def require_article(db: Session, ref: str) -> ArticleMetaStorage:
    """Resolve a fuzzy article reference → ORM object via lower guard."""
    return _resolve_ref(
        db, search_articles(db, ref), ref,
        _lower_require_article, format_article_candidates,
    )


def require_user_by_ref(db: Session, ref: str) -> UserStorage:
    """Resolve a user reference → ORM object via lower guard.

    ``@name`` → username/alias → canonical ID → lower guard.
    Plain string → prefix/name search → canonical ID → lower guard.
    """
    if ref.startswith("@"):
        name = ref[1:]
        by_name = search_users_by_name_or_alias(db, name=name)
        by_alias = search_users_by_name_or_alias(db, alias=name)
        seen: set[str] = set()
        candidates: list[UserStorage] = []
        for u in by_name + by_alias:
            if u.id not in seen:
                seen.add(u.id)
                candidates.append(u)
        return _resolve_ref(
            db, candidates, name,
            _lower_require_user, format_user_candidates_multiline,
        )
    return _resolve_ref(
        db, find_users(db, ref), ref,
        _lower_require_user, format_user_candidates,
    )


def require_notification(db: Session, notification_id: str, user_id: str) -> NotificationStorage:
    """Load a notification, verify it belongs to *user_id*.

    Raises NotFoundError if missing, NotAuthorizedError if not owned.
    """
    notif = db.get(NotificationStorage, notification_id)
    if notif is None:
        raise NotFoundError(code="NOTIFICATION_NOT_FOUND",
                            resource_type="notification", resource_id=notification_id)
    if notif.user_id != user_id:
        raise NotAuthorizedError(code="NOT_YOUR_NOTIFICATION")
    return notif


def guard_name_available(db: Session, name: str) -> None:
    """Raise BadRequestError if *name* is already taken."""
    existing = list_users_by_name(db, name)
    if existing:
        raise BadRequestError(
            code="DUPLICATE_NAME",
            ids=format_user_candidates(existing),
            name=name,
        )


def guard_user_id_available(db: Session, user_id: str) -> None:
    """Raise BadRequestError if *user_id* already exists (bootstrap dedup)."""
    existing = _get_user(db, user_id)
    if existing is not None:
        raise BadRequestError(code="DUPLICATE_USER_LOCAL",
            name=existing.name, id=user_id)


def require_user_by_name(db: Session, name: str | None) -> UserStorage:
    """Resolve a display name → ORM object.  Raises if missing/ambiguous."""
    if not name:
        raise BadRequestError(code="AMBIGUOUS_ARGS")
    users = list_users_by_name(db, name)
    if len(users) == 0:
        raise NotFoundError(code="USER_NOT_FOUND", resource_type="user")
    if len(users) > 1:
        raise _ambiguous(_format_user_id_candidates(users), name=name)
    return users[0]


# ── Internal ─────────────────────────────────────────────────────────────

def _resolve_ref(db, results, ref, lower_guard, format_fn):
    """Shared fuzzy resolution: 1 → return, >1 → ambiguous, 0 → try exact ID.

    *results* are pre-fetched ORM objects from a fuzzy search.
    When empty, ``lower_guard(db, ref)`` tries *ref* as an exact ID.
    When exactly one match, returns it directly — no redundant re-fetch.
    """
    if len(results) == 1:
        return results[0]
    if len(results) > 1:
        raise _ambiguous(format_fn(results))
    return lower_guard(db, ref)


def _ambiguous(ids: str, **extra) -> BadRequestError:
    """Raise AMBIGUOUS_NAME with formatted candidate list."""
    raise BadRequestError(code="AMBIGUOUS_NAME", ids=ids, **extra)


def format_article_candidates(articles: list[ArticleMetaStorage]) -> str:
    return ", ".join(f"{a.id} ({a.title})" for a in articles)


def format_user_candidates(users: list[UserStorage]) -> str:
    return ", ".join(f"{u.id} ({u.name})" for u in users)


def _format_user_id_candidates(users: list[UserStorage]) -> str:
    return ", ".join(u.id for u in users)


def format_user_candidates_multiline(users: list[UserStorage]) -> str:
    return "\n".join(f"  {u.id}  {u.name}" for u in users)
